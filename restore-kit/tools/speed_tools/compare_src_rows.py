# Phase S: rows = source window + results, N evenly spaced frames over the clip. Usage: OUT START N label=path...
import sys
import av
from PIL import Image, ImageDraw

out_path, start, N = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rows = [a.split("=", 1) for a in sys.argv[4:]]


def load(p):
    with av.open(p) as c:
        return [f.to_image() for f in c.decode(video=0)]


src = load("/workspace/runpod-slim/ComfyUI/input/phase2_source.mp4")
vids = [(name, load(p)) for name, p in rows]
n = min(len(v) for _, v in vids)
idx = [round(i * (n - 1) / (N - 1)) for i in range(N)]
allrows = [("source", src[start:start + n])] + vids
w, h = 480, 270
sheet = Image.new("RGB", (w * N + 110, h * len(allrows) + 30), "white")
d = ImageDraw.Draw(sheet)
for c, i in enumerate(idx):
    d.text((110 + c * w + 4, 4), f"out {i} ({i / 24:.2f}s) / src {start + i}", fill="black")
    for r, (name, fr) in enumerate(allrows):
        sheet.paste(fr[i].resize((w, h)), (110 + c * w, 30 + r * h))
for r, (name, _) in enumerate(allrows):
    d.text((4, 30 + r * h + h // 2), name, fill="black")
sheet.save(out_path)
print(out_path, idx)
