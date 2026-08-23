#!/usr/bin/env bash
set -Eeuo pipefail

echo "============================================="
echo " H3 Mobile runtime check"
echo "============================================="

# CUDA 13.x requires a sufficiently new host driver. Check before importing Torch.
DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 || true)"
DRIVER_MAJOR="${DRIVER_VERSION%%.*}"

if [ -z "$DRIVER_VERSION" ] || ! [[ "$DRIVER_MAJOR" =~ ^[0-9]+$ ]]; then
  echo "[H3][HOST_INCOMPATIBLE] NVIDIA driver could not be detected."
  echo "Terminate this Pod and redeploy on a CUDA 13 compatible host."
  sleep infinity
fi

if [ "$DRIVER_MAJOR" -lt 580 ]; then
  echo "[H3][HOST_INCOMPATIBLE] NVIDIA driver $DRIVER_VERSION is too old for this CUDA 13 image."
  echo "Required: NVIDIA driver 580+"
  echo "Terminate this Pod and redeploy using a CUDA 13.0 host filter."
  sleep infinity
fi

if ! python3.12 - <<'PY'
import torch
from importlib.metadata import version

print("Torch:", torch.__version__)
print("Torch CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit(1)

name = torch.cuda.get_device_name(0)
cap = torch.cuda.get_device_capability(0)
print("GPU:", name)
print("Capability:", cap)
print("SageAttention:", version("sageattention"))

assert torch.__version__ == "2.10.0+cu130"
assert torch.version.cuda == "13.0"
assert version("sageattention") == "2.2.0"
# This image's SageAttention wheel is intentionally compiled for RTX A6000 / SM86.
assert cap == (8, 6), f"Expected SM86, got {cap}"
PY
then
  echo "[H3][HOST_INCOMPATIBLE] Runtime validation failed."
  echo "This image is locked to Torch 2.10.0+cu130 / SageAttention 2.2.0 / SM86."
  echo "Terminate this Pod and redeploy on an RTX A6000 CUDA 13 compatible host."
  sleep infinity
fi

echo "[H3] Runtime OK: CUDA 13 / Torch cu130 / SageAttention / SM86"

# H3 Mobile: load the account-scope billing API key if one has been saved
# via set-runpod-billing-key.sh (or provided directly through a RunPod
# Template/Secret env var of the same name - this file is only a fallback
# for that case). Only adds RUNPOD_BILLING_API_KEY - never touches
# RUNPOD_API_KEY, RUNPOD_POD_ID, or anything else RunPod injects. Runs on
# every container start (fresh pod or Pod Stop -> Start of an existing
# one), so the key survives without re-entry once saved to
# /workspace/.secrets/runpod_billing.env.
H3_BILLING_ENV_FILE="/workspace/.secrets/runpod_billing.env"
if [ -f "$H3_BILLING_ENV_FILE" ]; then
  set -a
  source "$H3_BILLING_ENV_FILE"
  set +a
  echo "[H3] Loaded RUNPOD_BILLING_API_KEY from $H3_BILLING_ENV_FILE"
fi

echo "[H3] Starting standard RunPod ComfyUI services..."

exec /start.sh "$@"
