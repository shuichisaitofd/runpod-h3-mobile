#!/bin/bash
# Phase 2 downloads: wait for an empty ComfyUI queue, check disk, fetch to .part, verify size (and LoRA sha256), then rename.
set -euo pipefail
M=/workspace/runpod-slim/ComfyUI/models
qlen() { curl -s http://127.0.0.1:8188/queue | python3 -c 'import json,sys;q=json.load(sys.stdin);print(len(q["queue_running"])+len(q["queue_pending"]))'; }
until [ "$(qlen)" = "0" ]; do sleep 10; done
echo "queue empty $(date -Is)"
free=$(df -B1 /workspace | tail -1 | awk '{print $4}')
[ "$free" -ge 30000000000 ] || { echo "NOT ENOUGH DISK: $free bytes"; exit 1; }
echo "disk free $free bytes"

fetch() {  # url dest expected_size [expected_sha256]
    local url=$1 dest=$2 size=$3 sha=${4:-}
    local t0=$(date +%s)
    curl -fL --retry 5 --retry-delay 5 -C - -o "$dest.part" "$url"
    local got=$(stat -c %s "$dest.part")
    [ "$got" = "$size" ] || { echo "SIZE MISMATCH $dest: $got != $size"; exit 1; }
    local h=$(sha256sum "$dest.part" | cut -d' ' -f1)
    if [ -n "$sha" ] && [ "$h" != "$sha" ]; then echo "SHA256 MISMATCH $dest: $h"; exit 1; fi
    mv "$dest.part" "$dest"
    echo "OK $(basename "$dest") size=$got sha256=$h seconds=$(( $(date +%s) - t0 ))"
    echo "$h  $(basename "$dest")" >> /workspace/runpod-slim/phase2_downloads_sha256.txt
}
fetch "https://huggingface.co/akatz-ai/MiniMax-H3-Character-Swap-LoRA/resolve/main/h3_character_swap_pro4500_1000.safetensors" \
      "$M/loras/h3_character_swap_pro4500_1000.safetensors" 155110320 4b2a3f420ae804c0aa3422761ff84dbd1bf52eef6900ffab6d2e66df63cb4e79
fetch "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" \
      "$M/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" 20970379616
echo "done $(date -Is)"
