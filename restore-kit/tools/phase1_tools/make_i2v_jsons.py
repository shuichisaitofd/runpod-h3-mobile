# Phase 1: I2V A/B from a copy of production i2v.json (production file is only read).
import copy, json

SRC = "/workspace/runpod-slim/ComfyUI/custom_nodes/ComfyUI-H3-Mobile/api_workflows/i2v.json"
PROMPT = ("Live-action video, plain white studio background. The shocked man in the dark suit gasps, "
          "throws both hands up beside his face, then takes a big step back, waves both arms wildly "
          "and points off to the left while shouting. Natural body movement, steady camera. "
          "Audio: a loud gasp, then his surprised shouting voice.")
base = json.load(open(SRC))
base["114"]["inputs"]["image"] = "danda0I9A4330_TP_V.jpg"
base["119"]["inputs"]["megapixels"] = 0.6
base["105:111"]["inputs"]["value"] = 5
base["105:9"]["inputs"]["steps"] = 8
base["105:104"]["inputs"]["prompt"] = PROMPT
base["105:15"]["inputs"]["noise_seed"] = 757358688076805

a = copy.deepcopy(base)
a["92"]["inputs"]["filename_prefix"] = "phase1_I2V_A"
b = copy.deepcopy(base)
b["92"]["inputs"]["filename_prefix"] = "phase1_I2V_B90"
b["105:200"] = {"class_type": "VedaSparseAttention", "inputs": {"model": ["105:123", 0], "predictor": "minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors", "generated_sparsity": "90%", "reference_sparsity": "90%", "full_attention_layers": "", "full_attention_steps": "", "verbose": False}}
b["105:16"]["inputs"]["model"] = ["105:200", 0]
for name, g in (("A", a), ("B90", b)):
    json.dump(g, open(f"/workspace/runpod-slim/phase1_I2V_{name}.json", "w"), ensure_ascii=False, indent=1)
