from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import asyncio
import hashlib
import ipaddress
import os
import re
import socket

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer


WEB_DIR = Path(__file__).resolve().parent / "web"
_LORA_PATHS = [Path(path) for path in folder_paths.get_folder_paths("loras")]
LORA_DIR = _LORA_PATHS[0] if _LORA_PATHS else Path(folder_paths.models_dir) / "loras"
LORA_DIR.mkdir(parents=True, exist_ok=True)
routes = PromptServer.instance.routes
_DOWNLOAD_TASKS = {}
_DOWNLOAD_STATE = {}
_REDIRECT_CODES = {301, 302, 303, 307, 308}


def _safe_filename(value: str) -> str:
    name = (value or "").strip()
    if not name or Path(name).name != name or "/" in name or "\\" in name:
        raise web.HTTPBadRequest(text="invalid filename")
    if not name.lower().endswith(".safetensors"):
        raise web.HTTPBadRequest(text="filename must end with .safetensors")
    if len(name) > 240:
        raise web.HTTPBadRequest(text="filename too long")
    return name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise web.HTTPBadRequest(text="sha256 must be 64 hex chars")
    return value


def _resolve_public_host(host: str):
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"DNS lookup failed: {exc}")
    if not infos:
        raise ValueError("DNS lookup returned no addresses")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("private/local download targets are not allowed")


async def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("download URL must be https")
    await asyncio.to_thread(_resolve_public_host, parsed.hostname)
    return url


def _request_headers(url: str, api_key: str) -> dict:
    """Send the browser-held Civitai key only to Civitai-owned hosts."""
    host = (urlparse(url).hostname or "").lower()
    key = (api_key or "").strip()
    if key and (host == "civitai.com" or host.endswith(".civitai.com")):
        return {"Authorization": f"Bearer {key}"}
    return {}


def _filename_from_response(url: str, content_disposition: str) -> str:
    name = ""
    value = content_disposition or ""
    encoded = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", value, re.IGNORECASE)
    plain = re.search(r'filename\s*=\s*(?:"([^"]+)"|([^;]+))', value, re.IGNORECASE)
    if encoded:
        name = unquote(encoded.group(1).strip())
    elif plain:
        name = (plain.group(1) or plain.group(2) or "").strip()
    if not name:
        name = unquote(Path(urlparse(url).path).name)
    return _safe_filename(name)


async def _probe_download(url: str, api_key: str):
    current_url = url
    timeout = aiohttp.ClientTimeout(total=90, connect=60, sock_read=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for _ in range(6):
            await _validate_public_url(current_url)
            async with session.get(
                current_url,
                allow_redirects=False,
                headers=_request_headers(current_url, api_key),
            ) as response:
                if response.status in _REDIRECT_CODES:
                    location = response.headers.get("Location")
                    if not location:
                        raise RuntimeError(f"HTTP {response.status} without Location")
                    current_url = urljoin(current_url, location)
                    continue
                if response.status != 200:
                    detail = ""
                    try:
                        detail = (await response.text())[:300]
                    except Exception:
                        pass
                    raise RuntimeError(f"HTTP {response.status}" + (f": {detail}" if detail else ""))
                filename = _filename_from_response(current_url, response.headers.get("Content-Disposition", ""))
                response.release()
                return current_url, filename
    raise RuntimeError("too many redirects")


def _state(filename, **changes):
    current = _DOWNLOAD_STATE.setdefault(
        filename,
        {"filename": filename, "status": "missing", "downloaded": 0, "total": None, "error": None},
    )
    current.update(changes)
    return current


async def _download_worker(filename: str, url: str, expected_sha: str, api_key: str):
    dest = LORA_DIR / filename
    part = LORA_DIR / f"{filename}.part"
    try:
        _state(filename, status="downloading", downloaded=0, total=None, error=None)
        current_url = url
        timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for _ in range(6):
                await _validate_public_url(current_url)
                async with session.get(
                    current_url,
                    allow_redirects=False,
                    headers=_request_headers(current_url, api_key),
                ) as response:
                    if response.status in _REDIRECT_CODES:
                        location = response.headers.get("Location")
                        if not location:
                            raise RuntimeError(f"HTTP {response.status} without Location")
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status != 200:
                        detail = ""
                        try:
                            detail = (await response.text())[:300]
                        except Exception:
                            pass
                        raise RuntimeError(f"HTTP {response.status}" + (f": {detail}" if detail else ""))
                    total = response.content_length
                    _state(filename, total=total)
                    with part.open("wb") as handle:
                        async for chunk in response.content.iter_chunked(8 * 1024 * 1024):
                            handle.write(chunk)
                            _state(
                                filename,
                                downloaded=_DOWNLOAD_STATE[filename]["downloaded"] + len(chunk),
                            )
                    break
            else:
                raise RuntimeError("too many redirects")

        if not part.is_file() or part.stat().st_size <= 0:
            raise RuntimeError("downloaded file is empty")
        if expected_sha:
            actual = await asyncio.to_thread(_sha256, part)
            if actual.lower() != expected_sha:
                raise RuntimeError(f"SHA256 mismatch: expected {expected_sha}, got {actual}")
        os.replace(part, dest)
        size = dest.stat().st_size
        _state(filename, status="installed", downloaded=size, total=size, error=None)
    except asyncio.CancelledError:
        _state(filename, status="cancelled", error="cancelled")
        raise
    except Exception as exc:
        _state(filename, status="error", error=str(exc))
    finally:
        _DOWNLOAD_TASKS.pop(filename, None)


def _files_payload():
    items = {}
    if LORA_DIR.is_dir():
        for path in LORA_DIR.glob("*.safetensors"):
            if not path.is_file():
                continue
            size = path.stat().st_size
            items[path.name] = {
                "filename": path.name,
                "status": "installed" if size > 0 else "missing",
                "size": size,
                "downloaded": size if size > 0 else 0,
                "total": size if size > 0 else None,
                "error": None,
            }
    for filename, state in _DOWNLOAD_STATE.items():
        if filename not in items or state.get("status") != "installed":
            items[filename] = dict(state)
    return sorted(items.values(), key=lambda item: item["filename"].lower())


@routes.get("/h3-mobile/lora-library.js")
async def h3_mobile_lora_library_js(request):
    return web.FileResponse(WEB_DIR / "lora-library.js")


@routes.get("/h3-mobile/api/loras/files")
async def h3_mobile_lora_files(request):
    return web.json_response({"files": _files_payload()})


@routes.post("/h3-mobile/api/loras/resolve")
async def h3_mobile_lora_resolve(request):
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="invalid json")
    url = (body.get("url") or "").strip()
    if not url:
        raise web.HTTPBadRequest(text="url required")
    try:
        final_url, filename = await _probe_download(url, body.get("api_key") or "")
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))
    except RuntimeError as exc:
        raise web.HTTPBadGateway(text=str(exc))
    return web.json_response({"ok": True, "filename": filename, "final_url": final_url})


