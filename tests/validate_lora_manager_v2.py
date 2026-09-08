import ast
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "h3-mobile"
WEB = MOBILE / "web"
init_text = (MOBILE / "__init__.py").read_text()
routes_text = (MOBILE / "lora_routes.py").read_text()
run_text = (ROOT / "run.sh").read_text()
index_text = (WEB / "index.html").read_text()
js = (WEB / "lora-library.js").read_text()
app = (WEB / "app.js").read_text()
batch = (WEB / "batch-v2.js").read_text()

# Import structure: the aiohttp.web binding used by /h3 redirects must never be
# replaced by a package named web.
tree = ast.parse(init_text)
assert any(
    isinstance(node, ast.ImportFrom)
    and node.module == "aiohttp"
    and any(alias.name == "web" for alias in node.names)
    for node in tree.body
)
assert any(
    isinstance(node, ast.ImportFrom)
    and node.level == 1
    and node.module is None
    and any(alias.name == "lora_routes" and alias.asname is None for alias in node.names)
    for node in tree.body
)
assert "from .web import lora_routes" not in init_text
assert "from . import lora_routes" in run_text
assert "sed -i '/from \\.web import lora_routes/d'" in run_text
assert "printf '\\nfrom .web import lora_routes" not in run_text
assert "raise web.HTTPFound(\"/h3-mobile/\")" in init_text
assert (MOBILE / "lora_routes.py").is_file()
assert not (WEB / "lora_routes.py").exists()
assert 'WEB_DIR = Path(__file__).resolve().parent / "web"' in routes_text
assert "COPY h3-mobile/lora_routes.py" in (ROOT / "Dockerfile").read_text()

# Dedicated LoRA page and navigation; settings contains only the original
# model/Pod/connection cards.
assert 'data-page="lora"' in index_text
assert 'data-target="lora">LoRA<' in index_text
settings_html = index_text.split('<section class="page" data-page="settings">', 1)[1].split("</section>", 1)[0]
assert "LoRA管理" not in settings_html
assert "h3LoraPage" in js
assert "injectSettings" not in js

# Compact button toggles, project-scoped selection/strength/order, and batch
# generation sharing the active project's selection.
assert 'type="checkbox"' not in js
assert "h3-lora-toggle" in js and "aria-pressed" in js
assert "project.loraSelections" in js
assert "getProjects" in js and "getActiveProjectId" in js and "saveProjects" in js
assert "order:index" in js and "moveSelection" in js
assert "currentBatchCtx" in js and "selected(ctx)" in js
assert "h3:project-changed" in app and "h3:project-changed" in js

# File/URL addition, automatic filenames, restore flows, progress, auth, and
# backup are all explicit and are not mode-targeted.
assert 'accept=".safetensors" multiple' in js
assert "originalFilename===file.name" in js
assert "uploaded file SHA256 mismatch" in routes_text
assert "sha256=${encodeURIComponent(item.sha256)}" in js
assert "URLから一括再導入" in js and "bulkDownloadUrls" in js
assert "ファイルを一括アップロード" in js and "bulkUploadFiles" in js
assert "このPodにLoRAを復元" in js and "restoreToPod" in js
assert "downloaded" in js and "total" in js and "h3-lora-progress" in js
for label in ("未導入", "待機中", "ダウンロード中", "導入済み", "エラー"):
    assert label in js
assert "Civitai APIキー" in js and "h3MobileCivitaiApiKey" in js
assert "api_key:civitaiKey()" in js
assert "URLから取得できません。認証を確認するか、ファイルから追加してください。" in js
assert "設定バックアップ" in js and "設定を復元" in js
assert "projectSelections" in js and "originalFilename" in js
assert "loraNewTarget" not in js and "対象 Ref2VA" not in js
assert "/h3-mobile/api/loras/resolve" in routes_text
assert "Content-Disposition" in routes_text and "_filename_from_response" in routes_text

