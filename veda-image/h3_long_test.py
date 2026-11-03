#!/usr/bin/env python3
"""H3 long-video test (Herrgott's H3 Infinite Continuation Suite v1.4, Native Masked AV).

Takes the most recent I2V job that the H3 Mobile / H3 Studio page ran on this Pod (same image,
prompt, 10Eros model, Turbo LoRA 4 steps, Veda and extra LoRAs), and runs:
  clip 1  = the same I2V job, but built with H3ContinuousStartV14 and saving its AV latent
  clip 2+ = H3ContinuousContinueV14 from the previous clip's latent (39-frame protected context)
  final   = H3ContinuousStitchSavedChainV14 joins all clips into one MP4
The videos land in output/video/h3long/ so they also show up in the page's history.

Usage (Jupyter terminal):  python3 /opt/h3-veda/h3_long_test.py [--clips 2] [--seconds 10]
"""
import argparse, copy, json, sys, time, urllib.error, urllib.request

API = "http://127.0.0.1:8188"


def call(path, body=None, timeout=60):
    req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


INFO = {}


def info(cls):
    if cls not in INFO:
        INFO[cls] = call("/object_info/" + cls)[cls]
    return INFO[cls]


def out_slot(cls, name):
    names = info(cls).get("output_name") or []
    if name not in names:
        raise SystemExit(f"{cls} has no output '{name}' (outputs: {names})")
    return names.index(name)


def node(cls, **given):
    """API node; required widget inputs that are not given get their default from /object_info."""
    spec = info(cls)["input"]
    inputs = {}
    for name, s in (spec.get("required") or {}).items():
        if name in given:
            continue
        t, opts = (s[0], s[1] if len(s) > 1 and isinstance(s[1], dict) else {})
        if isinstance(t, list):
            inputs[name] = opts.get("default", t[0] if t else "")
        elif "default" in opts:
            inputs[name] = opts["default"]
    for name, v in given.items():
        if v is not None:
            inputs[name] = v
    return {"class_type": cls, "inputs": inputs}


def latest_i2v_graph():
    hist = call("/history?max_items=200")
    best = None
    for pid, item in hist.items():
        p = item.get("prompt") or []
        g = p[2] if len(p) > 2 else None
        if isinstance(g, dict) and "105:104" in g and g["105:104"].get("class_type") == "MiniMaxH3ImageToVideo":
            num = p[0] if p else 0
            if best is None or num > best[0]:
                best = (num, pid, g)
    if not best:
        raise SystemExit("No I2V job found in this Pod's history. Run one normal 画像から動画 job from the page first.")
    return best[1], copy.deepcopy(best[2])


