from pathlib import Path
import asyncio
import hashlib
import os
import shutil
import tempfile
import zipfile

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
API_WORKFLOWS = {
    "i2v": BASE_DIR / "api_workflows" / "i2v.json",
    "ref2va": BASE_DIR / "api_workflows" / "ref2va.json",
    "ref2va_04": BASE_DIR / "api_workflows" / "ref2va_04.json",
    "ref2va_03": BASE_DIR / "api_workflows" / "ref2va_03.json",
    "ref2va_05": BASE_DIR / "api_workflows" / "ref2va_05.json",
    "ref2va_06_fast": BASE_DIR / "api_workflows" / "ref2va_06_fast.json",
    "ref2va_06_stable": BASE_DIR / "api_workflows" / "ref2va_06_stable.json",
}
COMFYUI_DIR = BASE_DIR.parent.parent
MODELS_DIR = COMFYUI_DIR / "models"
OUTPUT_DIR = Path(folder_paths.get_output_directory())


def _resolve_diffusion_model_path(filename):
    # ComfyUI's folder_paths registers the "diffusion_models" folder type across
    # BOTH models/unet and models/diffusion_models (see folder_paths.py's
    # legacy "unet" -> "diffusion_models" alias). H3's large UNET files on this
    # pod live under models/unet/, so checking models/diffusion_models/ alone
    # reports them as missing and would trigger a redundant ~20GB re-download.
    for sub in ("unet", "diffusion_models"):
        candidate = MODELS_DIR / sub / filename
        if candidate.is_file():
            return candidate
    return MODELS_DIR / "diffusion_models" / filename


