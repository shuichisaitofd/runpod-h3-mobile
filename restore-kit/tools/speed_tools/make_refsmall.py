# Phase S: add an ImageScale (area, center crop) between GetVideoComponents and the Ref2VA <Video 1> input,
# so the reference video matches the output size. Usage: make_refsmall.py SRC.json DST.json WIDTH HEIGHT PREFIX
import json, sys

src, dst, w, h, prefix = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
g = json.load(open(src))
assert g["40"]["inputs"]["ref_videos.ref_video_0"] == ["23", 0]
g["25"] = {"class_type": "ImageScale", "inputs": {"image": ["23", 0], "upscale_method": "area", "width": w, "height": h, "crop": "center"}}
g["40"]["inputs"]["ref_videos.ref_video_0"] = ["25", 0]
g["92"]["inputs"]["filename_prefix"] = prefix
json.dump(g, open(dst, "w"), ensure_ascii=False, indent=1)
print(dst)
