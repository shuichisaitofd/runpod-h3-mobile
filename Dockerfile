FROM runpod/worker-comfyui:main-base

USER root

# Store our extra H3 custom nodes separately from RunPod's own baked ComfyUI bundle.
RUN set -eux; \
    mkdir -p /opt/h3-custom-nodes; \
    cd /opt/h3-custom-nodes; \
    git clone --depth 1 https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git; \
    git clone --depth 1 https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git; \
    git clone --depth 1 https://github.com/Saganaki22/ComfyUI-sol-attn.git

# SageAttention is installed system-wide; RunPod's venv uses --system-site-packages.
# Do not replace Torch/CUDA.
RUN python3.12 -m pip install --no-cache-dir sageattention==2.2.0 --no-build-isolation

COPY run.sh /run.sh
RUN chmod +x /run.sh

# Use our wrapper, which injects the extra nodes after RunPod has created ComfyUI,
# then hands control back to RunPod's normal startup logic.
ENTRYPOINT ["/run.sh"]
