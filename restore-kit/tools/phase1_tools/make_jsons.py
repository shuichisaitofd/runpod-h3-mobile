# Phase 1: build A/B API workflows (T2VA via FL2VA model, no keyframes). Production i2v.json is only read.
import copy, json, sys

PROMPT = json.load(open(sys.argv[1]))  # template T2VA prompt text (json string)
OUT = "/workspace/runpod-slim"


def build(tag, seconds, veda=None, width=1344, height=768, seed=757358688076805):
    frames = max(5, round(seconds * 24))
    frames += (5 - frames % 17) % 17
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "lora": {"class_type": "MiniMaxH3TurboLoRA", "inputs": {"lora_name": "minimax_h3_turbo_v4_step600_ema.safetensors", "strength": 1, "low_vram": False, "model": ["unet", 0]}},
        "sage": {"class_type": "PathchSageAttentionKJ", "inputs": {"model": ["lora", 0], "sage_attention": "auto", "allow_compile": False}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "vae_v": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "vae_a": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "cond": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"prompt": PROMPT, "width": width, "height": height, "length": frames, "clip": ["clip", 0], "vae": ["vae_v", 0]}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "sched": {"class_type": "BasicScheduler", "inputs": {"scheduler": "simple", "steps": 8, "denoise": 1, "model": ["lora", 0]}},
        "sampler": {"class_type": "MiniMaxH3TurboSampler", "inputs": {}},
        "guider": {"class_type": "BasicGuider", "inputs": {"model": ["sage", 0], "conditioning": ["cond", 0]}},
        "sample": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler", 0], "sigmas": ["sched", 0], "latent_image": ["cond", 1]}},
        "dec_v": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae_v", 0]}},
        "dec_a": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["sample", 0], "vae": ["vae_a", 0]}},
        "video": {"class_type": "CreateVideo", "inputs": {"fps": 24, "bit_depth": 8, "images": ["dec_v", 0], "audio": ["dec_a", 0]}},
        "save": {"class_type": "SaveVideo", "inputs": {"filename_prefix": f"phase1_{tag}", "format": "auto", "codec": "auto", "video": ["video", 0]}},
    }
    if veda is not None:
        g["veda"] = {"class_type": "VedaSparseAttention", "inputs": {"model": ["sage", 0], "predictor": "minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors", "generated_sparsity": veda, "reference_sparsity": veda, "full_attention_layers": "", "full_attention_steps": "", "verbose": False}}
        g["guider"]["inputs"]["model"] = ["veda", 0]
    path = f"{OUT}/phase1_{tag}.json"
    json.dump(g, open(path, "w"), ensure_ascii=False, indent=1)
    print(path, frames, "frames")


build("A_t2va_5s", 5)
build("B90_t2va_5s", 5, veda="90%")
