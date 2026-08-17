#!/usr/bin/env bash
set -Eeuo pipefail

COMFY="${COMFY:-/workspace/runpod-slim/ComfyUI}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CUSTOM="$COMFY/custom_nodes"
WORKFLOW_DST="$COMFY/user/default/workflows/H3_REF2VA_SPEED_TEST"

TURBO_URL="https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git"
TURBO_COMMIT="4274783a23afcfdbea3b4876cb79effd6c510785"
SPECTRUM_URL="https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git"
SPECTRUM_COMMIT="6a3d14f89cc717abf9815f51d0a599080a3321a6"
SOL_URL="https://github.com/Saganaki22/ComfyUI-sol-attn.git"
SOL_COMMIT="930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf"
ACCEL_URL="https://github.com/BMB12d3/ComfyUI-H3-Ref2VA-Accelerator.git"
ACCEL_COMMIT="b3299ac7c5e0e9da222cecaf9c07d1967e011cdf"

TURBO_LORA="minimax_h3_turbo_v4_step600_ema.safetensors"
TURBO_LORA_PATH="$COMFY/models/loras/$TURBO_LORA"

if [ ! -d "$COMFY" ]; then
  echo "[ERROR] ComfyUI not found: $COMFY"
  exit 1
fi
mkdir -p "$CUSTOM" "$COMFY/models/loras" "$WORKFLOW_DST"

ensure_repo() {
  local name="$1" url="$2" commit="$3"
  local dir="$CUSTOM/$name"
  if [ ! -d "$dir/.git" ]; then
    echo "[SETUP] cloning $name"
    rm -rf "$dir"
    git clone "$url" "$dir"
  else
    echo "[SETUP] found $name"
  fi
  git -C "$dir" fetch --quiet origin "$commit" || true
  git -C "$dir" checkout --quiet --detach "$commit"
  echo "[OK] $name $(git -C "$dir" rev-parse --short HEAD)"
}

# These three are already pinned in the normal Docker image. Re-check only;
# clone/checkout only if a Pod copy is missing or drifted.
ensure_repo "ComfyUI-MiniMax-H3-Turbo" "$TURBO_URL" "$TURBO_COMMIT"
ensure_repo "ComfyUI-Spectrum-MiniMax-H3" "$SPECTRUM_URL" "$SPECTRUM_COMMIT"
ensure_repo "ComfyUI-sol-attn" "$SOL_URL" "$SOL_COMMIT"

# Accelerator is test-only. Pin v0.4.2 and apply the known one-line fix.
ensure_repo "ComfyUI-H3-Ref2VA-Accelerator" "$ACCEL_URL" "$ACCEL_COMMIT"
ACCEL_DIR="$CUSTOM/ComfyUI-H3-Ref2VA-Accelerator"
PATCH="$SCRIPT_DIR/patches/h3_ref2va_accelerator_first_block_output_fix.patch"

if python3 - "$ACCEL_DIR/nodes.py" <<'PY'
import sys
p=sys.argv[1]
for line in open(p,encoding='utf-8'):
    if line.lstrip().startswith('context.first_block_output = _tensor_storage_copy(first_output, self.storage)'):
        raise SystemExit(0)
raise SystemExit(1)
PY
then
  echo "[OK] Accelerator first_block_output fix already present"
else
  echo "[SETUP] applying Accelerator v0.4.2 fix"
  git -C "$ACCEL_DIR" apply --check "$PATCH"
  git -C "$ACCEL_DIR" apply "$PATCH"
fi
python3 -m py_compile "$ACCEL_DIR/__init__.py" "$ACCEL_DIR/nodes.py"

echo "[OK] Accelerator syntax + patch verified"

# Turbo LoRA is intentionally not baked into the normal image.
# Download only when absent/incomplete.
if [ -f "$TURBO_LORA_PATH" ] && [ "$(stat -c%s "$TURBO_LORA_PATH")" -gt 700000000 ]; then
  echo "[OK] Turbo LoRA already present: $(du -h "$TURBO_LORA_PATH" | cut -f1)"
else
  echo "[SETUP] downloading Turbo LoRA (~744 MiB)"
  rm -f "$TURBO_LORA_PATH"
  python3.12 - "$TURBO_LORA_PATH" <<'PY'
import os, shutil, sys
from huggingface_hub import hf_hub_download
out=sys.argv[1]
name='minimax_h3_turbo_v4_step600_ema.safetensors'
src=hf_hub_download(repo_id='larryvrh/MiniMax-H3-Turbo-Lora', filename=name)
os.makedirs(os.path.dirname(out), exist_ok=True)
shutil.copy2(src,out)
size=os.path.getsize(out)
if size <= 700_000_000:
    raise SystemExit(f'Unexpected Turbo LoRA size: {size}')
print(f'[OK] Turbo LoRA: {size/1024/1024:.1f} MiB')
PY
fi

cp -f "$SCRIPT_DIR"/workflows/*.json "$WORKFLOW_DST/"
echo "[OK] workflows copied to: $WORKFLOW_DST"

echo
echo "============================================="
echo " H3 Ref2VA speed-test setup complete"
echo "============================================="
echo "Next:"
echo "  1) bash $SCRIPT_DIR/check_test.sh"
echo "  2) bash $SCRIPT_DIR/restart_comfy_test.sh"
echo "  3) Open workflows under H3_REF2VA_SPEED_TEST"
