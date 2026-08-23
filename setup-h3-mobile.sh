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
echo "  H3 mobile reproducible setup"
echo "============================================="

CUSTOM="$COMFYUI_DIR/custom_nodes"
WORKFLOWS="$COMFYUI_DIR/user/default/workflows"
MODELS="$COMFYUI_DIR/models"
H3_ROOT="$(dirname "$COMFYUI_DIR")"
mkdir -p "$CUSTOM" "$WORKFLOWS" \
  "$MODELS/diffusion_models" "$MODELS/text_encoders" "$MODELS/vae" "$MODELS/loras"

# ------------------------------------------------------------------
# Host preflight
# Known-good target: RTX A6000 / SM86, driver 580+, torch cu130.
# NVIDIA CUDA 13.x requires driver branch 580 or newer.
# Never replace torch with cu130 on an older RunPod host.
# ------------------------------------------------------------------
H3_CU130_HOST_OK=0
H3_DRIVER_VERSION=""
H3_DRIVER_MAJOR=0
H3_GPU_NAME=""

if command -v nvidia-smi >/dev/null 2>&1; then
    H3_DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n 1 | tr -d '[:space:]')"
    H3_GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    H3_DRIVER_MAJOR="${H3_DRIVER_VERSION%%.*}"
fi

case "$H3_DRIVER_MAJOR" in
    ''|*[!0-9]*) H3_DRIVER_MAJOR=0 ;;
esac

echo "[H3] Host GPU: ${H3_GPU_NAME:-unknown}"
echo "[H3] Host NVIDIA driver: ${H3_DRIVER_VERSION:-unknown}"

if [ "$H3_DRIVER_MAJOR" -ge 580 ]; then
    H3_CU130_HOST_OK=1
    echo "OK: Host driver supports CUDA 13.x target runtime."
else
    echo "============================================================="
    echo "[H3][HOST_INCOMPATIBLE] CUDA 13 target skipped."
    echo "[H3][HOST_INCOMPATIBLE] NVIDIA driver 580+ is required."
    echo "[H3][HOST_INCOMPATIBLE] Detected: ${H3_DRIVER_VERSION:-unknown}."
    if [ "$H3_DRIVER_MAJOR" -gt 0 ] && [ "$H3_DRIVER_MAJOR" -lt 570 ]; then
        echo "[H3][HOST_INCOMPATIBLE] Driver is also below the CUDA 12.8 base-image target range."
    fi
    echo "[H3][HOST_INCOMPATIBLE] Do NOT install H3 models on this Pod."
    echo "[H3][HOST_INCOMPATIBLE] Terminate and redeploy until driver 580+ is assigned."
    echo "============================================================="
    printf '%s\n' \
      "H3 target runtime not installed." \
      "Required NVIDIA driver: 580+" \
      "Detected NVIDIA driver: ${H3_DRIVER_VERSION:-unknown}" \
      "Action: terminate this Pod and redeploy." \
      > "$H3_ROOT/H3_HOST_INCOMPATIBLE.txt"
fi

# ------------------------------------------------------------------
# Runtime lock
# ------------------------------------------------------------------
if [ "$H3_CU130_HOST_OK" -eq 1 ]; then
    echo "[H3] Checking PyTorch runtime..."
    TORCH_RUNTIME="$(python3 - <<'PY2'
import torch
print(torch.__version__)
PY2
 2>/dev/null || true)"

    if [ "$TORCH_RUNTIME" != "2.10.0+cu130" ]; then
        echo "[H3] Installing PyTorch 2.10.0+cu130..."
        if ! PIP_CONSTRAINT= python3 -m pip install --upgrade --force-reinstall \
            torch==2.10.0 \
            torchvision==0.25.0 \
            torchaudio==2.10.0 \
            --index-url https://download.pytorch.org/whl/cu130; then
            echo "[ERROR] PyTorch cu130 installation failed."
            H3_CU130_HOST_OK=0
        fi
    else
        echo "OK: PyTorch already $TORCH_RUNTIME"
    fi
fi

