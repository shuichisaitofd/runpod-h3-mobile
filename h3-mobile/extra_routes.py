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


# Header balance/cost display (feature request: show account balance, an
# estimated remaining runtime, and the current hourly rate). Two separate
# RunPod endpoints are needed: REST v2 for this pod's cost-per-hour, and the
# GraphQL API for the account balance (REST v2 has no balance field as of
# 2026-08). Either call can fail independently (e.g. a pod-scoped API key -
# what RunPod auto-injects as RUNPOD_API_KEY - can read its own pod's cost
# via REST v2 but gets GraphQL "Unauthorized", since GraphQL access is a
# separate, broader permission) - each field degrades to null on its own
# rather than failing the whole response, so the frontend can show whatever
# partial data is available instead of an all-or-nothing dash.
@routes.get("/h3-mobile/api/pod-billing")
async def h3_mobile_pod_billing(request):
    pod_id = os.environ.get("RUNPOD_POD_ID")
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not pod_id or not api_key:
        return web.json_response({"balance": None, "cost_per_hour": None, "estimated_hours_remaining": None, "error": "RunPod metadata unavailable (pod id or API key missing)"})

    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"Authorization": f"Bearer {api_key}"}
    cost_per_hour = None
    balance = None
    errors = []

    # REST API v1 (rest.runpod.io/v1) is deprecated (sunset 2026-11-15) and
    # returns a blanket 403 for RunPod's own pod-scoped keys (the key every
    # pod gets auto-injected as RUNPOD_API_KEY). REST API v2 replaces
    # costPerHr with an equivalently-defined "cost" field ("Current cost in
    # USD per hour") and DOES work with a pod-scoped key for its own pod.
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.runpod.io/v2/pods/{pod_id}", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    cost_per_hour = data.get("cost")
                else:
                    errors.append(f"cost_per_hour: HTTP {response.status}")
    except Exception as exc:
        errors.append(f"cost_per_hour: {exc}")

    # Account credit balance has no REST v2 equivalent yet (checked against
    # the v2 OpenAPI spec, 2026-08) - only GraphQL's myself.clientBalance
    # exposes it, and it needs the key's separate "GraphQL access"
    # permission, which is distinct from (and usually narrower than) REST
    # endpoint permissions - a pod-scoped key can read its own pod's cost via
    # REST v2 while still getting GraphQL "Unauthorized".
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            query = {"query": "query { myself { clientBalance } }"}
            async with session.post("https://api.runpod.io/graphql", headers=headers, json=query) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("errors"):
                        errors.append("balance: " + "; ".join(e.get("message", "error") for e in data["errors"]))
                    else:
                        balance = (data.get("data") or {}).get("myself", {}).get("clientBalance")
                else:
                    errors.append(f"balance: HTTP {response.status}")
    except Exception as exc:
        errors.append(f"balance: {exc}")

    estimated_hours_remaining = None
    if isinstance(balance, (int, float)) and isinstance(cost_per_hour, (int, float)) and cost_per_hour > 0:
        estimated_hours_remaining = balance / cost_per_hour

    return web.json_response({
        "ok": balance is not None or cost_per_hour is not None,
        "balance": balance,
        "cost_per_hour": cost_per_hour,
        "estimated_hours_remaining": estimated_hours_remaining,
        "approximate": True,  # other pods/storage on the same account also draw from this balance
        "error": "; ".join(errors) if errors else None,
    })


# filepath -> (mtime_ns, size, sha256_hex). ComfyUI's own /upload/image only
# dedupes an upload against an existing file of the SAME filename (and only
# when overwrite is not set) — it never compares content across different
# filenames, so a re-selected photo exported under a new device filename (or
# uploaded again from a different UI flow) always lands as a brand new file.
# This cache lets input-image-lookup answer "does this content already exist
# anywhere under input/" cheaply on repeat calls, without rehashing unchanged
# files every time.
_INPUT_HASH_CACHE: dict[str, tuple[int, int, str]] = {}


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_input_image_by_hash(target_hash: str):
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    if not INPUT_DIR.is_dir():
        return None
    for path in INPUT_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        key = str(path)
        cached = _INPUT_HASH_CACHE.get(key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            digest = cached[2]
        else:
            try:
                digest = _sha256_of(path)
            except OSError:
                continue
            _INPUT_HASH_CACHE[key] = (stat.st_mtime_ns, stat.st_size, digest)
        if digest == target_hash:
            rel = path.relative_to(INPUT_DIR)
            subfolder = str(rel.parent) if str(rel.parent) != "." else ""
            return {"filename": path.name, "subfolder": subfolder}
    return None


@routes.get("/h3-mobile/api/input-image-lookup")
async def h3_mobile_input_image_lookup(request):
    target_hash = (request.query.get("sha256") or "").strip().lower()
    if len(target_hash) != 64 or any(c not in "0123456789abcdef" for c in target_hash):
        raise web.HTTPBadRequest(text="sha256 query param required (64 hex chars)")
    loop = asyncio.get_event_loop()
    match = await loop.run_in_executor(None, _find_input_image_by_hash, target_hash)
    if match is None:
        return web.json_response({"found": False})
    return web.json_response({"found": True, **match})


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
            "-vf", "scale=640:-2:force_original_aspect_ratio=decrease", "-q:v", "3", str(dest),
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


@routes.get("/h3-mobile/pod-billing.js")
async def h3_mobile_pod_billing_js(request):
    return web.FileResponse(WEB_DIR / "pod-billing.js")


@routes.get("/h3-mobile/prompt-library.js")
async def h3_mobile_prompt_library_js(request):
    return web.FileResponse(WEB_DIR / "prompt-library.js")
