from pathlib import Path
import asyncio
import hashlib
import os
import secrets

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer


WEB_DIR = Path(__file__).resolve().parent / "web"
_LORA_PATHS = [Path(path) for path in folder_paths.get_folder_paths("loras")]
LORA_DIR = _LORA_PATHS[0] if _LORA_PATHS else Path(folder_paths.models_dir) / "loras"
LORA_DIR.mkdir(parents=True, exist_ok=True)
routes = PromptServer.instance.routes

GITHUB_RELEASE_API = (
    "https://api.github.com/repos/shuichisaitofd/h3-lora-assets/"
    "releases/tags/h3-loras-v1"
)
MANAGED_LORA_SPECS = {
    "BJ_v3.safetensors": "fbb93a67b429c79145c95598e9ac38388ad49d6df1c09c96cf989cce99277d53",
    "deepthroat_v02.safetensors": "1fd239662f6290255b0bb3a220764fb53aab2859378f7fd3024030c1e1991cb2",
    "Finger_BEAN_v1.safetensors": "914e3ecb0b515ad1a40c0185a8d23a34f87a1ced370db8bfb0ed3b5845dbf0a2",
    "Motion_FL2VA_v2.safetensors": "f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3",
    "Mystic_FL2VA_v4.safetensors": "fc3e856d14c6c19557c888f48662d591e4794e281233ec0d987be5003068afba",
    "Nipple_v2.safetensors": "7c30c92178e01e33cfbc4684a7b3fb1b71368293443b2941a5b889db3fbd3b18",
    "Panties_v1.safetensors": "f2bf0b4fc7d0ab6f3f91300b0a810dcd76e61f6e8fe39f7dbbd480245987447f",
    "Penis_HM_v2.safetensors": "017dd1adddc1be3ec0605dd2e7de97138eb2c6c6ba24be402cf47f103ac1f1b3",
    "Pussy_HM_v1.safetensors": "373c3cad3bf27047fdd754fe111443d97e70e3108a8829f2ec63c48832466eb3",
    "Squirt_HM_v1.safetensors": "e7f48b0e9a9bc6252c29db963258fe5d70321c4bc336bc5e6041938c68ee5791",
}

# User-supplied LoRAs remain file-upload only; there is no user URL/Civitai
# path. Separately, the fixed server-owned manifest above may fetch only the
# named, SHA-pinned assets from the public GitHub Release.
_UPLOAD_LOCKS = {}
_ACTIVE_UPLOADS = set()

_TEMP_SUFFIX = ".upload.part"
_GITHUB_TEMP_SUFFIX = ".github.part"
_MANAGED_DOWNLOAD_TASK = None
_MANAGED_DOWNLOAD_STATE = {
    filename: {
        "filename": filename,
        "status": "pending" if (LORA_DIR / filename).is_file() else "missing",
        "downloaded": 0,
        "total": None,
        "error": None,
    }
    for filename in MANAGED_LORA_SPECS
}


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


def _is_temp_name(name: str) -> bool:
    return name.endswith(_TEMP_SUFFIX) or name.endswith(_GITHUB_TEMP_SUFFIX)


def _is_upload_temp_name(name: str) -> bool:
    return name.endswith(_TEMP_SUFFIX)


def _sweep_temp_files():
    """Browser-upload partials are private and never survive a restart.

    GitHub download partials are deliberately retained so a newly started Pod
    can resume a large Release asset instead of starting it again from zero.
    """
    if not LORA_DIR.is_dir():
        return
    for path in LORA_DIR.iterdir():
        if path.is_file() and _is_upload_temp_name(path.name):
            try:
                path.unlink()
            except OSError:
                pass


_sweep_temp_files()


def _lock_for(filename: str) -> asyncio.Lock:
    lock = _UPLOAD_LOCKS.get(filename)
    if lock is None:
        lock = asyncio.Lock()
        _UPLOAD_LOCKS[filename] = lock
    return lock


