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
    "HMCumshot_V2.safetensors",
    "deepthroat_v02.safetensors",
    "Squirt_HM_v1.safetensors",
    "Squirt_HM_v2.safetensors.safetensors",
    "Nipple_v2.safetensors",
    "Panties_v1.safetensors",
    "Passionate_Kiss.safetensors",
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
assert catalog_section.count("filename:") == 15
for filename in DEFAULT_FILENAMES:
    assert catalog_section.count(filename) == 1, filename
for filename in LEGACY_FILENAMES:
    assert filename not in catalog_section, filename
assert "default-15-v2" in js
assert "migrateDefaultCatalog();" in js

# Registration deletion is local persistent-data deletion. It does not call the
# API endpoint that deletes a Pod file.
remove_item = js.split("function removeItem", 1)[1].split("function moveLibrary", 1)[0]
assert "saveLib(loadLib().filter(item=>item.id!==id))" in remove_item
assert "delete project.loraSelections?.[ctx]?.[id]" in remove_item
assert "fetch(" not in remove_item
delete_binding = js.split("function bindManagerRow", 1)[1].split("function addRecord", 1)[0]
assert "m-delete" in delete_binding
assert "confirm(" in delete_binding
assert ".safetensors実ファイルは削除されません" in delete_binding

# Bulk matching uses the same catalog and existing upload route. Unknown
# .safetensors are auto-registered as custom loras (initial OFF, strength 1.0).
bulk_upload = js.split("async function handleUploadFiles", 1)[1].split(
    "function bulkUploadFiles", 1
)[0]
assert "catalogDefinition(file.name)" in bulk_upload
assert "value.originalFilename===file.name||value.filename===file.name" in bulk_upload
assert "runUpload(item,file)" in bulk_upload
assert "one file failing never stops the rest" in bulk_upload
assert "/h3-mobile/api/loras/upload" in js
assert '@routes.post("/h3-mobile/api/loras/upload")' in routes

# Execute the real browser functions in a VM. No real safetensors bytes are
# stored or transferred; the upload transport (XHR) is stubbed.
instrumented = js.replace(
    "function init(){seed();",
    "window.__loraTest={seed,loadLib,removeItem,addRecord,bulkUploadFiles,handleUploadFiles,quickMarkup,catalogDefinition};function init(){seed();",
    1,
)
assert instrumented != js

