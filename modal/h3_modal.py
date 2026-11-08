# H3 on Modal (test) — the same ComfyUI + H3 Mobile setup as the RunPod long-video image, on a Modal GPU.
#
#   modal deploy h3_modal.py
#
# Pieces:
#   web         : small CPU web app with a stable URL. Register https://<workspace>--h3-modal-web.modal.run
#                 in H3 Studio β like a Pod. It forwards every request to the GPU server while it runs, and
#                 answers 503 while it is stopped (so the phone's polling never wakes a GPU).
#                 /h3modal = start / stop / status page.
#   gpu_server  : the GPU container (ComfyUI). Started from /h3modal, stops itself after IDLE_MINUTES
#                 without jobs, downloads or video views. Nothing is kept: models are downloaded at every
#                 start (like a new RunPod Pod) and the videos are gone when it stops.
import json
import os
import subprocess
import time

import modal

IMAGE_TAG = "ghcr.io/shuichisaitofd/runpod-h3-mobile:h3-longtest-c9443c9e535d3053ec858f602daa50af59c65e0d"
GPU = "L40S"
IDLE_MINUTES = 20
# lora_routes.py (H3 Mobile long-video / LoRA routes) is taken from this commit, so Modal gets fixes without an image rebuild.
LORA_ROUTES_SHA = "599587cfb064c01b806e951192d8b7b6bc66776d"
W = "/workspace/runpod-slim"
C = W + "/ComfyUI"

# Build-time setup: what /start.sh + veda-boot-setup.sh do on a RunPod Pod, done once in the image.
SETUP = r"""
set -eux
mkdir -p /workspace/runpod-slim
cp -a /opt/comfyui-baked /workspace/runpod-slim/ComfyUI
cd /workspace/runpod-slim/ComfyUI
python3.12 -m venv --system-site-packages .venv-cu128
.venv-cu128/bin/python -m ensurepip
export PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt
git fetch origin tag v0.38.0
git checkout v0.38.0
.venv-cu128/bin/pip install -r requirements.txt
git clone https://github.com/veda-sparse/Veda-on-ComfyUI.git custom_nodes/Veda-on-ComfyUI
git -C custom_nodes/Veda-on-ComfyUI checkout 60bfae6
.venv-cu128/bin/pip install -r custom_nodes/Veda-on-ComfyUI/requirements.txt
git clone https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite.git custom_nodes/Herrgotts-H3-Infinite-Continuation-Suite
git -C custom_nodes/Herrgotts-H3-Infinite-Continuation-Suite checkout 4b1edd678de7356beebf3761b2532a35e07d0389
mkdir -p models/veda
curl -fL --retry 5 -o models/veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors https://huggingface.co/Veda-Sparse/Minimax-H3-T2VA-Veda-8NFE-600Step-Preview/resolve/main/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors
echo "2a8d8845c5342756a2781e8e69563940e4bb573c9a40ebb534915ff8fd76573a  models/veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors" | sha256sum -c -
curl -fsSL -o custom_nodes/ComfyUI-H3-Mobile/lora_routes.py "https://raw.githubusercontent.com/shuichisaitofd/runpod-h3-mobile/__SHA__/h3-mobile/lora_routes.py"
python3.12 -m py_compile custom_nodes/ComfyUI-H3-Mobile/lora_routes.py
F=custom_nodes/ComfyUI-H3-Mobile/__init__.py
sed -i '/from \.web import lora_routes/d' "$F"
grep -Fq 'from . import lora_routes' "$F" || printf '\nfrom . import lora_routes  # register dynamic LoRA manager endpoints\n' >> "$F"
# The image's SageAttention is compiled for RTX A6000 (SM86) only, so the I2V workflow uses PyTorch attention here.
python3.12 -c "
import json
p='custom_nodes/ComfyUI-H3-Mobile/api_workflows/i2v.json'
g=json.load(open(p))
for n in g.values():
    if n.get('class_type')=='PathchSageAttentionKJ':
        n['inputs']['sage_attention']='disabled'
json.dump(g,open(p,'w'),indent=2)
print('sage disabled in i2v.json')
"
"""

