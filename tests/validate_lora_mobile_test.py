import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "h3-mobile" / "api_workflows"
WEB = ROOT / "h3-mobile" / "web"
INIT_PATH = ROOT / "h3-mobile" / "__init__.py"

VARIANTS = {
    "ref2va_04.json": ("146", "147"),
    "ref2va_05.json": ("146", "147"),
    "ref2va_06_fast.json": ("146", "148"),
    "ref2va_06_stable.json": ("146", "148"),
}
AIO = "HMNSFW-AIO-V2.5.safetensors"
BOOSTER = "H3_Motion_BoosterV2.safetensors"
UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"


def load(name):
    return json.loads((API / name).read_text())


def contains_input_key(value, wanted):
    if isinstance(value, dict):
        return any(key.lower() == wanted or contains_input_key(child, wanted) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_input_key(child, wanted) for child in value)
    return False


for name, (attention_id, final_accelerator_id) in VARIANTS.items():
    path = API / name
    raw = path.read_text()
    wf = json.loads(raw)  # Explicitly validate that every shipped workflow parses.

    assert wf["127"]["class_type"] == "UNETLoader", name
    assert wf["127"]["inputs"]["unet_name"] == UNET, name
    assert wf["136"]["class_type"] == "MiniMaxH3ReferenceToVideo", name

    aio = wf["149"]
    booster = wf["150"]
    assert aio["class_type"] == "LoraLoaderModelOnly", name
    assert booster["class_type"] == "LoraLoaderModelOnly", name
    assert aio["inputs"] == {"model": ["127", 0], "lora_name": AIO, "strength_model": 0.4}, name
    assert booster["inputs"] == {"model": ["149", 0], "lora_name": BOOSTER, "strength_model": 0.5}, name

    # UNET -> AIO -> Booster -> attention accelerator -> cache/Spectrum.
    assert wf[attention_id]["inputs"]["model"] == ["150", 0], name
    if final_accelerator_id != attention_id:
        assert wf[final_accelerator_id]["inputs"]["model"] == [attention_id, 0], name
    assert wf["124"]["inputs"]["model"] == [final_accelerator_id, 0], name
    assert wf["126"]["inputs"]["model"] == [final_accelerator_id, 0], name

    assert wf["123"]["inputs"]["sampler_name"] == "euler", name
    assert wf["124"]["inputs"]["scheduler"] == "simple", name
    assert wf["124"]["inputs"]["steps"] == 12, name
    assert wf["124"]["inputs"]["denoise"] == 1, name

    ref_inputs = wf["136"]["inputs"]
    assert ref_inputs["ref_images.ref_image_0"] == ["137", 0], name
    assert ref_inputs["ref_images.ref_image_1"] == ["139", 0], name
    assert wf["137"]["class_type"] == "LoadImage", name
    assert wf["139"]["class_type"] == "LoadImage", name
    assert "beanflk" not in raw.lower(), name

    # These graphs expose neither shift nor CFG; the test edition must not
    # invent unsupported fields or nodes.
    assert not contains_input_key(wf, "shift"), name
    assert "cfg" not in wf["126"]["inputs"], name


# Ref2VA 03 is explicitly outside the LoRA workflow change.
ref03 = API / "ref2va_03.json"
assert hashlib.sha256(ref03.read_bytes()).hexdigest() == "7b040e3608daefc9e0c68b4c39ab650dcc9e20e62407e072db79677225cf95d0"

init = INIT_PATH.read_text()
lora_library = (WEB / "lora-library.js").read_text()
for retired_registration_data in (
    "https://huggingface.co/Hearmeman/minimax-h3-loras/resolve/main/HMNSFW-AIO-V2.5.safetensors",
    "https://huggingface.co/bilmemne13/1/resolve/main/H3_Motion_BoosterV2.safetensors",
    "a07732a84fd733085eb5d910f602f918fa7a3658117116927e4329f5951a9d2d",
    "f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3",
):
    assert retired_registration_data not in init, retired_registration_data
    assert retired_registration_data not in lora_library, retired_registration_data
assert "const DEFAULTS=" not in lora_library
assert "h3MobileLoraCatalogVersion" in lora_library
assert "default-12-v1" in lora_library
assert "civarchive.com" not in init
assert '"ref2va_aio_lora"' not in init
assert '"ref2va_motion_booster_lora"' not in init
assert '"turbo_lora"' in init
assert "minimax_h3_turbo_v4_step600_ema.safetensors" in init
assert "allow_redirects=True" in init
assert "await asyncio.to_thread(_verify_sha256, key, tmp)" in init
assert init.index("await asyncio.to_thread(_verify_sha256, key, tmp)") < init.index("os.replace(tmp, dest)")
assert 'status="sha256_error"' in init

app = (WEB / "app.js").read_text()
batch = (WEB / "batch-v2.js").read_text()
match = re.search(r"function ensureRef2VADynv2\(prompt\)\{[^\n]+\}", app)
assert match, "dynv2 helper missing from app.js"
assert "const prompt=isRef&&shouldAddRef2VADynv2(refCtx)?ensureRef2VADynv2(inputPrompt):inputPrompt" in app
assert "const prompt=runMode==='ref2va'&&shouldAddRef2VADynv2(refCtx)?ensureRef2VADynv2(inputPrompt):inputPrompt" in batch
assert "wf['105:104'].inputs.prompt=prompt" in app  # I2V receives the unmodified ternary branch.
assert "wf['105:104'].inputs.prompt=cfg.prompt" in batch
assert "sha256_error:'SHA256エラー'" in app

# Execute the exact browser helper in Node to prove prefixing and de-duplication.
node_test = match.group(0) + """
const cases = [
  ['a prompt', 'dynv2. a prompt'],
  ['dynv2 a prompt', 'dynv2 a prompt'],
  ['dynv2. a prompt', 'dynv2. a prompt'],
  ['DYNV2. a prompt', 'DYNV2. a prompt'],
];
for (const [input, expected] of cases) {
  if (ensureRef2VADynv2(input) !== expected) process.exit(1);
}
"""
subprocess.run(["node", "-e", node_test], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("LoRA mobile test validation OK: workflows, downloads, dynv2, UI status, and git safety")
