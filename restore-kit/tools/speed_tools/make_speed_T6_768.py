# Phase S: speed_T6_s6.json at a fixed 768x416, 124 frames, source frames 21-144 passed as <Video 1> (cuts included).
import json

START, FRAMES = 21, 124
g = json.load(open("/workspace/runpod-slim/speed_T6_s6.json"))
g["21"]["inputs"]["start_time"] = START / 24
g["21"]["inputs"]["duration"] = FRAMES / 24
g["33"]["inputs"]["value"] = FRAMES / 24
g["40"]["inputs"]["width"] = 768
g["40"]["inputs"]["height"] = 416
for nid in ("30", "31", "32"):  # frame-size probe, unused with a fixed size
    del g[nid]
g["92"]["inputs"]["filename_prefix"] = "speed/speed_T6_768x416_5s"
json.dump(g, open("/workspace/runpod-slim/speed_T6_768x416_5s.json", "w"), ensure_ascii=False, indent=1)