import base64 as _b64

_SETUP_B64 = _b64.b64encode(SETUP.replace("__SHA__", LORA_ROUTES_SHA).encode()).decode()

gpu_image = (
    modal.Image.from_registry(IMAGE_TAG)
    .entrypoint([])
    .run_commands('ln -sf "$(command -v python3.12)" /usr/local/bin/python')
    .run_commands(f"echo {_SETUP_B64} | base64 -d > /tmp/h3setup.sh && bash /tmp/h3setup.sh")
)
web_image = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi[standard]==0.115.12", "httpx==0.28.1")

app = modal.App("h3-modal")
state = modal.Dict.from_name("h3-modal-state", create_if_missing=True)


def _set(**kw):
    for k, v in kw.items():
        state[k] = v


RP_TEMPLATE = "rp0bq9dcco"  # RunPod template "H3 Mobile - veda 10max long" (disk sizes / ports come from it)


def rp_deploy(key, gpu, image, name):
    """Create one RunPod Pod with the same GraphQL call as the runpod-a6000-watcher workflow
    (it can ask for CUDA 13.0+ hosts with minCudaVersion, which the REST API cannot). The key is not logged."""
    import re

    import httpx
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", str(name or "h3-quick"))[:60]
    args = ", ".join([
        "cloudType: SECURE", "gpuCount: 1", "gpuTypeId: " + json.dumps(gpu), "name: " + json.dumps(name),
        "templateId: " + json.dumps(RP_TEMPLATE), "imageName: " + json.dumps(image),
        "containerDiskInGb: 150", "volumeInGb: 100", 'volumeMountPath: "/workspace"', 'minCudaVersion: "13.0"'])
    q = "mutation { podFindAndDeployOnDemand(input: { " + args + " }) { id imageName machineId } }"
    try:
        r = httpx.post("https://api.runpod.io/graphql", json={"query": q}, timeout=60,
                       headers={"Authorization": "Bearer " + key})
        data = r.json()
    except Exception as e:
        return {"ok": False, "noCapacity": False, "error": "RunPod API: " + str(e)[:200]}
    pod = ((data or {}).get("data") or {}).get("podFindAndDeployOnDemand") if isinstance(data, dict) else None
    if pod and pod.get("id"):
        return {"ok": True, "id": pod["id"], "gpu": gpu}
    errs = data.get("errors") if isinstance(data, dict) else None
    msg = str((errs[0] or {}).get("message") if errs else data)[:400]
    busy = bool(re.search(r"no longer any instances|not available|no available|capacity|insufficient", msg, re.I))
    return {"ok": False, "noCapacity": busy, "error": msg}


def _ntfy(topic, text):
    if not topic:
        return
    try:
        import httpx
        httpx.post("https://ntfy.sh/" + topic, content=text.encode(), timeout=15,
                   headers={"Title": "H3 RunPod", "Priority": "high", "Click": "https://shuichisaitofd.github.io/h3-studio-next/"})
    except Exception:
        pass


web_lite = modal.Image.debian_slim(python_version="3.12").pip_install("httpx==0.28.1")


@app.function(image=web_lite, cpu=0.125, memory=256, timeout=480)
def rp_watch(wid: str, key: str, gpus: list, image: str, topic: str = ""):
    """Try to get a RunPod Pod every 10 s for 5 minutes. Progress goes to state['rpwatch:<wid>']."""
    k = "rpwatch:" + wid
    started = time.time()
    tries = 0
    labels = {"NVIDIA RTX A6000": "A6000", "NVIDIA L40S": "L40S"}
    while True:
        if state.get("rpwatch-stop:" + wid, False):
            state[k] = {"status": "stopped", "started": started, "tries": tries, "gpus": gpus}
            return
        gpu = gpus[tries % len(gpus)]
        tries += 1
        res = rp_deploy(key, gpu, image, "h3-" + labels.get(gpu, "gpu").lower())
        if res.get("ok"):
            state[k] = {"status": "ok", "id": res["id"], "gpu": gpu, "started": started, "tries": tries,
                        "gpus": gpus, "at": time.time()}
            _ntfy(topic, f"✅ RunPod {labels.get(gpu, gpu)} を確保しました（{res['id']}）。課金中です。H3 Studio β を開くと自動で切り替わります。")
            return
        if not res.get("noCapacity"):
            state[k] = {"status": "error", "error": res.get("error"), "started": started, "tries": tries, "gpus": gpus}
            _ntfy(topic, "RunPod を起動できませんでした: " + str(res.get("error"))[:200])
            return
        if time.time() - started > 300:
            state[k] = {"status": "timeout", "started": started, "tries": tries, "gpus": gpus}
            _ntfy(topic, "5分間、RunPod に空きがありませんでした。もう一度「起動」を押すと、また5分見張ります。")
            return
        state[k] = {"status": "watching", "started": started, "tries": tries, "gpus": gpus}
        time.sleep(10)


