# H3 Mobile LoRA Test Status

- State: RUNNING
- Branch: `codex/h3-lora-mobile-test`
- Base SHA: `04f1d4f2827f055a79ac88ccc0c9f35a81996ab2`
- Pod real-device test: NOT STARTED

## Workflow model paths

- Ref2VA 04: Ref2VA UNET → HMNSFW AIO V2.5 (0.40) → H3 Motion Booster V2 (0.50) → Sol-Attn → Balanced BlockCache
- Ref2VA 05: Ref2VA UNET → HMNSFW AIO V2.5 (0.40) → H3 Motion Booster V2 (0.50) → SLA → Balanced BlockCache
- Ref2VA 06 fast: Ref2VA UNET → HMNSFW AIO V2.5 (0.40) → H3 Motion Booster V2 (0.50) → SLA → Spectrum fast
- Ref2VA 06 stable: Ref2VA UNET → HMNSFW AIO V2.5 (0.40) → H3 Motion Booster V2 (0.50) → SLA → Spectrum stable

## Sampling

| Workflow | Sampler | Scheduler | Steps | Shift | CFG |
| --- | --- | --- | ---: | --- | --- |
| Ref2VA 04 | euler | simple | 12 | N/A | N/A |
| Ref2VA 05 | euler | simple | 12 | N/A | N/A |
| Ref2VA 06 fast | euler | simple | 12 | N/A | N/A |
| Ref2VA 06 stable | euler | simple | 12 | N/A | N/A |

No shift input exists in these workflows. Their `BasicGuider` nodes have no CFG input, so neither value was invented.

## LoRA downloads

| Filename | Strength | Download URL | SHA256 |
| --- | ---: | --- | --- |
| `HMNSFW-AIO-V2.5.safetensors` | 0.40 | `https://huggingface.co/Hearmeman/minimax-h3-loras/resolve/main/HMNSFW-AIO-V2.5.safetensors` | `a07732a84fd733085eb5d910f602f918fa7a3658117116927e4329f5951a9d2d` |
| `H3_Motion_BoosterV2.safetensors` | 0.50 | `https://huggingface.co/bilmemne13/1/resolve/main/H3_Motion_BoosterV2.safetensors` | `f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3` |

Files are downloaded to `ComfyUI/models/loras/`. Redirects and existing `.part` resume are supported. SHA256 is checked before `.part` is renamed to the formal filename; existing formal files are checked before reuse.

## Prompt handling

Single and batch Ref2VA generation prepend `dynv2. ` exactly once. A prompt already beginning with `dynv2` or `dynv2.` is left unchanged. I2V prompts are unchanged.

## Tests and image

- Offline tests: PASS (`validate_lora_mobile_test.py`, `validate_ref2va06.py`, `validate_runtime_billing.py`)
- GitHub Actions: NOT STARTED (Hugging Face mirror rebuild)
- Test image: `ghcr.io/shuichisaitofd/runpod-h3-mobile:h3-lora-test`
- Production tags `h3-cu130-latest` and `h3-cu130-v4`: unchanged
