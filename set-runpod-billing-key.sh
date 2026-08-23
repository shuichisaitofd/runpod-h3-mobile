#!/bin/bash
# Interactive, one-time setup for the RunPod account-balance billing key
# (RUNPOD_BILLING_API_KEY). This is a SEPARATE key from RUNPOD_API_KEY
# (the pod-scoped key RunPod auto-injects, used only for this pod's
# cost_per_hour). This key is used only for the GraphQL
# myself.clientBalance query that powers the account balance shown in the
# mobile UI.
#
# What this does:
#   1. Prompts for the key with hidden input (never echoed, never a CLI
#      arg, never written to shell history since this file is run with
#      `bash set-runpod-billing-key.sh`, not typed key-by-key).
#   2. Saves it to /workspace/.secrets/runpod_billing.env, chmod 600.
#   3. Safely interrupts/clears the current ComfyUI queue and stops the
#      ComfyUI process ONLY (not the pod/container - SSH/JupyterLab keep
#      running).
#   4. Restarts ComfyUI with the key loaded.
#   5. Waits for it to come back up and checks /h3-mobile/api/pod-billing
#      once, printing only balance / spend_rate / estimated_hours_remaining
#      (plus this pod's own cost_per_hour as auxiliary info).
#
# The key itself is never printed by this script.
set -euo pipefail

SECRETS_DIR="/workspace/.secrets"
ENV_FILE="$SECRETS_DIR/runpod_billing.env"
COMFYUI_DIR="/workspace/runpod-slim/ComfyUI"
VENV_DIR="$COMFYUI_DIR/.venv-cu128"
ARGS_FILE="/workspace/runpod-slim/comfyui_args.txt"
PORT=8188
HEALTH_URL="http://127.0.0.1:${PORT}/"
BILLING_URL="http://127.0.0.1:${PORT}/h3-mobile/api/pod-billing"
RESTART_LOG="/workspace/runpod-slim/comfyui_restart.log"

echo "=== H3 Mobile: RunPod Billing API Key setup ==="
echo "Used ONLY for account balance (GraphQL clientBalance)."
echo "Stored locally at $ENV_FILE (chmod 600). Never printed, logged, or committed."
echo

read -r -s -p "Billing API Key: " BILLING_KEY
echo
echo

if [ -z "$BILLING_KEY" ]; then
    echo "No key entered. Aborting - nothing was changed." >&2
    exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
echo '*' > "$SECRETS_DIR/.gitignore"

# Write via temp file + mv (atomic, and the key only ever exists as a bash
# builtin's argument, so it never appears as a separate process in `ps`).
TMP_FILE="$(mktemp "$SECRETS_DIR/.runpod_billing.XXXXXX")"
printf 'RUNPOD_BILLING_API_KEY=%s\n' "$BILLING_KEY" > "$TMP_FILE"
chmod 600 "$TMP_FILE"
mv "$TMP_FILE" "$ENV_FILE"
unset BILLING_KEY TMP_FILE

echo "Saved to $ENV_FILE (chmod 600)."
echo

# --- Stop the current generation job (if any) and the ComfyUI process ---
echo "Interrupting any running job and clearing the queue..."
curl -s -X POST "http://127.0.0.1:${PORT}/interrupt" >/dev/null 2>&1 || true
curl -s -X POST "http://127.0.0.1:${PORT}/queue" -H "Content-Type: application/json" -d '{"clear": true}' >/dev/null 2>&1 || true

OLD_PID="$(pgrep -f "python main.py --listen 0.0.0.0 --port ${PORT}" || true)"
if [ -n "$OLD_PID" ]; then
    echo "Stopping current ComfyUI process (PID $OLD_PID)..."
    kill "$OLD_PID"
    while kill -0 "$OLD_PID" 2>/dev/null; do
        sleep 1
    done
    echo "Stopped."
else
    echo "No running ComfyUI process found - continuing to start one."
fi

# --- Restart ComfyUI with the billing key loaded. Pod/container itself is NOT restarted. ---
echo "Restarting ComfyUI..."
set -a
source "$ENV_FILE"
set +a

cd "$COMFYUI_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

FIXED_ARGS="--listen 0.0.0.0 --port ${PORT} --enable-cors-header"
if [ -s "$ARGS_FILE" ]; then
    CUSTOM_ARGS="$(grep -v '^#' "$ARGS_FILE" | tr '\n' ' ')"
    if [ -n "$CUSTOM_ARGS" ]; then
        FIXED_ARGS="$FIXED_ARGS $CUSTOM_ARGS"
    fi
fi

nohup python main.py $FIXED_ARGS > "$RESTART_LOG" 2>&1 &
disown 2>/dev/null || true

echo "Waiting for ComfyUI to come back up on port ${PORT}..."
UP=0
for i in $(seq 1 60); do
    if curl -s -o /dev/null "$HEALTH_URL"; then
        UP=1
        break
    fi
    sleep 3
done

if [ "$UP" -ne 1 ]; then
    echo "ComfyUI did not come back up within the timeout. Check $RESTART_LOG" >&2
    exit 1
fi
echo "ComfyUI is back up."
echo

# --- Check billing (numbers only - never the raw response or the key) ---
echo "Checking /h3-mobile/api/pod-billing ..."
RESPONSE="$(curl -s "$BILLING_URL")"
python3 - "$RESPONSE" <<'PYEOF'
import json
import sys

try:
    data = json.loads(sys.argv[1])
except Exception as exc:
    print(f"Failed to parse billing response: {exc}")
    sys.exit(1)


def fmt(v):
    return v if v is not None else "null"


print(f"balance: {fmt(data.get('balance'))}")
print(f"spend_rate: {fmt(data.get('spend_rate'))}")
print(f"estimated_hours_remaining: {fmt(data.get('estimated_hours_remaining'))}")
print(f"cost_per_hour (this pod only, auxiliary): {fmt(data.get('cost_per_hour'))}")
if data.get("error"):
    print(f"note: {data['error']}")
PYEOF

echo
echo "Done."
