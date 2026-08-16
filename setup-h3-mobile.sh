#!/usr/bin/env bash
set -uo pipefail

TMP_START="/tmp/start-h3-mobile.sh"

if ! cp /start.sh "$TMP_START"; then
    echo "[ERROR] Could not copy /start.sh. Starting standard RunPod startup."
    exec /start.sh
fi

if ! python3 - <<'PY'
from pathlib import Path

p = Path("/tmp/start-h3-mobile.sh")
text = p.read_text()
marker = "# Warm up pip so ComfyUI-Manager"
if marker not in text:
    raise SystemExit("RunPod start.sh structure changed: insertion point not found")

block = r'''
echo "============================================="
echo "  H3 mobile auto setup"
echo "============================================="

CUSTOM="$COMFYUI_DIR/custom_nodes"
WORKFLOWS="$COMFYUI_DIR/user/default/workflows"
MODELS="$COMFYUI_DIR/models"
mkdir -p "$CUSTOM" "$WORKFLOWS" \
  "$MODELS/diffusion_models" "$MODELS/text_encoders" "$MODELS/vae" "$MODELS/loras"

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

install_node "ComfyUI-MiniMax-H3-Turbo" "https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git" || true

if [ -d "$CUSTOM/ComfyUI-KJNodes" ]; then
    echo "OK: ComfyUI-KJNodes present"
else
    echo "[ERROR] ComfyUI-KJNodes is missing. Continuing startup without modifying it."
fi

if python -c "from sageattention import sageattn" >/dev/null 2>&1; then
    echo "OK: SageAttention already installed"
else
    echo "Installing SageAttention from official source..."
    SAGE_CAN_BUILD=1
    CUDA_VERSION="$(python - <<'PY2'
import torch
print(torch.version.cuda or "")
PY2
)"
    CUDA_DEV_SUFFIX="${CUDA_VERSION/./-}"
    case "$CUDA_DEV_SUFFIX" in
        12-8|13-0) echo "SageAttention CUDA toolkit target: $CUDA_VERSION" ;;
        *) echo "[ERROR] Unsupported/unknown PyTorch CUDA version: ${CUDA_VERSION:-none}; SageAttention build skipped."; SAGE_CAN_BUILD=0 ;;
    esac
    if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
        if ! apt-get update; then
            echo "[ERROR] apt-get update failed; SageAttention build skipped."
            SAGE_CAN_BUILD=0
        elif ! DEBIAN_FRONTEND=noninteractive apt-get install -y \
            "cuda-compiler-${CUDA_DEV_SUFFIX}" \
            "cuda-libraries-dev-${CUDA_DEV_SUFFIX}" \
            ninja-build git; then
            echo "[ERROR] SageAttention build dependencies failed to install; build skipped."
            SAGE_CAN_BUILD=0
        fi
    fi
    if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
        CUDA_HOME="/usr/local/cuda-${CUDA_VERSION}"
        export CUDA_HOME
        export PATH="$CUDA_HOME/bin:$PATH"
        export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        if [ ! -x "$CUDA_HOME/bin/nvcc" ]; then
            echo "[ERROR] nvcc not found at $CUDA_HOME/bin/nvcc; SageAttention build skipped."
            SAGE_CAN_BUILD=0
        else
            echo "SageAttention nvcc: $($CUDA_HOME/bin/nvcc -V | tail -n 1)"
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

install_node "ComfyUI-Spectrum-MiniMax-H3" "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git" || true
install_node "ComfyUI-sol-attn" "https://github.com/Saganaki22/ComfyUI-sol-attn.git" || true

echo "H3 model auto-download: disabled (manual/on-demand mode)"

MOBILE_SRC="https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/main/h3-mobile"
MOBILE_DEST="$CUSTOM/ComfyUI-H3-Mobile"
mkdir -p "$MOBILE_DEST/web" "$MOBILE_DEST/api_workflows"

install_mobile_file() {
    local relative="$1"
    local dest="$MOBILE_DEST/$relative"
    mkdir -p "$(dirname "$dest")"
    if curl -fsSL "$MOBILE_SRC/$relative" -o "$dest"; then
        echo "OK: H3 mobile file installed: $relative"
        return 0
    fi
    echo "[ERROR] H3 mobile file failed: $relative"
    return 1
}

install_mobile_file "__init__.py" || true
install_mobile_file "web/index.html" || true
install_mobile_file "web/app.js" || true
install_mobile_file "web/styles.css" || true

install_api_workflow() {
    local mode="$1"
    local dest="$MOBILE_DEST/api_workflows/$mode.json"
    if curl -fsSL "$MOBILE_SRC/api_workflows/$mode.json" -o "$dest" && python -m json.tool "$dest" >/dev/null 2>&1; then
        echo "OK: H3 mobile $mode API workflow installed"
        return 0
    fi
    rm -f "$dest"
    echo "[ERROR] H3 mobile $mode API workflow install failed"
    return 1
}

install_api_workflow "i2v" || true
install_api_workflow "ref2va" || true

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
echo "  H3 mobile URL: /h3-mobile"
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