def _files_payload():
    """Pod real files are the single source of truth for "installed".

    A zero-byte file or any ``*.upload.part`` / ``*.part`` temp file is never
    reported as installed.
    """
    items = []
    seen = set()
    if LORA_DIR.is_dir():
        for path in sorted(LORA_DIR.glob("*.safetensors")):
            if not path.is_file() or _is_temp_name(path.name):
                continue
            size = path.stat().st_size
            seen.add(path.name)
            items.append(
                {
                    "filename": path.name,
                    "status": "installed" if size > 0 else "incomplete",
                    "size": size,
                    "uploading": path.name in _ACTIVE_UPLOADS,
                }
            )
    for name in sorted(_ACTIVE_UPLOADS):
        if name not in seen:
            items.append(
                {"filename": name, "status": "uploading", "size": 0, "uploading": True}
            )
    return sorted(items, key=lambda item: item["filename"].lower())


def _managed_state_payload():
    return [dict(_MANAGED_DOWNLOAD_STATE[name]) for name in MANAGED_LORA_SPECS]


def _github_headers(accept: str) -> dict:
    return {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "h3-mobile-runpod",
    }


async def _verify_managed_file(filename: str, path: Path) -> None:
    expected = MANAGED_LORA_SPECS[filename]
    actual = await asyncio.to_thread(_sha256, path)
    if actual.lower() != expected:
        raise RuntimeError(
            f"SHA256 mismatch for {filename}: expected {expected}, got {actual}"
        )


async def _download_managed_lora(session, filename: str, asset: dict) -> None:
    state = _MANAGED_DOWNLOAD_STATE[filename]
    dest = LORA_DIR / filename
    part = LORA_DIR / f"{filename}{_GITHUB_TEMP_SUFFIX}"
    expected_sha = MANAGED_LORA_SPECS[filename]
    try:
        if dest.is_file() and dest.stat().st_size > 0:
            state.update(
                status="verifying",
                downloaded=dest.stat().st_size,
                total=dest.stat().st_size,
                error=None,
            )
            await _verify_managed_file(filename, dest)
            state["status"] = "installed"
            return

        published_digest = str(asset.get("digest") or "")
        if published_digest and published_digest.lower() != f"sha256:{expected_sha}":
            raise RuntimeError(
                f"GitHub digest mismatch for {filename}: {published_digest}"
            )

        existing = part.stat().st_size if part.is_file() else 0
        headers = _github_headers("application/octet-stream")
        if existing:
            headers["Range"] = f"bytes={existing}-"
        state.update(
            status="downloading",
            downloaded=existing,
            total=asset.get("size"),
            error=None,
        )
        async with session.get(
            asset["url"], headers=headers, allow_redirects=True
        ) as response:
            if response.status == 416 and existing:
                pass
            elif response.status not in (200, 206):
                raise RuntimeError(f"GitHub asset HTTP {response.status}")
            else:
                if existing and response.status == 200:
                    existing = 0
                    state["downloaded"] = 0
                mode = "ab" if existing and response.status == 206 else "wb"
                with part.open(mode) as handle:
                    async for chunk in response.content.iter_chunked(8 * 1024 * 1024):
                        handle.write(chunk)
                        state["downloaded"] += len(chunk)

        if not part.is_file() or part.stat().st_size <= 0:
            raise RuntimeError(f"GitHub returned an empty asset for {filename}")
        state["status"] = "verifying"
        await _verify_managed_file(filename, part)
        os.replace(part, dest)
        size = dest.stat().st_size
        state.update(status="installed", downloaded=size, total=size, error=None)
    except asyncio.CancelledError:
        state["status"] = "paused"
        raise
    except Exception as exc:
        state.update(status="error", error=str(exc))


