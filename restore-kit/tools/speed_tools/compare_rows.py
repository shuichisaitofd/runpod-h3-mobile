# Phase S: stack several results at 0.00/0.92/1.83/2.79/3.71 s, one row per video (label=path).
import sys
import av
from PIL import Image, ImageDraw

sheet_path, rows = sys.argv[1], [a.split("=", 1) for a in sys.argv[2:]]
IDX = [0, 22, 44, 67, 89]


def load(p):
    with av.open(p) as c:
        return [f.to_image() for f in c.decode(video=0)]


vids = [(name, load(p)) for name, p in rows]
w, h = 480, 272
sheet = Image.new("RGB", (w * len(IDX) + 90, h * len(vids) + 30), "white")
d = ImageDraw.Draw(sheet)
for c, i in enumerate(IDX):
    d.text((90 + c * w + 4, 4), f"frame {i} / {i / 24:.2f}s", fill="black")
    for r, (name, fr) in enumerate(vids):
        sheet.paste(fr[i].resize((w, h)), (90 + c * w, 30 + r * h))
for r, (name, _) in enumerate(vids):
    d.text((4, 30 + r * h + h // 2), name, fill="black")
sheet.save(sheet_path)
print(sheet_path)