HF_H3 = "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main"
MODEL_SPECS = {
    "ref2va": {"label": "MiniMax H3 Ref2VA INT8", "url": f"{HF_H3}/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", "path": _resolve_diffusion_model_path("minimax_h3_ref2va_pruned_int8_convrot.safetensors")},
    "fl2va": {"label": "MiniMax H3 FL2VA INT8", "url": f"{HF_H3}/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", "path": _resolve_diffusion_model_path("minimax_h3_fl2va_pruned_int8_convrot.safetensors")},
    "qwen": {"label": "Qwen3-VL 32B MiniMax H3 NVFP4 AWQ", "url": f"{HF_H3}/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "path": MODELS_DIR / "text_encoders" / "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"},
    "video_vae": {"label": "MiniMax H3 video VAE FP16", "url": f"{HF_H3}/vae/minimax_h3_video_vae_fp16.safetensors", "path": MODELS_DIR / "vae" / "minimax_h3_video_vae_fp16.safetensors"},
    "audio_vae": {"label": "MiniMax H3 audio VAE FP32", "url": f"{HF_H3}/vae/minimax_h3_audio_vae_fp32.safetensors", "path": MODELS_DIR / "vae" / "minimax_h3_audio_vae_fp32.safetensors"},
    "turbo_lora": {"label": "MiniMax H3 Turbo LoRA v4 step600 EMA", "url": "https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/resolve/main/minimax_h3_turbo_v4_step600_ema.safetensors", "path": MODELS_DIR / "loras" / "minimax_h3_turbo_v4_step600_ema.safetensors"},
}
MODE_SETS = {"ref2va": ["ref2va", "qwen", "video_vae", "audio_vae", "turbo_lora"], "i2v": ["fl2va", "qwen", "video_vae", "audio_vae", "turbo_lora"]}
_download_tasks = {}
_verified_files = {}
_download_state = {
    key: {
        # Files with an expected digest are not called installed until they have
        # actually been verified during this process lifetime.
        "status": "installed" if spec["path"].is_file() and not spec.get("sha256") else "missing",
        "downloaded": 0,
        "total": None,
        "error": None,
    }
    for key, spec in MODEL_SPECS.items()
}
routes = PromptServer.instance.routes


class SHA256MismatchError(RuntimeError):
    pass


def _file_fingerprint(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _is_verified(key):
    path = MODEL_SPECS[key]["path"]
    if not path.is_file():
        return False
    return _verified_files.get(key) == _file_fingerprint(path)


def _model_file_ready(key):
    spec = MODEL_SPECS[key]
    path = spec["path"]
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    return _is_verified(key) if spec.get("sha256") else True


def _verify_sha256(key, path):
    expected = MODEL_SPECS[key].get("sha256")
    if not expected:
        return
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual.lower() != expected.lower():
        raise SHA256MismatchError(f"SHA256 mismatch: expected {expected}, got {actual}")
    _verified_files[key] = _file_fingerprint(path)


def _model_state_payload():
    result = {}
    for key, spec in MODEL_SPECS.items():
        state = dict(_download_state[key])
        path = spec["path"]
        if _model_file_ready(key):
            state["status"] = "installed"
            state["downloaded"] = path.stat().st_size
            state["total"] = path.stat().st_size
        elif state["status"] == "installed":
            state.update(status="missing", downloaded=0, total=None)
        state.update({"key": key, "label": spec["label"], "filename": path.name})
        result[key] = state
    return result


def _container_uptime_seconds():
    try:
        system_uptime = float(Path("/proc/uptime").read_text().split()[0])
        fields = Path("/proc/1/stat").read_text().split()
        start_ticks = int(fields[21])
        hz = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        return max(0, int(system_uptime - (start_ticks / hz)))
    except Exception:
        return None


async def _delete_later(path, delay=3600):
    await asyncio.sleep(delay)
    shutil.rmtree(path, ignore_errors=True)


async def _download_one(key):
    spec = MODEL_SPECS[key]
    dest = spec["path"]
    tmp = Path(str(dest) + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    state = _download_state[key]
    try:
        if dest.is_file() and dest.stat().st_size > 0:
            size = dest.stat().st_size
            state.update(status="queued", downloaded=size, total=size, error=None)
            await asyncio.to_thread(_verify_sha256, key, dest)
            state.update(status="installed", downloaded=size, total=size, error=None)
            return

        state.update(status="downloading", error=None)
        existing = tmp.stat().st_size if tmp.is_file() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(spec["url"], headers=headers, allow_redirects=True) as response:
                if response.status not in (200, 206):
                    raise RuntimeError(f"HTTP {response.status}")
                if existing and response.status == 200:
                    existing = 0
                    try: tmp.unlink()
                    except FileNotFoundError: pass
                content_length = response.content_length
                total = (existing + content_length) if content_length is not None else None
                state.update(downloaded=existing, total=total)
                mode = "ab" if existing and response.status == 206 else "wb"
                with tmp.open(mode) as f:
                    async for chunk in response.content.iter_chunked(8 * 1024 * 1024):
                        f.write(chunk)
                        state["downloaded"] += len(chunk)
        await asyncio.to_thread(_verify_sha256, key, tmp)
        os.replace(tmp, dest)
        if spec.get("sha256"):
            _verified_files[key] = _file_fingerprint(dest)
        size = dest.stat().st_size
        state.update(status="installed", downloaded=size, total=size, error=None)
    except asyncio.CancelledError:
        state["status"] = "paused"
        raise
    except SHA256MismatchError as exc:
        # Keep a failed .part file as .part; it must never become the formal
        # model file. An existing formal file is likewise left untouched so
        # the mismatch remains visible and recoverable to the operator.
        state.update(status="sha256_error", error=str(exc))
    except Exception as exc:
        state.update(status="error", error=str(exc))
    finally:
        _download_tasks.pop(key, None)


def _schedule_model_set(mode):
    """Start missing downloads for one mode without blocking the web server."""
    started, skipped = [], []
    for key in MODE_SETS[mode]:
        if _model_file_ready(key):
            skipped.append(key)
            continue
        task = _download_tasks.get(key)
        if task and not task.done():
            skipped.append(key)
            continue
        _download_state[key].update(status="queued", error=None)
        _download_tasks[key] = asyncio.create_task(_download_one(key))
        started.append(key)
    return started, skipped


async def _auto_prepare_i2v_on_startup(_app):
    # I2V is the only set prepared automatically. Ref2VA remains an explicit
    # user action through /api/models/prepare so its large model is not fetched
    # on Pods that only need image-to-video generation.
    started, skipped = _schedule_model_set("i2v")
    print(
        "[H3] I2V model auto-prepare: "
        f"started={','.join(started) or '-'} skipped={','.join(skipped) or '-'}"
    )


if _auto_prepare_i2v_on_startup not in PromptServer.instance.app.on_startup:
    PromptServer.instance.app.on_startup.append(_auto_prepare_i2v_on_startup)


@routes.get("/h3")
async def h3_short_url(request):
    raise web.HTTPFound("/h3-mobile/")

@routes.get("/h3/")
async def h3_short_url_slash(request):
    raise web.HTTPFound("/h3-mobile/")

@routes.get("/h3-mobile")
async def h3_mobile_index_no_slash(request):
    # Redirect to the trailing-slash URL so index.html's relative asset
    # references (styles.css, app.js, ...) resolve under /h3-mobile/ instead
    # of the site root. This is what lets the same index.html work unchanged
    # whether it's served from here or from a GitHub Pages deployment rooted
    # at a different path.
    raise web.HTTPFound("/h3-mobile/")

@routes.get("/h3-mobile/")
async def h3_mobile_index(request): return web.FileResponse(WEB_DIR / "index.html")

@routes.get("/h3-mobile/app.js")
async def h3_mobile_js(request): return web.FileResponse(WEB_DIR / "app.js")

@routes.get("/h3-mobile/copy-prompts.js")
async def h3_mobile_copy_prompts_js(request): return web.FileResponse(WEB_DIR / "copy-prompts.js")

@routes.get("/h3-mobile/batch.js")
async def h3_mobile_batch_js(request): return web.FileResponse(WEB_DIR / "batch.js")

@routes.get("/h3-mobile/batch-v2.js")
async def h3_mobile_batch_v2_js(request): return web.FileResponse(WEB_DIR / "batch-v2.js")

@routes.get("/h3-mobile/history-autoplay.js")
async def h3_mobile_history_autoplay_js(request): return web.FileResponse(WEB_DIR / "history-autoplay.js")

@routes.get("/h3-mobile/styles.css")
async def h3_mobile_css(request): return web.FileResponse(WEB_DIR / "styles.css")

@routes.get("/h3-mobile/health")
async def h3_mobile_health(request): return web.json_response({"ok": True, "service": "h3-mobile"})

@routes.get("/h3-mobile/api/runtime")
async def h3_mobile_runtime(request):
    seconds = _container_uptime_seconds()
    return web.json_response({"ok": seconds is not None, "uptime_seconds": seconds})

@routes.get("/h3-mobile/api/history/download-all")
async def h3_mobile_download_all(request):
    video_dir = OUTPUT_DIR / "video"
    allowed = {".mp4", ".webm", ".mov", ".mkv", ".gif"}
    files = []
    if video_dir.is_dir():
        files = sorted((p for p in video_dir.rglob("*") if p.is_file() and p.suffix.lower() in allowed), key=lambda p: p.stat().st_mtime)
    if not files:
        raise web.HTTPNotFound(text="ダウンロードできる動画がありません。")
    temp_dir = Path(tempfile.mkdtemp(prefix="h3-mobile-zip-"))
    zip_path = temp_dir / "h3-mobile-videos.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for path in files:
                archive.write(path, arcname=str(path.relative_to(OUTPUT_DIR)))
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    asyncio.create_task(_delete_later(temp_dir))
    response = web.FileResponse(zip_path)
    response.headers["Content-Disposition"] = 'attachment; filename="h3-mobile-videos.zip"'
    return response

@routes.get("/h3-mobile/api/workflow/{mode}")
async def h3_mobile_workflow(request):
    mode = request.match_info["mode"]
    path = API_WORKFLOWS.get(mode)
    if path is None:
        raise web.HTTPBadRequest(text="mode must be i2v or ref2va")
    if not path.is_file():
        raise web.HTTPNotFound(text=f"{mode} API workflow is not installed yet")
    return web.FileResponse(path)

@routes.get("/h3-mobile/api/models")
async def h3_mobile_model_status(request): return web.json_response({"models": _model_state_payload(), "sets": MODE_SETS})

@routes.post("/h3-mobile/api/models/prepare")
async def h3_mobile_prepare_models(request):
    body = await request.json()
    mode = body.get("mode")
    if mode not in MODE_SETS:
        raise web.HTTPBadRequest(text="mode must be ref2va or i2v")
    started, skipped = _schedule_model_set(mode)
    return web.json_response({"ok": True, "mode": mode, "started": started, "skipped": skipped})

from . import extra_routes  # register additional H3 Mobile endpoints
from . import lora_routes  # register dynamic LoRA manager endpoints

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
