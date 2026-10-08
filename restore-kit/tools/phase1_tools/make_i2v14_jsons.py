# Phase 1: 14 s I2V A/B, same as the 5 s I2V pair except length, prompt and file names.
import json

PROMPT = ("Live-action video, plain white studio background, steady camera, one continuous shot. "
          "The same shocked man in the dark suit keeps moving the whole time: "
          "he gasps and throws both hands up beside his face, "
          "then staggers backward step by step, "
          "waves both arms wildly over his head, "
          "points off to the left while shouting, "
          "turns his body and points to the right, "
          "grabs his head with both hands and shakes it, "
          "then leans forward and waves both hands in front of his chest in disbelief. "
          "Natural, continuous body movement, the same person throughout. "
          "Audio: a loud gasp, then his surprised shouting voice and heavy breathing.")
for name in ("A", "B90"):
    g = json.load(open(f"/workspace/runpod-slim/phase1_I2V_{name}.json"))
    g["105:111"]["inputs"]["value"] = 14
    g["105:104"]["inputs"]["prompt"] = PROMPT
    g["92"]["inputs"]["filename_prefix"] = f"phase1_I2V14_{name}"
    json.dump(g, open(f"/workspace/runpod-slim/phase1_I2V14_{name}.json", "w"), ensure_ascii=False, indent=1)
a = round(14 * 24); print("frames:", a + (5 - a % 17) % 17)
