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
    "HMCumshot_V2.safetensors": "d2fa3bc9a5303db16099179d1e1f3897caadb93e7168f3402f440a18746ee788",
    "Motion_FL2VA_v2.safetensors": "f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3",
    "Mystic_FL2VA_v4.safetensors": "fc3e856d14c6c19557c888f48662d591e4794e281233ec0d987be5003068afba",
    "Nipple_v2.safetensors": "7c30c92178e01e33cfbc4684a7b3fb1b71368293443b2941a5b889db3fbd3b18",
    "Orgasm_Masturbate_v1.4.safetensors": "3216dedb116e8da8f343bde4551001dd39b2e84d2392af9766d6380ea24007c7",
    "Panties_v1.safetensors": "f2bf0b4fc7d0ab6f3f91300b0a810dcd76e61f6e8fe39f7dbbd480245987447f",
    "Passionate_Kiss.safetensors": "71b3435525ef8907d35f12cfb9cb81ee9931761ecb27039fc6919b55dd8cda75",
    "Penis_HM_v2.safetensors": "017dd1adddc1be3ec0605dd2e7de97138eb2c6c6ba24be402cf47f103ac1f1b3",
    "Pussy_HM_v1.safetensors": "373c3cad3bf27047fdd754fe111443d97e70e3108a8829f2ec63c48832466eb3",
    "Squirt_HM_v2.safetensors.safetensors": "f0e4bfbe5baebe972880d2250a227e2f475aa8c18d6d01ed897288d9741659d2",
    "MM-H3.-.Fingering.v4.safetensors": "02b1fe9e5df8588cce1424c7bffb8a3fbb2c89e719a9af7fbbfd939b3d6caf87",
    "Cumshot_HM_v1.safetensors": "634c39cfcbfd9421a2d7b5adc62573fc232384c4c75e003c2e11d3408ad0765c",
    "Deepthroat_Ultimate_v1.safetensors": "c94e43ba18cb1e7d6dc5b376821bf593a997f60b09b662a2c5fc5b6a4bfb6105",
    "Finger_Insert_3323149.safetensors": "2f69376ce473d8a9a9ba4e3b306fabfc65c8d9252decff06f413d73741533540",
    "JerkOff_H3.safetensors": "d9145b17a8eca7fe252cb1c2a51e64745484df819db9bce0f90699263800e8aa",
    "M3_Unlocked_v2.safetensors": "8138e5ec1c6cc79706f1129311e90dcd04cc0ef708336c494161b09057f34c07",
    "HMNSFW-AIO-V2.5.safetensors": "a07732a84fd733085eb5d910f602f918fa7a3658117116927e4329f5951a9d2d",
    "breastplayjiggle_h3_v2.safetensors": "18832302cd509749b5c6925f5593c2265bf3d9ee1e4f2a8599b576b835aa61c3",
    "minimax-timefreeze_000003020.safetensors": "838bd5aa8428047ff5055a6ee82991ec92b2e2bc3575ea20d7cbb4f415606ae3",
    "cxy_kiss_lora_h3_v02_step1200.safetensors": "03f9c53550182405679f0ada588eb31362358bb393e9455153c4db333ddc3136",
    "MysticXXX_MMH3-V5.safetensors": "4168917daeb6e570a004bc6994f73d091b9f3e887f7e946bd00c0f2f7573e5f3",
    "cxy_kiss_v3_000002200.safetensors": "a3a754ccbd217efd2d872bf3013050635cf3423e11f10e53220fbf50d0244061",
    "h3-nipplesuck-step00007000-k3nk.safetensors": "a8561078f72c9ffdee3fd2b758374a2cc9e4f210a648cf71ed04acc6dfe11cf4",
    "minimax-jav-voice.safetensors": "6198a007b4d7c8e6f8fabdcb9b3fabfd584f0dcc40a4ff04120373d195031fd1",
    "HMPussyV2.safetensors": "7b9559077d8ac623d52b64b438d8ad60cb85b31b6fecf011aab238b70962a2ed",
    "Rough.Sex.safetensors": "7c212b6f904db4f3841f74b08a1be334cbf9c68512d74c51138496ac15b095fd",
    "H3_speed_slider_1.1.safetensors": "593b074e8eb17bf9f858c3586fc12f53038dbfdd9634e146fe34a17e2661ca40",
    "HMNSFW-Extreme-Realism.safetensors": "55aa39239ea4b408dee601cb0fa49157ec13fe2a54eccbb2fb725b124e43c1b5",
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
                print("[H3] GitHub Release assets missing: " + ", ".join(missing))
                for name in missing:
                    _MANAGED_DOWNLOAD_STATE[name].update(
                        status="error",
                        error="GitHub Release にファイルがありません",
                    )
            present = [name for name in MANAGED_LORA_SPECS if name in assets]
            semaphore = asyncio.Semaphore(2)

            async def download(filename):
                async with semaphore:
                    await _download_managed_lora(session, filename, assets[filename])

            await asyncio.gather(*(download(name) for name in present))
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
            os.replace(part, dest)
            size = dest.stat().st_size
            return web.json_response(
                {"ok": True, "filename": filename, "size": size, "sha256": actual_sha}
            )
        finally:
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