# A completed file is authoritative, uploads stop a same-name URL task first,
# and worker failures preserve a completed destination.
upload_route = routes_text.split("async def h3_mobile_lora_upload", 1)[1].split(
    '@routes.post("/h3-mobile/api/loras/delete")', 1
)[0]
assert "await _cancel_download_for_upload(filename)" in upload_route
assert upload_route.index("await _cancel_download_for_upload(filename)") < upload_route.index(
    "await request.multipart()"
)
assert '_DOWNLOAD_TASKS.pop(filename, None)' in routes_text
assert '_DOWNLOAD_STATE.pop(filename, None)' in routes_text
assert 'LORA_DIR / f"{filename}.part"' in routes_text
assert routes_text.count("if not _keep_installed_if_present(filename, dest):") == 2

# File bulk upload is a strictly sequential file-only recovery path. A failed
# file is counted and the loop continues to the remaining selections.
bulk_upload = js.split("async function bulkUploadFiles", 1)[1].split(
    "async function restoreToPod", 1
)[0]
for forbidden in (
    "bulkDownloadUrls",
    "resolveUrl",
    "civitaiKey",
    "/h3-mobile/api/loras/download",
):
    assert forbidden not in bulk_upload
assert "for(const file of [...files])" in bulk_upload
assert "try{const result=await uploadItem(item,file)" in bulk_upload
assert "catch{failed++;errors.push(file.name);}" in bulk_upload

# URL registrations that fail to redownload are selected by actual Pod file
# status, not excluded just because their saved record still has a URL.
restore_candidates = js.split("function restoreCandidates", 1)[1].split(
    "async function bulkUploadFiles", 1
)[0]
restore_to_pod = js.split("async function restoreToPod", 1)[1].split(
    "function exportSettings", 1
)[0]
assert "!isInstalledFile(fileMap.get(item.filename))" in restore_candidates
assert "!item.url" not in restore_candidates
assert "waitForUrlDownloads(result.pending)" in restore_to_pod
assert "restoreCandidates(files)" in restore_to_pod
assert "ファイルで復元できます" in restore_to_pod

# Registration origin and current-Pod installation method are separate. File
# restore never converts a URL registration into a file registration.
assert "sourceType" in js and "installMethod" in js
assert "登録: ${sourceTypeLabel(item.sourceType)}" in js
assert "Pod導入: ${installMethodLabel(item,installed)}" in js
assert "installMethod:'file'" in bulk_upload
assert "sourceType:item.url?'url':'file'" not in js
assert "sourceType:'file',originalFilename:file.name" not in js

# Dynamic prefixing is gated by Motion Booster for both Ref2VA entry points,
# while I2V follows the unchanged inputPrompt branch.
assert "h3LoraShouldAddDynv2" in js
assert "Motion_REF2VA_v2.safetensors" in js
assert "isRef&&shouldAddRef2VADynv2(refCtx)" in app
assert "runMode==='ref2va'&&shouldAddRef2VADynv2(refCtx)" in batch
assert "h3LoraSnapshot" in js and "h3ApplyLoraSnapshot" in js
assert "const runMode=batch.mode,runRefVariant=batch.refVariant" in batch
assert "loraSnapshot,refVariant:runRefVariant" in batch
assert "wf['105:104'].inputs.prompt=prompt" in app
assert "wf['105:104'].inputs.prompt=cfg.prompt" in batch

# Import the route module with minimal ComfyUI stubs to exercise filename
# resolution and prove a zero-byte safetensors is reported as missing.
class Routes:
    def get(self, _path):
        return lambda function: function

    def post(self, _path):
        return lambda function: function