@app.function(image=gpu_image, gpu=GPU, cpu=2.0, memory=32768, timeout=6 * 3600, max_containers=1)
def gpu_server(idle_minutes: int = IDLE_MINUTES):
    import urllib.request

    def get(path, t=10):
        with urllib.request.urlopen("http://127.0.0.1:8188" + path, timeout=t) as r:
            return json.loads(r.read() or b"null")

    os.makedirs(W, exist_ok=True)
    with open("/workspace/veda_boot_status.txt", "w") as f:
        f.write("OK: Veda is ready (ComfyUI v0.38.0)\n")
    env = dict(os.environ, VIRTUAL_ENV=C + "/.venv-cu128", PATH=C + "/.venv-cu128/bin:" + os.environ.get("PATH", ""),
               PIP_CONSTRAINT="/opt/comfyui-runtime-constraints.txt")
    log = open(W + "/comfyui.log", "ab")
    proc = subprocess.Popen([C + "/.venv-cu128/bin/python", "main.py", "--listen", "0.0.0.0", "--port", "8188",
                             "--enable-cors-header"], cwd=C, stdout=log, stderr=subprocess.STDOUT, env=env)
    t0 = time.time()
    try:
        with modal.forward(8188) as tunnel:
            _set(url=None, status="starting", since=t0, hb=time.time(), stop=False, error=None, touch=0)
            while True:
                if proc.poll() is not None:
                    raise RuntimeError("ComfyUI stopped while starting")
                try:
                    get("/system_stats", 5)
                    break
                except Exception:
                    time.sleep(2)
                    state["hb"] = time.time()
                    if time.time() - t0 > 900:
                        raise RuntimeError("ComfyUI did not start in 15 minutes")
            _set(url=tunnel.url, status="ready", ready_at=time.time(), hb=time.time())
            last = time.time()
            while True:
                time.sleep(15)
                if proc.poll() is not None:
                    raise RuntimeError("ComfyUI stopped")
                if state.get("stop"):
                    break
                busy = False
                try:
                    q = get("/queue")
                    busy = bool(q.get("queue_running") or q.get("queue_pending"))
                    m = get("/h3-mobile/api/models")
                    busy = busy or any(v.get("status") in ("queued", "downloading") for v in m.get("models", {}).values())
                    e = get("/h3-mobile/api/eros/status")
                    busy = busy or any(v.get("status") in ("queued", "downloading") for v in e.get("models", {}).values())
                    lr = get("/h3-mobile/api/long/status")
                    busy = busy or any(not r.get("done") for r in lr.get("runs", []))
                except Exception:
                    busy = True  # ComfyUI busy / slow: do not stop
                touch = state.get("touch") or 0
                if busy:
                    last = time.time()
                last = max(last, touch)
                left = idle_minutes * 60 - (time.time() - last)
                _set(hb=time.time(), idle_left=int(max(0, left)), busy=busy)
                if left <= 0:
                    break
    except Exception as exc:
        state["error"] = str(exc)[:500]
        raise
    finally:
        _set(status="stopped", url=None, stopped_at=time.time())
        try:
            proc.terminate()
            proc.wait(20)
        except Exception:
            proc.kill()


PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H3 on Modal</title><style>
body{margin:0;background:#0b0b0d;color:#f2f2f2;font:16px/1.6 -apple-system,system-ui,sans-serif;padding:20px}
.card{background:#151518;border:1px solid #26262b;border-radius:16px;padding:18px;margin:0 0 14px}
h1{font-size:20px;margin:0 0 12px}b{color:#fff}.s{color:#a1a1aa;font-size:14px}
button{font:inherit;font-weight:700;border:0;border-radius:12px;padding:14px;width:100%;margin:6px 0;background:#ff6a2b;color:#111}
button.sec{background:#26262b;color:#f2f2f2}code{word-break:break-all;background:#000;padding:2px 6px;border-radius:6px}
</style></head><body>
<h1>H3 on Modal（テスト）</h1>
<div class="card"><div>状態：<b id="st">…</b></div><div class="s" id="sub"></div></div>
<div class="card"><button id="start">GPUを起動</button><button class="sec" id="ext">停止を先に延ばす</button><button class="sec" id="stop">GPUを停止</button></div>
<div class="card s">H3 Studio β の設定で、Podの代わりにこのURLを登録します：<br><code id="me"></code><br>
GPUは使われていない状態が""" + str(IDLE_MINUTES) + """分続くと自動で止まります。止まると動画は消えるので、先にダウンロードしてください。</div>
<script>
const me=location.origin;document.getElementById('me').textContent=me;
const L={stopped:'停止中',starting:'起動中',ready:'動いています',crashed:'エラーで停止'};
async function st(){try{const j=await (await fetch('/h3modal/status',{cache:'no-store'})).json();
document.getElementById('st').textContent=L[j.status]||j.status||'停止中';
let s='';if(j.status==='starting')s='起動中… '+Math.round((Date.now()/1000-j.since))+'秒（モデルのダウンロードは起動後に始まります）';
if(j.status==='ready')s='自動停止まで あと約'+Math.ceil((j.idle_left||0)/60)+'分'+(j.busy?'（生成・ダウンロード中）':'');
if(j.error)s+='\\nエラー: '+j.error;document.getElementById('sub').textContent=s;}catch(e){document.getElementById('sub').textContent='状態の取得に失敗';}}
async function post(p,b,label){if(b){b.disabled=true;b.textContent=label;}try{await fetch(p,{method:'POST'});}catch(e){}await st();if(b)setTimeout(()=>{b.disabled=false;b.textContent=b.dataset.t;},4000);}
document.querySelectorAll('button').forEach(b=>b.dataset.t=b.textContent);
document.getElementById('start').onclick=e=>{document.getElementById('st').textContent='起動中';post('/h3modal/start',e.target,'起動しています…');};
document.getElementById('stop').onclick=e=>{if(confirm('GPUを止めますか？（動画は消えます）'))post('/h3modal/stop',e.target,'止めています…');};
document.getElementById('ext').onclick=e=>post('/h3modal/extend',e.target,'延ばしました（20分）');
st();setInterval(st,5000);
</script></body></html>"""


@app.function(image=web_image, cpu=1.0, memory=1024, scaledown_window=300, max_containers=1)
@modal.concurrent(max_inputs=200)
@modal.asgi_app()
def web():
    import re

    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
    from starlette.background import BackgroundTask

    api = FastAPI()
    client = httpx.AsyncClient(timeout=httpx.Timeout(900, connect=20))
    cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "*"}
    direct_paths = ("view", "api/view", "h3-mobile/api/history/download-all", "h3-mobile/api/long/download")
    touch_paths = ("view", "upload", "prompt", "h3-mobile/api/long/run", "h3-mobile/api/history/download-all",
                   "h3-mobile/api/long/download", "h3-mobile/api/models/prepare")

    async def info():
        keys = ("status", "since", "ready_at", "idle_left", "busy", "error", "hb", "url")
        out = {}
        for k in keys:
            out[k] = await state.get.aio(k, None)
        st = out.get("status") or "stopped"
        age = time.time() - (out.get("hb") or 0)
        if (st == "starting" and age > 900) or (st == "ready" and age > 180):
            st = "stopped"  # the GPU container died without saying so
        out["status"] = st
        return out

    @api.get("/h3modal")
    async def page():
        return HTMLResponse(PAGE)

    @api.get("/h3modal/status")
    async def status():
        i = await info()
        i.pop("url", None)
        return JSONResponse(i, headers=cors)

    @api.post("/h3modal/start")
    async def start():
        i = await info()
        if i["status"] in ("starting", "ready"):
            return JSONResponse({"ok": True, "already": True}, headers=cors)
        await state.put.aio("status", "starting")
        await state.put.aio("since", time.time())
        await state.put.aio("hb", time.time())
        await state.put.aio("error", None)
        await gpu_server.spawn.aio()
        return JSONResponse({"ok": True}, headers=cors)

    @api.post("/h3modal/stop")
    async def stop():
        await state.put.aio("stop", True)
        return JSONResponse({"ok": True}, headers=cors)

    @api.post("/h3modal/extend")
    async def extend():
        await state.put.aio("touch", time.time())
        return JSONResponse({"ok": True}, headers=cors)

    # RunPod one-tap start for H3 Studio β. The phone sends its own RunPod API key with each request
    # (browsers cannot call the RunPod API directly because of CORS). The key is never stored or logged here.
    RP = "https://rest.runpod.io/v1"
    RP_GPUS = ("NVIDIA RTX A6000", "NVIDIA L40S", "NVIDIA RTX 6000 Ada Generation", "NVIDIA A40")

    async def rp_body(request):
        try:
            b = json.loads((await request.body()) or b"{}")
        except Exception:
            b = {}
        return b if isinstance(b, dict) else {}

    async def rp_call(method, path, key, body=None):
        r = await client.request(method, RP + path, json=body, timeout=60,
                                 headers={"Authorization": "Bearer " + key})
        try:
            data = r.json()
        except Exception:
            data = {"error": r.text[:300]}
        return r.status_code, data

    def rp_err(data):
        if isinstance(data, dict):
            return str(data.get("error") or data.get("message") or data)[:400]
        return str(data)[:400]

    @api.post("/h3modal/runpod/create")
    async def rp_create(request: Request):
        b = await rp_body(request)
        key, gpu, image = str(b.get("key") or ""), str(b.get("gpu") or ""), str(b.get("image") or "")
        if not key:
            return JSONResponse({"ok": False, "error": "API key missing"}, headers=cors)
        if gpu not in RP_GPUS:
            return JSONResponse({"ok": False, "error": "GPU not allowed: " + gpu}, headers=cors)
        if not image.startswith("ghcr.io/shuichisaitofd/runpod-h3-mobile:"):
            return JSONResponse({"ok": False, "error": "image not allowed"}, headers=cors)
        import asyncio
        res = await asyncio.to_thread(rp_deploy, key, gpu, image, str(b.get("name") or "h3-quick"))
        return JSONResponse(res, headers=cors)

    # Server-side watch: the phone can close the page. A tiny CPU job tries every 10 s for 5 minutes.
    @api.post("/h3modal/runpod/watch")
    async def rp_watch_start(request: Request):
        import uuid
        b = await rp_body(request)
        key, image = str(b.get("key") or ""), str(b.get("image") or "")
        gpus = [g for g in (b.get("gpus") or []) if g in RP_GPUS][:4]
        if not key:
            return JSONResponse({"ok": False, "error": "API key missing"}, headers=cors)
        if not gpus:
            return JSONResponse({"ok": False, "error": "GPU not allowed"}, headers=cors)
        if not image.startswith("ghcr.io/shuichisaitofd/runpod-h3-mobile:"):
            return JSONResponse({"ok": False, "error": "image not allowed"}, headers=cors)
        topic = re.sub(r"[^A-Za-z0-9_-]", "", str(b.get("ntfy") or ""))[:64]
        wid = uuid.uuid4().hex
        await state.put.aio("rpwatch:" + wid, {"status": "watching", "started": time.time(), "tries": 0,
                                               "gpus": gpus})
        await rp_watch.spawn.aio(wid, key, gpus, image, topic)
        return JSONResponse({"ok": True, "watch": wid}, headers=cors)

    @api.post("/h3modal/runpod/watch-status")
    async def rp_watch_status(request: Request):
        b = await rp_body(request)
        wid = re.sub(r"[^0-9a-f]", "", str(b.get("watch") or ""))[:32]
        st = await state.get.aio("rpwatch:" + wid, None) if wid else None
        if not st:
            return JSONResponse({"ok": False, "error": "unknown watch"}, headers=cors)
        return JSONResponse({"ok": True, **st}, headers=cors)

    @api.post("/h3modal/runpod/watch-stop")
    async def rp_watch_stop(request: Request):
        b = await rp_body(request)
        wid = re.sub(r"[^0-9a-f]", "", str(b.get("watch") or ""))[:32]
        if wid:
            await state.put.aio("rpwatch-stop:" + wid, True)
        return JSONResponse({"ok": True}, headers=cors)

    @api.post("/h3modal/runpod/pods")
    async def rp_pods(request: Request):
        b = await rp_body(request)
        key = str(b.get("key") or "")
        if not key:
            return JSONResponse({"ok": False, "error": "API key missing"}, headers=cors)
        code, data = await rp_call("GET", "/pods", key)
        if code >= 300 or not isinstance(data, list):
            return JSONResponse({"ok": False, "error": rp_err(data), "code": code}, headers=cors)
        def gpu_name(p):
            g, m = p.get("gpu"), p.get("machine")
            for src in (g if isinstance(g, dict) else {}, m if isinstance(m, dict) else {}):
                for k in ("displayName", "gpuDisplayName", "id", "gpuTypeId"):
                    if src.get(k):
                        return str(src[k]).replace("NVIDIA ", "").replace("GeForce ", "")
            return None
        pods = [{"id": p.get("id"), "name": p.get("name"), "desiredStatus": p.get("desiredStatus"),
                 "costPerHr": p.get("costPerHr"), "image": p.get("image"), "gpu": gpu_name(p)}
                for p in data if isinstance(p, dict)]
        return JSONResponse({"ok": True, "pods": pods}, headers=cors)

    @api.post("/h3modal/runpod/delete")
    async def rp_delete(request: Request):
        b = await rp_body(request)
        key, pid = str(b.get("key") or ""), str(b.get("id") or "")
        if not key or not pid.isalnum():
            return JSONResponse({"ok": False, "error": "API key or pod id missing"}, headers=cors)
        code, data = await rp_call("DELETE", "/pods/" + pid, key)
        return JSONResponse({"ok": code < 300, "code": code, "error": None if code < 300 else rp_err(data)},
                            headers=cors)

    @api.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request):
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)
        i = await info()
        url = i.get("url")
        if i["status"] != "ready" or not url:
            msg = {"stopped": "GPUは停止中です。/h3modal から起動してください。", "starting": "GPUを起動中です。少し待ってください。"}
            return JSONResponse({"error": msg.get(i["status"], "GPUが使えません。"), "status": i["status"]},
                                status_code=503, headers=cors)
        if path.startswith(touch_paths):
            await state.put.aio("touch", time.time())
        target = url.rstrip("/") + "/" + path + (("?" + request.url.query) if request.url.query else "")
        if request.method in ("GET", "HEAD") and path.startswith(direct_paths):
            # videos and zips: let the phone fetch them straight from the GPU (no second hop through this small proxy)
            return RedirectResponse(target, status_code=307, headers=cors)
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
        body = await request.body()
        req = client.build_request(request.method, target, headers=headers, content=body)
        r = await client.send(req, stream=True)
        resp = StreamingResponse(r.aiter_raw(), status_code=r.status_code, background=BackgroundTask(r.aclose))
        # pass the headers through as raw bytes: ComfyUI's /view sends the (Japanese) file name in Content-Disposition,
        # which cannot be re-encoded as latin-1 text
        resp.raw_headers = [(k, v) for k, v in r.headers.raw if k.lower() not in (b"transfer-encoding", b"connection")]
        return resp

    return api
