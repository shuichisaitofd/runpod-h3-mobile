# Phase 1: 20 s I2V A/B at 4 steps and 0.5 MP; built from the 14 s 4-step pair.
import json

PROMPT = ("Live-action video, plain white studio background, steady camera, one continuous shot. "
          "The same shocked man in the dark suit keeps moving the whole time: "
          "he gasps and throws both hands up beside his face, "
          "then staggers backward step by step, "
          "waves both arms wildly over his head, "
          "points off to the left while shouting, "
          "turns his body and points to the right, "
          "grabs his head with both hands and shakes it, "
          "leans forward and waves both hands in front of his chest in disbelief, "
          "then claps his hands together twice, "
          "spreads both arms wide and shrugs, "
          "covers his mouth with one hand and shakes his head, "
          "and finally throws both fists up and shouts again. "
          "Natural, continuous body movement, the same person throughout. "
          "Audio: a loud gasp, then his surprised shouting voice, two hand claps and heavy breathing.")
for name in ("A", "B90"):
    g = json.load(open(f"/workspace/runpod-slim/phase1_I2V14s4_{name}.json"))
    g["119"]["inputs"]["megapixels"] = 0.5
    g["105:111"]["inputs"]["value"] = 20
    g["105:104"]["inputs"]["prompt"] = PROMPT
    g["92"]["inputs"]["filename_prefix"] = f"phase1_I2V20_{name}"
    json.dump(g, open(f"/workspace/runpod-slim/phase1_I2V20_{name}.json", "w"), ensure_ascii=False, indent=1)
a = round(20 * 24); print("frames:", a + (5 - a % 17) % 17)
