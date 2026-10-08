"""H3 Veda test page: a copy of the H3 Mobile page with an on/off + sparsity panel for Veda (I2V only).

Serves /h3-veda/ . It reads the production page at request time, so the production app
(ComfyUI-H3-Mobile) and its i2v.json are never modified. Delete this folder to remove it.
"""
from pathlib import Path
import re

from aiohttp import web
from server import PromptServer

BASE_DIR = Path(__file__).resolve().parent
MOBILE_INDEX = BASE_DIR.parent / "ComfyUI-H3-Mobile" / "web" / "index.html"
routes = PromptServer.instance.routes
NO_STORE = {"Cache-Control": "no-store"}


def build_page(html):
    # Resolve every relative asset (styles.css, app.js, ...) against /h3-mobile/ so the production files are reused.
    html = re.sub(r"(<head[^>]*>)", r'\1<base href="/h3-mobile/">', html, count=1, flags=re.I)
    tag = '<script src="/h3-veda/veda-panel.js?v=1"></script>'
    if re.search(r"</body>", html, flags=re.I):
        return re.sub(r"</body>", tag + "</body>", html, count=1, flags=re.I)
    return html + tag


@routes.get("/h3-veda")
async def h3_veda_no_slash(request):
    raise web.HTTPFound("/h3-veda/")


@routes.get("/h3-veda/")
async def h3_veda_index(request):
    if not MOBILE_INDEX.is_file():
        raise web.HTTPNotFound(text="H3 Mobile (ComfyUI-H3-Mobile) is not installed on this Pod")
    return web.Response(text=build_page(MOBILE_INDEX.read_text(encoding="utf-8")), content_type="text/html", headers=NO_STORE)


@routes.get("/h3-veda/veda-panel.js")
async def h3_veda_panel_js(request):
    return web.FileResponse(BASE_DIR / "veda-panel.js", headers=NO_STORE)


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