if [ "$H3_CU130_HOST_OK" -eq 1 ]; then
    if python3 - <<'PY2'
import torch
print("[H3] Torch:", torch.__version__)
print("[H3] Torch CUDA:", torch.version.cuda)
if not torch.cuda.is_available():
    raise SystemExit(1)
print("[H3] GPU:", torch.cuda.get_device_name(0))
print("[H3] Capability:", torch.cuda.get_device_capability(0))
PY2
    then
        echo "OK: CUDA runtime initialized successfully."
        rm -f "$H3_ROOT/H3_HOST_INCOMPATIBLE.txt"
    else
        echo "[ERROR] CUDA 13 runtime could not initialize on this host."
        H3_CU130_HOST_OK=0
    fi
fi

install_node_pinned() {
    local name="$1"
    local url="$2"
    local commit="$3"
    local path="$CUSTOM/$name"
    local tmp="${path}.tmp"

    echo "[H3] Pinning $name -> $commit"

    if [ ! -d "$path/.git" ]; then
        rm -rf "$path" "$tmp"
        if ! git clone "$url" "$tmp"; then
            rm -rf "$tmp"
            echo "[ERROR] $name clone failed."
            return 1
        fi
        mv "$tmp" "$path"
    fi

    if ! git -C "$path" cat-file -e "${commit}^{commit}" >/dev/null 2>&1; then
        git -C "$path" fetch --depth 1 origin "$commit" >/dev/null 2>&1 || \
        git -C "$path" fetch origin >/dev/null 2>&1 || true
    fi

    if git -C "$path" checkout --detach -f "$commit" >/dev/null 2>&1; then
        echo "OK: $name pinned at $(git -C "$path" rev-parse HEAD)"
        return 0
    fi

    echo "[ERROR] Could not pin $name to $commit."
    return 1
}

install_node_pinned \
  "ComfyUI-MiniMax-H3-Turbo" \
  "https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git" \
  "4274783a23afcfdbea3b4876cb79effd6c510785" || true

install_node_pinned \
  "ComfyUI-KJNodes" \
  "https://github.com/kijai/ComfyUI-KJNodes.git" \
  "d19ce9078f03cc66a462efc082defd30aef16d02" || true

install_node_pinned \
  "ComfyUI-Spectrum-MiniMax-H3" \
  "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git" \
  "6a3d14f89cc717abf9815f51d0a599080a3321a6" || true

install_node_pinned \
  "ComfyUI-sol-attn" \
  "https://github.com/Saganaki22/ComfyUI-sol-attn.git" \
  "930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf" || true

install_node_pinned \
  "ComfyUI-PlagueKind-Nodes" \
  "https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes.git" \
  "6ca3037bd16dc143b6d461c67c87a28ca8074063" || true

# ------------------------------------------------------------------
# Ref2VA 05 (SLA Attention + Balanced BlockCache) co-existence patch.
#
# ComfyUI-PlagueKind-Nodes' SLA attention wrapper re-invokes the wrapped
# forward function via executor.original(...) instead of executor(...).
# That call bypasses any OTHER wrapper chained onto the same hook - in
# particular Ref2VA's Balanced BlockCache node - instead of composing with
# it, so SLA and BlockCache silently stop co-existing correctly.
#
# This is a third-party repository we do not control, so this step never
# blind-overwrites the file: it only edits sla/patch.py when the exact
# known-unpatched text is found unmodified, does nothing if the fix is
# already present (safe to run on every startup), and only warns (never
# force-edits) if the file doesn't match either known state - e.g. after an
# upstream release changes this code path.
# ------------------------------------------------------------------
SLA_PATCH="$CUSTOM/ComfyUI-PlagueKind-Nodes/ComfyUI-H3-SLA-Attention/sla/patch.py"
if [ -f "$SLA_PATCH" ]; then
    python3 - "$SLA_PATCH" <<'PY_SLA'
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

OLD = (
    "        out = executor.original(x, timestep, context,\n"
    "                                transformer_options=transformer_options,\n"
    "                                **kwargs)"
)
NEW = (
    "        out = executor(x, timestep, context,\n"
    "                       transformer_options=transformer_options,\n"
    "                       **kwargs)"
)