async def _sync_managed_loras() -> None:
    global _MANAGED_DOWNLOAD_TASK
    timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=180)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                GITHUB_RELEASE_API,
                headers=_github_headers("application/vnd.github+json"),
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"GitHub Release API HTTP {response.status}")
                release = await response.json()
            assets = {
                asset.get("name"): asset for asset in release.get("assets", [])
            }
            missing = [name for name in MANAGED_LORA_SPECS if name not in assets]
            if missing:
                raise RuntimeError(
                    "GitHub Release assets missing: " + ", ".join(missing)
                )
            semaphore = asyncio.Semaphore(2)

            async def download(filename):
                async with semaphore:
                    await _download_managed_lora(session, filename, assets[filename])

            await asyncio.gather(*(download(name) for name in MANAGED_LORA_SPECS))
        # Refresh ComfyUI's filename cache after the atomic installs.
        folder_paths.get_filename_list("loras")
        installed = sum(
            state["status"] == "installed"
            for state in _MANAGED_DOWNLOAD_STATE.values()
        )
        print(
            "[H3] Managed LoRA auto-download complete: "
            f"{installed}/{len(MANAGED_LORA_SPECS)} installed"
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        message = str(exc)
        for state in _MANAGED_DOWNLOAD_STATE.values():
            if state["status"] not in {"installed", "downloading", "verifying"}:
                state.update(status="error", error=message)
        print(f"[H3] Managed LoRA auto-download error: {message}")
    finally:
        _MANAGED_DOWNLOAD_TASK = None


def _schedule_managed_lora_sync() -> bool:
    global _MANAGED_DOWNLOAD_TASK
    if _MANAGED_DOWNLOAD_TASK and not _MANAGED_DOWNLOAD_TASK.done():
        return False
    for state in _MANAGED_DOWNLOAD_STATE.values():
        if state["status"] != "installed":
            state.update(status="queued", error=None)
    _MANAGED_DOWNLOAD_TASK = asyncio.create_task(_sync_managed_loras())
    return True


async def _auto_sync_managed_loras_on_startup(_app):
    _schedule_managed_lora_sync()


if _auto_sync_managed_loras_on_startup not in PromptServer.instance.app.on_startup:
    PromptServer.instance.app.on_startup.append(_auto_sync_managed_loras_on_startup)


@routes.get("/h3-mobile/lora-library.js")
async def h3_mobile_lora_library_js(request):
    return web.FileResponse(WEB_DIR / "lora-library.js")


@routes.get("/h3-mobile/api/loras/files")
async def h3_mobile_lora_files(request):
    return web.json_response(
        {"files": _files_payload(), "managed": _managed_state_payload()}
    )


@routes.post("/h3-mobile/api/loras/managed/prepare")
async def h3_mobile_prepare_managed_loras(request):
    return web.json_response(
        {"ok": True, "started": _schedule_managed_lora_sync()}
    )


@routes.post("/h3-mobile/api/loras/upload")
async def h3_mobile_lora_upload(request):
    filename = _safe_filename(request.query.get("filename"))
    # Only a caller-supplied *trusted catalog* digest may gate an upload. A
    # digest the browser merely learned from a previous successful upload must
    # never be replayed here as ``expected_sha256`` — that is exactly what
    # rejected a legitimately re-exported file in the past.
    expected_sha = _validate_sha(request.query.get("expected_sha256"))

    async with _lock_for(filename):
        dest = LORA_DIR / filename
        part = LORA_DIR / f"{filename}.{os.getpid()}.{secrets.token_hex(8)}{_TEMP_SUFFIX}"
        _ACTIVE_UPLOADS.add(filename)
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
            # Only a fully received, verified file is ever renamed into place.
            os.replace(part, dest)
            size = dest.stat().st_size
            return web.json_response(
                {"ok": True, "filename": filename, "size": size, "sha256": actual_sha}
            )
        finally:
            # Success, client disconnect, cancellation or any exception all land
            # here: the private temp file must not be left behind.
            _ACTIVE_UPLOADS.discard(filename)
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
    removed = False
    if LORA_DIR.is_dir():
        for path in list(LORA_DIR.iterdir()):
            if not path.is_file():
                continue
            is_target = path.name == filename or (
                path.name.startswith(filename + ".") and _is_temp_name(path.name)
            )
            if not is_target:
                continue
            try:
                path.unlink()
                removed = True
            except OSError as exc:
                raise web.HTTPInternalServerError(text=str(exc))
    return web.json_response({"ok": True, "removed": removed, "filename": filename})
