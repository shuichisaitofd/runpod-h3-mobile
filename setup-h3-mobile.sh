#!/usr/bin/env bash
set -Eeuo pipefail

TMP_START="/tmp/start-h3-mobile.sh"
cp /start.sh "$TMP_START"

python3 - <<'PY'
from pathlib import Path

p = Path("/tmp/start-h3-mobile.sh")
text = p.read_text()

marker = "# Warm up pip so ComfyUI-Manager"
if marker not in text:
    raise SystemExit("RunPod start.sh structure changed: insertion point not found")

block = r'''
echo "============================================="
echo "  H3 mobile auto setup"
echo "============================================="

CUSTOM="$COMFYUI_DIR/custom_nodes"
WORKFLOWS="$COMFYUI_DIR/user/default/workflows"
mkdir -p "$CUSTOM" "$WORKFLOWS"

clone_if_missing() {
    local name="$1"
    local url="$2"
    local path="$CUSTOM/$name"

    if [ -e "$path" ]; then
        echo "OK: $name already exists"
    else
        echo "Installing $name..."
        git clone --depth 1 "$url" "$path"
    fi
}

# 1) Turbo v4 + SageAttention
clone_if_missing \
  "ComfyUI-MiniMax-H3-Turbo" \
  "https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git"

if [ -d "$CUSTOM/ComfyUI-KJNodes" ]; then
    echo "OK: ComfyUI-KJNodes present"
else
    echo "WARNING: ComfyUI-KJNodes missing"
fi

if python -c "import sageattention" >/dev/null 2>&1; then
    echo "OK: SageAttention already installed"
else
    echo "Installing SageAttention 2.2.0..."
    python -m pip install sageattention==2.2.0 --no-build-isolation
    python -c "from sageattention import sageattn"
    echo "OK: SageAttention installed"
fi

# 2) Spectrum + Sol-Attn
clone_if_missing \
  "ComfyUI-Spectrum-MiniMax-H3" \
  "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git"

clone_if_missing \
  "ComfyUI-sol-attn" \
  "https://github.com/Saganaki22/ComfyUI-sol-attn.git"

RAW_BASE="https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/main/workflows"

curl -fsSL \
  "$RAW_BASE/H3_TurboV4_SageAttention_4step.json" \
  -o "$WORKFLOWS/H3_TurboV4_SageAttention_4step.json"

curl -fsSL \
  "$RAW_BASE/H3_Spectrum_SolAttn_16step.json" \
  -o "$WORKFLOWS/H3_Spectrum_SolAttn_16step.json"

echo "OK: 2 H3 workflows installed"
echo "============================================="
'''

text = text.replace(marker, block + "\n" + marker, 1)
p.write_text(text)
PY

exec bash "$TMP_START"
