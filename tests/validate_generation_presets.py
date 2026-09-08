import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "h3-mobile"
WEB = MOBILE / "web"

init_text = (MOBILE / "__init__.py").read_text()
index_text = (WEB / "index.html").read_text()
app = (WEB / "app.js").read_text()
batch = (WEB / "batch-v2.js").read_text()
lora = (WEB / "lora-library.js").read_text()
presets = (WEB / "prompt-library.js").read_text()

# AIO and Motion Booster are owned by the LoRA tab, never by the legacy model
# preparation list. The workflow-required Turbo LoRA remains in both sets.
model_specs = init_text.split("MODEL_SPECS = {", 1)[1].split("\n}", 1)[0]
mode_sets = init_text.split("MODE_SETS =", 1)[1].split("\n", 1)[0]
for removed in (
    "ref2va_aio_lora",
    "ref2va_motion_booster_lora",
    "HMNSFW-AIO-V2.5.safetensors",
    "H3_Motion_BoosterV2.safetensors",
):
    assert removed not in model_specs
    assert removed not in mode_sets
assert '"turbo_lora"' in model_specs and '"turbo_lora"' in mode_sets
assert "minimax_h3_turbo_v4_step600_ema.safetensors" in model_specs

# Bulk file upload matches the original filename, preserves the registration,
# uploads through runUpload()/uploadItem(), and rerenders from the installed Pod
# state. Upload does not alter project ON/OFF/strength settings.
bulk_upload = lora.split("async function handleUploadFiles", 1)[1].split(
    "function bulkUploadFiles", 1
)[0]
assert "value.originalFilename===file.name||value.filename===file.name" in bulk_upload
assert "runUpload(item,file)" in bulk_upload
assert "setSelection" not in bulk_upload
assert "enabled:" not in bulk_upload
# The stale-learned-SHA bug is gone: no learned hash is ever sent as expected.
assert "const expected=item.sha256?" not in lora
assert "&sha256=${encodeURIComponent(item.sha256)}" not in lora
assert "uploadItem(item,file,onProgress)" in lora and "xhr.upload.onprogress" in lora

# History metadata keeps filename plus the registered display name and strength.
# The formatter is backward compatible with entries that have no loras field.
assert "extra.loras=loras" in lora
for field in ("filename", "name:item?.name", "strength:Number"):
    assert field in lora
assert "historyLorasHtml(extra.loras)" in app
metadata_match = re.search(r"async function assertInstalledForPrompt\(baseFetch,input,init\)\{[^\n]+\}", lora)
assert metadata_match
metadata_test = (
    "function loadLib(){return [{filename:'a.safetensors',name:'Display A'}];}\n"
    "function autoName(value){return value;} function apiUrl(value){return value;}\n"
    + metadata_match.group(0)
    + "\n(async()=>{\n"
    "const fetchOk=async()=>({ok:true,json:async()=>({files:[{filename:'a.safetensors',status:'installed',size:10}]})});\n"
    "const withLora={body:JSON.stringify({prompt:{n:{class_type:'LoraLoaderModelOnly',inputs:{lora_name:'a.safetensors',strength_model:0.4}}},extra_data:{h3_mobile:{}}})};\n"
    "await assertInstalledForPrompt(fetchOk,'/prompt',withLora);const saved=JSON.parse(withLora.body).extra_data.h3_mobile.loras;\n"
    "if(saved.length!==1||saved[0].filename!=='a.safetensors'||saved[0].name!=='Display A'||saved[0].strength!==0.4)process.exit(1);\n"
    "const withoutLora={body:JSON.stringify({prompt:{},extra_data:{h3_mobile:{}}})};\n"
    "await assertInstalledForPrompt(async()=>{throw new Error('must not fetch');},'/prompt',withoutLora);\n"
    "if(JSON.parse(withoutLora.body).extra_data.h3_mobile.loras.length!==0)process.exit(2);\n"
    "})().catch(()=>process.exit(3));\n"
)
subprocess.run(["node", "-e", metadata_test], check=True)
history_match = re.search(r"function historyLorasHtml\(value\)\{[^\n]+\}", app)
assert history_match
history_test = (
    "function escapeHtml(value){return String(value);}\n"
    + history_match.group(0)
    + "\n"
    + "if(historyLorasHtml(undefined)!=='LoRA: なし')process.exit(1);\n"
    + "const shown=historyLorasHtml([{name:'HMNSFW AIO V2.5',strength:0.4},{filename:'H3_Motion_BoosterV2.safetensors',strength:0.5}]);\n"
    + "if(!shown.includes('HMNSFW AIO V2.5 — 0.40')||!shown.includes('H3_Motion_BoosterV2.safetensors — 0.50'))process.exit(2);\n"
)
subprocess.run(["node", "-e", history_test], check=True)

