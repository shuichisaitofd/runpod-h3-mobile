# Build api_workflows/i2v.json.veda90: production i2v.json plus Veda (90%/90%) between Sage and the guider.
import json

D = "/workspace/runpod-slim/ComfyUI/custom_nodes/ComfyUI-H3-Mobile/api_workflows"
g = json.load(open(f"{D}/i2v.json"))
assert g["105:16"]["inputs"]["model"] == ["105:123", 0] and "105:200" not in g
g["105:200"] = {"inputs": {"model": ["105:123", 0], "predictor": "minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors",
                           "generated_sparsity": "90%", "reference_sparsity": "90%", "full_attention_layers": "",
                           "full_attention_steps": "", "verbose": False},
                "class_type": "VedaSparseAttention", "_meta": {"title": "Veda Sparse Attention (MiniMax H3)"}}
g["105:16"]["inputs"]["model"] = ["105:200", 0]
json.dump(g, open(f"{D}/i2v.json.veda90", "w"), ensure_ascii=False, indent=2)
