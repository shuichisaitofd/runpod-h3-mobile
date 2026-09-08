import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "h3-mobile" / "web" / "lora-library.js"
ROUTES_PATH = ROOT / "h3-mobile" / "lora_routes.py"
js = JS_PATH.read_text()
routes = ROUTES_PATH.read_text()

DEFAULT_FILENAMES = (
    "AIO_v2.5.safetensors",
    "BJ_v3.safetensors",
    "Finger_BEAN_v1.safetensors",
    "deepthroat_v02.safetensors",
    "Squirt_HM_v1.safetensors",
    "Nipple_v2.safetensors",
    "Panties_v1.safetensors",
    "Motion_FL2VA_v2.safetensors",
    "Motion_REF2VA_v2.safetensors",
    "Mystic_FL2VA_v4.safetensors",
    "Penis_HM_v2.safetensors",
    "Pussy_HM_v1.safetensors",
)

LEGACY_FILENAMES = (
    "HMNSFW-AIO-V2.5.safetensors",
    "MM-H3 - Blowjob v3.safetensors",
    "BEANFLK_H3_V1.safetensors",
    "HMMasturbationV1.safetensors",
    "H3_Motion_BoosterV2.safetensors",
    "ref2VA_Motion_v2.safetensors",
    "MysticXXX_MMH3-V4.safetensors",
    "PenisV2_minimax-h3_epoch60.safetensors",
    "Vagina_minimax-h3_epoch20.safetensors",
)

# Single source of truth: only this catalog defines current defaults. Legacy
# filenames live outside it and are used strictly as one-time migration input.
catalog_section = js.split("const DEFAULT_LORA_CATALOG=", 1)[1].split(
    "const LEGACY_DEFAULT_FILENAMES=", 1
)[0]
assert catalog_section.count("filename:") == 12
for filename in DEFAULT_FILENAMES:
    assert catalog_section.count(filename) == 1, filename
for filename in LEGACY_FILENAMES:
    assert filename not in catalog_section, filename
assert "default-12-v1" in js
assert "migrateDefaultCatalog();" in js

# Registration deletion is local persistent-data deletion. It does not call
# the API endpoint that deletes a Pod file.
remove_item = js.split("function removeItem", 1)[1].split("function moveLibrary", 1)[0]
assert "saveLib(loadLib().filter(item=>item.id!==id))" in remove_item
assert "delete project.loraSelections?.[ctx]?.[id]" in remove_item
assert "fetch(" not in remove_item
delete_binding = js.split("function bindManagerRow", 1)[1].split("let managerPoll", 1)[0]
assert "m-delete" in delete_binding
assert "confirm(" in delete_binding
assert ".safetensors実ファイルは削除されません" in delete_binding

# Bulk matching uses the same catalog and existing upload route. Unknown files
# are reported instead of being attached to an arbitrary card.
bulk_upload = js.split("async function bulkUploadFiles", 1)[1].split(
    "async function restoreToPod", 1
)[0]
assert "catalogDefinition(file.name)" in bulk_upload
assert "value.originalFilename===file.name||value.filename===file.name" in bulk_upload
assert "await uploadItem(item,file)" in bulk_upload
assert "未登録ファイル" in bulk_upload
assert "/h3-mobile/api/loras/upload" in js
assert '@routes.post("/h3-mobile/api/loras/upload")' in routes

# Execute the real browser functions in a VM. This covers TEST 1-10 without
# storing or transferring real safetensors bytes.
instrumented = js.replace(
    "function init(){seed();",
    "window.__loraTest={seed,loadLib,removeItem,bulkUploadFiles,quickMarkup};function init(){seed();",
    1,
)
assert instrumented != js

