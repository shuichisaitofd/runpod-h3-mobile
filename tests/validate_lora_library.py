import json
import re
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
    "HMNSFW-AIO-V2.5.safetensors",
    "H3_Motion_BoosterV2.safetensors",
    "PenisV2_minimax-h3_epoch60.safetensors",
):
    assert filename in js, filename

assert "h3MobileLoraLibraryV1" in js
assert "loraSelections" in js
assert "localStorage.setItem" in js
assert "type=\"number\" step=\"0.01\" inputmode=\"decimal\"" in js
assert "m-url" in js and 'id="loraNewUrl"' in js
assert "URLから追加" in js
assert "ファイルから追加" in js
assert "PodへDL" in js
assert "登録削除" in js
assert "設定バックアップ" in js and "設定を復元" in js
assert "LoraLoaderModelOnly" in js
assert "stripManaged" in js
assert "applyLoras" in js
assert "LoRA未導入" in js

for endpoint in (
    '/h3-mobile/api/loras/files',
    '/h3-mobile/api/loras/download',
    '/h3-mobile/api/loras/resolve',
    '/h3-mobile/api/loras/upload',
    '/h3-mobile/api/loras/delete',
    '/h3-mobile/lora-library.js',
):
    assert endpoint in routes, endpoint

assert "_safe_filename" in routes
assert "filename must end with .safetensors" in routes
assert "SHA256 mismatch" in routes
assert "os.replace(part, dest)" in routes
assert "allow_redirects=False" in routes
assert "_validate_public_url" in routes

assert "from . import lora_routes" in run
assert "printf '\\nfrom .web import lora_routes" not in run
assert '<script src="lora-library.js"></script>' in index

subprocess.run(["node", "--check", str(WEB / "lora-library.js")], check=True)
subprocess.run(["python3", "-m", "py_compile", str(MOBILE / "lora_routes.py")], check=True)

print("Dynamic LoRA library validation OK")
