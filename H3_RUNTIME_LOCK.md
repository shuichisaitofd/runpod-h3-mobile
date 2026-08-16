# H3 Runtime Lock

Known-good runtime captured from the working RTX A6000 Pod on 2026-08-16.

## Base runtime

- GPU: NVIDIA RTX A6000
- Compute capability: 8.6 (SM86)
- PyTorch: 2.10.0+cu130
- torch.version.cuda: 13.0
- CUDA compiler/toolkit: 13.0
- SageAttention: 2.2.0 (built from thu-ml/SageAttention tag v2.2.0)

## Pinned custom nodes

- ComfyUI-MiniMax-H3-Turbo: `4274783a23afcfdbea3b4876cb79effd6c510785`
- ComfyUI-KJNodes: `d19ce9078f03cc66a462efc082defd30aef16d02`
- ComfyUI-Spectrum-MiniMax-H3: `6a3d14f89cc717abf9815f51d0a599080a3321a6`
- ComfyUI-sol-attn: `930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf`

## Acceleration recipes

- I2V / FL2VA: Turbo v4 + SageAttention, Turbo sampler, 4 steps.
- Ref2VA: Spectrum + Sol-Attn. Sampling steps, aspect ratio, duration, seed and ref_image_size are user-adjustable in H3 Mobile.

## CUDA 13.0 build dependencies used for SageAttention

- `cuda-compiler-13-0`
- `libcusparse-dev-13-0`
- `libcublas-dev-13-0`
- `libcusolver-dev-13-0`
- `ninja-build`

## Runtime verification targets

Startup should report:

- `pytorch version: 2.10.0+cu130`
- `comfy_kitchen backend cuda` with `available=True` and `disabled=False`
- SageAttention import succeeds

Ref2VA execution should show Sol-Attn patch activation. I2V should run without `No module named 'sageattention'`.
