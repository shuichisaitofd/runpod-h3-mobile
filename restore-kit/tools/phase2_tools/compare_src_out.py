# Phase 2: 2-row sheet, top = source window frames, bottom = generated frames at the same times.
import sys
import av
from PIL import Image, ImageDraw

src_path, out_path, sheet_path, start = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 5


def load(p):
    with av.open(p) as c:
        return [f.to_image() for f in c.decode(video=0)]


src, out = load(src_path), load(out_path)
n = min(len(out), len(src) - start)
idx = [round(i * (n - 1) / (N - 1)) for i in range(N)]
w, h = 480, 270
sheet = Image.new("RGB", (w * N + 70, h * 2 + 30), "white")
d = ImageDraw.Draw(sheet)
for c, i in enumerate(idx):
    d.text((70 + c * w + 4, 4), f"out {i} / src {start + i} / {i / 24:.2f}s", fill="black")
    sheet.paste(src[start + i].resize((w, h)), (70 + c * w, 30))
    sheet.paste(out[i].resize((w, h)), (70 + c * w, 30 + h))
d.text((4, 30 + h // 2), "source", fill="black")
d.text((4, 30 + h + h // 2), "result", fill="black")
sheet.save(sheet_path)
print("frames out", len(out), "used", idx, "->", sheet_path)