# ---------------------------------------------------------------------------
# 10Eros-Max INT8 models (Veda test only). Each entry is one fixed, SHA-pinned
# file fetched from a public Hugging Face repo into the diffusion_models folder.
# ---------------------------------------------------------------------------
EROS_MODELS = {
    "beta7": {
        "label": "10Eros-Max beta7 raw INT8",
        "filename": "10Eros_Max_h3_raw_beta7_int8.safetensors",
        "url": "https://huggingface.co/TenStrip/10Eros-Max/resolve/main/10Eros_Max_h3_raw_beta7_int8.safetensors",
        "sha256": "9a1fc37d490e68bf578de2c395bfea4e4891f0bd0694409d6d79acc977b274a9",
        "size": 20970401624,
        "auto": True,
    },
    "v2": {
        "label": "10Eros-Max 旧版 FL2VA INT8",
        "filename": "10Eros_Max_H3_FL2VA-INT8-ConvRot.safetensors",
        "url": "https://huggingface.co/DmitryDB/MiniMax-H3-10Eros-Max-Quants/resolve/main/FL2VA/10Eros_Max_H3_FL2VA-INT8-ConvRot.safetensors",
        "sha256": "964a1e0ff49a393cf47bdb3c2bc39e57be02fc1b05fbbb2fddc3eae92dca322f",
        "size": 22484074696,
        "auto": False,
    },
}
_DM_DIRS = [Path(path) for path in folder_paths.get_folder_paths("diffusion_models")]
_EROS_TASKS = {}


def _eros_installed_path(key):
    spec = EROS_MODELS[key]
    for folder in _DM_DIRS:
        candidate = folder / spec["filename"]
        if candidate.is_file() and candidate.stat().st_size == spec["size"]:
            return candidate
    return None


_EROS_STATE = {
    key: {
        "status": "installed" if _eros_installed_path(key) else "missing",
        "downloaded": spec["size"] if _eros_installed_path(key) else 0,
        "total": spec["size"],
        "error": None,
    }
    for key, spec in EROS_MODELS.items()
}


