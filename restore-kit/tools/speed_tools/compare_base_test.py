# Phase S: 2-row sheet at 0.00/0.92/1.83/2.79/3.71 s, top = Phase 2 baseline result, bottom = speed test result.
import sys
import av
from PIL import Image, ImageDraw

base_path, test_path, sheet_path, label = sys.argv[1:5]
IDX = [0, 22, 44, 67, 89]


def load(p):
    with av.open(p) as c:
        return [f.to_image() for f in c.decode(video=0)]


base, test = load(base_path), load(test_path)
w, h = 480, 272
sheet = Image.new("RGB", (w * len(IDX) + 90, h * 2 + 30), "white")
d = ImageDraw.Draw(sheet)
for c, i in enumerate(IDX):
    d.text((90 + c * w + 4, 4), f"frame {i} / {i / 24:.2f}s", fill="black")
    sheet.paste(base[i].resize((w, h)), (90 + c * w, 30))
    sheet.paste(test[i].resize((w, h)), (90 + c * w, 30 + h))
d.text((4, 30 + h // 2), "baseline", fill="black")
d.text((4, 30 + h + h // 2), label, fill="black")
sheet.save(sheet_path)
print("frames base", len(base), "test", len(test), "->", sheet_path)
