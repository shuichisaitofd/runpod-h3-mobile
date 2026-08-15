FROM runpod/worker-comfyui:main-base

USER root

# Add MiniMax H3 acceleration custom nodes to the image itself.
RUN set -eux; \
    cd /workspace/runpod-slim/ComfyUI/custom_nodes; \
    git clone --depth 1 https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git; \
    git clone --depth 1 https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git; \
    git clone --depth 1 https://github.com/Saganaki22/ComfyUI-sol-attn.git

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
