from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
import asyncio
import hashlib
import os
import shutil

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
INPUT_DIR = Path(folder_paths.get_input_directory())
OUTPUT_DIR = Path(folder_paths.get_output_directory())
THUMB_DIR = OUTPUT_DIR / ".h3_mobile_thumbs"
routes = PromptServer.instance.routes


def _safe_under(base: Path, subfolder: str, filename: str) -> Path:
    base = base.resolve()
    target = (base / (subfolder or "") / filename).resolve()
    if target != base and base not in target.parents:
        raise web.HTTPBadRequest(text="invalid path")
    return target


@routes.get("/h3-mobile/api/pod-runtime")
async def h3_mobile_pod_runtime(request):
    pod_id = os.environ.get("RUNPOD_POD_ID")
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not pod_id or not api_key:
        return web.json_response({"ok": False, "source": "unavailable", "error": "RunPod metadata unavailable"})
    url = f"https://rest.runpod.io/v1/pods/{pod_id}"
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"Authorization": f"Bearer {api_key}"}) as response:
                if response.status != 200:
                    return web.json_response({"ok": False, "source": "runpod", "error": f"HTTP {response.status}"})
                data = await response.json()
        started = data.get("lastStartedAt")
        if not started:
            return web.json_response({"ok": False, "source": "runpod", "error": "lastStartedAt missing"})
        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        seconds = max(0, int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()))
        return web.json_response({"ok": True, "source": "runpod", "pod_id": pod_id, "started_at": started, "uptime_seconds": seconds})
    except Exception as exc:
        return web.json_response({"ok": False, "source": "runpod", "error": str(exc)})


@routes.get("/h3-mobile/api/input-images")
async def h3_mobile_input_images(request):
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    items = []
    if INPUT_DIR.is_dir():
        for path in INPUT_DIR.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            try:
                rel = path.relative_to(INPUT_DIR)
                subfolder = str(rel.parent) if str(rel.parent) != "." else ""
                stat = path.stat()
                items.append({
                    "filename": path.name,
                    "subfolder": subfolder,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "url": f"/view?filename={quote(path.name)}&subfolder={quote(subfolder)}&type=input",
                })
            except Exception:
                continue
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return web.json_response({"images": items[:100]})


@routes.get("/h3-mobile/api/thumbnail")
async def h3_mobile_thumbnail(request):
    filename = request.query.get("filename", "")
    subfolder = request.query.get("subfolder", "")
    if not filename:
        raise web.HTTPBadRequest(text="filename required")
    src = _safe_under(OUTPUT_DIR, subfolder, filename)
    if not src.is_file():
        raise web.HTTPNotFound(text="video not found")
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{src}:{src.stat().st_mtime_ns}:{src.stat().st_size}".encode()).hexdigest()
    dest = THUMB_DIR / f"{key}.jpg"
    if not dest.is_file():
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise web.HTTPServiceUnavailable(text="ffmpeg not available")
        proc = await asyncio.create_subprocess_exec(
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", "0.10", "-i", str(src), "-frames:v", "1",
            "-vf", "scale='min(640,iw)':-2", "-q:v", "3", str(dest),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0 or not dest.is_file():
            raise web.HTTPInternalServerError(text=(err or b"thumbnail failed").decode(errors="ignore")[:500])
    return web.FileResponse(dest)


@routes.get("/h3-mobile/media-library.js")
async def h3_mobile_media_library_js(request):
    return web.FileResponse(WEB_DIR / "media-library.js")


@routes.get("/h3-mobile/history-thumbnails.js")
async def h3_mobile_history_thumbnails_js(request):
    return web.FileResponse(WEB_DIR / "history-thumbnails.js")


@routes.get("/h3-mobile/pod-runtime.js")
async def h3_mobile_pod_runtime_js(request):
    return web.FileResponse(WEB_DIR / "pod-runtime.js")
