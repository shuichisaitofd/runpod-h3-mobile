import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "h3-mobile" / "api_workflows"
WEB = ROOT / "h3-mobile" / "web"


def load(name):
    return json.loads((API / name).read_text())


def check_variant(name, degree, warmup, bootstrap):
    wf = load(name)
    assert wf["146"]["class_type"] == "H3SLAAttention", name
    assert wf["148"]["class_type"] == "SpectrumApplyMiniMaxH3", name
    spec = wf["148"]["inputs"]
    assert spec["model"] == ["146", 0], name
    assert spec["degree"] == degree, (name, spec["degree"])
    assert spec["warmup_steps"] == warmup, (name, spec["warmup_steps"])
    assert spec["bootstrap_first_forecast"] is bootstrap, (name, spec["bootstrap_first_forecast"])
    assert spec["offline_smoothing_replay"] is False, name
    assert wf["124"]["inputs"]["model"] == ["148", 0], name
    assert wf["126"]["inputs"]["model"] == ["148", 0], name


check_variant("ref2va_06_fast.json", degree=1, warmup=1, bootstrap=True)
check_variant("ref2va_06_stable.json", degree=4, warmup=5, bootstrap=False)

# Base API workflows intentionally carry ref 1/2 only. The browser adds ref 3/4
# dynamically at queue time for all Ref2VA variants, including 06 fast/stable.
app = (WEB / "app.js").read_text()
assert "ref_images.ref_image_2" in app
assert "ref_images.ref_image_3" in app
assert "h3mobile_ref3" in app
assert "h3mobile_ref4" in app
assert "ref2va_06_fast" in app
assert "ref2va_06_stable" in app

batch = (WEB / "batch-v2.js").read_text()
assert "const REF_SLOTS=4" in batch
assert "ref_images.ref_image_2" in batch
assert "ref_images.ref_image_3" in batch
assert "h3mobile_ref3" in batch
assert "h3mobile_ref4" in batch
assert "ref2va_06_fast" in batch
assert "ref2va_06_stable" in batch

index = (WEB / "index.html").read_text()
for slot in ("ref0", "ref1", "ref2", "ref3"):
    assert f'id="{slot}"' in index, slot

print("Ref2VA 06 validation OK: fast/stable + SLA/Spectrum + 1-4 refs (single and batch)")
