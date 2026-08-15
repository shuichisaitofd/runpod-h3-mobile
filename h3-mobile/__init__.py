from pathlib import Path

from aiohttp import web
from server import PromptServer

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
API_WORKFLOW = BASE_DIR / "api_workflows" / "ref2va.json"

routes = PromptServer.instance.routes


@routes.get("/h3-mobile")
async def h3_mobile_index(request):
    return web.FileResponse(WEB_DIR / "index.html")


@routes.get("/h3-mobile/app.js")
async def h3_mobile_js(request):
    return web.FileResponse(WEB_DIR / "app.js")


@routes.get("/h3-mobile/styles.css")
async def h3_mobile_css(request):
    return web.FileResponse(WEB_DIR / "styles.css")


@routes.get("/h3-mobile/health")
async def h3_mobile_health(request):
    return web.json_response({"ok": True, "service": "h3-mobile"})


@routes.get("/h3-mobile/api/ref2va-workflow")
async def h3_mobile_ref2va_workflow(request):
    if not API_WORKFLOW.is_file():
        raise web.HTTPNotFound(text="Ref2VA API workflow is not installed yet")
    return web.FileResponse(API_WORKFLOW)


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