with tempfile.TemporaryDirectory() as temp_dir:
    temp = Path(temp_dir)
    old_folder_paths = sys.modules.get("folder_paths")
    old_server = sys.modules.get("server")
    old_aiohttp = sys.modules.get("aiohttp")

    class HTTPError(Exception):
        def __init__(self, text=""):
            super().__init__(text)

    fake_web = types.SimpleNamespace(
        HTTPBadRequest=HTTPError,
        HTTPBadGateway=HTTPError,
        HTTPConflict=HTTPError,
        HTTPInternalServerError=HTTPError,
        FileResponse=lambda *args, **kwargs: None,
        json_response=lambda *args, **kwargs: None,
    )
    sys.modules["aiohttp"] = types.SimpleNamespace(
        web=fake_web,
        ClientTimeout=lambda *args, **kwargs: None,
        ClientSession=lambda *args, **kwargs: None,
    )
    sys.modules["folder_paths"] = types.SimpleNamespace(
        get_folder_paths=lambda _kind: [str(temp)], models_dir=str(temp)
    )
    sys.modules["server"] = types.SimpleNamespace(
        PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=Routes()))
    )
    try:
        spec = importlib.util.spec_from_file_location("h3_lora_routes_test", MOBILE / "lora_routes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module._filename_from_response(
            "https://example.com/download?id=1",
            "attachment; filename*=UTF-8''My%20LoRA.safetensors",
        ) == "My LoRA.safetensors"
        (temp / "empty.safetensors").touch()
        state = {item["filename"]: item for item in module._files_payload()}
        assert state["empty.safetensors"]["status"] == "missing"
        assert state["empty.safetensors"]["downloaded"] == 0

        # Actual non-empty files must beat any stale error/cancel/download
        # state left behind by URL processing.
        (temp / "present.safetensors").write_bytes(b"valid")
        module._DOWNLOAD_STATE["present.safetensors"] = {
            "filename": "present.safetensors",
            "status": "error",
            "downloaded": 0,
            "total": None,
            "error": "HTTP 401",
        }
        state = {item["filename"]: item for item in module._files_payload()}
        assert state["present.safetensors"]["status"] == "installed"
        assert state["present.safetensors"]["size"] == 5
        assert state["present.safetensors"]["error"] is None

        # Even if the worker itself enters its exception path, a completed
        # destination that appeared concurrently remains installed.
        (temp / "worker-race.safetensors").write_bytes(b"complete")
        asyncio.run(
            module._download_worker(
                "worker-race.safetensors", "https://example.com/model", "", ""
            )
        )
        assert module._DOWNLOAD_STATE["worker-race.safetensors"]["status"] == "installed"

        # Starting file upload cancels and awaits the same-name URL task,
        # clears stale state, and removes the download .part file.
        async def verify_upload_cancellation():
            filename = "recover.safetensors"
            started = asyncio.Event()
            blocker = asyncio.Event()

            async def stale_download():
                started.set()
                await blocker.wait()

            task = asyncio.create_task(stale_download())
            await started.wait()
            module._DOWNLOAD_TASKS[filename] = task
            module._DOWNLOAD_STATE[filename] = {
                "filename": filename,
                "status": "downloading",
            }
            part = temp / f"{filename}.part"
            part.write_bytes(b"partial")
            await module._cancel_download_for_upload(filename)
            assert task.cancelled()
            assert filename not in module._DOWNLOAD_TASKS
            assert filename not in module._DOWNLOAD_STATE
            assert not part.exists()

        asyncio.run(verify_upload_cancellation())
    finally:
        if old_folder_paths is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = old_folder_paths
        if old_server is None:
            sys.modules.pop("server", None)
        else:
            sys.modules["server"] = old_server
        if old_aiohttp is None:
            sys.modules.pop("aiohttp", None)
        else:
            sys.modules["aiohttp"] = old_aiohttp

subprocess.run(["node", "--check", str(WEB / "lora-library.js")], check=True)
subprocess.run(["node", "--check", str(WEB / "app.js")], check=True)
subprocess.run(["node", "--check", str(WEB / "batch-v2.js")], check=True)
subprocess.run(["python3", "-m", "py_compile", str(MOBILE / "lora_routes.py")], check=True)
subprocess.run(["bash", "-n", str(ROOT / "run.sh")], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("LoRA manager v2 validation OK")
