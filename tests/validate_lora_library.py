import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "h3-mobile"
WEB = MOBILE / "web"

js = (WEB / "lora-library.js").read_text()
routes = (MOBILE / "lora_routes.py").read_text()
run = (ROOT / "run.sh").read_text()
index = (WEB / "index.html").read_text()

for filename in (
    "AIO_v2.5.safetensors",
    "BJ_v3.safetensors",
    "Finger_BEAN_v1.safetensors",
    "deepthroat_v02.safetensors",
    "Squirt_HM_v1.safetensors",
    "Nipple_v2.safetensors",
    "Panties_v1.safetensors",
    "Motion_FL2VA_v2.safetensors",
    "Motion_REF2VA_v2.safetensors",
    "Mystic_FL2VA_v4.safetensors",
    "Penis_HM_v2.safetensors",
    "Pussy_HM_v1.safetensors",
):
    assert filename in js, filename

assert "h3MobileLoraLibraryV1" in js
assert "loraSelections" in js
assert "localStorage.setItem" in js
assert 'type="number" step="0.01" inputmode="decimal"' in js
assert "LoraLoaderModelOnly" in js
assert "stripManaged" in js
assert "applyLoras" in js
assert "LoRA未導入" in js

# File-only add UI: no URL entry field, no URL add mode, no Civitai auth.
for forbidden in (
    "loraNewUrl",
    "loraChooseUrl",
    "URLから追加",
    "URLから一括再導入",
    "m-url",
    "PodへDL",
    "CIVITAI_KEY",
    "civitaiKey",
    "Civitai APIキー",
    "loraSaveKey",
    "resolveUrl",
    "downloadItem",
    "addUrlFromForm",
    "bulkDownloadUrls",
    "waitForUrlDownloads",
    "loraChooseFile",
    "sourceTypeLabel",
    "installMethodLabel",
    "syncInstallMethods",
):
    assert forbidden not in js, forbidden

# URL-era record fields only ever appear inside the one-time discard helper.
assert "function stripUrlFields(item)" in js
assert js.count("sourceType") == 1 and js.count("installMethod") == 1
assert "...item" not in js.split("function normalizeItem", 1)[1].split("}\n", 1)[0]

assert 'accept=".safetensors" multiple' in js
assert "登録削除" in js
assert "全設定バックアップ" in js and "全設定を復元" in js
assert "XMLHttpRequest" in js and "xhr.upload.onprogress" in js
assert "検証中" in js and "導入失敗" in js and "再試行" in js

# Backend: file-only endpoints only. resolve/download and the aiohttp
# downloader are gone; upload/files/delete remain.
for endpoint in (
    "/h3-mobile/api/loras/files",
    "/h3-mobile/api/loras/upload",
    "/h3-mobile/api/loras/delete",
    "/h3-mobile/lora-library.js",
):
    assert endpoint in routes, endpoint
for forbidden in (
    "/h3-mobile/api/loras/resolve",
    "/h3-mobile/api/loras/download",
    "import aiohttp",
    "_download_worker",
    "_probe_download",
    "allow_redirects",
    "Authorization",
    "civitai",
    "_validate_public_url",
):
    assert forbidden not in routes, forbidden

assert "_safe_filename" in routes
assert "filename must end with .safetensors" in routes
assert "uploaded file SHA256 mismatch" in routes
assert "os.replace(part, dest)" in routes
assert "_sweep_temp_files" in routes
assert "expected_sha256" in routes  # trusted catalog hash only

assert "from . import lora_routes" in run
assert "printf '\\nfrom .web import lora_routes" not in run
assert '<script src="lora-library.js"></script>' in index

subprocess.run(["node", "--check", str(WEB / "lora-library.js")], check=True)
subprocess.run(["python3", "-m", "py_compile", str(MOBILE / "lora_routes.py")], check=True)

print("Dynamic LoRA library (file-only) validation OK")