# prompt-library.js is loaded directly after the LoRA APIs and provides the new
# compact controls rather than relying on media-library's dynamic loader.
script_tag = '<script src="prompt-library.js" data-h3-prompt-library="1"></script>'
assert script_tag in index_text
assert index_text.index('<script src="lora-library.js"></script>') < index_text.index(script_tag)
assert "プリセット保存" in presets and "プリセット" in presets
assert "プロンプトを保存" not in presets and "保存済みから選ぶ" not in presets
for action in ("適用", "上書き", "削除"):
    assert action in presets
for summary_field in ("steps", "megapixels", "loras.filter"):
    assert summary_field in presets

# Normal and batch captures contain every requested generation parameter and a
# full context LoRA snapshot (including disabled entries and ordering).
normal_capture = app.split("window.h3CaptureNormalPreset", 1)[1].split(
    "window.h3ApplyNormalPreset", 1
)[0]
batch_capture = batch.split("window.h3CaptureBatchPreset", 1)[1].split(
    "window.h3ApplyBatchPreset", 1
)[0]
normal_apply = app.split("window.h3ApplyNormalPreset", 1)[1].split(
    "async function persistProjectImageSlot", 1
)[0]
batch_apply = batch.split("window.h3ApplyBatchPreset", 1)[1].split(
    "function filePreview", 1
)[0]
for field in (
    "mode",
    "refVariant",
    "prompt",
    "seconds",
    "steps",
    "megapixels",
    "ratio",
    "ref_image_size",
    "seed",
    "loras",
):
    assert field in normal_capture, field
    assert field in batch_capture, field
assert "seedMode" in batch_capture
assert "window.h3LoraPresetSnapshot" in lora
for field in ("id:item.id", "filename:item.filename", "enabled:!!sel.enabled", "strength:Number", "order:Number"):
    assert field in lora, field

normal_runtime_test = f"""
global.window=global;
const fields={{prompt:{{value:'hello'}},sec:{{value:'6'}},steps:{{value:'12'}},mp:{{value:'0.5'}},ratio:{{value:'3:4'}},refSize:{{value:'max'}},seed:{{value:'42'}},title:{{value:'keep title'}},image0:{{value:'keep image'}}}};
function $(selector){{return fields[selector.slice(1)];}}
const state={{mode:'ref',refVariant:'04'}};
function setMode(value){{state.mode=value;}} function setRefVariant(value){{state.refVariant=value;}}
let persisted=0,rendered=0,loraApply=null;
function persistActiveProjectFields(){{persisted++;}} function renderQuick(){{rendered++;}}
window.h3LoraPresetSnapshot=()=>[{{id:'one',filename:'one.safetensors',enabled:false,strength:0.7,order:2}}];
window.h3ApplyLoraPreset=(ctx,value)=>{{loraApply={{ctx,value}};}};
window.h3CaptureNormalPreset{normal_capture.strip()}
window.h3ApplyNormalPreset{normal_apply.strip()}
const captured=window.h3CaptureNormalPreset();
if(captured.mode!=='ref'||captured.seconds!==6||captured.steps!==12||captured.megapixels!==0.5||captured.seed!==42||captured.loras.length!==1)process.exit(1);
window.h3ApplyNormalPreset({{mode:'i2v',refVariant:'05',prompt:'new',seconds:9,steps:8,megapixels:1,ratio:'16:9',ref_image_size:'match',seed:99,loras:[{{id:'one'}}]}});
if(fields.title.value!=='keep title'||fields.image0.value!=='keep image'||fields.prompt.value!=='new'||persisted!==1||rendered<1||loraApply.ctx!=='i2v')process.exit(2);
"""
subprocess.run(["node", "-e", normal_runtime_test], check=True)

batch_runtime_test = f"""
global.window=global;
const fields={{batchPrompt:{{value:'batch'}},batchSec:{{value:'7'}},batchSteps:{{value:'12'}},batchMp:{{value:'0.75'}},batchRatio:{{value:'9:16'}},batchRefSize:{{value:'max'}},batchSeedMode:{{value:'sequence'}},batchSeed:{{value:'123'}},batchTitle:{{value:'keep batch title'}},batchI2VFiles:{{value:'keep files'}}}};
function q(selector){{return fields[selector.slice(1)];}}
const batch={{mode:'ref2va',refVariant:'fast',submitting:false}};
function setMode(value){{batch.mode=value;}} function setBatchVariant(value){{batch.refVariant=value;}}
let persisted=0,rendered=0,quick=0,loraApply=null;
function persistBatchMeta(){{persisted++;}} function render(){{rendered++;}} function renderQuick(){{quick++;}}
window.h3LoraPresetSnapshot=()=>[{{id:'one',filename:'one.safetensors',enabled:true,strength:0.5,order:0}}];
window.h3ApplyLoraPreset=(ctx,value)=>{{loraApply={{ctx,value}};}};
window.h3CaptureBatchPreset{batch_capture.strip()}
window.h3ApplyBatchPreset{batch_apply.strip()}
const captured=window.h3CaptureBatchPreset();
if(captured.mode!=='ref2va'||captured.refVariant!=='fast'||captured.seedMode!=='sequence'||captured.seed!==123||captured.loras.length!==1)process.exit(1);
window.h3ApplyBatchPreset({{mode:'i2v',refVariant:'04',prompt:'new batch',seconds:10,steps:4,megapixels:0.5,ratio:'元画像と同じ',ref_image_size:'match',seedMode:'fixed',seed:88,loras:[{{id:'one'}}]}});
if(fields.batchTitle.value!=='keep batch title'||fields.batchI2VFiles.value!=='keep files'||fields.batchPrompt.value!=='new batch'||persisted!==1||rendered!==1||quick!==1||loraApply.ctx!=='i2v')process.exit(2);
"""
subprocess.run(["node", "-e", batch_runtime_test], check=True)

