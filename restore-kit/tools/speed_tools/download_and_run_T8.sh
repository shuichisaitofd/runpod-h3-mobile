#!/bin/bash
# Phase S test 2: wait for an empty queue, fetch the official Ref2VA Turbo 8-step LoRA (verify size + sha256), run speed_T8_s6.json.
set -euo pipefail
cd /workspace/runpod-slim
qlen() { curl -s http://127.0.0.1:8188/queue | python3 -c 'import json,sys;q=json.load(sys.stdin);print(len(q["queue_running"])+len(q["queue_pending"]))'; }
until [ "$(qlen)" = "0" ]; do sleep 5; done
D=ComfyUI/models/loras/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors
t0=$(date +%s)
curl -fL --retry 5 --retry-delay 5 -C - -o "$D.part" "https://huggingface.co/lightx2v/Minimax-h3-Turbo/resolve/main/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors"
size=$(stat -c %s "$D.part"); h=$(sha256sum "$D.part" | cut -d' ' -f1)
[ "$size" = "1956193000" ] || { echo "SIZE MISMATCH $size"; exit 1; }
[ "$h" = "6a56f41ab4229c9dd845b9501bbd475ee57e112d846cf2e819d534a1ae928c5a" ] || { echo "SHA256 MISMATCH $h"; exit 1; }
mv "$D.part" "$D"; echo "$h  $(basename "$D")" >> speed_results/downloads_sha256.txt
echo "download OK size=$size sha256=$h seconds=$(( $(date +%s) - t0 ))"
until [ "$(qlen)" = "0" ]; do sleep 5; done
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu,clocks.sm,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader -l 2 > speed_results/T8_s6_gpu.csv & SMI=$!
echo "===== speed T8_s6 $(date -Is) =====" >> phase1_comfyui.log
python3 -I phase1_tools/run_bench.py speed_T8_s6.json 757358688076805 speed_T8_s6 > speed_results/T8_s6.json || true
kill $SMI
grep -E '"status"|"error"|total_s|sampling_s|peak_gpu' speed_results/T8_s6.json
echo "done $(date -Is)"
