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
ARG SPECTRUM_COMMIT=6a3d14f89cc717abf9815f51d0a599080a3321a6
ARG SOL_COMMIT=930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf
ARG PLAGUEKIND_COMMIT=6ca3037bd16dc143b6d461c67c87a28ca8074063

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

# Pin the H3-specific custom nodes that were verified on the working A6000 Pod.
# KJNodes is intentionally kept from the digest-pinned RunPod base image. That
# exact baked copy is already reproducible via RUNPOD_BASE, while the historical
# local commit observed on the old Pod is no longer fetchable from upstream.
RUN set -eux; \
    cd /opt/comfyui-baked/custom_nodes; \
    test -d ComfyUI-KJNodes; \
    echo "Using KJNodes baked into pinned RunPod base: $(git -C ComfyUI-KJNodes rev-parse HEAD 2>/dev/null || echo baked-copy)"; \
    rm -rf ComfyUI-MiniMax-H3-Turbo ComfyUI-Spectrum-MiniMax-H3 ComfyUI-sol-attn ComfyUI-PlagueKind-Nodes; \
    git clone https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git ComfyUI-MiniMax-H3-Turbo; \
    git -C ComfyUI-MiniMax-H3-Turbo checkout --detach "$TURBO_COMMIT"; \
    git clone https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git ComfyUI-Spectrum-MiniMax-H3; \
    git -C ComfyUI-Spectrum-MiniMax-H3 checkout --detach "$SPECTRUM_COMMIT"; \
    git clone https://github.com/Saganaki22/ComfyUI-sol-attn.git ComfyUI-sol-attn; \
    git -C ComfyUI-sol-attn checkout --detach "$SOL_COMMIT"; \
    git clone https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes.git ComfyUI-PlagueKind-Nodes; \
    git -C ComfyUI-PlagueKind-Nodes checkout --detach "$PLAGUEKIND_COMMIT"

# Apply the verified SLA + Balanced BlockCache wrapper-chain compatibility patch
# at image build time, then fail the build if the SLA node is missing or the
# expected source text has drifted. This prevents a Pod from booting with 05/06
# workflows present but H3SLAAttention unavailable.
RUN python3.12 - <<'PY'
from pathlib import Path

root = Path('/opt/comfyui-baked/custom_nodes/ComfyUI-PlagueKind-Nodes')
sla_node = root / 'ComfyUI-H3-SLA-Attention' / 'sla_node.py'
patch = root / 'ComfyUI-H3-SLA-Attention' / 'sla' / 'patch.py'

assert sla_node.is_file(), f'Missing SLA node: {sla_node}'
assert patch.is_file(), f'Missing SLA patch file: {patch}'

text = patch.read_text()
old = (
    "        out = executor.original(x, timestep, context,\n"
    "                                transformer_options=transformer_options,\n"
    "                                **kwargs)"
)
new = (
    "        out = executor(x, timestep, context,\n"
    "                       transformer_options=transformer_options,\n"
    "                       **kwargs)"
)

if new in text:
    pass
elif old in text:
    patch.write_text(text.replace(old, new, 1))
else:
    raise RuntimeError('PlagueKind SLA patch.py matched neither known patched nor unpatched source')

assert new in patch.read_text(), 'SLA wrapper-chain compatibility patch was not applied'
print('PlagueKind SLA build validation OK:', sla_node)
PY

RUN python3.12 -m py_compile \
    /opt/comfyui-baked/custom_nodes/ComfyUI-PlagueKind-Nodes/ComfyUI-H3-SLA-Attention/sla_node.py \
    /opt/comfyui-baked/custom_nodes/ComfyUI-PlagueKind-Nodes/ComfyUI-H3-SLA-Attention/sla/patch.py

# Install custom-node Python requirements at build time only.
RUN set -eux; \
    for req in \
      /opt/comfyui-baked/custom_nodes/ComfyUI-MiniMax-H3-Turbo/requirements.txt \
      /opt/comfyui-baked/custom_nodes/ComfyUI-Spectrum-MiniMax-H3/requirements.txt \
      /opt/comfyui-baked/custom_nodes/ComfyUI-sol-attn/requirements.txt \
      /opt/comfyui-baked/custom_nodes/ComfyUI-PlagueKind-Nodes/requirements.txt; do \
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
COPY h3-mobile/extra_routes.py /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/extra_routes.py
COPY h3-mobile/web/ /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/web/
COPY h3-mobile/api_workflows/ /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/api_workflows/
COPY workflows/ /opt/comfyui-baked/user/default/workflows/

# Ref2VA Ultra Safe BlockCache accelerator (ApplyH3Ref2VAUltraSafeBlockCache),
# required by the Ref2VA 04 workflow (Node 147). nodes.py is the verified
# original recovered from h3-accelerator-source/verified.part00-06
# (SHA256 6334f6102be897c512452e6113a6243e87824423d04e108dd2474ae382dc6f8a,
# 40012 bytes) and must be baked in unmodified.
RUN mkdir -p /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator
COPY h3-accelerator/__init__.py /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator/__init__.py
COPY h3-accelerator/nodes.py /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator/nodes.py

# Build-time guard: fail the build itself (not just ComfyUI boot) if the
# accelerator file fails to compile, its NODE_CLASS_MAPPINGS does not expose
# ApplyH3Ref2VAUltraSafeBlockCache, or that class name drifts from what
# ref2va_04.json (Node 147) actually references.
RUN sha256sum /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator/nodes.py \
    && python3.12 -m py_compile /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator/nodes.py \
    && python3.12 - <<'PY'
import ast, json

nodes_path = "/opt/comfyui-baked/custom_nodes/ComfyUI-H3-Ref2VA-Accelerator/nodes.py"
with open(nodes_path) as f:
    tree = ast.parse(f.read(), filename=nodes_path)

mapping_keys = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS" for t in node.targets
    ):
        mapping_keys = [k.value for k in node.value.keys]
        break

assert mapping_keys is not None, "NODE_CLASS_MAPPINGS not found in nodes.py"
assert "ApplyH3Ref2VAUltraSafeBlockCache" in mapping_keys, mapping_keys

wf_path = "/opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/api_workflows/ref2va_04.json"
with open(wf_path) as f:
    wf = json.load(f)
class_type = wf.get("147", {}).get("class_type")
assert class_type == "ApplyH3Ref2VAUltraSafeBlockCache", (
    f"ref2va_04.json Node 147 class_type={class_type!r} does not match accelerator node"
)

print("Accelerator build validation OK:", class_type, "registered and matches ref2va_04.json Node 147")
PY

# Runtime guard: fail fast on an incompatible RunPod host before ComfyUI starts.
COPY run.sh /run-h3.sh
RUN chmod +x /run-h3.sh

ENTRYPOINT ["/run-h3.sh"]
