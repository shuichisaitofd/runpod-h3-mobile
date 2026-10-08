# Phase 2: Character-Swap test workflow (API format). Ref2VA + character-swap LoRA 1.0, no Turbo, no Veda.
# Source video (must already be 24 fps) -> cut-free window (START_FRAME, FRAMES) -> <Video 1>; person image -> <Picture 1>.
# No VideoFrameSample: it re-decodes from the start of the file and ignores the Video Slice trim.
import json

SOURCE, PERSON = "phase2_source.mp4", "phase2_person.jpeg"
START_FRAME, FRAMES = 55, 90  # frames 55-144: after the 2.12 s cut, 90 = 17*5+5 (H3 frame grid), 3.75 s
SECONDS = FRAMES / 24
PROMPT = ("Replace only the woman with short black bob hair in the beige trench coat in <Video 1> with the person in <Picture 1>. "
          "Keep the replacement person's identity, hairstyle and outfit from <Picture 1>. "
          "Preserve the source video's camera, framing, background, lighting, objects, and all other people. "
          "In <Video 1>, the woman in the gray sweater reaches out and hugs the target person, the target person hugs her back, then they let go and face each other. "
          "Match the target person's position, scale, pose, and movement throughout the clip. "
          "Do not show the reference image's background.")
g = {
    "10": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "11": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["10", 0], "lora_name": "h3_character_swap_pro4500_1000.safetensors", "strength_model": 1.0}},
    "12": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
    "13": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "14": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "20": {"class_type": "LoadVideo", "inputs": {"file": SOURCE}},
    "21": {"class_type": "Video Slice", "inputs": {"video": ["20", 0], "start_time": START_FRAME / 24, "duration": SECONDS, "strict_duration": False}},
    "23": {"class_type": "GetVideoComponents", "inputs": {"video": ["21", 0]}},
    "24": {"class_type": "LoadImage", "inputs": {"image": PERSON}},
    "30": {"class_type": "ImageFromBatch", "inputs": {"image": ["23", 0], "batch_index": 0, "length": 1}},
    "31": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["30", 0], "upscale_method": "area", "megapixels": 0.5, "resolution_steps": 32}},
    "32": {"class_type": "GetImageSize", "inputs": {"image": ["31", 0]}},
    "33": {"class_type": "PrimitiveFloat", "inputs": {"value": SECONDS}},
    "34": {"class_type": "ComfyMathExpression", "inputs": {"expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17", "values.a": ["33", 0]}},
    "40": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {"prompt": PROMPT, "width": ["32", 0], "height": ["32", 1], "length": ["34", 1],
           "ref_image_size": "match", "clip": ["12", 0], "vae": ["13", 0], "audio_vae": ["14", 0],
           "ref_images.ref_image_0": ["24", 0], "ref_videos.ref_video_0": ["23", 0]}},
    "50": {"class_type": "RandomNoise", "inputs": {"noise_seed": 757358688076805}},
    "51": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
    "52": {"class_type": "BasicScheduler", "inputs": {"model": ["11", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0}},
    "53": {"class_type": "BasicGuider", "inputs": {"model": ["11", 0], "conditioning": ["40", 0]}},
    "54": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["50", 0], "guider": ["53", 0], "sampler": ["51", 0], "sigmas": ["52", 0], "latent_image": ["40", 1]}},
    "60": {"class_type": "VAEDecode", "inputs": {"samples": ["54", 0], "vae": ["13", 0]}},
    "61": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["54", 0], "vae": ["14", 0]}},
    "62": {"class_type": "CreateVideo", "inputs": {"fps": 24, "bit_depth": 8, "images": ["60", 0], "audio": ["61", 0]}},
    "92": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "phase2/phase2_charswap", "format": "auto", "codec": "auto", "video": ["62", 0]}},
}
json.dump(g, open("/workspace/runpod-slim/phase2_charswap_api.json", "w"), ensure_ascii=False, indent=1)
print("written", len(g), "nodes")
