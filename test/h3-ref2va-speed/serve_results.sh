#!/usr/bin/env bash
set -Eeuo pipefail
ARCHIVE="${1:-$(ls -1t /workspace/H3_TEST_RESULTS_*.tar.gz 2>/dev/null | head -n1 || true)}"
[ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ] || { echo "No H3_TEST_RESULTS archive found"; exit 1; }
DL=/workspace/h3-test-download
rm -rf "$DL"
mkdir -p "$DL"
cp -p "$ARCHIVE" "$DL/"

pid="$(pgrep -f 'python(3|3\.12)? .*main.py.*--port 8188' | head -n1 || true)"
if [ -n "$pid" ]; then
  echo "[DOWNLOAD] stopping ComfyUI PID $pid to reuse port 8188"
  kill "$pid" || true
  sleep 2
fi
cd "$DL"
echo "[DOWNLOAD] Open RunPod Port 8188, then click $(basename "$ARCHIVE")"
exec python3 -m http.server 8188 --bind 0.0.0.0
