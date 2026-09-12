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
routes_tree = ast.parse(routes_text)
route_functions = {
    node.name: node
    for node in routes_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
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
assert (MOBILE / "lora_routes.py").is_file()
assert not (WEB / "lora_routes.py").exists()
assert 'WEB_DIR = Path(__file__).resolve().parent / "web"' in routes_text
assert "COPY h3-mobile/lora_routes.py" in (ROOT / "Dockerfile").read_text()

# The H3 body/Qwen/VAE/Turbo model auto-download is a separate feature and must
# survive: it still lives in __init__.py with its own URL downloader.
assert "MODEL_SPECS" in init_text and "aiohttp" in init_text
assert "turbo_lora" in init_text
assert "minimax_h3_turbo_v4_step600_ema.safetensors" in init_text

# Dedicated LoRA page and navigation.
assert 'data-page="lora"' in index_text
assert 'data-target="lora">LoRA<' in index_text
settings_html = index_text.split('<section class="page" data-page="settings">', 1)[1].split("</section>", 1)[0]
assert "LoRA管理" not in settings_html

# --- URL / Civitai removal, frontend --------------------------------------
for forbidden in (
    "loraNewUrl",
    "URLから追加",
    "URLから一括再導入",
    "Civitai",
    "CIVITAI_KEY",
    "civitaiKey",
    "resolveUrl",
    "downloadItem",
    "addUrlFromForm",
    "bulkDownloadUrls",
    "waitForUrlDownloads",
    "startManagerPolling",
    "sourceTypeLabel",
    "installMethodLabel",
    "PodへDL",
):
    assert forbidden not in js, forbidden

# URL-era record fields survive only inside the one-time discard helper.
assert "function stripUrlFields(item)" in js
assert js.count("sourceType") == 1 and js.count("pendingInstallMethod") == 1

# --- User-controlled URL / Civitai removal, backend ----------------------
for forbidden in (
    "/h3-mobile/api/loras/resolve",
    "/h3-mobile/api/loras/download",
    "_download_worker",
    "_probe_download",
    "_validate_public_url",
    "_request_headers",
    "civitai",
    "_REDIRECT_CODES",
    "_DOWNLOAD_TASKS",
):
    assert forbidden not in routes_text, forbidden

user_upload_source = ast.get_source_segment(
    routes_text, route_functions["h3_mobile_lora_upload"]
)
for forbidden in (
    "aiohttp.ClientSession",
    "allow_redirects",
    "Authorization",
    "Bearer",
    "redirect",
):
    assert forbidden not in user_upload_source, forbidden

# The automatic downloader is a separate server-owned allowlist. It cannot
# accept an arbitrary URL from the browser.
assert "MANAGED_LORA_SPECS" in routes_text
assert "GITHUB_RELEASE_API" in routes_text
assert "H3_LORA_GITHUB_TOKEN" in routes_text

# --- File-only add flow --------------------------------------------------
assert 'accept=".safetensors" multiple' in js
assert "value.originalFilename===file.name||value.filename===file.name" in js
assert "catalogDefinition(file.name)" in js
assert "addRecord(catalogRecord(definition))" in js
# custom auto-register defaults: strength 1.0, initial OFF everywhere.
assert "addRecord({name:autoName(file.name),filename:file.name,originalFilename:file.name,sha256:'',defaultStrength:1})" in js
assert "project.loraSelections[ctx][item.id]={enabled:false,strength:item.defaultStrength,order:library.length-1}" in js
# no duplicate registration for a filename already present.
assert "const existing=library.find(entry=>entry.filename===item.filename||entry.originalFilename===item.originalFilename);" in js
assert "if(existing)return existing;" in js

# --- Upload progress + status + retry ----------------------------------
assert "XMLHttpRequest" in js
assert "xhr.upload.onprogress" in js
for label in ("未導入", "待機中", "アップロード中", "検証中", "導入済み", "導入失敗", "再試行"):
    assert label in js, label
assert "friendlyError" in js
assert "SHA256が一致しません" in js
assert "通信が切断されました" in js
# The failed state stays on the card (uploadState) until the next action, with a
# details block for the raw error — no console-only diagnosis.
assert "uploadState" in js and "clearUploadState" in js
assert "<details><summary>詳細</summary>" in js

# --- SHA256 roles are separate ---------------------------------------
# A learned hash is stored as metadata only; only a *trusted catalog* hash is
# ever sent to the server as an expected hash.
assert "trustedExpectedSha" in js
assert "expectedSha256" in js
assert "&expected_sha256=" in js
assert "&sha256=${encodeURIComponent(item.sha256)}" not in js  # the old stale-SHA bug
assert "const expected=item.sha256?" not in js
assert "Persist the" in js  # comment explaining learned-hash handling

# --- Pod real files are authoritative --------------------------------
assert "function isInstalledFile(file){return !!file&&file.status==='installed'&&Number(file.size)>0;}" in js
assert "/h3-mobile/api/loras/files" in js
assert "_files_payload" in routes_text
assert '"incomplete"' in routes_text  # zero-byte real file is not installed

# --- .upload.part safety --------------------------------------------
upload_route = routes_text.split("async def h3_mobile_lora_upload", 1)[1].split(
    '@routes.post("/h3-mobile/api/loras/delete")', 1
)[0]
assert "_lock_for(filename)" in upload_route  # per-filename lock -> no concurrent clobber
assert "secrets.token_hex" in upload_route  # unique private temp name
assert "_TEMP_SUFFIX" in upload_route
assert "os.replace(part, dest)" in upload_route
assert upload_route.index("await asyncio.to_thread(_sha256, part)") < upload_route.index("os.replace(part, dest)")
assert "finally:" in upload_route and "part.unlink()" in upload_route
assert "_sweep_temp_files()" in routes_text
assert "_is_temp_name" in routes_text

# --- Backup: full settings, no URL/API key ---------------------------
assert "BACKUP_SCHEMA='h3-mobile-settings'" in js
assert "BACKUP_VERSION=3" in js
assert "generationPresets" in js and "loraRegistry" in js
assert "sanitizeProject" in js and "blankImages" in js
assert "data.version===2&&Array.isArray(data.library)" in js  # legacy v2 migration
assert "stripUrlFields" in js
export_fn = js.split("function exportSettings", 1)[1].split("function normalizeBackup", 1)[0]
for forbidden in ("api_key", "apiKey", "Civitai", "item.url", "sourceType", "images:{"):
    assert forbidden not in export_fn, forbidden
# registry entries carry the learned sha as plain metadata, nothing else.
assert "sha256:item.sha256||''" in export_fn
assert "generationPresets:loadPresets()" in export_fn

# --- Python: exercise the file-only route module -----------------------
class Routes:
    def get(self, _path):
        return lambda function: function

    def post(self, _path):
        return lambda function: function


with tempfile.TemporaryDirectory() as temp_dir:
    temp = Path(temp_dir)
    saved = {name: sys.modules.get(name) for name in ("folder_paths", "server", "aiohttp")}

    class HTTPError(Exception):
        def __init__(self, text=""):
            super().__init__(text)
            self.text = text

    fake_web = types.SimpleNamespace(
        HTTPBadRequest=HTTPError,
        HTTPConflict=HTTPError,
        HTTPInternalServerError=HTTPError,
        FileResponse=lambda *a, **k: None,
        json_response=lambda *a, **k: (a[0] if a else k),
    )
    sys.modules["aiohttp"] = types.SimpleNamespace(web=fake_web)
    sys.modules["folder_paths"] = types.SimpleNamespace(
        get_folder_paths=lambda _kind: [str(temp)],
        get_filename_list=lambda _kind: [],
        models_dir=str(temp),
    )
    sys.modules["server"] = types.SimpleNamespace(
        PromptServer=types.SimpleNamespace(
            instance=types.SimpleNamespace(
                routes=Routes(), app=types.SimpleNamespace(on_startup=[])
            )
        )
    )
    try:
        spec = importlib.util.spec_from_file_location("h3_lora_routes_fileonly", MOBILE / "lora_routes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # zero-byte real file is not installed.
        (temp / "empty.safetensors").touch()
        state = {item["filename"]: item for item in module._files_payload()}
        assert state["empty.safetensors"]["status"] == "incomplete"

        # a *.upload.part temp file never appears as installed and is swept.
        stale = temp / "Panties_v1.safetensors.12345.abcdef.upload.part"
        stale.write_bytes(b"partial")
        module._sweep_temp_files()
        assert not stale.exists()
        state = {item["filename"]: item for item in module._files_payload()}
        assert "Panties_v1.safetensors" not in state

        # a real non-empty file is installed.
        (temp / "present.safetensors").write_bytes(b"valid-bytes")
        state = {item["filename"]: item for item in module._files_payload()}
        assert state["present.safetensors"]["status"] == "installed"
        assert state["present.safetensors"]["size"] == 11

        # per-filename lock object is stable (serialises concurrent uploads).
        lock_a = module._lock_for("x.safetensors")
        assert module._lock_for("x.safetensors") is lock_a

        # delete removes the formal file and any leftover temp parts, never a
        # different lora's file.
        (temp / "victim.safetensors").write_bytes(b"bytes")
        (temp / "victim.safetensors.1.2.upload.part").write_bytes(b"tmp")
        (temp / "keep.safetensors").write_bytes(b"bytes")

        async def _delete_body():
            return {"filename": "victim.safetensors"}

        asyncio.run(
            module.h3_mobile_lora_delete(types.SimpleNamespace(json=_delete_body))
        )
        assert not (temp / "victim.safetensors").exists()
        assert not (temp / "victim.safetensors.1.2.upload.part").exists()
        assert (temp / "keep.safetensors").exists()
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

subprocess.run(["node", "--check", str(WEB / "lora-library.js")], check=True)
subprocess.run(["node", "--check", str(WEB / "app.js")], check=True)
subprocess.run(["node", "--check", str(WEB / "batch-v2.js")], check=True)
subprocess.run(["python3", "-m", "py_compile", str(MOBILE / "lora_routes.py")], check=True)
subprocess.run(["bash", "-n", str(ROOT / "run.sh")], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("LoRA manager v2 (file-only) validation OK")
