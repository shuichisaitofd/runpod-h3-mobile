# Phase 2: build ComfyUI/user/default/workflows/H3_CharacterSwap.json from the LoRA author's example (UI format).
# Changes: drop the Turbo switch path, FP16 video VAE, cut-free slice of the (24 fps) source video,
# and file names / seed / prompt / length taken from phase2_charswap_api.json. Same model path as phase2_charswap_api.json.
import json, sys

src, dst = sys.argv[1], sys.argv[2]
api = json.load(open("/workspace/runpod-slim/phase2_charswap_api.json"))
d = json.load(open(src))
nodes = {n["id"]: n for n in d["nodes"]}

drop = {141, 142, 143, 144, 145, 146}
dropped_links = {l[0] for l in d["links"] if l[1] in drop or l[3] in drop}
d["nodes"] = [n for n in d["nodes"] if n["id"] not in drop]
d["links"] = [l for l in d["links"] if l[0] not in dropped_links]
for n in d["nodes"]:
    for o in n.get("outputs", []):
        if o.get("links"):
            o["links"] = [x for x in o["links"] if x not in dropped_links] or None
    for i in n.get("inputs", []):
        if i.get("link") in dropped_links:
            i["link"] = None

next_link = d["last_link_id"]


def link(origin, oslot, target, tslot, typ):
    global next_link
    next_link += 1
    d["links"].append([next_link, origin, oslot, target, tslot, typ])
    out = nodes[origin]["outputs"][oslot]
    out["links"] = (out.get("links") or []) + [next_link]
    nodes[target]["inputs"][tslot]["link"] = next_link


def set_widgets(nid, named):
    n = nodes[nid]
    n["widgets_values_named"] = dict(n.get("widgets_values_named", {}), **named)


# BasicScheduler steps back to a plain widget; guider takes the character-swap LoRA model directly.
nodes[124]["inputs"] = [i for i in nodes[124]["inputs"] if i["name"] != "steps"]
nodes[124]["widgets_values"] = ["simple", 20, 1]
set_widgets(124, {"scheduler": "simple", "steps": 20, "denoise": 1})
link(147, 0, 126, 0, "MODEL")

nodes[119]["widgets_values"] = ["minimax_h3_video_vae_fp16.safetensors"]
set_widgets(119, {"vae_name": "minimax_h3_video_vae_fp16.safetensors"})
nodes[119].get("properties", {}).pop("models", None)
nodes[129]["widgets_values"] = [api["50"]["inputs"]["noise_seed"], "fixed"]
set_widgets(129, {"noise_seed": api["50"]["inputs"]["noise_seed"]})
nodes[137]["widgets_values"] = [api["24"]["inputs"]["image"], "image"]
set_widgets(137, {"image": api["24"]["inputs"]["image"]})
nodes[139]["widgets_values"] = [api["20"]["inputs"]["file"], "image"]
set_widgets(139, {"file": api["20"]["inputs"]["file"]})
nodes[138]["widgets_values"] = [api["40"]["inputs"]["prompt"]]
nodes[92]["widgets_values"][0] = "phase2/phase2_charswap"
nodes[115]["widgets_values"][1] = 0.5
nodes[132]["widgets_values"] = [api["33"]["inputs"]["value"]]

# Source video: LoadVideo -> Video Slice (cut-free window) -> GetVideoComponents.
sl = api["21"]["inputs"]
x, y = nodes[139]["pos"]
old = next(l for l in d["links"] if l[1] == 139 and l[3] == 148)
d["links"].remove(old)
nodes[139]["outputs"][0]["links"] = []
nodes[148]["inputs"][0]["link"] = None
base = {"flags": {}, "mode": 0, "order": nodes[139]["order"]}
d["nodes"].append(dict(base, id=150, type="Video Slice", pos=[x, y + 450], size=[300, 130], title="Source: cut-free window",
                       inputs=[{"name": "video", "type": "VIDEO", "link": None}],
                       outputs=[{"name": "VIDEO", "type": "VIDEO", "links": []}],
                       properties={"Node name for S&R": "Video Slice", "cnr_id": "comfy-core"},
                       widgets_values=[sl["start_time"], sl["duration"], sl["strict_duration"]]))
nodes[150] = d["nodes"][-1]
link(139, 0, 150, 0, "VIDEO")
link(150, 0, 148, 0, "VIDEO")

d["last_node_id"] = max(n["id"] for n in d["nodes"])
d["last_link_id"] = next_link
json.dump(d, open(dst, "w"), ensure_ascii=False, indent=1)
print("nodes", len(d["nodes"]), "links", len(d["links"]))
