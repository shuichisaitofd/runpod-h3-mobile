# Phase 1: queue one API workflow, time sampling vs total from websocket events, track peak GPU memory.
import json, subprocess, sys, threading, time, urllib.request, uuid
import websocket

HOST = "127.0.0.1:8188"
path, seed, label = sys.argv[1], int(sys.argv[2]), sys.argv[3]
graph = json.load(open(path))
by_type = {v["class_type"]: k for k, v in graph.items()}
SAMPLE = by_type["SamplerCustomAdvanced"]
graph[by_type["RandomNoise"]]["inputs"]["noise_seed"] = seed
if seed == 1:  # warm-up runs use seed 1
    graph[by_type["SaveVideo"]]["inputs"]["filename_prefix"] += "_warmup"

peak = {"mib": 0}
stop = threading.Event()


def watch_gpu():
    while not stop.is_set():
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
        peak["mib"] = max(peak["mib"], int(out.split()[0]))
        time.sleep(0.5)


client_id = str(uuid.uuid4())
ws = websocket.create_connection(f"ws://{HOST}/ws?clientId={client_id}")
threading.Thread(target=watch_gpu, daemon=True).start()
req = urllib.request.Request(f"http://{HOST}/prompt", data=json.dumps({"prompt": graph, "client_id": client_id}).encode(), headers={"Content-Type": "application/json"})
prompt_id = json.load(urllib.request.urlopen(req))["prompt_id"]
t_submit = time.time()
starts, steps, result = {}, [], {}
while True:
    msg = ws.recv()
    if not isinstance(msg, str):
        continue
    m = json.loads(msg)
    d = m.get("data", {})
    if d.get("prompt_id") not in (None, prompt_id):
        continue
    now = time.time()
    if m["type"] == "executing" and d.get("node"):
        starts.setdefault(d["node"], now)
    elif m["type"] == "progress" and d.get("node") == SAMPLE:
        steps.append((d["value"], now))
    elif m["type"] in ("execution_success", "execution_error", "execution_interrupted"):
        result = {"status": m["type"], "end": now, "error": d.get("exception_message")}
        break
stop.set()
hist = json.load(urllib.request.urlopen(f"http://{HOST}/history/{prompt_id}"))[prompt_id]
msgs = {k: v for k, v in hist["status"]["messages"]}
order = sorted(starts.items(), key=lambda kv: kv[1])
sample_end = next((t for n, t in order if t > starts.get(SAMPLE, 1e30)), result["end"])
rep = {
    "label": label, "json": path, "seed": seed, "prompt_id": prompt_id, "status": result["status"], "error": result["error"],
    "total_s_ws": round(result["end"] - t_submit, 2),
    "total_s_history": round((msgs.get("execution_success", msgs.get("execution_error", {})).get("timestamp", 0) - msgs["execution_start"]["timestamp"]) / 1000, 2),
    "sampling_s": round(sample_end - starts[SAMPLE], 2) if SAMPLE in starts else None,
    "step_times_s": [round(b[1] - a[1], 2) for a, b in zip([(0, starts.get(SAMPLE, 0))] + steps, steps)],
    "node_start_offsets_s": {n: round(t - t_submit, 2) for n, t in order},
    "peak_gpu_mib": peak["mib"],
    "outputs": hist.get("outputs", {}),
}
print(json.dumps(rep, ensure_ascii=False, indent=1))
