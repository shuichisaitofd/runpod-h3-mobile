FROM runpod/worker-comfyui:main-base

USER root

# The RunPod base image keeps its baked ComfyUI bundle under /opt/comfyui-baked.
# Anything added there is copied into /workspace/runpod-slim/ComfyUI on first boot.
RUN set -eux; \
    cd /opt/comfyui-baked/custom_nodes; \
    git clone --depth 1 https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git; \
    git clone --depth 1 https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git; \
    git clone --depth 1 https://github.com/Saganaki22/ComfyUI-sol-attn.git

# Bake SageAttention into the image. Do not replace Torch/CUDA.
RUN python3.12 -m pip install --no-cache-dir sageattention==2.2.0 --no-build-isolation

# Keep RunPod's normal /start.sh unchanged.
CMD ["/start.sh"]
