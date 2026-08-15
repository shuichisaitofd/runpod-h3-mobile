#!/usr/bin/env bash
set -Eeuo pipefail

COMFY="/workspace/runpod-slim/ComfyUI"
CUSTOM="$COMFY/custom_nodes"
LOG="/workspace/runpod-slim/h3_mobile_boot.log"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "============================================="
echo " H3 mobile boot setup"
date -Is
echo "============================================="

# RunPod base image normally provides ComfyUI-KJNodes already.
if [ -d "$CUSTOM/ComfyUI-KJNodes" ]; then
  echo "OK: ComfyUI-KJNodes present"
else
  echo "WARNING: ComfyUI-KJNodes not found"
fi

# SageAttention can depend on the runtime Torch/CUDA stack, so install/check it at Pod boot.
PYTHON_BIN=""
for c in "$COMFY/.venv/bin/python" "/workspace/runpod-slim/.venv/bin/python" "$(command -v python3 2>/dev/null || true)" "$(command -v python 2>/dev/null || true)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then
    PYTHON_BIN="$c"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "WARNING: Python not found before /start.sh; SageAttention check deferred"
else
  if "$PYTHON_BIN" -c "import sageattention" >/dev/null 2>&1; then
    echo "OK: SageAttention already installed"
  else
    echo "Installing SageAttention 2.2.0..."
    "$PYTHON_BIN" -m pip install sageattention==2.2.0 --no-build-isolation || echo "WARNING: SageAttention install failed"
  fi
fi

# Do not replace Torch, ComfyUI itself, or H3 model files here.
# Hand control back to RunPod's standard startup so Jupyter/SSH/ComfyUI behave normally.
exec /start.sh