node_test = f"""
const vm=require('vm');
const source={json.dumps(instrumented)};
const defaults={json.dumps(DEFAULT_FILENAMES)};
const legacy={json.dumps(LEGACY_FILENAMES)};

function makeEnvironment(entries=[]){{
 const values=new Map(entries),fetchCalls=[];
 const message={{textContent:''}},bulkInput={{value:'selected'}};
 const nodes=new Map([['#loraRestoreMsg',message],['#loraBulkFiles',bulkInput]]);
 const localStorage={{
  getItem:key=>values.has(key)?values.get(key):null,
  setItem:(key,value)=>values.set(key,String(value)),
  removeItem:key=>values.delete(key)
 }};
 class FakeFormData{{constructor(){{this.parts=[];}}append(...args){{this.parts.push(args);}}}}
 const fetchImpl=async(url,init)=>{{fetchCalls.push({{url:String(url),method:init?.method,body:init?.body}});return{{ok:true,json:async()=>({{sha256:'a'.repeat(64)}}),text:async()=>''}};}};
 const document={{readyState:'loading',addEventListener:()=>{{}},querySelector:selector=>nodes.get(selector)||null,querySelectorAll:()=>[],createElement:()=>({{}}),head:{{appendChild:()=>{{}}}}}};
 const window={{fetch:fetchImpl,addEventListener:()=>{{}}}};
 const context={{
  localStorage,document,window,fetch:fetchImpl,FormData:FakeFormData,
  crypto:require('crypto').webcrypto,console,setInterval:()=>0,clearInterval:()=>{{}},setTimeout,
  URL,Blob,Response,confirm:()=>true,alert:()=>{{}},apiUrl:value=>value,
  getProjects:()=>JSON.parse(localStorage.getItem('h3MobileProjects')||'[]'),
  saveProjects:value=>localStorage.setItem('h3MobileProjects',JSON.stringify(value)),
  getActiveProjectId:()=>null
 }};
 vm.createContext(context);vm.runInContext(source,context);
 return{{values,fetchCalls,message,api:window.__loraTest}};
}}
function names(env){{return env.api.loadLib().map(item=>item.filename);}}
function check(condition,code){{if(!condition){{console.error('TEST '+code+' failed');process.exit(code);}}}}

(async()=>{{
 // TEST 1: new storage receives the 12 defaults exactly once.
 let env=makeEnvironment();env.api.seed();
 check(JSON.stringify(names(env))===JSON.stringify(defaults),1);
 check(env.api.loadLib().every(item=>item.sourceType==='file'&&item.installMethod===null),1);

 // TEST 2: a normal seed/page reload does not append another 12.
 env.api.seed();check(names(env).length===12&&new Set(names(env)).size===12,2);

 // TEST 3: all 12 selected files match exact cards and use Pod upload.
 const files=defaults.map(name=>({{name,payload:'BINARY_MUST_NOT_ENTER_LOCAL_STORAGE'}}));
 await env.api.bulkUploadFiles(files);
 check(env.fetchCalls.length===12,3);
 check(env.api.loadLib().every(item=>item.installMethod==='file'),3);
 check(env.fetchCalls.every((call,index)=>call.url.includes('/h3-mobile/api/loras/upload?filename='+encodeURIComponent(defaults[index]))),10);
 check(!env.values.get('h3MobileLoraLibraryV1').includes('BINARY_MUST_NOT_ENTER_LOCAL_STORAGE'),3);

 // TEST 4: selecting the same 12 again reuses cards, never duplicates.
 await env.api.bulkUploadFiles(files);
 check(names(env).length===12&&new Set(names(env)).size===12,4);
 check(env.fetchCalls.length===24,4);

 // Unknown and legacy aliases are reported, not assigned or uploaded.
 const beforeUnknown=env.fetchCalls.length;
 await env.api.bulkUploadFiles([{{name:'Unknown.safetensors'}},{{name:legacy[0]}}]);
 check(env.fetchCalls.length===beforeUnknown,9);
 check(env.message.textContent.includes('未登録ファイル: Unknown.safetensors, '+legacy[0]),9);

 // TEST 5/7/8: delete one registration only; no file-delete request occurs.
 const victim=env.api.loadLib()[0];env.api.removeItem(victim.id);
 check(names(env).length===11&&!names(env).includes(victim.filename),5);
 check(!env.api.quickMarkup('i2v').includes(victim.name),5);
 check(names(env).every(name=>defaults.includes(name)),7);
 check(env.fetchCalls.length===beforeUnknown,8);

 // TEST 6: recreate the page VM over the same storage; deleted card stays gone.
 const reloaded=makeEnvironment([...env.values.entries()]);reloaded.api.seed();
 check(names(reloaded).length===11&&!names(reloaded).includes(victim.filename),6);

 // TEST 9: one-time migration removes every legacy record, preserves an
 // unrelated card, keeps unchanged deepthroat once, and installs all defaults.
 const oldLibrary=legacy.map((filename,index)=>({{id:'old-'+index,name:'old-'+index,filename,originalFilename:filename,sourceType:'url'}}));
 oldLibrary.push({{id:'deep-existing',name:'deep',filename:'deepthroat_v02.safetensors',originalFilename:'deepthroat_v02.safetensors',sourceType:'file'}});
 oldLibrary.push({{id:'custom',name:'Custom',filename:'Custom.safetensors',originalFilename:'Custom.safetensors',sourceType:'file'}});
 const oldSelections=Object.fromEntries(oldLibrary.map((item,index)=>[item.id,{{enabled:true,strength:.5,order:index}}]));
 const migrated=makeEnvironment([
  ['h3MobileLoraLibraryV1',JSON.stringify(oldLibrary)],
  ['h3MobileLoraSelectionsV1',JSON.stringify({{'ref:04':oldSelections}})],
  ['h3MobileProjects',JSON.stringify([{{id:'p',loraSelections:{{'ref:04':oldSelections}}}}])]
 ]);
 migrated.api.seed();const migratedNames=names(migrated);
 check(defaults.every(name=>migratedNames.filter(value=>value===name).length===1),9);
 check(legacy.every(name=>!migratedNames.includes(name)),9);
 check(migratedNames.includes('Custom.safetensors')&&migratedNames.length===13,9);
 check(migrated.values.get('h3MobileLoraCatalogVersion')==='default-12-v1',9);

 // TEST 10 is also covered by the 24 calls through the existing upload route.
 check(env.fetchCalls.slice(0,24).every(call=>call.method==='POST'),10);
}})().catch(error=>{{console.error(error);process.exit(99);}});
"""
subprocess.run(["node", "-e", node_test], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("Default LoRA catalog TEST 1-10 OK")
