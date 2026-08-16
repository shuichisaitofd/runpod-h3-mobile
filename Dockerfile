# Reproducible MiniMax H3 image for RunPod / RTX A6000 (SM86)
# Base image is pinned by digest so upstream changes cannot silently alter the runtime.
ARG RUNPOD_BASE=runpod/comfyui:1.4.5-cuda13.0@sha256:976ebfd8fe76d2899bbe31fbeb56970d2a409763aadff81377578842e27fe997

# -----------------------------------------------------------------------------
# Stage 1: build SageAttention 2.2.0 wheel for Python 3.12 / Torch cu130 / SM86
# -----------------------------------------------------------------------------
FROM ${RUNPOD_BASE} AS sage-builder

USER root

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      cuda-compiler-13-0 \
      libcublas-dev-13-0 \
      libcusolver-dev-13-0 \
      libcusparse-dev-13-0 \
      ninja-build \
      git \
    && rm -rf /var/lib/apt/lists/*

ENV CUDA_HOME=/usr/local/cuda-13.0
ENV PATH=/usr/local/cuda-13.0/bin:${PATH}
ENV TORCH_CUDA_ARCH_LIST=8.6
ENV MAX_JOBS=1

RUN git clone --depth 1 --branch v2.2.0 https://github.com/thu-ml/SageAttention.git /tmp/SageAttention \
    && cd /tmp/SageAttention \
    && PIP_CONSTRAINT= python3.12 -m pip wheel . --no-build-isolation --no-deps -w /wheelhouse

# -----------------------------------------------------------------------------
# Stage 2: final runtime image
# -----------------------------------------------------------------------------
FROM ${RUNPOD_BASE}

USER root

ARG TURBO_COMMIT=4274783a23afcfdbea3b4876cb79effd6c510785
ARG KJNODES_COMMIT=d19ce9078f03cc66a462efc082defd30aef16d02
ARG SPECTRUM_COMMIT=6a3d14f89cc717abf9815f51d0a599080a3321a6
ARG SOL_COMMIT=930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf

# SageAttention is compiled once during image build, not on every Pod boot.
COPY --from=sage-builder /wheelhouse/ /tmp/wheelhouse/
RUN PIP_CONSTRAINT= python3.12 -m pip install --no-cache-dir /tmp/wheelhouse/sageattention-*.whl \
    && rm -rf /tmp/wheelhouse \
    && cd /opt/comfyui-baked \
    && python3.12 - <<'PY'
import torch
from importlib.metadata import version
from sageattention import sageattn
assert torch.__version__ == "2.10.0+cu130", torch.__version__
assert torch.version.cuda == "13.0", torch.version.cuda
assert version("sageattention") == "2.2.0", version("sageattention")
print("Build validation OK:", torch.__version__, torch.version.cuda, version("sageattention"))
PY

# Pin the custom nodes that were verified on the working A6000 Pod.
RUN set -eux; \
    cd /opt/comfyui-baked/custom_nodes; \
    rm -rf ComfyUI-MiniMax-H3-Turbo ComfyUI-Spectrum-MiniMax-H3 ComfyUI-sol-attn; \
    git clone https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git ComfyUI-MiniMax-H3-Turbo; \
    git -C ComfyUI-MiniMax-H3-Turbo checkout --detach "$TURBO_COMMIT"; \
    git clone https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git ComfyUI-Spectrum-MiniMax-H3; \
    git -C ComfyUI-Spectrum-MiniMax-H3 checkout --detach "$SPECTRUM_COMMIT"; \
    git clone https://github.com/Saganaki22/ComfyUI-sol-attn.git ComfyUI-sol-attn; \
    git -C ComfyUI-sol-attn checkout --detach "$SOL_COMMIT"; \
    if [ -d ComfyUI-KJNodes/.git ]; then \
      git -C ComfyUI-KJNodes fetch origin "$KJNODES_COMMIT" || true; \
      git -C ComfyUI-KJNodes checkout --detach -f "$KJNODES_COMMIT"; \
    else \
      git clone https://github.com/kijai/ComfyUI-KJNodes.git ComfyUI-KJNodes; \
      git -C ComfyUI-KJNodes checkout --detach "$KJNODES_COMMIT"; \
    fi

# Install custom-node Python requirements at build time only.
RUN set -eux; \
    for req in \
      /opt/comfyui-baked/custom_nodes/ComfyUI-MiniMax-H3-Turbo/requirements.txt \
      /opt/comfyui-baked/custom_nodes/ComfyUI-Spectrum-MiniMax-H3/requirements.txt \
      /opt/comfyui-baked/custom_nodes/ComfyUI-sol-attn/requirements.txt; do \
        if [ -f "$req" ]; then \
          PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt python3.12 -m pip install --no-cache-dir -r "$req"; \
        fi; \
    done

# H3 Mobile and known-good workflows are baked into the ComfyUI copy that RunPod
# places in /workspace on first boot. Models remain on-demand and are NOT baked in.
RUN mkdir -p \
    /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/web \
    /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/api_workflows \
    /opt/comfyui-baked/user/default/workflows

COPY h3-mobile/__init__.py /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/__init__.py
COPY h3-mobile/web/ /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/web/
COPY h3-mobile/api_workflows/ /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/api_workflows/
COPY workflows/ /opt/comfyui-baked/user/default/workflows/

# Runtime guard: fail fast on an incompatible RunPod host before ComfyUI starts.
COPY run.sh /run-h3.sh
RUN chmod +x /run-h3.sh

ENTRYPOINT ["/run-h3.sh"]