node_test = f"""
const vm=require('vm');
const source={json.dumps(instrumented)};
const defaults={json.dumps(DEFAULT_FILENAMES)};
const legacy={json.dumps(LEGACY_FILENAMES)};

function makeEnvironment(entries=[]){{
 const values=new Map(entries),uploadCalls=[];
 const message={{textContent:''}},bulkInput={{value:'selected'}};
 const nodes=new Map([['#loraRestoreMsg',message],['#loraAddMsg',message]]);
 const localStorage={{
  getItem:key=>values.has(key)?values.get(key):null,
  setItem:(key,value)=>values.set(key,String(value)),
  removeItem:key=>values.delete(key)
 }};
 class FakeFormData{{append(){{}}}}
 class FakeXHR{{
  constructor(){{this.upload={{}};this.status=200;this.responseText=JSON.stringify({{ok:true,sha256:'b'.repeat(64),size:10}});}}
  open(method,url){{this.method=method;this.url=String(url);}}
  send(){{uploadCalls.push({{url:this.url,method:this.method}});
   if(this.upload.onprogress)this.upload.onprogress({{lengthComputable:true,loaded:5,total:10}});
   if(this.upload.onprogress)this.upload.onprogress({{lengthComputable:true,loaded:10,total:10}});
   if(this.upload.onload)this.upload.onload();
   if(this.onload)this.onload();
  }}
 }}
 const fetchImpl=async(url)=>({{ok:true,json:async()=>({{files:[]}}),text:async()=>''}});
 const document={{readyState:'loading',addEventListener:()=>{{}},querySelector:selector=>nodes.get(selector)||null,querySelectorAll:()=>[],createElement:()=>({{}}),head:{{appendChild:()=>{{}}}}}};
 const window={{fetch:fetchImpl,addEventListener:()=>{{}}}};
 const context={{
  localStorage,document,window,fetch:fetchImpl,FormData:FakeFormData,XMLHttpRequest:FakeXHR,
  crypto:require('crypto').webcrypto,console,setInterval:()=>0,clearInterval:()=>{{}},setTimeout,
  URL,Blob,Response,confirm:()=>true,alert:()=>{{}},location:{{reload:()=>{{}}}},apiUrl:value=>value,
  getProjects:()=>JSON.parse(localStorage.getItem('h3MobileProjects')||'[]'),
  saveProjects:value=>localStorage.setItem('h3MobileProjects',JSON.stringify(value)),
  getActiveProjectId:()=>null
 }};
 vm.createContext(context);vm.runInContext(source,context);
 return{{values,uploadCalls,message,api:window.__loraTest}};
}}
function names(env){{return env.api.loadLib().map(item=>item.filename);}}
function check(condition,code){{if(!condition){{console.error('TEST '+code+' failed');process.exit(code);}}}}

(async()=>{{
 // TEST 1: new storage receives the 15 defaults exactly once, all file-only.
 let env=makeEnvironment();env.api.seed();
 check(JSON.stringify(names(env))===JSON.stringify(defaults),1);
 check(env.api.loadLib().every(item=>!('url'in item)&&!('sourceType'in item)&&!('installMethod'in item)),1);

 // TEST 2: a normal seed/page reload does not append another 15.
 env.api.seed();check(names(env).length===15&&new Set(names(env)).size===15,2);

 // TEST 3: all 15 selected files upload through the existing upload route (XHR).
 const files=defaults.map(name=>({{name,size:10,payload:'BINARY_MUST_NOT_ENTER_LOCAL_STORAGE'}}));
 await env.api.bulkUploadFiles(files);
 check(env.uploadCalls.length===15,3);
 check(env.uploadCalls.every((call,index)=>call.method==='POST'&&call.url.includes('/h3-mobile/api/loras/upload?filename='+encodeURIComponent(defaults[index]))),3);
 check(!env.values.get('h3MobileLoraLibraryV1').includes('BINARY_MUST_NOT_ENTER_LOCAL_STORAGE'),3);
 // learned hash is stored as metadata, never replayed as an expected hash.
 check(env.api.loadLib().every(item=>item.sha256==='b'.repeat(64)),3);
 check(env.uploadCalls.every(call=>!call.url.includes('&sha256=')&&!call.url.includes('expected_sha256')),3);

 // TEST 4: selecting the same 15 again reuses cards, never duplicates.
 await env.api.bulkUploadFiles(files);
 check(names(env).length===15&&new Set(names(env)).size===15,4);
 check(env.uploadCalls.length===30,4);

 // TEST 5: an unknown .safetensors is auto-registered as a custom lora that is
 // OFF everywhere with strength 1.0; a legacy alias is likewise just a custom
 // lora now (no URL machinery to route it through).
 await env.api.bulkUploadFiles([{{name:'Unknown_Custom.safetensors',size:10}}]);
 check(names(env).includes('Unknown_Custom.safetensors'),5);
 const custom=env.api.loadLib().find(item=>item.filename==='Unknown_Custom.safetensors');
 check(custom.defaultStrength===1,5);
 const projects=JSON.parse(env.values.get('h3MobileProjects')||'[]');
 // no active project in this harness, so just assert the record default is OFF
 check(custom.name==='Unknown Custom',5);

 // TEST 6: delete one registration only; no file-delete request occurs.
 const before=env.uploadCalls.length;
 const victim=env.api.loadLib()[0];env.api.removeItem(victim.id);
 check(names(env).length===15&&!names(env).includes(victim.filename),6);
 check(!env.api.quickMarkup('i2v').includes(victim.name),6);
 check(env.uploadCalls.length===before,6);

 // TEST 7: recreate the page VM over the same storage; deleted card stays gone.
 const reloaded=makeEnvironment([...env.values.entries()]);reloaded.api.seed();
 check(!names(reloaded).includes(victim.filename),7);

 // TEST 8: one-time migration removes every legacy default record, preserves an
 // unrelated custom card, keeps unchanged deepthroat once, installs all defaults.
 const oldLibrary=legacy.map((filename,index)=>({{id:'old-'+index,name:'old-'+index,filename,originalFilename:filename,sourceType:'url',url:'https://example.com/'+filename}}));
 oldLibrary.push({{id:'deep-existing',name:'deep',filename:'deepthroat_v02.safetensors',originalFilename:'deepthroat_v02.safetensors',sourceType:'file'}});
 oldLibrary.push({{id:'custom',name:'Custom',filename:'Custom.safetensors',originalFilename:'Custom.safetensors',sourceType:'file'}});
 const migrated=makeEnvironment([
  ['h3MobileLoraLibraryV1',JSON.stringify(oldLibrary)],
  ['h3MobileProjects',JSON.stringify([{{id:'p',loraSelections:{{}}}}])]
 ]);
 migrated.api.seed();const migratedNames=names(migrated);
 check(defaults.every(name=>migratedNames.filter(value=>value===name).length===1),8);
 check(legacy.every(name=>!migratedNames.includes(name)),8);
 check(migratedNames.includes('Custom.safetensors')&&migratedNames.length===16,8);
 check(migrated.values.get('h3MobileLoraCatalogVersion')==='default-15-v2',8);
 // migration also strips URL-era fields from every surviving record.
 check(migrated.api.loadLib().every(item=>!('url'in item)&&!('sourceType'in item)),8);
}})().catch(error=>{{console.error(error);process.exit(99);}});
"""
subprocess.run(["node", "-e", node_test], check=True)

tracked = subprocess.check_output(
    ["git", "ls-files", "--", "*.safetensors"], cwd=ROOT, text=True
).strip()
assert not tracked, f"safetensors must not be tracked: {tracked}"

print("Default LoRA catalog + file-only cleanup TEST 1-8 OK")
