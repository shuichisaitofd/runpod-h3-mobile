import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "h3-mobile" / "__init__.py"
text = INIT.read_text()
tree = ast.parse(text)


functions = {
    node.name: node
    for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}

assert "_schedule_model_set" in functions
assert "_auto_prepare_i2v_on_startup" in functions

startup_source = ast.get_source_segment(
    text, functions["_auto_prepare_i2v_on_startup"]
)
assert '_schedule_model_set("i2v")' in startup_source
assert '"ref2va"' not in startup_source

# Tie the automatic action to aiohttp startup, not module-import-time
# create_task(), because the server loop may not be running during import.
assert "PromptServer.instance.app.on_startup.append(_auto_prepare_i2v_on_startup)" in text

# Manual preparation still accepts both modes and reuses the idempotent
# scheduler. This preserves the existing Ref2VA button behavior.
prepare_source = ast.get_source_segment(
    text, functions["h3_mobile_prepare_models"]
)
assert "if mode not in MODE_SETS" in prepare_source
assert "_schedule_model_set(mode)" in prepare_source

print("I2V startup auto-prepare validation passed")