if NEW in text:
    print("OK: SLA + Balanced BlockCache co-existence patch already present")
elif OLD in text:
    backup_dir = path.parent / "_backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (backup_dir / f"patch.py.orig.{stamp}").write_text(text)
    path.write_text(text.replace(OLD, NEW, 1))
    print("OK: applied SLA + Balanced BlockCache co-existence patch (executor.original -> executor)")
else:
    print("[WARN] sla/patch.py matched neither the known-good nor known-bad text.")
    print("[WARN] Skipping the SLA/BlockCache co-existence patch - upstream file has changed.")
    print("[WARN] SLA Attention alone is unaffected; combining it with Balanced BlockCache may not work correctly.")
PY_SLA
else
    echo "[WARN] sla/patch.py not found at $SLA_PATCH - ComfyUI-PlagueKind-Nodes clone may have failed."
fi

if [ "$H3_CU130_HOST_OK" -eq 1 ]; then
    if python3 -c "import triton" >/dev/null 2>&1; then
        echo "OK: Triton available for SLA Attention ($(python3 -c 'import triton; print(triton.__version__)' 2>/dev/null))"
    else
        echo "[WARN] Triton not importable - SLA Attention (Ref2VA 05) will not load. It normally ships with the torch cu130 install above."
    fi
fi

# ------------------------------------------------------------------
# SageAttention 2.2.0 - only on validated CUDA 13 host.
# ------------------------------------------------------------------
if [ "$H3_CU130_HOST_OK" -eq 1 ]; then
    SAGE_OK=0
    if python3 - <<'PY2' >/dev/null 2>&1
from importlib.metadata import version
from sageattention import sageattn
raise SystemExit(0 if version("sageattention") == "2.2.0" else 1)
PY2
    then
        SAGE_OK=1
        echo "OK: SageAttention 2.2.0 already installed"
    fi

    if [ "$SAGE_OK" -ne 1 ]; then
        echo "[H3] Preparing CUDA 13.0 build environment for SageAttention 2.2.0..."
        SAGE_CAN_BUILD=1

        if ! apt-get update; then
            echo "[ERROR] apt-get update failed; SageAttention build skipped."
            SAGE_CAN_BUILD=0
        elif ! DEBIAN_FRONTEND=noninteractive apt-get install -y \
            cuda-compiler-13-0 \
            libcusparse-dev-13-0 \
            libcublas-dev-13-0 \
            libcusolver-dev-13-0 \
            ninja-build \
            git; then
            echo "[ERROR] CUDA 13.0 development packages failed to install; SageAttention build skipped."
            SAGE_CAN_BUILD=0
        fi

        if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
            export CUDA_HOME="/usr/local/cuda-13.0"
            export PATH="$CUDA_HOME/bin:$PATH"
            export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

            if [ ! -x "$CUDA_HOME/bin/nvcc" ]; then
                echo "[ERROR] nvcc not found at $CUDA_HOME/bin/nvcc; SageAttention build skipped."
                SAGE_CAN_BUILD=0
            else
                echo "[H3] $($CUDA_HOME/bin/nvcc --version | tail -n 1)"
            fi
        fi

        if [ "$SAGE_CAN_BUILD" -eq 1 ]; then
            SAGE_SRC="$H3_ROOT/SageAttention"
            rm -rf "$SAGE_SRC"

            if git clone --depth 1 --branch v2.2.0 \
                https://github.com/thu-ml/SageAttention.git "$SAGE_SRC"; then

                SAGE_ARCH="$(python3 - <<'PY2'