async def _eros_download(key) -> None:
    spec = EROS_MODELS[key]
    state = _EROS_STATE[key]
    size = spec["size"]
    try:
        if _eros_installed_path(key):
            state.update(status="installed", downloaded=size, error=None)
            return
        dest_dir = (
            _DM_DIRS[0] if _DM_DIRS else Path(folder_paths.models_dir) / "diffusion_models"
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / spec["filename"]
        part = dest_dir / (spec["filename"] + ".part")
        existing = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": "h3-mobile-runpod"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        state.update(status="downloading", downloaded=existing, error=None)
        timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                spec["url"], headers=headers, allow_redirects=True
            ) as response:
                if response.status == 416 and existing:
                    pass
                elif response.status not in (200, 206):
                    raise RuntimeError(f"Hugging Face HTTP {response.status}")
                else:
                    if existing and response.status == 200:
                        existing = 0
                        state["downloaded"] = 0
                    mode = "ab" if existing and response.status == 206 else "wb"
                    with part.open(mode) as handle:
                        async for chunk in response.content.iter_chunked(8 * 1024 * 1024):
                            handle.write(chunk)
                            state["downloaded"] += len(chunk)
        if not part.is_file() or part.stat().st_size != size:
            raise RuntimeError("ダウンロードが途中で止まりました。もう一度ボタンを押してください")
        state["status"] = "verifying"
        actual = await asyncio.to_thread(_sha256, part)
        if actual.lower() != spec["sha256"]:
            part.unlink()
            raise RuntimeError("ファイルの検証に失敗しました。もう一度ボタンを押してください")
        os.replace(part, dest)
        folder_paths.get_filename_list("diffusion_models")
        state.update(status="installed", downloaded=size, error=None)
        print(f"[H3] {spec['label']} installed")
    except asyncio.CancelledError:
        state["status"] = "paused"
        raise
    except Exception as exc:
        state.update(status="error", error=str(exc))
        print(f"[H3] {spec['label']} download error: {exc}")
    finally:
        _EROS_TASKS.pop(key, None)


def _eros_start(key) -> bool:
    if _eros_installed_path(key):
        _EROS_STATE[key].update(status="installed", downloaded=EROS_MODELS[key]["size"], error=None)
        return False
    task = _EROS_TASKS.get(key)
    if task and not task.done():
        return False
    _EROS_STATE[key].update(status="queued", error=None)
    _EROS_TASKS[key] = asyncio.create_task(_eros_download(key))
    return True


@routes.get("/h3-mobile/api/eros/status")
async def h3_mobile_eros_status(request):
    return web.json_response(
        {
            "models": {
                key: {"label": spec["label"], "filename": spec["filename"], **_EROS_STATE[key]}
                for key, spec in EROS_MODELS.items()
            }
        }
    )


