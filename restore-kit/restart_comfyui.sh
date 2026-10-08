#!/bin/bash
# ComfyUI だけを再起動する(/start.sh と同じ venv・同じ引数)。
cd /workspace/runpod-slim/ComfyUI
source .venv-cu128/bin/activate
export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
for p in $(pgrep -f '^python main.py --listen 0.0.0.0 --port 8188'); do kill $p; done
for i in $(seq 30); do pgrep -f '^python main.py --listen 0.0.0.0 --port 8188' >/dev/null || break; sleep 1; done
nohup python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header >> /workspace/runpod-slim/comfyui.log 2>&1 &
echo "started pid $!"