# Applying a preset updates current project settings and the matching LoRAs,
# then persists and rerenders. It never touches images or project/batch titles.
assert "window.h3ApplyLoraPreset" in normal_apply
assert "persistActiveProjectFields()" in normal_apply and "renderQuick()" in normal_apply
assert "window.h3ApplyLoraPreset" in batch_apply
assert "persistBatchMeta()" in batch_apply and "renderQuick()" in batch_apply
for forbidden in ("#title", "#image0", "#ref0", "PROJECT_IMG_SLOTS"):
    assert forbidden not in normal_apply
for forbidden in ("#batchTitle", "batch.i2vFiles", "batch.refSets", "persistBatchImages"):
    assert forbidden not in batch_apply
apply_lora = lora.split("window.h3ApplyLoraPreset", 1)[1].split(
    "function style", 1
)[0]
assert "for(const saved of snapshot)" in apply_lora
assert "if(!item)continue" in apply_lora
assert "settings[item.id]" in apply_lora
lora_apply_test = f"""
global.window=global;
const library=[{{id:'saved',filename:'saved.safetensors',defaultStrength:1}},{{id:'new',filename:'new.safetensors',defaultStrength:0.8}}];
let projects=[{{id:'project',loraSelections:{{'ref:04':{{saved:{{enabled:false,strength:1,order:0}},new:{{enabled:true,strength:0.8,order:1}}}}}}}}];
function loadLib(){{return library;}} function getProjectList(){{return projects;}} function getActiveProjectId(){{return'project';}}
function saveProjectList(value){{projects=value;}} function renderQuick(){{}}
window.h3ApplyLoraPreset{apply_lora.strip()}
window.h3ApplyLoraPreset('ref:04',[{{id:'deleted',filename:'gone.safetensors',enabled:true,strength:2,order:0}},{{id:'saved',filename:'saved.safetensors',enabled:true,strength:0.4,order:3}}]);
const settings=projects[0].loraSelections['ref:04'];
if(!settings.saved.enabled||settings.saved.strength!==0.4||settings.saved.order!==3)process.exit(1);
if(!settings.new.enabled||settings.new.strength!==0.8||settings.new.order!==1)process.exit(2);
"""
subprocess.run(["node", "-e", lora_apply_test], check=True)

# V2 localStorage has an explicit version and imports legacy {name,text}
# records as prompt-only presets, leaving missing settings to apply-time APIs.
assert "h3MobileGenerationPresetsV2" in presets
assert "STORE_VERSION=2" in presets
assert "h3MobilePromptLibraryV1" in presets
node_harness = f"""
const values=new Map();
values.set('h3MobilePromptLibraryV1',JSON.stringify([{{name:'Legacy',text:'old prompt'}}]));
global.window=global;
global.localStorage={{getItem:key=>values.has(key)?values.get(key):null,setItem:(key,value)=>values.set(key,value)}};
global.document={{readyState:'loading',addEventListener:()=>{{}},querySelector:()=>null}};
global.alert=()=>{{}};global.confirm=()=>true;
eval({json.dumps(presets)});
const items=window.h3GenerationPresets.load();
if(items.length!==1||items[0].name!=='Legacy'||items[0].prompt!=='old prompt'||items[0].kind!=='legacy')process.exit(1);
const stored=JSON.parse(values.get('h3MobileGenerationPresetsV2'));
if(stored.version!==2||stored.items[0].prompt!=='old prompt')process.exit(2);
"""
subprocess.run(["node", "-e", node_harness], check=True)

# No image files, project titles, batch titles, or credentials enter the preset
# snapshot/storage implementation.
for forbidden in ("CIVITAI", "api_key", "Civitai API", "batchTitle", "#title", "#image0"):
    assert forbidden not in presets

for path in (
    WEB / "prompt-library.js",
    WEB / "app.js",
    WEB / "batch-v2.js",
    WEB / "lora-library.js",
):
    subprocess.run(["node", "--check", str(path)], check=True)

print("Generation preset and history validation OK")
