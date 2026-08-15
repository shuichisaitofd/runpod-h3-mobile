#!/usr/bin/env bash
set -Eeuo pipefail

TMP_START="/tmp/start-h3-mobile.sh"
cp /start.sh "$TMP_START"

python3.12 - <<'PY'
from pathlib import Path

p = Path('/tmp/start-h3-mobile.sh')
text = p.read_text()
marker = 'python -m pip --version > /dev/null 2>&1'
if marker not in text:
    raise SystemExit('RunPod start.sh structure changed: insertion point not found')

block = r'''
# -------------------------------------------------------------------------
# H3 MOBILE: copy extra custom nodes into the real ComfyUI after first setup
# -------------------------------------------------------------------------
mkdir -p "$COMFYUI_DIR/custom_nodes"
for src in /opt/h3-custom-nodes/*; do
    [ -e "$src" ] || continue
    name=$(basename "$src")
    dest="$COMFYUI_DIR/custom_nodes/$name"
    if [ -e "$dest" ]; then
        echo "H3 mobile: $name already present"
    else
        echo "H3 mobile: installing $name"
        cp -a "$src" "$dest"
    fi
done

if python -c "import sageattention" >/dev/null 2>&1; then
    echo "H3 mobile: SageAttention OK"
else
    echo "H3 mobile: WARNING SageAttention import failed"
fi
# -------------------------------------------------------------------------
'''

text = text.replace(marker, block + '\n' + marker, 1)
p.write_text(text)
PY

exec bash "$TMP_START" "$@"
