#!/usr/bin/env bash
set -uo pipefail

TMP_START="/tmp/start-h3-mobile.sh"

# Keep RunPod's official startup flow intact. If patch preparation fails,
# fall back to the untouched official /start.sh instead of crash-looping.
if ! cp /start.sh "$TMP_START"; then
    echo "[ERROR] Could not copy /start.sh. Starting standard RunPod startup."
    exec /start.sh
fi

if ! python3 - <<'PY'
from pathlib import Path

p = Path("/tmp/start-h3-mobile.sh")
text = p.read_text()

# Insert only after ComfyUI exists and its venv has been activated.
marker = "# Warm up pip so ComfyUI-Manager"
if marker not in text:
    raise SystemExit("RunPod start.sh structure changed: insertion point not found")

block = r'''
echo "============================================="
echo "  H3 mobile auto setup"
echo "============================================="

CUSTOM="$COMFYUI_DIR/custom_nodes"
WORKFLOWS="$COMFYUI_DIR/user/default/workflows"
mkdir -p "$CUSTOM" "$WORKFLOWS"

# Clone into a temporary directory first. This avoids treating a partial clone
# from a previous failed download as a valid installation.
install_node() {
    local name="$1"
    local url="$2"
    local path="$CUSTOM/$name"
    local tmp="${path}.tmp"

    if [ -d "$path/.git" ] && git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "OK: $name already exists"
        return 0
    fi

    echo "Installing $name..."
    rm -rf "$path" "$tmp"
    if git clone --depth 1 "$url" "$tmp"; then
        mv "$tmp" "$path"
        echo "OK: $name installed"
        return 0
    fi

    rm -rf "$tmp"
    echo "[ERROR] $name clone failed. Continuing startup."
    return 1
}

# 1) Turbo v4
install_node \
  "ComfyUI-MiniMax-H3-Turbo" \
  "https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git" || true

# KJNodes is baked into the RunPod ComfyUI image. Do not reinstall/overwrite it.
if [ -d "$CUSTOM/ComfyUI-KJNodes" ]; then
    echo "OK: ComfyUI-KJNodes present"
else
    echo "[ERROR] ComfyUI-KJNodes is missing. Continuing startup without modifying it."
fi

# 2) SageAttention
# Use the same source-build path that has already worked in this RunPod H3 setup.
# Select CUDA dev libraries to match the active PyTorch CUDA build (12.8 or 13.0).
# Do not use PyPI sageattention==2.2.0 here.
if python -c "from sageattention import sageattn" >/dev/null 2>&1; then
    echo "OK: SageAttention already installed"
else
    echo "Installing SageAttention from official source..."
    SAGE_CAN_BUILD=1

    CUDA_DEV_SUFFIX="$(python - <<'PY2'
import torch
v = torch.version.cuda or ""
parts = v.split(".")
if len(parts) >= 2:
    print(f"{parts[0]}-{parts[1]}")
PY2
)"

    case "$CUDA_DEV_SUFFIX" in
        12-8|13-0)
            echo "SageAttention CUDA toolkit target: $CUDA_DEV_SUFFIX"
            ;;
        *)
            echo "[ERROR] Unsupported/unknown PyTorch CUDA version: ${CUDA_DEV_SUFFIX:-none}; SageAttention build skipped."
            SAGE_CAN_BUILD=0
            ;;
    esac

    if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
        if ! apt-get update; then
            echo "[ERROR] apt-get update failed; SageAttention build skipped."
            SAGE_CAN_BUILD=0
        elif ! DEBIAN_FRONTEND=noninteractive apt-get install -y "cuda-libraries-dev-${CUDA_DEV_SUFFIX}" ninja-build git; then
            echo "[ERROR] SageAttention build dependencies failed to install; build skipped."
            SAGE_CAN_BUILD=0
        fi
    fi

    if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
        rm -rf /workspace/SageAttention

        if git clone https://github.com/thu-ml/SageAttention.git /workspace/SageAttention; then
            if SAGE_ARCH="$(python - <<'PY2'
import torch
major, minor = torch.cuda.get_device_capability()
print(f"{major}.{minor}")
PY2
)"; then
                echo "SageAttention CUDA arch: $SAGE_ARCH"

                if (
                    cd /workspace/SageAttention
                    rm -rf build
                    export TORCH_CUDA_ARCH_LIST="$SAGE_ARCH"
                    export EXT_PARALLEL=4
                    export NVCC_APPEND_FLAGS="--threads 8"
                    export MAX_JOBS=8
                    python setup.py install
                ) && python -c "from sageattention import sageattn" >/dev/null 2>&1; then
                    echo "OK: SageAttention installed"
                else
                    echo "[ERROR] SageAttention source build failed. Continuing startup without SageAttention."
                fi
            else
                echo "[ERROR] Could not detect GPU compute capability; SageAttention build skipped."
            fi
        else
            echo "[ERROR] SageAttention source clone failed. Continuing startup without SageAttention."
        fi
    fi
fi

# 3) Spectrum + Sol-Attn
install_node \
  "ComfyUI-Spectrum-MiniMax-H3" \
  "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git" || true

install_node \
  "ComfyUI-sol-attn" \
  "https://github.com/Saganaki22/ComfyUI-sol-attn.git" || true

# 4) Workflow JSONs
# Download to /tmp, validate as JSON, then move into the ComfyUI workflow folder.
RAW_BASE="https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/main/workflows"

install_workflow() {
    local filename="$1"
    local tmp="/tmp/${filename}.download"
    local dest="$WORKFLOWS/$filename"

    rm -f "$tmp"
    if curl -fsSL "$RAW_BASE/$filename" -o "$tmp" && python -m json.tool "$tmp" >/dev/null 2>&1; then
        mv "$tmp" "$dest"
        echo "OK: workflow $filename installed"
        return 0
    fi

    rm -f "$tmp"
    echo "[ERROR] workflow $filename download/validation failed. Continuing startup."
    return 1
}

install_workflow "H3_TurboV4_SageAttention_4step.json" || true
install_workflow "H3_Spectrum_SolAttn_16step.json" || true

echo "============================================="
echo "  H3 mobile auto setup finished"
echo "  Continuing official RunPod startup"
echo "============================================="
'''

text = text.replace(marker, block + "\n" + marker, 1)
p.write_text(text)
PY
then
    echo "[ERROR] Could not patch RunPod /start.sh. Starting standard RunPod startup."
    exec /start.sh
fi

exec bash "$TMP_START"
