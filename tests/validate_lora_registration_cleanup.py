import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "h3-mobile" / "web" / "lora-library.js"
js = JS_PATH.read_text()

retired = {
    "aio-v25": "HMNSFW-AIO-V2.5.safetensors",
    "motion-booster-v2": "H3_Motion_BoosterV2.safetensors",
    "penisv2-epoch60": "PenisV2_minimax-h3_epoch60.safetensors",
}

# The old records are migration targets only; they are no longer seed records.
assert "const DEFAULTS=" not in js
assert "RETIRED_REGISTRATIONS" in js
assert "purgeRetiredRegistrations();" in js
assert "h3MobileLoraRegistrationCleanupV3" in js
for filename in retired.values():
    assert filename in js

# Registration deletion is persistent browser-data deletion and remains
# separate from the explicit Pod-file delete endpoint.
remove_item = js.split("function removeItem", 1)[1].split("function moveLibrary", 1)[0]
assert "saveLib(loadLib().filter(item=>item.id!==id))" in remove_item
assert "delete project.loraSelections?.[ctx]?.[id]" in remove_item
assert "removeSelectionIds(legacy,new Set([id]))" in remove_item
assert "fetch(" not in remove_item
delete_binding = js.split("function bindManagerRow", 1)[1].split("let managerPoll", 1)[0]
assert "m-delete" in delete_binding
assert ".safetensors実ファイルは削除されません" in delete_binding

remove_match = re.search(r"function removeItem\(id\)\{[^\n]+\}", js)
assert remove_match
remove_test = (
    "const CONTEXTS=['i2v','ref:04'];const LIB_KEY='library',LEGACY_SEL_KEY='legacy';"
    "const values=new Map([[LIB_KEY,JSON.stringify([{id:'remove'},{id:'keep'}])],[LEGACY_SEL_KEY,JSON.stringify({'ref:04':{remove:{},keep:{}}})]]);"
    "const localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,String(value))};"
    "let projects=[{loraSelections:{i2v:{remove:{},keep:{}},'ref:04':{remove:{},keep:{}}}}];"
    "function loadJson(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}}"
    "function loadLib(){return loadJson(LIB_KEY,[]);}function saveLib(value){localStorage.setItem(LIB_KEY,JSON.stringify(value));}"
    "function getProjectList(){return projects;}function saveProjectList(value){projects=value;}"
    "function removeSelectionIds(selections,ids){for(const values of Object.values(selections||{}))for(const id of ids)delete values[id];return true;}"
    + remove_match.group(0)
    + "removeItem('remove');"
    + "if(loadLib().map(item=>item.id).join(',')!=='keep')process.exit(1);"
    + "if(Object.keys(projects[0].loraSelections.i2v).join(',')!=='keep')process.exit(2);"
    + "if(Object.keys(loadJson(LEGACY_SEL_KEY,{})['ref:04']).join(',')!=='keep')process.exit(3);"
)
subprocess.run(["node", "-e", remove_test], check=True)

# Simulate an upgraded browser with the three stale localStorage records, one
# unrelated record, and project/legacy selections. Running the real script
# twice models the first load plus a full page reload.
old_library = [
    {
        "id": "aio-v25",
        "name": "HMNSFW AIO V2.5",
        "filename": retired["aio-v25"],
        "sourceType": "url",
    },
    {
        "id": "custom-motion-record",
        "name": "H3 Motion Booster V2",
        "filename": retired["motion-booster-v2"],
        "sourceType": "url",
    },
    {
        "id": "penisv2-epoch60",
        "name": "PenisV2 epoch60",
        "filename": retired["penisv2-epoch60"],
        "sourceType": "url",
    },
    {
        "id": "keep-me",
        "name": "Keep Me",
        "filename": "Keep_Me.safetensors",
        "sourceType": "file",
    },
]
ids = ["aio-v25", "custom-motion-record", "penisv2-epoch60", "keep-me"]
selection = {item_id: {"enabled": True, "strength": 0.5, "order": index} for index, item_id in enumerate(ids)}
node_test = f"""
const fs=require('fs'),vm=require('vm'),source=fs.readFileSync({json.dumps(str(JS_PATH))},'utf8');
const values=new Map([
 ['h3MobileLoraLibraryV1',JSON.stringify({json.dumps(old_library)})],
 ['h3MobileLoraSelectionsV1',JSON.stringify({{'ref:04':{json.dumps(selection)}}})],
 ['h3MobileProjects',JSON.stringify([{{id:'project',loraSelections:{{'ref:04':{json.dumps(selection)}}}}}])]
]);
const localStorage={{getItem:key=>values.has(key)?values.get(key):null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)}};
let ready;
const document={{readyState:'loading',addEventListener:(name,callback)=>{{if(name==='DOMContentLoaded')ready=callback;}},querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>({{}}),head:{{appendChild:()=>{{}}}}}};
const window={{fetch:async()=>({{ok:true,json:async()=>({{files:[]}})}}),addEventListener:()=>{{}}}};
const context={{localStorage,document,window,crypto:require('crypto').webcrypto,console,setInterval:()=>0,clearInterval:()=>{{}},setTimeout,URL,Blob,Response,FormData,confirm:()=>true,alert:()=>{{}},getProjects:()=>JSON.parse(localStorage.getItem('h3MobileProjects')||'[]'),saveProjects:value=>localStorage.setItem('h3MobileProjects',JSON.stringify(value)),getActiveProjectId:()=>null}};
context.globalThis=context;vm.createContext(context);
function loadPage(){{ready=null;vm.runInContext(source,context);if(!ready)throw new Error('DOMContentLoaded handler missing');ready();}}
loadPage();
let library=JSON.parse(localStorage.getItem('h3MobileLoraLibraryV1'));
if(library.length!==1||library[0].id!=='keep-me')process.exit(1);
let projects=JSON.parse(localStorage.getItem('h3MobileProjects'));
if(Object.keys(projects[0].loraSelections['ref:04']).join(',')!=='keep-me')process.exit(2);
let legacy=JSON.parse(localStorage.getItem('h3MobileLoraSelectionsV1'));
if(Object.keys(legacy['ref:04']).join(',')!=='keep-me')process.exit(3);
if(localStorage.getItem('h3MobileLoraRegistrationCleanupV3')!=='1')process.exit(4);
loadPage();
library=JSON.parse(localStorage.getItem('h3MobileLoraLibraryV1'));
if(library.length!==1||library[0].filename!=='Keep_Me.safetensors')process.exit(5);
"""
subprocess.run(["node", "-e", node_test], check=True)

# With no registered dynamic LoRA, fixed workflow LoRA nodes are not stripped.
strip_match = re.search(r"function stripManaged\(workflow\)\{[^\n]+\}", js)
assert strip_match
strip_test = (
    "function loadLib(){return [];}\n"
    + strip_match.group(0)
    + "\nconst workflow={a:{class_type:'LoraLoaderModelOnly',inputs:{model:['u',0],lora_name:'HMNSFW-AIO-V2.5.safetensors'},_meta:{title:'Ref2VA HMNSFW AIO V2.5'}},b:{inputs:{model:['a',0]}}};\n"
    + "stripManaged(workflow);if(!workflow.a||workflow.b.inputs.model[0]!=='a')process.exit(1);\n"
)
subprocess.run(["node", "-e", strip_test], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("LoRA registration cleanup validation OK")
