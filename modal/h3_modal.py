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
LORA_ROUTES_SHA = "6244f533623bedd19a346408989849122d940b9d"
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


@app.function(image=web_image, cpu=0.25, memory=512, scaledown_window=120, max_containers=1)
@modal.concurrent(max_inputs=200)
@modal.asgi_app()
def web():
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
    from starlette.background import BackgroundTask

    api = FastAPI()
    client = httpx.AsyncClient(timeout=httpx.Timeout(900, connect=20))
    cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "*"}
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
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
        body = await request.body()
        req = client.build_request(request.method, target, headers=headers, content=body)
        r = await client.send(req, stream=True)
        rh = {k: v for k, v in r.headers.items() if k.lower() not in ("transfer-encoding", "connection")}
        return StreamingResponse(r.aiter_raw(), status_code=r.status_code, headers=rh, background=BackgroundTask(r.aclose))

    return api
