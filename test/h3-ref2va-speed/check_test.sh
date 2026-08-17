#!/usr/bin/env bash
set -Eeuo pipefail
COMFY="${COMFY:-/workspace/runpod-slim/ComfyUI}"
CUSTOM="$COMFY/custom_nodes"
LORA="$COMFY/models/loras/minimax_h3_turbo_v4_step600_ema.safetensors"

echo "=== H3 Ref2VA speed-test check ==="
echo "ComfyUI: $COMFY"
[ -d "$COMFY" ] || { echo "[FAIL] ComfyUI missing"; exit 1; }

printf "GPU: "
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1 || true
python3.12 - <<'PY'
import torch
print('Torch:', torch.__version__)
print('CUDA:', torch.version.cuda, 'available=', torch.cuda.is_available())
PY

echo
echo "=== Custom nodes ==="
for d in ComfyUI-MiniMax-H3-Turbo ComfyUI-Spectrum-MiniMax-H3 ComfyUI-sol-attn ComfyUI-H3-Ref2VA-Accelerator; do
  if [ -d "$CUSTOM/$d" ]; then
    rev="$(git -C "$CUSTOM/$d" rev-parse --short HEAD 2>/dev/null || echo no-git)"
    echo "[OK] $d @ $rev"
  else
    echo "[FAIL] missing $d"
    exit 1
  fi
done

python3 - "$CUSTOM/ComfyUI-H3-Ref2VA-Accelerator/nodes.py" <<'PY'
import sys
p=sys.argv[1]
lines=open(p,encoding='utf-8').read().splitlines()
fixed=any(x.lstrip().startswith('context.first_block_output = _tensor_storage_copy(first_output, self.storage)') for x in lines)
bad=any('tokens truncated' in x for x in lines)
print('[OK] Accelerator fix present' if fixed and not bad else '[FAIL] Accelerator source is not correctly patched')
raise SystemExit(0 if fixed and not bad else 1)
PY
python3 -m py_compile "$CUSTOM/ComfyUI-H3-Ref2VA-Accelerator/nodes.py"

if [ -f "$LORA" ]; then
  bytes="$(stat -c%s "$LORA")"
  echo "Turbo LoRA: $bytes bytes"
  [ "$bytes" -gt 700000000 ] || { echo "[FAIL] Turbo LoRA incomplete"; exit 1; }
  echo "[OK] Turbo LoRA"
else
  echo "[FAIL] Turbo LoRA missing"
  exit 1
fi

echo
echo "=== Test workflows ==="
find "$COMFY/user/default/workflows/H3_REF2VA_SPEED_TEST" -maxdepth 1 -type f -name '*.json' -printf '[OK] %f\n' | sort

echo
echo "=== Running ComfyUI ==="
ps aux | grep -E '[p]ython(3|3\.12)? .*main.py.*8188' || echo '[INFO] ComfyUI process not detected'

echo
echo "CHECK PASSED"
