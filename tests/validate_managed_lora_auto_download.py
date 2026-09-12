import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "h3-mobile" / "lora_routes.py"
WEB = ROOT / "h3-mobile" / "web" / "lora-library.js"
text = ROUTES.read_text()
js = WEB.read_text()
tree = ast.parse(text)

assignments = {}
functions = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        functions[node.name] = node

expected = {
    "BJ_v3.safetensors": "fbb93a67b429c79145c95598e9ac38388ad49d6df1c09c96cf989cce99277d53",
    "deepthroat_v02.safetensors": "1fd239662f6290255b0bb3a220764fb53aab2859378f7fd3024030c1e1991cb2",
    "Finger_BEAN_v1.safetensors": "914e3ecb0b515ad1a40c0185a8d23a34f87a1ced370db8bfb0ed3b5845dbf0a2",
    "HMCumshot_V2.safetensors": "1a5b7948bb97f27737e62c3dd5497a3afb77517f230787f45e45c7d8fe3dc24d",
    "Motion_FL2VA_v2.safetensors": "f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3",
    "Mystic_FL2VA_v4.safetensors": "fc3e856d14c6c19557c888f48662d591e4794e281233ec0d987be5003068afba",
    "Nipple_v2.safetensors": "7c30c92178e01e33cfbc4684a7b3fb1b71368293443b2941a5b889db3fbd3b18",
    "Panties_v1.safetensors": "f2bf0b4fc7d0ab6f3f91300b0a810dcd76e61f6e8fe39f7dbbd480245987447f",
    "Passionate_Kiss.safetensors": "71b3435525ef8907d35f12cfb9cb81ee9931761ecb27039fc6919b55dd8cda75",
    "Penis_HM_v2.safetensors": "017dd1adddc1be3ec0605dd2e7de97138eb2c6c6ba24be402cf47f103ac1f1b3",
    "Pussy_HM_v1.safetensors": "373c3cad3bf27047fdd754fe111443d97e70e3108a8829f2ec63c48832466eb3",
    "Squirt_HM_v1.safetensors": "e7f48b0e9a9bc6252c29db963258fe5d70321c4bc336bc5e6041938c68ee5791",
    "Squirt_HM_v2.safetensors.safetensors": "f0e4bfbe5baebe972880d2250a227e2f475aa8c18d6d01ed897288d9741659d2",
}

assert ast.literal_eval(assignments["MANAGED_LORA_SPECS"]) == expected
assert "GITHUB_TOKEN_ENV" not in assignments
assert "repos/shuichisaitofd/h3-lora-assets/" in text
assert "releases/tags/h3-loras-v1" in text
assert "H3_LORA_GITHUB_TOKEN" not in text
assert '"Authorization"' not in text
assert "auth_required" not in text

download_source = ast.get_source_segment(
    text, functions["_download_managed_lora"]
)
assert '"application/octet-stream"' in download_source
assert 'headers["Range"]' in download_source
assert "response.status == 206" in download_source
assert "await _verify_managed_file" in download_source
assert "os.replace(part, dest)" in download_source

sync_source = ast.get_source_segment(text, functions["_sync_managed_loras"])
assert "asyncio.Semaphore(2)" in sync_source
assert "GITHUB_RELEASE_API" in sync_source
assert "Authorization" not in sync_source

assert (
    "PromptServer.instance.app.on_startup.append("
    "_auto_sync_managed_loras_on_startup)"
) in text
assert '@routes.post("/h3-mobile/api/loras/managed/prepare")' in text
assert "lastManagedDownloads" in js
assert "hasActiveManagedDownload()" in js
assert "GitHubから自動取得中" in js
assert "RunPod Secretの設定が必要です" not in js
assert "auth_required" not in js

# Managed downloads are fixed server configuration. The browser upload route
# must remain file-only and accept no URL/Civitai source.
upload_source = ast.get_source_segment(text, functions["h3_mobile_lora_upload"])
assert "http://" not in upload_source
assert "https://" not in upload_source
assert "civitai" not in upload_source.lower()

print("managed GitHub LoRA auto-download validation passed")
