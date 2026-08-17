#!/usr/bin/env bash
set -Eeuo pipefail
COMFY="${COMFY:-/workspace/runpod-slim/ComfyUI}"
STAMP="$(date +%Y%m%d_%H%M%S)"
DIR="/workspace/H3_TEST_RESULTS_$STAMP"
ARCHIVE="$DIR.tar.gz"
mkdir -p "$DIR/videos" "$DIR/workflows" "$DIR/logs"

if [ -d "$COMFY/output/video" ]; then
  find "$COMFY/output/video" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.webm' -o -iname '*.mov' \) -exec cp -p {} "$DIR/videos/" \;
fi
if [ -d "$COMFY/user/default/workflows/H3_REF2VA_SPEED_TEST" ]; then
  cp -a "$COMFY/user/default/workflows/H3_REF2VA_SPEED_TEST/." "$DIR/workflows/"
fi
[ -f /workspace/comfyui-h3-speed-test.log ] && cp -p /workspace/comfyui-h3-speed-test.log "$DIR/logs/"

{
  echo "created=$(date -Iseconds)"
  echo "comfy=$COMFY"
  echo "gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 2>/dev/null || true)"
  echo "videos=$(find "$DIR/videos" -maxdepth 1 -type f | wc -l)"
  echo "workflows=$(find "$DIR/workflows" -maxdepth 1 -type f | wc -l)"
  echo
  echo "=== video files ==="
  find "$DIR/videos" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %f\n' | sort
  echo
  echo "=== Prompt executed timings ==="
  grep -h 'Prompt executed in' "$DIR"/logs/* 2>/dev/null || true
} > "$DIR/manifest.txt"

tar -czf "$ARCHIVE" -C /workspace "$(basename "$DIR")"
echo "[OK] $ARCHIVE"
ls -lh "$ARCHIVE"
echo
echo "To download through Port 8188 after testing:"
echo "  bash $(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/serve_results.sh $ARCHIVE"
