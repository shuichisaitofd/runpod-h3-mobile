# Phase 1: 14 s I2V A/B at 4 steps; only steps and file names differ from the 8-step pair.
import json

for name in ("A", "B90"):
    g = json.load(open(f"/workspace/runpod-slim/phase1_I2V14_{name}.json"))
    g["105:9"]["inputs"]["steps"] = 4
    g["92"]["inputs"]["filename_prefix"] = f"phase1_I2V14s4_{name}"
    json.dump(g, open(f"/workspace/runpod-slim/phase1_I2V14s4_{name}.json", "w"), ensure_ascii=False, indent=1)
