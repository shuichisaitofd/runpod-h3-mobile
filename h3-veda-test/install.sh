#!/bin/bash
# H3 Veda テスト版を Pod に入れる(または --remove で外す)。
# 本番のアプリ(ComfyUI-H3-Mobile)と i2v.json は変更しない。入れるのは新しいフォルダ１つだけ。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
C=${H3_COMFY_DIR:-/workspace/runpod-slim/ComfyUI}
N=$C/custom_nodes
DEST=$N/ComfyUI-H3-Veda-Test

restart_comfyui() {
    [ "${H3_NO_RESTART:-0}" = 1 ] && { echo "(再起動は省略)"; return; }
    cd "$C"
    source .venv-cu128/bin/activate
    export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
    for p in $(pgrep -f '^python main.py --listen 0.0.0.0 --port 8188' || true); do kill "$p"; done
    for i in $(seq 30); do pgrep -f '^python main.py --listen 0.0.0.0 --port 8188' >/dev/null || break; sleep 1; done
    nohup python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header >> /workspace/runpod-slim/comfyui.log 2>&1 &
    echo "ComfyUI を再起動しています(1〜2分かかります)"
    for i in $(seq 90); do curl -sf http://127.0.0.1:8188/system_stats >/dev/null && { echo "ComfyUI が起動しました"; return; }; sleep 2; done
    echo "注意: 3分待っても起動を確認できません。/workspace/runpod-slim/comfyui.log を見てください"
}

if [ "${1:-}" = "--remove" ]; then
    rm -rf "$DEST"
    echo "テスト版を外しました。本番のアプリは元のままです。"
    restart_comfyui
    exit 0
fi

[ -d "$N/ComfyUI-H3-Mobile" ] || { echo "ERROR: $N/ComfyUI-H3-Mobile (H3 Mobile) が見つかりません"; exit 1; }
[ -d "$N/Veda-on-ComfyUI" ] || echo "注意: Veda ノード(Veda-on-ComfyUI)が入っていません。先に restore.sh を実行してください。このまま続けるとページは開けますが、ONにすると生成が失敗します"
[ -f "$C/models/veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors" ] || echo "注意: Veda の予測モデルファイルが見つかりません(models/veda/)"

mkdir -p "$DEST"
cp "$HERE/__init__.py" "$HERE/veda-panel.js" "$DEST/"
echo "入れました: $DEST"
restart_comfyui
echo
echo "スマホで開くURL: いつものアプリのURLの末尾を /h3-veda/ にしたもの"
echo "(いつもが https://xxxx-8188.proxy.runpod.net/h3-mobile/ なら https://xxxx-8188.proxy.runpod.net/h3-veda/ )"
