# Phase 1: find shot cuts, then stack N (default 8) evenly spaced frames: A on top, B below.
import sys
import av
import numpy as np
from PIL import Image, ImageDraw

a_path, b_path, out_path = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 8


def load(path):
    with av.open(path) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


A, B = load(a_path), load(b_path)
for name, fr in (("A", A), ("B", B)):
    small = [f[::8, ::8].astype(np.float32) for f in fr]
    d = [float(np.abs(small[i] - small[i - 1]).mean()) for i in range(1, len(small))]
    top = sorted(range(len(d)), key=lambda i: -d[i])[:5]
    print(name, "frames", len(fr), "biggest changes (frame:mean diff):", [(i + 1, round(d[i], 1)) for i in sorted(top)], "median", round(float(np.median(d)), 1))

n = min(len(A), len(B))
idx = [round(i * (n - 1) / (N - 1)) for i in range(N)]
print("sampled frames:", idx, "seconds:", [round(i / 24, 2) for i in idx])
w, h = 448, 256
sheet = Image.new("RGB", (w * N + 60, h * 2 + 30), "white")
draw = ImageDraw.Draw(sheet)
for col, i in enumerate(idx):
    draw.text((60 + col * w + 4, 4), f"frame {i} / {i / 24:.2f}s", fill="black")
    for row, fr in enumerate((A, B)):
        sheet.paste(Image.fromarray(fr[i]).resize((w, h), Image.LANCZOS), (60 + col * w, 30 + row * h))
draw.text((4, 30 + h // 2), "A", fill="black")
draw.text((4, 30 + h + h // 2), "B90", fill="black")
sheet.save(out_path)
print(out_path)