@routes.post("/h3-mobile/api/loras/download")
async def h3_mobile_lora_download(request):
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="invalid json")
    url = (body.get("url") or "").strip()
    if not url:
        raise web.HTTPBadRequest(text="url required")
    api_key = body.get("api_key") or ""
    filename_value = (body.get("filename") or "").strip()
    if filename_value:
        filename = _safe_filename(filename_value)
    else:
        try:
            _, filename = await _probe_download(url, api_key)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc))
        except RuntimeError as exc:
            raise web.HTTPBadGateway(text=str(exc))
    expected_sha = _validate_sha(body.get("sha256"))

    dest = LORA_DIR / filename
    if dest.is_file() and dest.stat().st_size > 0:
        if expected_sha:
            actual = await asyncio.to_thread(_sha256, dest)
            if actual.lower() != expected_sha:
                raise web.HTTPConflict(text=f"existing file SHA256 mismatch: {actual}")
        size = dest.stat().st_size
        _state(filename, status="installed", downloaded=size, total=size, error=None)
        return web.json_response({"ok": True, "status": "installed", "filename": filename})

    task = _DOWNLOAD_TASKS.get(filename)
    if task and not task.done():
        return web.json_response({"ok": True, "status": "downloading", "filename": filename})

    try:
        await _validate_public_url(url)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc))
    _state(filename, status="queued", downloaded=0, total=None, error=None)
    _DOWNLOAD_TASKS[filename] = asyncio.create_task(
        _download_worker(filename, url, expected_sha, api_key)
    )
    return web.json_response({"ok": True, "status": "queued", "filename": filename})


@routes.post("/h3-mobile/api/loras/upload")
async def h3_mobile_lora_upload(request):
    filename = _safe_filename(request.query.get("filename"))
    expected_sha = _validate_sha(request.query.get("sha256"))
    dest = LORA_DIR / filename
    part = LORA_DIR / f"{filename}.upload.part"
    try:
        reader = await request.multipart()
        found = False
        with part.open("wb") as out:
            while True:
                field = await reader.next()
                if field is None:
                    break
                if field.name != "file":
                    continue
                found = True
                while True:
                    chunk = await field.read_chunk(size=8 * 1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                break
        if not found:
            raise web.HTTPBadRequest(text="file field required")
        if not part.is_file() or part.stat().st_size <= 0:
            raise web.HTTPBadRequest(text="uploaded file is empty")
        actual_sha = await asyncio.to_thread(_sha256, part)
        if expected_sha and actual_sha.lower() != expected_sha:
            raise web.HTTPConflict(
                text=f"uploaded file SHA256 mismatch: expected {expected_sha}, got {actual_sha}"
            )
        os.replace(part, dest)
        size = dest.stat().st_size
        _state(filename, status="installed", downloaded=size, total=size, error=None)
        return web.json_response(
            {"ok": True, "filename": filename, "size": size, "sha256": actual_sha}
        )
    finally:
        try:
            if part.is_file():
                part.unlink()
        except OSError:
            pass


@routes.post("/h3-mobile/api/loras/delete")
async def h3_mobile_lora_delete(request):
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="invalid json")
    filename = _safe_filename(body.get("filename"))
    task = _DOWNLOAD_TASKS.get(filename)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    removed = False
    for path in (
        LORA_DIR / filename,
        LORA_DIR / f"{filename}.part",
        LORA_DIR / f"{filename}.upload.part",
    ):
        try:
            if path.is_file():
                path.unlink()
                removed = True
        except OSError as exc:
            raise web.HTTPInternalServerError(text=str(exc))
    _DOWNLOAD_STATE.pop(filename, None)
    return web.json_response({"ok": True, "removed": removed, "filename": filename})
