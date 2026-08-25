#!/usr/bin/env bash
set -Eeuo pipefail

COMFYUI_DIR="/workspace/runpod-slim/ComfyUI"
EXT="$COMFYUI_DIR/custom_nodes/ComfyUI-H3-Mobile"
BASE="https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/main"
PORT=8188
LOG="$COMFYUI_DIR/user/comfyui_8188_browser_billing.log"

cd "$COMFYUI_DIR"

echo "=== QUEUE CHECK ==="
python3 - <<'PY'
import json, urllib.request, sys
q=json.load(urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=10))
r=len(q.get("queue_running", []))
p=len(q.get("queue_pending", []))
print(f"running: {r} pending: {p}")
if r or p:
    print("STOP: generation job exists; nothing changed")
    sys.exit(2)
print("QUEUE EMPTY")
PY

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

curl -fsSL "$BASE/h3-mobile/extra_routes.py" -o "$tmpdir/extra_routes.py"
curl -fsSL "$BASE/h3-mobile/web/pod-billing.js" -o "$tmpdir/pod-billing.js"
python3 -m py_compile "$tmpdir/extra_routes.py"

cp "$EXT/extra_routes.py" "$EXT/extra_routes.py.bak-browser-billing"
cp "$EXT/web/pod-billing.js" "$EXT/web/pod-billing.js.bak-browser-billing"
install -m 0644 "$tmpdir/extra_routes.py" "$EXT/extra_routes.py"
install -m 0644 "$tmpdir/pod-billing.js" "$EXT/web/pod-billing.js"

echo "=== RESTART COMFYUI ONLY ==="
PID="$(pgrep -f '[p]ython.*main.py.*--port 8188' | head -1 || true)"
if [ -n "$PID" ]; then
  echo "stopping PID $PID"
  kill "$PID"
  while kill -0 "$PID" 2>/dev/null; do sleep 1; done
fi

nohup .venv-cu128/bin/python main.py \
  --listen 0.0.0.0 \
  --port "$PORT" \
  --enable-cors-header \
  > "$LOG" 2>&1 &
disown 2>/dev/null || true

READY=0
for _ in $(seq 1 180); do
  if curl -sf "http://127.0.0.1:${PORT}/object_info" >/dev/null; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "ERROR: ComfyUI did not become ready"
  tail -80 "$LOG" || true
  exit 1
fi

echo "=== BROWSER BILLING ROUTE CHECK ==="
RESP="$(curl -sS -X POST --data-urlencode 'billing_api_key=' "http://127.0.0.1:${PORT}/h3-mobile/api/pod-billing")"
python3 - "$RESP" <<'PY'
import json, sys
j=json.loads(sys.argv[1])
err=j.get("error") or ""
print("POST route:", "OK" if "account API key not provided" in err else "CHECK")
print("cost_per_hour:", j.get("cost_per_hour"))
print("error:", err)
if "account API key not provided" not in err:
    raise SystemExit(1)
PY

echo "DONE: current Pod now accepts browser-stored RunPod account keys"
