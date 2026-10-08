#!/bin/bash
# Veda test image: runs in the background at Pod boot. Idempotent. Same steps as restore.sh (1,2 + predictor only).
# Log: /workspace/veda_boot_setup.log   Status: /workspace/veda_boot_status.txt
W=/workspace/runpod-slim
C=$W/ComfyUI
PY=$C/.venv-cu128/bin
V=$C/custom_nodes/Veda-on-ComfyUI
PRED_REL=models/veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors
PRED=$C/$PRED_REL
PRED_SIZE=275415648
PRED_SHA=2a8d8845c5342756a2781e8e69563940e4bb573c9a40ebb534915ff8fd76573a
PRED_URL=https://huggingface.co/Veda-Sparse/Minimax-H3-T2VA-Veda-8NFE-600Step-Preview/resolve/main/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors
TAG=v0.38.0
STATUS=/workspace/veda_boot_status.txt
log() { echo "[$(date -u +%FT%TZ)] $*"; }
status() { echo "$*" > "$STATUS"; log "STATUS: $*"; }
fail() { status "FAILED: $*"; exit 1; }

status "WAITING: ComfyUI is starting"
for i in $(seq 900); do
  [ -d "$C/.git" ] && [ -x "$PY/pip" ] && curl -sf http://127.0.0.1:8188/system_stats >/dev/null 2>&1 && break
  sleep 2
done
[ -d "$C/.git" ] && [ -x "$PY/pip" ] || fail "ComfyUI folder not found after 30 minutes"
log "ComfyUI is up"

need_restart=0

# 1. ComfyUI >= v0.38.0 (Veda needs it). Same method as restore.sh step 1.
cur=$(git -C "$C" describe --tags --exact-match 2>/dev/null || true)
if [ "$cur" != "$TAG" ]; then
  status "WORKING: upgrading ComfyUI ($cur -> $TAG)"
  git -C "$C" rev-parse HEAD > "$W/restore_backup_git_head.txt"
  "$PY/pip" freeze > "$W/restore_backup_pip_freeze.txt" 2>/dev/null || true
  git -C "$C" fetch origin tag "$TAG" || fail "git fetch of ComfyUI $TAG failed"
  git -C "$C" checkout "$TAG" || fail "git checkout $TAG failed"
  export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
  plan=$("$PY/pip" install --dry-run -r "$C/requirements.txt" 2>&1 || true)
  if echo "$plan" | grep -E '^Would install' | grep -E -i -w 'torch|torchvision|torchaudio|torch-[0-9]|torchvision-[0-9]|torchaudio-[0-9]' >/dev/null; then
    git -C "$C" checkout "$(cat "$W/restore_backup_git_head.txt")" >/dev/null 2>&1
    fail "pip wanted to change torch; ComfyUI upgrade cancelled and rolled back"
  fi
  "$PY/pip" install -r "$C/requirements.txt" || fail "pip install of ComfyUI requirements failed"
  need_restart=1
else
  log "ComfyUI is already $TAG"
fi

# 2. Veda node at commit 60bfae6
if [ ! -d "$V/.git" ]; then
  status "WORKING: installing Veda node"
  git clone https://github.com/veda-sparse/Veda-on-ComfyUI.git "$V" || fail "git clone of Veda failed"
  need_restart=1
fi
if [ "$(git -C "$V" rev-parse --short=7 HEAD 2>/dev/null)" != "60bfae6" ]; then
  git -C "$V" checkout 60bfae6 || fail "git checkout 60bfae6 failed"
  need_restart=1
fi
if [ ! -f "$V/.h3_veda_reqs_ok" ]; then
  PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt "$PY/pip" install -r "$V/requirements.txt" || fail "pip install of Veda requirements failed"
  touch "$V/.h3_veda_reqs_ok"
  need_restart=1
fi

# 3. Predictor model (275 MB, size + sha256 checked)
if ! { [ -f "$PRED" ] && [ "$(stat -c %s "$PRED")" = "$PRED_SIZE" ] && [ "$(sha256sum "$PRED" | cut -d' ' -f1)" = "$PRED_SHA" ]; }; then
  status "WORKING: downloading the Veda predictor model (275 MB)"
  mkdir -p "$(dirname "$PRED")"
  curl -fL --retry 5 --retry-delay 5 -C - -o "$PRED.part" "$PRED_URL" || fail "predictor download failed"
  [ "$(stat -c %s "$PRED.part")" = "$PRED_SIZE" ] || fail "predictor size mismatch"
  [ "$(sha256sum "$PRED.part" | cut -d' ' -f1)" = "$PRED_SHA" ] || fail "predictor sha256 mismatch"
  mv "$PRED.part" "$PRED"
  need_restart=1
fi

# 4. Restart ComfyUI once if anything changed (same command as restart_comfyui.sh)
if [ "$need_restart" = 1 ]; then
  status "WORKING: restarting ComfyUI"
  (
    cd "$C" && source .venv-cu128/bin/activate
    export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
    for p in $(pgrep -f '^python main.py --listen 0.0.0.0 --port 8188'); do kill "$p"; done
    for i in $(seq 30); do pgrep -f '^python main.py --listen 0.0.0.0 --port 8188' >/dev/null || break; sleep 1; done
    nohup python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header >> "$W/comfyui.log" 2>&1 &
  )
  for i in $(seq 120); do curl -sf http://127.0.0.1:8188/system_stats >/dev/null 2>&1 && break; sleep 2; done
fi

# 5. Verify
if curl -sf http://127.0.0.1:8188/object_info/VedaSparseAttention 2>/dev/null | grep -q VedaSparseAttention; then
  status "OK: Veda is ready (ComfyUI $(git -C "$C" describe --tags 2>/dev/null))"
else
  fail "ComfyUI is running but the VedaSparseAttention node is not registered (see $W/comfyui.log)"
fi
