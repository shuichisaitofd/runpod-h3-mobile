# Phase S: rows of results at chosen frame indices. Usage: OUT IDX(comma) label=path...
import sys
import av
from PIL import Image, ImageDraw

out_path, idx = sys.argv[1], [int(x) for x in sys.argv[2].split(",")]
rows = [a.split("=", 1) for a in sys.argv[3:]]


def load(p):
    with av.open(p) as c:
        return [f.to_image() for f in c.decode(video=0)]


vids = [(name, load(p)) for name, p in rows]
w, h = 440, 250
sheet = Image.new("RGB", (w * len(idx) + 130, h * len(vids) + 30), "white")
d = ImageDraw.Draw(sheet)
for c, i in enumerate(idx):
    d.text((130 + c * w + 4, 4), f"frame {i} / {i / 24:.2f}s", fill="black")
    for r, (name, fr) in enumerate(vids):
        sheet.paste(fr[i].resize((w, h)), (130 + c * w, 30 + r * h))
for r, (name, _) in enumerate(vids):
    d.text((4, 30 + r * h + h // 2), name, fill="black")
sheet.save(out_path)
print(out_path)
