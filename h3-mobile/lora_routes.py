from pathlib import Path
import asyncio
import hashlib
import os
import secrets

from aiohttp import web
import folder_paths
from server import PromptServer


WEB_DIR = Path(__file__).resolve().parent / "web"
_LORA_PATHS = [Path(path) for path in folder_paths.get_folder_paths("loras")]
LORA_DIR = _LORA_PATHS[0] if _LORA_PATHS else Path(folder_paths.models_dir) / "loras"
LORA_DIR.mkdir(parents=True, exist_ok=True)
routes = PromptServer.instance.routes

# User LoRAs are file-upload only. There is no URL/Civitai download path here:
# the only writer of a formal ``*.safetensors`` in LORA_DIR is a completed,
# verified upload that atomically renames its own private temp file into place.
_UPLOAD_LOCKS = {}
_ACTIVE_UPLOADS = set()

_TEMP_SUFFIX = ".upload.part"


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
    return name.endswith(_TEMP_SUFFIX) or name.endswith(".part")


def _sweep_temp_files():
    """No partial upload is ever authoritative, and none survives a restart."""
    if not LORA_DIR.is_dir():
        return
    for path in LORA_DIR.iterdir():
        if path.is_file() and _is_temp_name(path.name):
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


@routes.get("/h3-mobile/lora-library.js")
async def h3_mobile_lora_library_js(request):
    return web.FileResponse(WEB_DIR / "lora-library.js")


@routes.get("/h3-mobile/api/loras/files")
async def h3_mobile_lora_files(request):
    return web.json_response({"files": _files_payload()})


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