@routes.post("/h3-mobile/api/eros/prepare")
async def h3_mobile_eros_prepare(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    key = body.get("key") or "beta7"
    if key not in EROS_MODELS:
        raise web.HTTPBadRequest(text="unknown model key")
    return web.json_response({"ok": True, "started": _eros_start(key)})


async def _auto_eros_on_startup(_app):
    # Veda test image: only the default 10Eros model is fetched automatically.
    for key, spec in EROS_MODELS.items():
        if spec.get("auto"):
            _eros_start(key)


if _auto_eros_on_startup not in PromptServer.instance.app.on_startup:
    PromptServer.instance.app.on_startup.append(_auto_eros_on_startup)


# Veda test image: progress of the background Veda setup (veda-image/veda-boot-setup.sh),
# read from its status file and the size of the predictor download. Read-only.
VEDA_STATUS_FILE = Path("/workspace/veda_boot_status.txt")
VEDA_PREDICTOR_FILE = Path(
    "/workspace/runpod-slim/ComfyUI/models/veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors"
)
VEDA_PREDICTOR_SIZE = 275415648


@routes.get("/h3-mobile/api/veda/status")
async def h3_mobile_veda_status(request):
    import time as _time

    try:
        raw = VEDA_STATUS_FILE.read_text(encoding="utf-8", errors="replace").strip()
        since = max(0, int(_time.time() - VEDA_STATUS_FILE.stat().st_mtime))
    except FileNotFoundError:
        raw, since = "", None
    except Exception as exc:
        raw, since = f"FAILED: could not read status ({exc})", None
    low = raw.lower()
    downloaded, total = None, None
    if not raw:
        state, pct, step = "unknown", None, "Vedaの準備状況がまだありません（起動直後）"
    elif raw.startswith("OK"):
        state, pct, step = "ok", 100, "準備完了"
    elif raw.startswith("FAILED"):
        state, pct, step = "failed", None, "失敗: " + raw[len("FAILED:"):].strip()
    elif raw.startswith("WAITING"):
        state, pct, step = "working", 3, "ComfyUIの起動を待っています"
    elif "upgrading comfyui" in low:
        state, pct, step = "working", 15, "ComfyUIを新しい版に更新中"
    elif "installing veda node" in low:
        state, pct, step = "working", 40, "Vedaノードを入れています"
    elif "predictor" in low:
        part = VEDA_PREDICTOR_FILE.with_name(VEDA_PREDICTOR_FILE.name + ".part")
        try:
            downloaded = part.stat().st_size if part.exists() else (VEDA_PREDICTOR_FILE.stat().st_size if VEDA_PREDICTOR_FILE.exists() else 0)
        except Exception:
            downloaded = 0
        total = VEDA_PREDICTOR_SIZE
        frac = min(1.0, downloaded / total) if total else 0
        state, pct, step = "working", 50 + int(frac * 40), "Vedaの予測モデルをダウンロード中"
    elif "restarting comfyui" in low:
        state, pct, step = "working", 95, "ComfyUIを再起動中"
    else:
        state, pct, step = "working", None, raw
    return web.json_response(
        {"state": state, "pct": pct, "step": step, "raw": raw, "since": since, "downloaded": downloaded, "total": total}
    )


# Veda test image: the stock FL2VA model is not used, so it is not downloaded
# (the I2V model set and the model list no longer include it).
import sys as _sys

_pkg = _sys.modules.get(__package__) if __package__ else None
if _pkg is not None and hasattr(_pkg, "MODE_SETS") and hasattr(_pkg, "MODEL_SPECS"):
    _pkg.MODE_SETS["i2v"] = [key for key in _pkg.MODE_SETS["i2v"] if key != "fl2va"]
    _pkg.MODEL_SPECS.pop("fl2va", None)
    print("[H3] Veda image: stock FL2VA model excluded (10Eros-Max only)")
else:
    print("[H3] Veda image: could not exclude stock FL2VA model")


# ---------------------------------------------------------------------------
# Long-video TEST image only (branch h3-longtest): chain I2V clips with
# Herrgott's H3 Infinite Continuation v1.4 (Native Masked AV) and join them.
#   POST /h3-mobile/api/long/run    body: {"prompt": <the page's I2V API graph>, "extra_data": {...}, "clips": 2, "prompts": ["<clip 2 prompt>", "<clip 3 prompt>", ...]}
#        (each prompt is optional: empty = same as the clip before; old "prompt2" = clip 2+)
#        -> queues clip 1 now and returns its prompt_id (the page tracks it like a normal job);
#           the remaining clips and the join run in the background on the Pod.
#   GET  /h3-mobile/api/long/status -> recent runs (stage, clip, error, final file)
# Every clip is saved "Stitch Ready" (overlap already removed), so joining is a plain
# ffmpeg concat (seconds) done by the H3LongConcat node, which also puts the result in the history.
import json as _json
import subprocess as _subprocess
import time as _time
import uuid as _uuid

_LONG_RUNS = {}
_LONG_PORT = None


def _long_port():
    global _LONG_PORT
    if _LONG_PORT is None:
        port = getattr(PromptServer.instance, "port", None)
        if not port:
            try:
                import comfy.cli_args as _ca
                port = _ca.args.port
            except Exception:
                port = 8188
        _LONG_PORT = int(port)
    return _LONG_PORT


def _long_cls(name):
    import nodes as _nodes
    cls = _nodes.NODE_CLASS_MAPPINGS.get(name)
    if cls is None:
        raise RuntimeError(f"ComfyUI node {name} is not installed (long-video nodes missing?)")
    return cls


def _long_slot(cls_name, out_name):
    names = list(getattr(_long_cls(cls_name), "RETURN_NAMES", None) or [])
    if out_name not in names:
        raise RuntimeError(f"{cls_name} has no output {out_name} ({names})")
    return names.index(out_name)


def _long_node(cls_name, **given):
    spec = _long_cls(cls_name).INPUT_TYPES()
    inputs = {}
    for name, s in (spec.get("required") or {}).items():
        if name in given:
            continue
        t = s[0]
        opts = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
        if isinstance(t, (list, tuple)):
            inputs[name] = opts.get("default", t[0] if t else "")
        elif "default" in opts:
            inputs[name] = opts["default"]
    for name, value in given.items():
        if value is not None:
            inputs[name] = value
    return {"class_type": cls_name, "inputs": inputs}


def _long_build(base, run_id, idx, clips, seconds, prompt2=None):
    import copy as _copy
    g = _copy.deepcopy(base)
    i2v = g["105:104"]["inputs"]
    prefix = f"h3long/{run_id}/clip"
    head = None
    if idx == 1:
        g["L_cond"] = _long_node("H3ContinuousStartV14", clip=i2v["clip"], vae=i2v["vae"], prompt=i2v.get("prompt", ""),
                                 width=i2v["width"], height=i2v["height"], duration=float(seconds),
                                 first_frame=i2v.get("first_frame"))
    else:
        g["105:15"]["inputs"]["noise_seed"] = int(g["105:15"]["inputs"].get("noise_seed", 0)) + idx
        g["L_load"] = _long_node("H3ContinuousLoadLatent", latent_path=f"h3long/{run_id}", clip_index=idx - 1)
        g["L_cond"] = _long_node("H3ContinuousContinueV14", clip=i2v["clip"], vae=i2v["vae"],
                                 previous_latent=["L_load", _long_slot("H3ContinuousLoadLatent", "latent")],
                                 handover=["L_load", _long_slot("H3ContinuousLoadLatent", "handover")],
                                 prompt=(prompt2 or i2v.get("prompt", "")), width=i2v["width"], height=i2v["height"],
                                 duration=float(seconds), masked_context_frames="39",
                                 duration_mode="Net New Content", audio_tail_carryover="Full Previous Tail")
        head = ["L_cond", _long_slot("H3ContinuousContinueV14", "actual_head_context_frames")]
    del g["105:104"]
    cond_cls = g["L_cond"]["class_type"]
    g["105:16"]["inputs"]["conditioning"] = ["L_cond", _long_slot(cond_cls, "positive")]
    g["105:14"]["inputs"]["latent_image"] = ["L_cond", _long_slot(cond_cls, "latent")]
    h_slot = _long_slot("H3ContinuousAnalyzeHandoverV14", "handover")
    g["L_an"] = _long_node("H3ContinuousAnalyzeHandoverV14", images=["105:10", 0])
    mode = "Final Clip" if idx == clips else "Stitch Ready"
    g["L_out"] = _long_node("H3ContinuousStitchOutputV14", images=["105:10", 0], audio=["105:23", 0],
                            handover=["L_an", h_slot], output_mode=mode, head_context_frames=head)
    g["105:91"]["inputs"]["images"] = ["L_out", _long_slot("H3ContinuousStitchOutputV14", "images")]
    g["105:91"]["inputs"]["audio"] = ["L_out", _long_slot("H3ContinuousStitchOutputV14", "audio")]
    g["92"]["inputs"]["filename_prefix"] = f"video/h3long/{run_id}_part{idx}"
    if idx < clips:
        g["L_save"] = _long_node("H3ContinuousSaveLatent", latent=["105:14", 0], filename_prefix=prefix, clip_index=idx,
                                 handover=["L_an", h_slot], head_context_frames=head)
    for n in g.values():
        n.pop("_meta", None)
    return g


async def _long_http(method, path, body=None):
    url = f"http://127.0.0.1:{_long_port()}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=body, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"{path}: HTTP {resp.status}: {text[:2000]}")
            return _json.loads(text or "null")


def _long_extra(extra, run_id, label):
    import copy as _copy
    e = _copy.deepcopy(extra or {})
    h = e.setdefault("h3_mobile", {})
    if isinstance(h, dict):
        h["title"] = f"{h.get('title') or '長尺'}（{label}）"
        h["long_run"] = run_id
    return e


async def _long_queue(graph, extra, front=False):
    body = {"prompt": graph, "extra_data": extra, "client_id": "h3-long"}
    if front:
        body["front"] = True  # continuation / join go next, before other queued jobs
    r = await _long_http("POST", "/prompt", body)
    return r["prompt_id"]


async def _long_wait(pid):
    while True:
        await asyncio.sleep(3)
        h = await _long_http("GET", f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m and m[0] in ("execution_error", "execution_interrupted")]
                detail = ""
                if msgs and isinstance(msgs[0][1], dict):
                    detail = msgs[0][1].get("exception_message") or ""
                raise RuntimeError(f"生成に失敗しました: {detail or msgs}"[:800])
            files = []
            for out in h[pid].get("outputs", {}).values():
                for key in ("images", "gifs", "videos", "video"):
                    for f in out.get(key, []) if isinstance(out.get(key), list) else []:
                        if isinstance(f, dict) and str(f.get("filename", "")).lower().endswith((".mp4", ".webm", ".mov")):
                            files.append(f)
            return files


def _long_keep_cache(base):
    import copy as _copy
    import nodes as _nodes
    g = {}
    for nid, n in base.items():
        cls = _nodes.NODE_CLASS_MAPPINGS.get(n.get("class_type"))
        if cls is None or getattr(cls, "OUTPUT_NODE", False):
            continue
        g[nid] = _copy.deepcopy(n)
        g[nid].pop("_meta", None)
    return g


async def _long_worker(run_id, base, extra, clips, seconds, first_pid, prompts=None):
    st = _LONG_RUNS[run_id]
    parts = []
    try:
        pid = first_pid
        for idx in range(1, clips + 1):
            if idx > 1:
                st.update(stage=f"{idx}/{clips}本目を生成中", clip=idx)
                pid = await _long_queue(_long_build(base, run_id, idx, clips, seconds, (prompts or [None] * clips)[idx - 2]), _long_extra(extra, run_id, f"{idx}/{clips}"), front=True)
            st["prompt_ids"].append(pid)
            files = await _long_wait(pid)
            if not files:
                raise RuntimeError(f"{idx}本目の動画ファイルが見つかりません")
            parts.append(files[0])
        st.update(stage="つないでいます", clip=clips)
        files_text = "\n".join(f"{p.get('subfolder', '')}/{p['filename']}".lstrip("/") for p in parts)
        # Keep the I2V loader nodes in this prompt (they are not run): a prompt without them makes ComfyUI
        # drop the cached models, and the next normal job would load them from disk again (+1~2 min).
        g = _long_keep_cache(base)
        g["c"] = _long_node("H3LongConcat", files=files_text, filename_prefix=f"video/h3long/{run_id}_long")
        pid = await _long_queue(g, _long_extra(extra, run_id, f"{clips}本つなぎ"), front=True)
        st["prompt_ids"].append(pid)
        final = await _long_wait(pid)
        st.update(stage="完成", done=True, final=(final[0] if final else None), finished=_time.time())
    except Exception as exc:
        st.update(stage="失敗", error=str(exc)[:800], done=True, finished=_time.time())


@routes.post("/h3-mobile/api/long/run")
async def h3_mobile_long_run(request):
    body = await request.json()
    base = body.get("prompt") or {}
    if not isinstance(base, dict) or base.get("105:104", {}).get("class_type") != "MiniMaxH3ImageToVideo":
        raise web.HTTPBadRequest(text="長尺は「画像から動画」だけで使えます。")
    clips = max(2, min(6, int(body.get("clips") or 2)))
    seconds = float(base.get("105:111", {}).get("inputs", {}).get("value") or 10)
    extra = body.get("extra_data") or {}
    # 2本目以降のプロンプト（それぞれ空欄なら1つ前の本と同じ。1本目は元のプロンプト）
    raw = body.get("prompts")
    if not isinstance(raw, list):
        raw = [body.get("prompt2")] if body.get("prompt2") else []
    prompts, prev = [], None
    for i in range(clips - 1):
        p = str(raw[i] if i < len(raw) and raw[i] else "").strip() or prev
        prompts.append(p)
        prev = p
    run_id = _time.strftime("%Y%m%d-%H%M%S") + "-" + _uuid.uuid4().hex[:4]
    try:
        first = await _long_queue(_long_build(base, run_id, 1, clips, seconds), _long_extra(extra, run_id, f"1/{clips}"))
    except Exception as exc:
        raise web.HTTPBadRequest(text=f"長尺の1本目を開始できませんでした: {exc}"[:1500])
    _LONG_RUNS[run_id] = {"id": run_id, "clips": clips, "seconds": seconds, "clip": 1, "stage": f"1/{clips}本目を生成中",
                          "prompt_ids": [], "done": False, "error": None, "final": None, "started": _time.time(),
                          "prompt2": any(prompts), "custom_prompts": sum(1 for x in raw[:clips - 1] if str(x or "").strip())}
    h3m = extra.get("h3_mobile") if isinstance(extra, dict) else None
    _long_write_meta(run_id, {"title": (h3m or {}).get("title") or "", "clips": clips, "seconds": seconds,
                              "started": _time.time(), "prompts": [bool(p) for p in raw[:clips - 1]]})
    asyncio.create_task(_long_worker(run_id, base, extra, clips, seconds, first, prompts))
    return web.json_response({"prompt_id": first, "number": 0, "node_errors": {}, "long_run": run_id})


@routes.get("/h3-mobile/api/long/status")
async def h3_mobile_long_status(request):
    runs = sorted(_LONG_RUNS.values(), key=lambda r: r["started"], reverse=True)[:10]
    now = _time.time()
    return web.json_response({"runs": [dict(r, elapsed=int((r.get("finished") or now) - r["started"])) for r in runs]})


# --- parts page / split downloads (β) -------------------------------------------------
import re as _re
import shutil as _shutil_mod
import tempfile as _tempfile
import zipfile as _zipfile

_LONG_PART_RE = _re.compile(r"^(?P<run>.+)_part(?P<n>\d+)_\d+_\.mp4$")
_LONG_JOIN_RE = _re.compile(r"^(?P<run>.+)_long_\d+_\.mp4$")
_LONG_VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".gif"}


