# Phase S test 2: phase2_charswap_api.json + official Ref2VA Turbo 8-step LoRA (after the swap LoRA),
# MiniMaxH3SigmaShift, 8 steps res_multistep/simple, no Veda. Usage: make_speed_T8.py SHIFT_VIDEO SHIFT_AUDIO [SAMPLER]
import json, sys

sv, sa = float(sys.argv[1]), float(sys.argv[2])
sampler = sys.argv[3] if len(sys.argv) > 3 else "res_multistep"
g = json.load(open("/workspace/runpod-slim/phase2_charswap_api.json"))
assert g["53"]["inputs"]["model"] == ["11", 0] and g["52"]["inputs"]["model"] == ["11", 0]
g["12a"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["11", 0],
            "lora_name": "minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors", "strength_model": 1.0}}
g["12b"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["12a", 0], "shift_video": sv, "shift_audio": sa}}
g["52"]["inputs"]["model"] = ["12b", 0]
g["52"]["inputs"]["steps"] = 8
g["53"]["inputs"]["model"] = ["12b", 0]
g["51"]["inputs"]["sampler_name"] = sampler
tag = f"T8_s{sv:g}" + ("" if sampler == "res_multistep" else f"_{sampler}")
g["92"]["inputs"]["filename_prefix"] = f"speed/speed_{tag}"
out = f"/workspace/runpod-slim/speed_{tag}.json"
json.dump(g, open(out, "w"), ensure_ascii=False, indent=1)
print(out)