def run(graph, label):
    for n in graph.values():
        n.pop("_meta", None)
    t0 = time.time()
    try:
        r = call("/prompt", {"prompt": graph, "client_id": "h3-long-test"})
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{label}: ComfyUI rejected the workflow: {e.read().decode()[:3000]}")
    pid = r["prompt_id"]
    log(f"{label}: queued {pid}")
    while True:
        time.sleep(3)
        h = call(f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error" or not st.get("completed", True):
                msgs = [m for m in st.get("messages", []) if m[0] in ("execution_error", "execution_interrupted")]
                raise SystemExit(f"{label}: failed after {time.time()-t0:.0f}s: {json.dumps(msgs, ensure_ascii=False)[:3000]}")
            files = []
            for o in h[pid].get("outputs", {}).values():
                for k in ("images", "gifs", "videos", "video", "text"):
                    for f in o.get(k, []) if isinstance(o.get(k), list) else []:
                        files.append(f.get("filename", f) if isinstance(f, dict) else f)
            log(f"{label}: done in {time.time()-t0:.0f}s  outputs={files}")
            return h[pid]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=2, help="number of clips in the chain (>=2)")
    ap.add_argument("--seconds", type=float, default=None, help="new seconds per continuation clip (default: same as clip 1)")
    ap.add_argument("--context", default="39", choices=["39", "90", "141", "192"])
    ap.add_argument("--prompt", default=None, help="prompt for the continuation clips (default: same as clip 1)")
    a = ap.parse_args()

    for c in ("H3ContinuousStartV14", "H3ContinuousContinueV14", "H3ContinuousSaveLatent", "H3ContinuousLoadLatent",
              "H3ContinuousAnalyzeHandoverV14", "H3ContinuousStitchOutputV14", "H3ContinuousStitchSavedChainV14"):
        try:
            info(c)
        except Exception as e:
            raise SystemExit(f"Node {c} is not available in ComfyUI ({e}). Is the long-video node pack installed and ComfyUI restarted?")

    src_id, base = latest_i2v_graph()
    i2v = base["105:104"]["inputs"]
    seconds = None
    sec_src = base.get("105:111", {}).get("inputs", {}).get("value")
    if isinstance(sec_src, (int, float)):
        seconds = float(sec_src)
    seconds = seconds or 10.0
    cont_seconds = a.seconds or seconds
    prompt1 = i2v.get("prompt", "")
    prompt2 = a.prompt if a.prompt is not None else prompt1
    run_id = time.strftime("%Y%m%d-%H%M%S")
    prefix = f"h3long/{run_id}/clip"
    veda = base.get("105:200", {}).get("inputs") if "105:200" in base else None
    log(f"source job {src_id}: {seconds:g}s, model={base.get('105:6',{}).get('inputs',{}).get('unet_name')}, "
        f"veda={'%s/%s' % (veda.get('generated_sparsity'), veda.get('reference_sparsity')) if veda else 'off'}, run={run_id}")

    def outputs(g, cond_node, latent_slot_name, head_frames, idx):
        # clip output: decoded images -> handover analysis -> Full output -> SaveVideo; AV latent -> SaveLatent
        h_slot = out_slot("H3ContinuousAnalyzeHandoverV14", "handover")
        g["L_an"] = node("H3ContinuousAnalyzeHandoverV14", images=["105:10", 0])
        g["L_out"] = node("H3ContinuousStitchOutputV14", images=["105:10", 0], audio=["105:23", 0],
                          handover=["L_an", h_slot], output_mode="Full", head_context_frames=head_frames)
        g["105:91"]["inputs"]["images"] = ["L_out", out_slot("H3ContinuousStitchOutputV14", "images")]
        g["105:91"]["inputs"]["audio"] = ["L_out", out_slot("H3ContinuousStitchOutputV14", "audio")]
        g["92"]["inputs"]["filename_prefix"] = f"video/h3long/{run_id}_clip{idx}"
        g["L_save"] = node("H3ContinuousSaveLatent", latent=["105:14", 0], filename_prefix=prefix, clip_index=idx,
                           handover=["L_an", h_slot], head_context_frames=head_frames)
        g["105:16"]["inputs"]["conditioning"] = [cond_node, out_slot(g[cond_node]["class_type"], "positive")]
        g["105:14"]["inputs"]["latent_image"] = [cond_node, out_slot(g[cond_node]["class_type"], latent_slot_name)]
        return g

    # clip 1
    g = copy.deepcopy(base)
    g["L_start"] = node("H3ContinuousStartV14", clip=i2v["clip"], vae=i2v["vae"], prompt=prompt1,
                        width=i2v["width"], height=i2v["height"], duration=seconds, first_frame=i2v["first_frame"])
    del g["105:104"]
    g = outputs(g, "L_start", "latent", None, 1)
    run(g, "clip 1")

    # clip 2..N
    for idx in range(2, max(2, a.clips) + 1):
        g = copy.deepcopy(base)
        g["105:15"]["inputs"]["noise_seed"] = int(g["105:15"]["inputs"].get("noise_seed", 0)) + idx
        g["L_load"] = node("H3ContinuousLoadLatent", latent_path=f"h3long/{run_id}", clip_index=idx - 1)
        g["L_cont"] = node("H3ContinuousContinueV14", clip=i2v["clip"], vae=i2v["vae"],
                           previous_latent=["L_load", out_slot("H3ContinuousLoadLatent", "latent")],
                           handover=["L_load", out_slot("H3ContinuousLoadLatent", "handover")],
                           prompt=prompt2, width=i2v["width"], height=i2v["height"], duration=cont_seconds,
                           masked_context_frames=a.context, duration_mode="Net New Content",
                           audio_tail_carryover="Full Previous Tail")
        del g["105:104"]
        head = ["L_cont", out_slot("H3ContinuousContinueV14", "actual_head_context_frames")]
        g = outputs(g, "L_cont", "latent", head, idx)
        run(g, f"clip {idx}")

    # stitch everything into one MP4
    g = {
        "v": copy.deepcopy(base["105:11"]), "a": copy.deepcopy(base["105:24"]),
        "s": node("H3ContinuousStitchSavedChainV14", video_vae=["v", 0], audio_vae=["a", 0],
                  latent_prefix=prefix, first_clip=1, last_clip=max(2, a.clips),
                  filename_prefix=f"video/h3long/{run_id}_stitched"),
    }
    res = run(g, "stitch")
    log("stitch result:", json.dumps(res.get("outputs", {}), ensure_ascii=False)[:1500])
    log(f"finished. Look in output/video/h3long/ (run {run_id}).")


if __name__ == "__main__":
    main()