def _long_out():
    return Path(folder_paths.get_output_directory())


def _long_meta_path(run_id):
    return _long_out() / "h3long" / run_id / "meta.json"


def _long_write_meta(run_id, data):
    try:
        p = _long_meta_path(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[H3] long-video: could not write meta for {run_id}: {exc}")


def _long_is_part(path):
    return path.parent == _long_out() / "video" / "h3long" and bool(_LONG_PART_RE.match(path.name))


@routes.get("/h3-mobile/api/long/parts")
async def h3_mobile_long_parts(request):
    vdir = _long_out() / "video" / "h3long"
    runs = {}
    if vdir.is_dir():
        for p in vdir.glob("*.mp4"):
            m = _LONG_PART_RE.match(p.name)
            j = None if m else _LONG_JOIN_RE.match(p.name)
            if not m and not j:
                continue
            run_id = (m or j).group("run")
            st = p.stat()
            r = runs.setdefault(run_id, {"id": run_id, "parts": [], "joined": None, "mtime": 0})
            r["mtime"] = max(r["mtime"], st.st_mtime)
            f = {"filename": p.name, "subfolder": "video/h3long", "type": "output", "size": st.st_size, "mtime": st.st_mtime}
            if m:
                f["n"] = int(m.group("n"))
                r["parts"].append(f)
            else:
                r["joined"] = f
    out = []
    for r in runs.values():
        if not r["parts"]:
            continue
        r["parts"].sort(key=lambda f: (f["n"], f["mtime"]))
        meta = {}
        try:
            meta = _json.loads(_long_meta_path(r["id"]).read_text(encoding="utf-8"))
        except Exception:
            pass
        live = _LONG_RUNS.get(r["id"]) or {}
        r["title"] = meta.get("title") or ""
        r["clips"] = meta.get("clips") or live.get("clips") or len(r["parts"])
        r["seconds"] = meta.get("seconds") or live.get("seconds")
        r["stage"] = live.get("stage") or ("完成" if r["joined"] else "")
        out.append(r)
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return web.json_response({"runs": out})


def _long_zip(files, name):
    temp_dir = Path(_tempfile.mkdtemp(prefix="h3-long-zip-"))
    zip_path = temp_dir / name
    try:
        with _zipfile.ZipFile(zip_path, "w", compression=_zipfile.ZIP_STORED, allowZip64=True) as archive:
            for path in files:
                archive.write(path, arcname=str(path.relative_to(_long_out())))
    except Exception:
        _shutil_mod.rmtree(temp_dir, ignore_errors=True)
        raise
    return temp_dir, zip_path


async def _long_rm_later(path, delay=3600):
    await asyncio.sleep(delay)
    _shutil_mod.rmtree(path, ignore_errors=True)


@routes.get("/h3-mobile/api/long/download")
async def h3_mobile_long_download(request):
    """kind=main: every video except the long-video parts (same as 一括ダウンロード without parts). kind=parts: parts only."""
    kind = request.query.get("kind", "main")
    vdir = _long_out() / "video"
    files = []
    if vdir.is_dir():
        files = [p for p in vdir.rglob("*") if p.is_file() and p.suffix.lower() in _LONG_VIDEO_EXT]
    files = [p for p in files if _long_is_part(p) == (kind == "parts")]
    files.sort(key=lambda p: p.stat().st_mtime)
    if not files:
        raise web.HTTPNotFound(text="ダウンロードできる動画がありません。")
    name = "h3-long-parts.zip" if kind == "parts" else "h3-videos.zip"
    temp_dir, zip_path = await asyncio.to_thread(_long_zip, files, name)
    asyncio.create_task(_long_rm_later(temp_dir))
    response = web.FileResponse(zip_path)
    response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


def _long_ffmpeg():
    import shutil as _shutil
    exe = _shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg as _iff
        return _iff.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("ffmpeg が見つかりません")


class H3LongConcat:
    """Join already-trimmed MP4 parts with ffmpeg (video copied, audio re-encoded) and show the result in the history."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"files": ("STRING", {"multiline": True, "default": ""}),
                             "filename_prefix": ("STRING", {"default": "video/h3long/long"})}}

    RETURN_TYPES = ()
    FUNCTION = "join"
    OUTPUT_NODE = True
    CATEGORY = "H3 Mobile/long"

    def join(self, files, filename_prefix):
        out_root = Path(folder_paths.get_output_directory())
        parts = [out_root / f.strip() for f in str(files).splitlines() if f.strip()]
        for p in parts:
            if not p.is_file():
                raise RuntimeError(f"part not found: {p}")
        sub = str(Path(filename_prefix).parent)
        name = Path(filename_prefix).name
        target_dir = out_root / sub
        target_dir.mkdir(parents=True, exist_ok=True)
        n = 1
        while (target_dir / f"{name}_{n:05d}_.mp4").exists():
            n += 1
        target = target_dir / f"{name}_{n:05d}_.mp4"
        lst = target_dir / f".{name}_{n:05d}_list.txt"
        lst.write_text("".join(f"file '{str(p)}'\n" for p in parts), encoding="utf-8")
        cmd = [_long_ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)]
        r = _subprocess.run(cmd, capture_output=True, text=True)
        try:
            lst.unlink()
        except Exception:
            pass
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {r.stderr[-1500:]}")
        return {"ui": {"images": [{"filename": target.name, "subfolder": sub, "type": "output"}], "animated": (True,)}}


try:
    import nodes as _nodes_mod
    _nodes_mod.NODE_CLASS_MAPPINGS["H3LongConcat"] = H3LongConcat
    _nodes_mod.NODE_DISPLAY_NAME_MAPPINGS["H3LongConcat"] = "H3 Long: Concat parts"
    print("[H3] long-video test routes ready (/h3-mobile/api/long/*, H3LongConcat)")
except Exception as _exc:
    print(f"[H3] long-video test: could not register H3LongConcat: {_exc}")
