import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "h3-mobile" / "web"

js = (WEB / "lora-library.js").read_text()
routes = (WEB / "lora_routes.py").read_text()
run = (ROOT / "run.sh").read_text()
index = (WEB / "index.html").read_text()

for filename in (
    "HMNSFW-AIO-V2.5.safetensors",
    "H3_Motion_BoosterV2.safetensors",
    "PenisV2_minimax-h3_epoch60.safetensors",
):
    assert filename in js, filename

assert "h3MobileLoraLibraryV1" in js
assert "h3MobileLoraSelectionsV1" in js
assert "localStorage.setItem" in js
assert "type=\"number\" step=\"0.01\" inputmode=\"decimal\"" in js
assert "m-url" in js and "ダウンロードURL" in js
assert "URLを登録" in js
assert "ファイルから登録" in js
assert "PodへDL" in js
assert "登録削除" in js
assert "設定を書き出す" in js and "設定を読み込む" in js
assert "LoraLoaderModelOnly" in js
assert "stripManaged" in js
assert "applyLoras" in js
assert "LoRA未導入" in js

for endpoint in (
    '/h3-mobile/api/loras/files',
    '/h3-mobile/api/loras/download',
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

assert "from .web import lora_routes" in run
assert '<script src="lora-library.js"></script>' in index

subprocess.run(["node", "--check", str(WEB / "lora-library.js")], check=True)
subprocess.run(["python3", "-m", "py_compile", str(WEB / "lora_routes.py")], check=True)

print("Dynamic LoRA library validation OK")
