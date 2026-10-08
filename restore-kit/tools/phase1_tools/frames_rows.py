# Phase 1: stack N evenly spaced frames from several videos, one row per video (labels given as name=path).
import sys
import av
import numpy as np
from PIL import Image, ImageDraw

out_path, N = sys.argv[1], int(sys.argv[2])
rows = [a.split("=", 1) for a in sys.argv[3:]]


def load(path):
    with av.open(path) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


vids = []
for name, path in rows:
    fr = load(path)
    small = [f[::4, ::4].astype(np.float32) for f in fr]
    d = np.array([np.abs(small[i] - small[i - 1]).mean() for i in range(1, len(small))])
    j = np.abs(np.diff([f.mean() for f in small]))
    bg = np.abs(np.diff([f[:, :30].mean() for f in small]))
    top = sorted((np.argsort(-d)[:5] + 1).tolist())
    print(name, len(fr), "frames | motion per 2s:", [round(float(d[i:i + 48].mean()), 1) for i in range(0, len(d), 48)],
          "| biggest changes:", top, "| brightness step med %.2f max %.2f | bg step med %.2f max %.2f" % (np.median(j), j.max(), np.median(bg), bg.max()))
    vids.append((name, fr))
n = min(len(fr) for _, fr in vids)
idx = [round(i * (n - 1) / (N - 1)) for i in range(N)]
print("sampled frames:", idx, "seconds:", [round(i / 24, 2) for i in idx])
w, h = 360, 240
sheet = Image.new("RGB", (w * N + 70, h * len(vids) + 30), "white")
draw = ImageDraw.Draw(sheet)
for col, i in enumerate(idx):
    draw.text((70 + col * w + 4, 4), f"frame {i} / {i / 24:.2f}s", fill="black")
    for row, (name, fr) in enumerate(vids):
        sheet.paste(Image.fromarray(fr[i]).resize((w, h), Image.LANCZOS), (70 + col * w, 30 + row * h))
for row, (name, _) in enumerate(vids):
    draw.text((4, 30 + row * h + h // 2), name, fill="black")
sheet.save(out_path)
print(out_path)