import torch
major, minor = torch.cuda.get_device_capability(0)
print(f"{major}.{minor}")
PY2
 2>/dev/null || true)"

                echo "[H3] SageAttention CUDA arch: ${SAGE_ARCH:-unknown}"

                if [ -n "$SAGE_ARCH" ] && (
                    cd "$SAGE_SRC"
                    rm -rf build
                    export TORCH_CUDA_ARCH_LIST="$SAGE_ARCH"
                    export MAX_JOBS=1
                    PIP_CONSTRAINT= python3 -m pip install . --no-build-isolation
                ) && (
                    cd "$COMFYUI_DIR"
                    python3 - <<'PY2'
from importlib.metadata import version
from sageattention import sageattn
print("OK: SageAttention", version("sageattention"))
PY2
                ); then
                    echo "OK: SageAttention 2.2.0 installed"
                else
                    echo "[ERROR] SageAttention 2.2.0 source build/import failed. Continuing startup without Sage acceleration."
                fi
            else
                echo "[ERROR] SageAttention v2.2.0 clone failed."
            fi
        fi
    fi
else
    echo "[H3] SageAttention build skipped because this host did not pass the CUDA 13 driver preflight."
fi

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
install_mobile_file "extra_routes.py" || true
install_mobile_file "web/index.html" || true
install_mobile_file "web/app.js" || true
install_mobile_file "web/batch.js" || true
install_mobile_file "web/batch-v2.js" || true
install_mobile_file "web/copy-prompts.js" || true
install_mobile_file "web/history-autoplay.js" || true
install_mobile_file "web/history-thumbnails.js" || true
install_mobile_file "web/media-library.js" || true
install_mobile_file "web/pod-runtime.js" || true
install_mobile_file "web/pod-billing.js" || true
install_mobile_file "web/prompt-library.js" || true
install_mobile_file "web/styles.css" || true

install_api_workflow() {
    local mode="$1"
    local dest="$MOBILE_DEST/api_workflows/$mode.json"
    if curl -fsSL "$MOBILE_SRC/api_workflows/$mode.json" -o "$dest" && \
       python3 -m json.tool "$dest" >/dev/null 2>&1; then
        echo "OK: H3 mobile $mode API workflow installed"
        return 0
    fi
    rm -f "$dest"
    echo "[ERROR] H3 mobile $mode API workflow install failed"
    return 1
}

install_api_workflow "i2v" || true
install_api_workflow "ref2va" || true
install_api_workflow "ref2va_03" || true
install_api_workflow "ref2va_04" || true
install_api_workflow "ref2va_05" || true

RAW_BASE="https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/main/workflows"
install_workflow() {
    local filename="$1"
    local tmp="/tmp/${filename}.download"
    local dest="$WORKFLOWS/$filename"
    rm -f "$tmp"
    if curl -fsSL "$RAW_BASE/$filename" -o "$tmp" && \
       python3 -m json.tool "$tmp" >/dev/null 2>&1; then
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

# H3 Mobile: load the account-scope billing API key if one has been saved
# via set-runpod-billing-key.sh (or provided directly through a RunPod
# Template/Secret env var of the same name - this file is only a fallback
# for that case). Only adds RUNPOD_BILLING_API_KEY - never touches
# RUNPOD_API_KEY, RUNPOD_POD_ID, or anything else RunPod injects.
H3_BILLING_ENV_FILE="/workspace/.secrets/runpod_billing.env"
if [ -f "$H3_BILLING_ENV_FILE" ]; then
    set -a
    source "$H3_BILLING_ENV_FILE"
    set +a
    echo "OK: loaded RUNPOD_BILLING_API_KEY from $H3_BILLING_ENV_FILE"
fi

echo "============================================="
if [ "$H3_CU130_HOST_OK" -eq 1 ]; then
    echo "  H3 mobile reproducible setup finished"
    echo "  Host driver: ${H3_DRIVER_VERSION:-unknown} (CUDA 13 target OK)"
    echo "  Expected runtime: torch 2.10.0+cu130"
    echo "  I2V: Turbo v4 + SageAttention 2.2.0"
    echo "  Ref2VA: Spectrum + Sol-Attn"
else
    echo "  H3 setup installed UI/workflows only"
    echo "  HOST INCOMPATIBLE WITH CUDA 13 TARGET"
    echo "  Driver: ${H3_DRIVER_VERSION:-unknown}; required: 580+"
    echo "  Terminate/redeploy before downloading H3 models"
fi
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
