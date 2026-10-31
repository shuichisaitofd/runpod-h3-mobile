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
    "HMCumshot_V2.safetensors": "1a5b7948bb97f27737e62c3dd5497a3afb77517f230787f45e45c7d8fe3dc24d",
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
# 10Eros-Max INT8 (Veda test only). One fixed, SHA-pinned file is fetched from
# the public Hugging Face repo into the diffusion_models folder.
# ---------------------------------------------------------------------------
EROS_FILENAME = "10Eros_Max_H3_FL2VA-INT8-ConvRot.safetensors"
EROS_URL = (
    "https://huggingface.co/DmitryDB/MiniMax-H3-10Eros-Max-Quants/resolve/main/"
    "FL2VA/10Eros_Max_H3_FL2VA-INT8-ConvRot.safetensors"
)
EROS_SHA256 = "964a1e0ff49a393cf47bdb3c2bc39e57be02fc1b05fbbb2fddc3eae92dca322f"
EROS_SIZE = 22484074696
_DM_DIRS = [Path(path) for path in folder_paths.get_folder_paths("diffusion_models")]
_EROS_TASK = None


def _eros_installed_path():
    for folder in _DM_DIRS:
        candidate = folder / EROS_FILENAME
        if candidate.is_file() and candidate.stat().st_size == EROS_SIZE:
            return candidate
    return None


_EROS_STATE = {
    "status": "installed" if _eros_installed_path() else "missing",
    "downloaded": EROS_SIZE if _eros_installed_path() else 0,
    "total": EROS_SIZE,
    "error": None,
}


async def _eros_download() -> None:
    global _EROS_TASK
    state = _EROS_STATE
    try:
        if _eros_installed_path():
            state.update(status="installed", downloaded=EROS_SIZE, error=None)
            return
        dest_dir = (
            _DM_DIRS[0] if _DM_DIRS else Path(folder_paths.models_dir) / "diffusion_models"
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / EROS_FILENAME
        part = dest_dir / (EROS_FILENAME + ".part")
        existing = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": "h3-mobile-runpod"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        state.update(status="downloading", downloaded=existing, error=None)
        timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                EROS_URL, headers=headers, allow_redirects=True
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
        if not part.is_file() or part.stat().st_size != EROS_SIZE:
            raise RuntimeError("ダウンロードが途中で止まりました。もう一度ボタンを押してください")
        state["status"] = "verifying"
        actual = await asyncio.to_thread(_sha256, part)
        if actual.lower() != EROS_SHA256:
            part.unlink()
            raise RuntimeError("ファイルの検証に失敗しました。もう一度ボタンを押してください")
        os.replace(part, dest)
        folder_paths.get_filename_list("diffusion_models")
        state.update(status="installed", downloaded=EROS_SIZE, error=None)
        print("[H3] 10Eros-Max INT8 installed")
    except asyncio.CancelledError:
        state["status"] = "paused"
        raise
    except Exception as exc:
        state.update(status="error", error=str(exc))
        print(f"[H3] 10Eros-Max download error: {exc}")
    finally:
        _EROS_TASK = None


@routes.get("/h3-mobile/api/eros/status")
async def h3_mobile_eros_status(request):
    return web.json_response({"filename": EROS_FILENAME, **_EROS_STATE})


@routes.post("/h3-mobile/api/eros/prepare")
async def h3_mobile_eros_prepare(request):
    global _EROS_TASK
    if _eros_installed_path():
        _EROS_STATE.update(status="installed", downloaded=EROS_SIZE, error=None)
        return web.json_response({"ok": True, "started": False})
    if _EROS_TASK and not _EROS_TASK.done():
        return web.json_response({"ok": True, "started": False})
    _EROS_STATE.update(status="queued", error=None)
    _EROS_TASK = asyncio.create_task(_eros_download())
    return web.json_response({"ok": True, "started": True})
