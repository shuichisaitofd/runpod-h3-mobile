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

# Billing account credentials are now browser-managed by default. The mobile UI
# keeps account keys in that browser and POSTs them transiently to the current
# Pod only for the balance/currentSpendPerHr request. Nothing needs to be stored
# in /workspace for normal operation. Keep the old environment/file path only as
# a backwards-compatible fallback for existing deployments.
H3_BILLING_ENV_FILE="/workspace/.secrets/runpod_billing.env"
if [ -n "${RUNPOD_BILLING_API_KEY:-}" ]; then
  echo "[H3] Legacy RUNPOD_BILLING_API_KEY environment fallback is available."
elif [ -f "$H3_BILLING_ENV_FILE" ]; then
  set -a
  source "$H3_BILLING_ENV_FILE"
  set +a
  if [ -n "${RUNPOD_BILLING_API_KEY:-}" ]; then
    echo "[H3] Loaded legacy billing-key fallback from $H3_BILLING_ENV_FILE"
  fi
else
  echo "[H3] Billing account key will be supplied by H3 Mobile browser storage when configured."
fi

echo "[H3] Starting standard RunPod ComfyUI services..."

exec /start.sh "$@"
