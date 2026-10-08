# Phase S test 1: phase2_charswap_api.json + Veda (generated 90%, reference 0%) between the swap LoRA and the guider.
import json

g = json.load(open("/workspace/runpod-slim/phase2_charswap_api.json"))
assert g["53"]["inputs"]["model"] == ["11", 0]
g["70"] = {"class_type": "VedaSparseAttention", "inputs": {"model": ["11", 0],
           "predictor": "minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors",
           "generated_sparsity": "90%", "reference_sparsity": "0%",
           "full_attention_layers": "", "full_attention_steps": "", "verbose": False}}
g["53"]["inputs"]["model"] = ["70", 0]
g["92"]["inputs"]["filename_prefix"] = "speed/speed_V90_ref0"
json.dump(g, open("/workspace/runpod-slim/speed_V90_ref0.json", "w"), ensure_ascii=False, indent=1)
