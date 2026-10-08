#!/bin/bash
# H3 復旧キット: 新しい Pod でこのスクリプトを1回実行する。 使い方: bash restore.sh [--dry-run]
# /start.sh、.runpod-bundle-version、アプリの本番 i2v.json は変更しない。
set -euo pipefail
KIT=$(cd "$(dirname "$0")" && pwd)
W=/workspace/runpod-slim
C=$W/ComfyUI
M=$C/models
A=$C/custom_nodes/ComfyUI-H3-Mobile/api_workflows
PY=$C/.venv-cu128/bin
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
run() { if [ $DRY = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }
step() { echo; echo "=== $* ==="; }

step "1/6 ComfyUI を v0.38.0 にする"
if [ ! -d "$C/.git" ]; then echo "ERROR: $C に ComfyUI が見つかりません。Pod が起動しきってから実行してください"; exit 1; fi
if [ $DRY = 1 ]; then
    echo "  [dry-run] 戻す控え: git の HEAD と pip freeze を $W/restore_backup_* に保存"
    echo "  [dry-run] git fetch origin tag v0.38.0 && git checkout v0.38.0 (既に v0.38.0 なら何もしない)"
    echo "  [dry-run] pip install --dry-run -r requirements.txt → torch/torchvision/torchaudio が変わるなら中止"
    echo "  [dry-run] pip install -r requirements.txt"
else
    git -C "$C" rev-parse HEAD > "$W/restore_backup_git_head.txt"
    "$PY/pip" freeze > "$W/restore_backup_pip_freeze.txt" 2>/dev/null || true
    if [ "$(git -C "$C" describe --tags --exact-match 2>/dev/null || true)" != "v0.38.0" ]; then
        git -C "$C" fetch origin tag v0.38.0
        git -C "$C" checkout v0.38.0
    fi
    export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
    plan=$("$PY/pip" install --dry-run -r "$C/requirements.txt" 2>&1 || true)
    if echo "$plan" | grep -E '^Would install' | grep -E -i -w 'torch|torchvision|torchaudio|torch-[0-9]|torchvision-[0-9]|torchaudio-[0-9]' >/dev/null; then
        echo "ERROR: pip が torch を変えようとしています。中止します。内容:"; echo "$plan" | grep '^Would install'; exit 1
    fi
    "$PY/pip" install -r "$C/requirements.txt"
fi

step "2/6 Veda をコミット 60bfae6 で入れる"
V=$C/custom_nodes/Veda-on-ComfyUI
if [ ! -d "$V/.git" ]; then run git clone https://github.com/veda-sparse/Veda-on-ComfyUI.git "$V"; fi
run git -C "$V" checkout 60bfae6
run env PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt "$PY/pip" install -r "$V/requirements.txt"

step "3/6 モデルのダウンロード(sha256 で確認)"
[ $DRY = 1 ] || { free=$(df -B1 /workspace | tail -1 | awk '{print $4}'); echo "  空き容量: $((free/1000000000)) GB"; }
while IFS=$'\t' read -r rel size sha url; do
    case "$rel" in "#"*|"") continue;; esac
    dest=$M/$rel
    if [ $DRY = 1 ]; then echo "  [dry-run] $rel ($((size/1000000)) MB) 既にあれば sha256 を確認、無ければ $url から取得"; continue; fi
    if [ -f "$dest" ] && [ "$(stat -c %s "$dest")" = "$size" ] && [ "$(sha256sum "$dest" | cut -d' ' -f1)" = "$sha" ]; then
        echo "  OK(既にある): $rel"; continue
    fi
    mkdir -p "$(dirname "$dest")"
    curl -fL --retry 5 --retry-delay 5 -C - -o "$dest.part" "$url"
    [ "$(stat -c %s "$dest.part")" = "$size" ] || { echo "ERROR: サイズが違います: $rel"; exit 1; }
    [ "$(sha256sum "$dest.part" | cut -d' ' -f1)" = "$sha" ] || { echo "ERROR: sha256 が違います: $rel"; exit 1; }
    mv "$dest.part" "$dest"
    echo "  OK(取得): $rel"
done < "$KIT/models.tsv"

step "4/6 ワークフローと作業スクリプトの配置"
run mkdir -p "$C/user/default/workflows"
run cp "$KIT/workflows/H3_CharacterSwap.json" "$KIT/workflows/H3_CharacterSwap_Fast.json" "$C/user/default/workflows/"
run cp "$KIT/workflows/phase2_charswap_api.json" "$KIT/workflows/speed_T8_s6_refsmall.json" "$W/"
run cp -r "$KIT/tools/phase1_tools" "$KIT/tools/phase2_tools" "$KIT/tools/speed_tools" "$W/"
run mkdir -p "$W/backup_h3mobile_20261008/api_workflows"
if [ ! -f "$W/backup_h3mobile_20261008/api_workflows/i2v.json" ]; then
    run cp "$KIT/app_workflows/i2v.json.original" "$W/backup_h3mobile_20261008/api_workflows/i2v.json"
fi
if [ -d "$A" ]; then
    (cd "$KIT/app_workflows" && [ $DRY = 1 ] || sha256sum -c SHA256SUMS >/dev/null) || { echo "ERROR: Veda 入りワークフローが壊れています"; exit 1; }
    run cp "$KIT/app_workflows/i2v.json.veda90" "$KIT/app_workflows/i2v.json.veda80" "$KIT/app_workflows/i2v.json.veda70" "$A/"
else
    echo "  注意: アプリ(ComfyUI-H3-Mobile)が見つかりません。i2v.json.vedaNN は置きません"
fi

step "5/6 切り替えコマンドの設置"
run mkdir -p /workspace/bin
run cp "$KIT/bin/veda_on" "$KIT/bin/veda_on80" "$KIT/bin/veda_pct" "$KIT/bin/veda_off" "$KIT/bin/veda_status" /workspace/bin/
run chmod +x /workspace/bin/veda_on /workspace/bin/veda_on80 /workspace/bin/veda_pct /workspace/bin/veda_off /workspace/bin/veda_status

step "6/6 ComfyUI の再起動"
run bash "$KIT/restart_comfyui.sh"
if [ $DRY = 0 ]; then
    for i in $(seq 60); do curl -sf http://127.0.0.1:8188/system_stats >/dev/null && break; sleep 2; done
    curl -sf http://127.0.0.1:8188/system_stats | head -c 120; echo
fi
echo; echo "完了($([ $DRY = 1 ] && echo dry-run || echo 実行済み))。本番の i2v.json は変更していません。/workspace/bin/veda_status で現在の設定を確認できます。"
