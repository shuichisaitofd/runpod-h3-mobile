#!/usr/bin/env bash
set -Eeuo pipefail
COMFY="${COMFY:-/workspace/runpod-slim/ComfyUI}"
LOG="/workspace/comfyui-h3-speed-test.log"

pid="$(pgrep -f 'python(3|3\.12)? .*main.py.*--port 8188' | head -n1 || true)"
if [ -n "$pid" ]; then
  py="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  echo "[RESTART] stopping PID $pid"
  kill "$pid"
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
else
  py=""
  cwd=""
fi

[ -n "$py" ] && [ -x "$py" ] || py="$(command -v python3.12 || command -v python3)"
[ "$cwd" = "$COMFY" ] || cwd="$COMFY"

echo "[RESTART] python=$py"
echo "[RESTART] cwd=$cwd"
echo "[RESTART] log=$LOG"
cd "$cwd"
nohup "$py" main.py --listen 0.0.0.0 --port 8188 --enable-cors-header >"$LOG" 2>&1 &
newpid=$!
sleep 4
if kill -0 "$newpid" 2>/dev/null; then
  echo "[OK] ComfyUI restarted: PID $newpid"
  echo "Browser: refresh Port 8188"
else
  echo "[FAIL] ComfyUI did not stay up. Last log lines:"
  tail -80 "$LOG" || true
  exit 1
fi
