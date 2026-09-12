(()=>{
'use strict';

const LIB_KEY='h3MobileLoraLibraryV1';
const LEGACY_SEL_KEY='h3MobileLoraSelectionsV1';
const CATALOG_VERSION_KEY='h3MobileLoraCatalogVersion';
const CATALOG_VERSION='default-12-v1';
const PROJECTS_KEY='h3MobileProjects';
const ACTIVE_PROJECT_KEY='h3MobileActiveProjectId';
const PRESET_KEY='h3MobileGenerationPresetsV2';
const BACKUP_SCHEMA='h3-mobile-settings';
const BACKUP_VERSION=3;
const CONTEXTS=['i2v','ref:03','ref:04','ref:05','ref:fast','ref:stable'];
// Catalog entries carry no `expectedSha256` today. When one is added it is a
// *trusted* digest and is the only value ever sent to the server as an expected
// hash. A hash the browser learned from its own past upload is never trusted.
const DEFAULT_LORA_CATALOG=Object.freeze([
 {id:'default-aio-v25',name:'AIO v2.5',filename:'AIO_v2.5.safetensors'},
 {id:'default-bj-v3',name:'BJ v3',filename:'BJ_v3.safetensors'},
 {id:'default-finger-bean-v1',name:'Finger BEAN v1',filename:'Finger_BEAN_v1.safetensors'},
 {id:'default-deepthroat-v02',name:'deepthroat v02',filename:'deepthroat_v02.safetensors'},
 {id:'default-squirt-hm-v1',name:'Squirt HM v1',filename:'Squirt_HM_v1.safetensors'},
 {id:'default-nipple-v2',name:'Nipple v2',filename:'Nipple_v2.safetensors'},
 {id:'default-panties-v1',name:'Panties v1',filename:'Panties_v1.safetensors'},
 {id:'default-motion-fl2va-v2',name:'Motion FL2VA v2',filename:'Motion_FL2VA_v2.safetensors'},
 {id:'default-motion-ref2va-v2',name:'Motion REF2VA v2',filename:'Motion_REF2VA_v2.safetensors'},
 {id:'default-mystic-fl2va-v4',name:'Mystic FL2VA v4',filename:'Mystic_FL2VA_v4.safetensors'},
 {id:'default-penis-hm-v2',name:'Penis HM v2',filename:'Penis_HM_v2.safetensors'},
 {id:'default-pussy-hm-v1',name:'Pussy HM v1',filename:'Pussy_HM_v1.safetensors'}
]);
const LEGACY_DEFAULT_FILENAMES=new Set([
 'HMNSFW-AIO-V2.5.safetensors',
 'MM-H3 - Blowjob v3.safetensors',
 'BEANFLK_H3_V1.safetensors',
 'HMMasturbationV1.safetensors',
 'H3_Motion_BoosterV2.safetensors',
 'ref2VA_Motion_v2.safetensors',
 'MysticXXX_MMH3-V4.safetensors',
 'PenisV2_minimax-h3_epoch60.safetensors',
 'Vagina_minimax-h3_epoch20.safetensors'
]);
const q=s=>document.querySelector(s);
const qa=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function uid(){return crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random();}
function loadJson(key,fallback){try{const value=JSON.parse(localStorage.getItem(key)||'null');return value??fallback;}catch{return fallback;}}
function autoName(filename){return String(filename||'LoRA').replace(/\.safetensors$/i,'').replace(/[_-]+/g,' ').trim()||'LoRA';}
// file-only registry record. URL-era fields are intentionally dropped on load
// (see stripUrlFields) so an old backup or an old localStorage value is
// normalized to the file-only shape.
function normalizeItem(item){
 const filename=String(item?.filename||item?.originalFilename||'').trim();
 return {
  id:String(item?.id||uid()),
  name:String(item?.name||autoName(filename)),
  filename,
  originalFilename:String(item?.originalFilename||filename),
  sha256:String(item?.sha256||'').toLowerCase(),
  defaultStrength:Number.isFinite(Number(item?.defaultStrength))?Number(item.defaultStrength):1
 };
}
function stripUrlFields(item){const clone={...item};for(const key of ['url','sourceType','installMethod','pendingInstallMethod'])delete clone[key];return clone;}
function loadLib(){const value=loadJson(LIB_KEY,[]);return Array.isArray(value)?value.map(normalizeItem):[];}
function saveLib(value){localStorage.setItem(LIB_KEY,JSON.stringify(value.map(normalizeItem)));}
function defaultEnabled(){return false;}
function getProjectList(){return typeof getProjects==='function'?getProjects():[];}
function saveProjectList(projects){if(typeof saveProjects==='function')saveProjects(projects);}
function clone(value){return JSON.parse(JSON.stringify(value||{}));}
function removeSelectionIds(selections,ids){let changed=false;for(const values of Object.values(selections||{})){if(!values||typeof values!=='object')continue;for(const id of ids){if(Object.prototype.hasOwnProperty.call(values,id)){delete values[id];changed=true;}}}return changed;}
function catalogRecord(definition){return normalizeItem({...definition,originalFilename:definition.filename,sha256:'',defaultStrength:1});}
function catalogDefinition(filename){return DEFAULT_LORA_CATALOG.find(item=>item.filename===filename)||null;}
function trustedExpectedSha(filename){const def=catalogDefinition(filename);return def&&def.expectedSha256?String(def.expectedSha256).toLowerCase():'';}
function migrateDefaultCatalog(){
 if(localStorage.getItem(CATALOG_VERSION_KEY)===CATALOG_VERSION)return;
 const library=loadLib(),removedIds=new Set(library.filter(item=>LEGACY_DEFAULT_FILENAMES.has(item.filename)).map(item=>item.id));
 const next=library.filter(item=>!LEGACY_DEFAULT_FILENAMES.has(item.filename));
 for(const definition of DEFAULT_LORA_CATALOG)if(!next.some(item=>item.filename===definition.filename))next.push(catalogRecord(definition));
 saveLib(next);
 const legacy=loadJson(LEGACY_SEL_KEY,null);if(legacy&&removeSelectionIds(legacy,removedIds))localStorage.setItem(LEGACY_SEL_KEY,JSON.stringify(legacy));
 const projects=getProjectList();let changed=false;for(const project of projects)if(removeSelectionIds(project.loraSelections,removedIds))changed=true;if(changed)saveProjectList(projects);
 localStorage.setItem(CATALOG_VERSION_KEY,CATALOG_VERSION);
}
function seed(){
 migrateDefaultCatalog();
 const library=loadLib();
 const legacy=loadJson(LEGACY_SEL_KEY,{}),projects=getProjectList();let changed=false;
 for(const project of projects){
  if(!project.loraSelections){project.loraSelections=clone(legacy);changed=true;}
  for(const ctx of CONTEXTS){project.loraSelections[ctx]=project.loraSelections[ctx]||{};library.forEach((item,index)=>{if(!project.loraSelections[ctx][item.id]){project.loraSelections[ctx][item.id]={enabled:defaultEnabled(ctx,item.id),strength:item.defaultStrength,order:index};changed=true;}else if(!Number.isFinite(Number(project.loraSelections[ctx][item.id].order))){project.loraSelections[ctx][item.id].order=index;changed=true;}});}
 }
 if(changed)saveProjectList(projects);
}
function projectContext(ctx){seed();const projects=getProjectList(),activeId=typeof getActiveProjectId==='function'?getActiveProjectId():null,index=projects.findIndex(project=>project.id===activeId);if(index<0)return{};projects[index].loraSelections=projects[index].loraSelections||{};projects[index].loraSelections[ctx]=projects[index].loraSelections[ctx]||{};const settings=projects[index].loraSelections[ctx];let changed=false;loadLib().forEach((item,order)=>{if(!settings[item.id]){settings[item.id]={enabled:defaultEnabled(ctx,item.id),strength:item.defaultStrength,order};changed=true;}});if(changed)saveProjectList(projects);return settings;}
function setSelection(ctx,id,patch){const projects=getProjectList(),activeId=typeof getActiveProjectId==='function'?getActiveProjectId():null,index=projects.findIndex(project=>project.id===activeId);if(index<0)return;projects[index].loraSelections=projects[index].loraSelections||{};projects[index].loraSelections[ctx]=projects[index].loraSelections[ctx]||{};projects[index].loraSelections[ctx][id]={...(projects[index].loraSelections[ctx][id]||{}),...patch};saveProjectList(projects);}
function ordered(ctx){const settings=projectContext(ctx);return loadLib().map((item,index)=>({item,sel:settings[item.id]||{enabled:false,strength:item.defaultStrength,order:index},libraryOrder:index})).sort((a,b)=>(Number(a.sel.order)-Number(b.sel.order))||(a.libraryOrder-b.libraryOrder));}
function selected(ctx){return ordered(ctx).filter(entry=>entry.sel.enabled);}
function ctxFromWorkflow(name){return name==='i2v'?'i2v':name==='ref2va_03'?'ref:03':name==='ref2va_04'?'ref:04':name==='ref2va_05'?'ref:05':name==='ref2va_06_fast'?'ref:fast':name==='ref2va_06_stable'?'ref:stable':null;}
function currentCreateCtx(){return state?.mode==='ref'?`ref:${state.refVariant}`:'i2v';}
function currentBatchCtx(){const mode=q('[data-batch-mode].active')?.dataset.batchMode||'i2v';if(mode!=='ref2va')return'i2v';return`ref:${q('#batchRefVariant [data-batch-variant].active')?.dataset.batchVariant||'04'}`;}
window.h3LoraShouldAddDynv2=ctx=>(ctx!=='i2v'&&ctx!=='ref:03')||selected(ctx).some(({item})=>item.filename==='Motion_REF2VA_v2.safetensors');
window.h3LoraPresetSnapshot=ctx=>ordered(ctx).map(({item,sel})=>({id:item.id,filename:item.filename,enabled:!!sel.enabled,strength:Number(sel.strength),order:Number(sel.order)}));
window.h3ApplyLoraPreset=(ctx,snapshot)=>{if(!Array.isArray(snapshot))return;const library=loadLib(),projects=getProjectList(),activeId=typeof getActiveProjectId==='function'?getActiveProjectId():null,index=projects.findIndex(project=>project.id===activeId);if(index<0)return;projects[index].loraSelections=projects[index].loraSelections||{};projects[index].loraSelections[ctx]=projects[index].loraSelections[ctx]||{};const settings=projects[index].loraSelections[ctx];for(const saved of snapshot){const item=library.find(value=>value.id===saved.id)||library.find(value=>value.filename===saved.filename);if(!item)continue;const current=settings[item.id]||{enabled:false,strength:item.defaultStrength,order:library.indexOf(item)};settings[item.id]={...current,...(typeof saved.enabled==='boolean'?{enabled:saved.enabled}:{}),...(Number.isFinite(Number(saved.strength))?{strength:Number(saved.strength)}:{}),...(Number.isFinite(Number(saved.order))?{order:Number(saved.order)}:{})};}saveProjectList(projects);renderQuick();};

function style(){if(q('#h3LoraCss'))return;const node=document.createElement('style');node.id='h3LoraCss';node.textContent=`
 .bottomin{grid-template-columns:repeat(6,1fr)}
 .h3-lora-quick{display:grid;margin-top:6px}.h3-lora-qrow{display:grid;grid-template-columns:minmax(0,1fr) 48px 68px 26px 26px;gap:5px;align-items:center;padding:7px 0;border-top:1px solid #2b3240}.h3-lora-qrow:first-child{border-top:0}.h3-lora-qname{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.h3-lora-toggle,.h3-lora-mini{border:1px solid #384254;border-radius:8px;background:#151922;color:#98a2b3;padding:6px 3px;font-size:11px}.h3-lora-toggle.active{border-color:#7aa2ff;background:#1b365d;color:#fff;font-weight:700}.h3-lora-strength{padding:6px!important;margin:0!important;font-size:12px}
 .h3-lora-top-actions,.h3-lora-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.h3-lora-top-actions>*{flex:1}.h3-lora-actions>*{flex:0 1 auto}.h3-lora-compact{padding:7px 9px!important;font-size:12px!important;min-width:0!important}.h3-lora-manager{display:grid;gap:8px;margin-top:10px}.h3-lora-item{border:1px solid #2b3240;border-radius:12px;padding:10px;background:#121722}.h3-lora-summary{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:7px;align-items:center}.h3-lora-name{font-size:13px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.h3-lora-status{font-size:11px;color:#f0df9b}.h3-lora-ok{color:#78d99b}.h3-lora-err{color:#ff8d8d}.h3-lora-edit{border-top:0;padding-top:0;margin-top:8px}.h3-lora-edit summary{font-size:12px;text-align:right}.h3-lora-edit-body{padding-top:6px}.h3-lora-progress{height:7px;background:#0b0f15;border:1px solid #293140;border-radius:999px;overflow:hidden;margin:7px 0 4px}.h3-lora-progress>span{display:block;height:100%;background:#7aa2ff;transition:width .2s}.h3-lora-progress.indeterminate>span{width:38%!important;transition:none;animation:h3loraIndeterminate 1.15s ease-in-out infinite}@keyframes h3loraIndeterminate{0%{margin-left:-40%}100%{margin-left:102%}}.h3-lora-inline-progress{font-size:11px;display:flex;justify-content:space-between;color:#cbd2df}.h3-lora-status.h3-lora-busy{color:#7aa2ff}.h3-lora-form{margin-top:10px}.h3-lora-form input{margin-bottom:8px}.h3-lora-filepick{display:block;border:1px dashed #44506a;border-radius:11px;padding:12px;text-align:center;cursor:pointer}.h3-lora-filepick input{display:none}.h3-lora-danger{border-color:#683333!important;color:#ffc0c0!important}.h3-lora-errbox{border:1px solid #683333;border-radius:9px;background:#1c1113;padding:7px 9px;margin-top:7px;font-size:12px}
 @media(max-width:420px){.nav{font-size:11px;padding-left:1px;padding-right:1px}.h3-lora-qrow{grid-template-columns:minmax(0,1fr) 44px 64px 24px 24px;gap:4px}}
 `;document.head.appendChild(node);}
function quickMarkup(ctx){const items=ordered(ctx);if(!items.length)return'<div class="small">登録LoRAはありません。</div>';return items.map(({item,sel})=>`<div class="h3-lora-qrow" data-lora-id="${esc(item.id)}"><span class="h3-lora-qname">${esc(item.name)}</span><button type="button" class="h3-lora-toggle ${sel.enabled?'active':''}" aria-pressed="${sel.enabled?'true':'false'}">${sel.enabled?'ON':'OFF'}</button><input class="h3-lora-strength" type="number" step="0.01" inputmode="decimal" value="${esc(sel.strength)}" aria-label="${esc(item.name)} strength"><button type="button" class="h3-lora-mini lora-up" aria-label="上へ">↑</button><button type="button" class="h3-lora-mini lora-down" aria-label="下へ">↓</button></div>`).join('');}
function moveSelection(ctx,id,delta){const items=ordered(ctx),index=items.findIndex(entry=>entry.item.id===id),next=index+delta;if(index<0||next<0||next>=items.length)return;const currentOrder=items[index].sel.order,nextOrder=items[next].sel.order;setSelection(ctx,items[index].item.id,{order:nextOrder});setSelection(ctx,items[next].item.id,{order:currentOrder});renderQuick();}
function bindQuick(root,ctx){root.querySelectorAll('.h3-lora-qrow').forEach(row=>{const id=row.dataset.loraId,toggle=row.querySelector('.h3-lora-toggle'),strength=row.querySelector('.h3-lora-strength');toggle.onclick=()=>{setSelection(ctx,id,{enabled:toggle.getAttribute('aria-pressed')!=='true'});renderQuick();};strength.oninput=()=>{const value=Number(strength.value);if(Number.isFinite(value))setSelection(ctx,id,{strength:value});};row.querySelector('.lora-up').onclick=()=>moveSelection(ctx,id,-1);row.querySelector('.lora-down').onclick=()=>moveSelection(ctx,id,1);});}
function renderQuick(){const create=q('#h3LoraQuick');if(create){const ctx=currentCreateCtx();create.innerHTML=quickMarkup(ctx);bindQuick(create,ctx);}const batchRoot=q('#h3LoraBatchQuick');if(batchRoot){const ctx=currentBatchCtx();batchRoot.innerHTML=quickMarkup(ctx);bindQuick(batchRoot,ctx);}syncNotes();}
function injectQuick(){const createActions=q('[data-page="create"] .card .actions')?.closest('.card');if(createActions&&!q('#h3LoraQuickCard')){const card=document.createElement('div');card.className='card';card.id='h3LoraQuickCard';card.innerHTML='<div class="row"><h2 style="margin:0;flex:1">LoRA</h2><span class="small">案件別</span></div><div id="h3LoraQuick" class="h3-lora-quick"></div>';createActions.parentNode.insertBefore(card,createActions);}const batchActions=q('#startBatch')?.closest('.card');if(batchActions&&!q('#h3LoraBatchQuickCard')){const card=document.createElement('div');card.className='card';card.id='h3LoraBatchQuickCard';card.innerHTML='<div class="row"><h2 style="margin:0;flex:1">LoRA</h2><span class="small">案件別</span></div><div id="h3LoraBatchQuick" class="h3-lora-quick"></div>';batchActions.parentNode.insertBefore(card,batchActions);}}
function syncNotes(){const create=q('#modeNote');if(create){if(state.mode==='i2v')create.innerHTML='I2V: <b>Turbo + Sage / 4step固定</b>。追加LoRAは上の案件別設定を使用します。';else{const map={'03':'Turbo Enhanced','04':'Sol-Attn + BlockCache Balanced','05':'SLA + BlockCache Balanced',fast:'SLA + Spectrum（高速）',stable:'SLA + Spectrum（安定）'};create.innerHTML=`Ref2VA ${esc(refVariantLabel(state.refVariant))}: <b>${map[state.refVariant]||''}</b>。追加LoRAは上の案件別設定を使用します。`;}}const batchNote=q('#batchModeNote');if(batchNote)batchNote.innerHTML=currentBatchCtx()==='i2v'?'I2V: <b>Turbo + Sage / 4step固定</b>。追加LoRAは上の案件別設定を使用します。':'Ref2VA: 追加LoRAは上の案件別設定を使用します。';}

function formatBytes(value){if(value==null)return'--';const units=['B','KB','MB','GB','TB'];let size=Number(value)||0,index=0;while(size>=1024&&index<units.length-1){size/=1024;index++;}return`${size.toFixed(index>=3?2:index>=2?1:0)} ${units[index]}`;}

// --- upload state -----------------------------------------------------------
// Ephemeral per-card state for the current browser's uploads. "installed" is
// NEVER decided from here or from localStorage: only an actual Pod file counts.
//
// The manager list is painted from THREE independent inputs:
//   loadLib()      - registrations (localStorage, synchronous)
//   lastPodFiles   - last successful /loras/files result (cached, may be stale)
//   uploadState    - this browser's in-flight uploads (synchronous)
// paintManager() rebuilds the list from all three WITHOUT any network call, so
// an upload's status/progress is on screen the instant a file is chosen -
// before xhr.send() runs and regardless of how slow or flaky /loras/files is.
const uploadState=new Map(); // id -> {phase:'queued'|'uploading'|'verifying'|'error', loaded, total, since, message, detail}
const retryFiles=new Map();  // id -> File, so a failed card's [再試行] can resend
let lastPodFiles=new Map();   // cache of the last successful /loras/files
let lastManagedDownloads=new Map(); // server-owned GitHub Release downloads
let podFilesWarning='';       // set when a refresh failed; shown, never destructive
let uploadTicker=null;        // 1s heartbeat so a stalled upload never looks frozen
function setUploadState(id,patch){uploadState.set(id,{...(uploadState.get(id)||{}),...patch});}
function clearUploadState(id){uploadState.delete(id);retryFiles.delete(id);}
function hasActiveUpload(){for(const s of uploadState.values())if(['queued','uploading','verifying'].includes(s.phase))return true;return false;}

function friendlyError(error){
 const detail=String(error&&error.message||error||'').trim();
 if(/sha-?256/i.test(detail))return'SHA256が一致しません';
 if(/timeout|タイムアウト/i.test(detail))return'通信がタイムアウトしました';
 if(/切断|network|load failed|failed to fetch|中止|abort/i.test(detail))return'通信が切断されました';
 if(/empty|空です/i.test(detail))return'アップロードされたファイルが空です';
 return detail?`アップロードに失敗しました: ${detail}`:'アップロードに失敗しました';
}

// onProgress(loadedBytes, knownTotalBytes | 0, phase). knownTotal is 0 when the
// transfer is not length-computable (a proxy stripped Content-Length): the UI
// then shows an indeterminate bar + bytes-sent instead of a percentage, so the
// state is never blank.
function uploadItem(item,file,onProgress){
 return new Promise((resolve,reject)=>{
  const xhr=new XMLHttpRequest();
  const size=Number(file.size)||0;
  const trusted=trustedExpectedSha(item.filename);
  const query=`/h3-mobile/api/loras/upload?filename=${encodeURIComponent(item.filename)}${trusted?`&expected_sha256=${encodeURIComponent(trusted)}`:''}`;
  xhr.open('POST',apiUrl(query));
  const emit=(loaded,total,phase)=>{if(typeof onProgress==='function')onProgress(Number(loaded)||0,Number(total)||0,phase);};
  xhr.upload.onloadstart=()=>emit(0,size,'uploading');
  xhr.upload.onprogress=event=>{
   if(event.lengthComputable)emit(event.loaded,event.total||size,'uploading');
   else emit(event.loaded||0,0,'uploading');
  };
  // Request body fully sent: the server is now streaming + hashing it.
  xhr.upload.onload=()=>emit(size,size,'verifying');
  xhr.onload=()=>{
   if(xhr.status>=200&&xhr.status<300){try{resolve(JSON.parse(xhr.responseText||'{}'));}catch{reject(new Error('サーバー応答を解析できませんでした'));}}
   else reject(new Error((xhr.responseText||'').trim()||`HTTP ${xhr.status}`));
  };
  xhr.onerror=()=>reject(new Error('通信が切断されました'));
  xhr.ontimeout=()=>reject(new Error('通信がタイムアウトしました'));
  xhr.onabort=()=>reject(new Error('アップロードを中止しました'));
  const data=new FormData();data.append('file',file,file.name);
  xhr.send(data);
 });
}

function ensureUploadTicker(){
 if(uploadTicker||!hasActiveUpload())return;
 uploadTicker=setInterval(()=>{
  if(!hasActiveUpload()){clearInterval(uploadTicker);uploadTicker=null;return;}
  for(const [id,state] of uploadState){
   if(state.phase==='verifying'||(state.phase==='uploading'&&!state.total))tickCard(id,state);
  }
 },1000);
}
function tickCard(id,state){
 const row=q(`#h3LoraManager .h3-lora-item[data-id="${id}"]`);if(!row)return;
 const status=row.querySelector('.h3-lora-status');if(!status)return;
 const secs=state.since?Math.max(0,Math.round((Date.now()-state.since)/1000)):0;
 status.classList.add('h3-lora-busy');
 if(state.phase==='verifying')status.textContent=`サーバー検証中… ${secs?`(${secs}s)`:''}`.trim();
 else status.textContent=`アップロード中… ${state.loaded?formatBytes(state.loaded):''} ${secs?`(${secs}s)`:''}`.replace(/\s+/g,' ').trim();
}

async function runUpload(item,file){
 retryFiles.set(item.id,file);
 // Synchronous: the "uploading" row (status + 0% bar) is in the DOM before the
 // XHR is even created, so the very first upload.onprogress has a target.
 setUploadState(item.id,{phase:'uploading',loaded:0,total:Number(file.size)||0,since:Date.now(),message:'',detail:''});
 paintManager();
 renderQuick();
 ensureUploadTicker();
 try{
  const result=await uploadItem(item,file,(loaded,total,phase)=>{
   const next=(phase==='verifying'||(total>0&&loaded>=total))?'verifying':'uploading';
   const prev=uploadState.get(item.id)?.phase;
   setUploadState(item.id,{phase:next,loaded,total,...(prev!==next?{since:Date.now()}:{})});
   if(prev!==next)paintManager();       // phase change: swap markup once
   else applyProgress(item.id);         // same phase: cheap in-place update
  });
  // Server has verified the SHA and atomically renamed by now. Persist the
  // *learned* hash as metadata only — it is never replayed as an expected hash.
  updateItem(item.id,{sha256:String(result.sha256||'').toLowerCase()||item.sha256,originalFilename:file.name});
  // The server returned {ok:true} only AFTER os.replace(part,dest), so the file
  // is on the Pod now. Seed the cache optimistically so the card reads
  // "✓ 導入済み" even if the /loras/files refresh below is slow or failing.
  lastPodFiles.set(item.filename,{filename:item.filename,status:'installed',size:Number(result.size)||1,uploading:false});
  clearUploadState(item.id);
  paintManager();
  renderManager().catch(()=>{scheduleRefresh();});
  renderQuick();
  return true;
 }catch(error){
  setUploadState(item.id,{phase:'error',message:friendlyError(error),detail:String(error&&error.message||error||'')});
  paintManager();
  renderManager().catch(()=>{scheduleRefresh();});
  return false;
 }
}
// Self-heal: while a /loras/files refresh is failing, keep retrying in the
// background so the Pod summary and any stale rows recover on their own.
let refreshTimer=null;
function hasActiveManagedDownload(){for(const state of lastManagedDownloads.values())if(['queued','downloading','verifying'].includes(state.status))return true;return false;}
function managedDownloadSummary(){
 const states=[...lastManagedDownloads.values()];if(!states.length)return'';
 const installed=states.filter(state=>state.status==='installed').length;
 const active=states.filter(state=>['queued','downloading','verifying'].includes(state.status)).length;
 const auth=states.some(state=>state.status==='auth_required');
 const errors=states.filter(state=>state.status==='error').length;
 if(active)return`GitHubから自動取得中 ${installed}/${states.length}件`;
 if(installed===states.length)return`GitHub自動取得 ${installed}/${states.length}件 完了`;
 if(auth)return'GitHub自動取得: RunPod Secretの設定が必要です';
 if(errors)return`GitHub自動取得エラー ${errors}件`;
 return`GitHub自動取得 ${installed}/${states.length}件`;
}
function scheduleRefresh(){
 if(refreshTimer)return;
 refreshTimer=setInterval(async()=>{
  try{lastPodFiles=await podFiles();podFilesWarning='';paintManager();if(!hasActiveManagedDownload()){clearInterval(refreshTimer);refreshTimer=null;}}
  catch{/* keep retrying */}
 },4000);
}

async function podFiles(){const response=await fetch(apiUrl('/h3-mobile/api/loras/files'));if(!response.ok)throw new Error(await response.text());const data=await response.json();lastManagedDownloads=new Map((data.managed||[]).map(item=>[item.filename,item]));return new Map((data.files||[]).map(item=>[item.filename,item]));}
function isInstalledFile(file){return !!file&&file.status==='installed'&&Number(file.size)>0;}
function restoreCandidates(fileMap){return loadLib().filter(item=>!isInstalledFile(fileMap.get(item.filename)));}

function progressMarkup(state){
 const total=Number(state?.total)||0,loaded=Number(state?.loaded)||0,pct=total?Math.min(100,Math.round(loaded/total*100)):0;
 const cls=total?'h3-lora-progress':'h3-lora-progress indeterminate';
 const width=total?pct+'%':'38%';
 const line=total
  ?`<span>${esc(formatBytes(loaded))} / ${esc(formatBytes(total))}</span><span>${pct}%</span>`
  :`<span>送信済み ${esc(formatBytes(loaded))}</span><span>アップロード中…</span>`;
 return`<div class="${cls}"><span style="width:${width}"></span></div><div class="h3-lora-inline-progress">${line}</div>`;
}
function statusMarkup(item,file){
 const state=uploadState.get(item.id);
 if(state?.phase==='error')return`<span class="h3-lora-status h3-lora-err">✕ 導入失敗</span>`;
 if(state?.phase==='verifying')return`<span class="h3-lora-status h3-lora-busy">サーバー検証中…</span>`;
 if(state?.phase==='uploading'){const total=Number(state.total)||0,pct=total?Math.min(100,Math.round((Number(state.loaded)||0)/total*100)):0;return`<span class="h3-lora-status h3-lora-busy">アップロード中 ${total?pct+'%':'…'}</span>`;}
 if(state?.phase==='queued')return`<span class="h3-lora-status h3-lora-busy">待機中</span>`;
 if(isInstalledFile(file))return`<span class="h3-lora-status h3-lora-ok">✓ 導入済み</span>`;
 if(file&&file.status==='incomplete')return`<span class="h3-lora-status h3-lora-err">不完全ファイル</span>`;
 return`<span class="h3-lora-status">未導入</span>`;
}
function managerRow(item,fileMap){
 const file=fileMap.get(item.filename),state=uploadState.get(item.id),installed=isInstalledFile(file);
 const busy=state&&['queued','uploading','verifying'].includes(state.phase);
 const body=[];
 body.push(`<div class="h3-lora-summary"><span class="h3-lora-name">${esc(item.name)}</span><span class="small">${esc(item.defaultStrength)}</span>${statusMarkup(item,file)}</div>`);
 // The progress element is always present while uploading/verifying, so
 // applyProgress() can update it in place without a full repaint.
 if(state?.phase==='uploading'||state?.phase==='verifying')body.push(progressMarkup(state));
 if(installed&&!busy)body.push(`<div class="small">${esc(formatBytes(file.size))}</div>`);
 if(state?.phase==='error')body.push(`<div class="h3-lora-errbox"><div class="h3-lora-err">${esc(state.message)}</div><details><summary>詳細</summary><div class="small">${esc(state.detail||'')}</div></details><div class="h3-lora-actions"><button class="secondary h3-lora-compact m-retry">再試行</button></div></div>`);
 if(!installed&&!busy)body.push(`<div class="h3-lora-actions"><label class="secondary h3-lora-compact" style="cursor:pointer">ファイルを選択<input class="m-upload" type="file" accept=".safetensors" style="display:none"></label></div>`);
 body.push(`<details class="h3-lora-edit"><summary>編集</summary><div class="h3-lora-edit-body"><label>表示名</label><input class="m-name" value="${esc(item.name)}"><label>ファイル名</label><input value="${esc(item.filename)}" readonly><label>初期strength</label><input class="m-strength" type="number" step="0.01" inputmode="decimal" value="${esc(item.defaultStrength)}"><div class="h3-lora-actions"><button class="secondary h3-lora-compact m-save">保存</button><button class="secondary h3-lora-compact m-up">↑</button><button class="secondary h3-lora-compact m-down">↓</button>${installed?'<button class="secondary h3-lora-compact m-poddelete">Podから削除</button>':''}<button class="secondary h3-lora-compact h3-lora-danger m-delete">登録削除</button></div></div></details>`);
 body.push(`<div class="small m-msg"></div>`);
 return`<div class="h3-lora-item" data-id="${esc(item.id)}">${body.join('')}</div>`;
}
// In-place update for the common case (same phase, frequent progress events):
// avoids rebuilding innerHTML so open <details> and focus are preserved. Falls
// back to a full synchronous paint if the row or its progress element is not
// there yet (e.g. first event for a just-registered custom LoRA).
function applyProgress(id){
 const state=uploadState.get(id);if(!state)return;
 const row=q(`#h3LoraManager .h3-lora-item[data-id="${id}"]`);
 if(!row){paintManager();return;}
 const progress=row.querySelector('.h3-lora-progress');
 if(!progress){paintManager();return;}
 const bar=progress.querySelector('span'),info=row.querySelector('.h3-lora-inline-progress'),status=row.querySelector('.h3-lora-status');
 if(state.phase==='verifying'){if(status){status.classList.add('h3-lora-busy');status.textContent='サーバー検証中…';}return;}
 const total=Number(state.total)||0,loaded=Number(state.loaded)||0,pct=total?Math.min(100,Math.round(loaded/total*100)):0;
 if(total>0){progress.classList.remove('indeterminate');if(bar)bar.style.width=pct+'%';}
 else{progress.classList.add('indeterminate');if(bar)bar.style.width='38%';}
 if(info)info.innerHTML=total
  ?`<span>${esc(formatBytes(loaded))} / ${esc(formatBytes(total))}</span><span>${pct}%</span>`
  :`<span>送信済み ${esc(formatBytes(loaded))}</span><span>アップロード中…</span>`;
 if(status){status.classList.add('h3-lora-busy');status.textContent=total?`アップロード中 ${pct}%`:'アップロード中…';}
}
// Synchronous full paint from cached data. Never fetches, never blanks the list.
function paintManager(fileMap){
 const root=q('#h3LoraManager');if(!root)return;
 const files=fileMap||lastPodFiles;
 const library=loadLib();
 root.innerHTML=library.length?library.map(item=>managerRow(item,files)).join(''):'<div class="small">登録LoRAはありません。</div>';
 root.querySelectorAll('.h3-lora-item').forEach(bindManagerRow);
 const summary=q('#loraPodSummary');
 if(summary){
  const missing=restoreCandidates(files);
  const base=missing.length?`未導入 ${missing.length}件: ${missing.map(item=>item.name).join(', ')}`:'すべてのLoRAがPod上にあります。';
  const managed=managedDownloadSummary();
  const message=managed?`${base} / ${managed}`:base;
  summary.textContent=podFilesWarning?`${message}（${podFilesWarning}）`:message;
 }
}
// Refresh the real Pod file list, then paint. A failed/slow /loras/files (very
// possible while a large multipart upload is saturating the RunPod proxy) keeps
// the last known state and an in-progress upload's progress bar - it is NEVER
// allowed to wipe the list.
async function renderManager(){
 const root=q('#h3LoraManager');if(!root)return;
 try{
  lastPodFiles=await podFiles();
  podFilesWarning='';
  if(hasActiveManagedDownload())scheduleRefresh();
  else if(refreshTimer){clearInterval(refreshTimer);refreshTimer=null;}
 }catch(error){
  podFilesWarning='Pod状態を更新できません';
  scheduleRefresh();
 }
 paintManager();
}
function updateItem(id,patch){const library=loadLib(),index=library.findIndex(item=>item.id===id);if(index<0)return null;library[index]=normalizeItem({...library[index],...patch});saveLib(library);return library[index];}
function removeItem(id){saveLib(loadLib().filter(item=>item.id!==id));const legacy=loadJson(LEGACY_SEL_KEY,null);if(legacy&&removeSelectionIds(legacy,new Set([id])))localStorage.setItem(LEGACY_SEL_KEY,JSON.stringify(legacy));const projects=getProjectList();for(const project of projects){for(const ctx of CONTEXTS)delete project.loraSelections?.[ctx]?.[id];}saveProjectList(projects);clearUploadState(id);}
function moveLibrary(id,delta){const library=loadLib(),index=library.findIndex(item=>item.id===id),next=index+delta;if(index<0||next<0||next>=library.length)return;[library[index],library[next]]=[library[next],library[index]];saveLib(library);renderManager();}
function bindManagerRow(row){
 const id=row.dataset.id,message=row.querySelector('.m-msg'),find=()=>loadLib().find(item=>item.id===id);
 row.querySelector('.m-save').onclick=()=>{const strength=Number(row.querySelector('.m-strength').value),item=find();updateItem(id,{name:row.querySelector('.m-name').value.trim()||item.name,defaultStrength:Number.isFinite(strength)?strength:item.defaultStrength});message.textContent='保存しました。';renderQuick();};
 row.querySelector('.m-up').onclick=()=>moveLibrary(id,-1);
 row.querySelector('.m-down').onclick=()=>moveLibrary(id,1);
 row.querySelector('.m-delete').onclick=()=>{if(!confirm('このLoRA登録を削除しますか？ Pod・Finder上の.safetensors実ファイルは削除されません。'))return;removeItem(id);renderManager();renderQuick();};
 row.querySelector('.m-retry')?.addEventListener('click',async()=>{const file=retryFiles.get(id),item=find();if(!file||!item){message.textContent='再選択してください。';return;}await runUpload(item,file);});
 row.querySelector('.m-upload')?.addEventListener('change',async event=>{const file=event.target.files?.[0],item=find();if(!file||!item)return;await runUpload(item,file);});
 row.querySelector('.m-poddelete')?.addEventListener('click',async()=>{const item=find();if(!confirm('Pod上のLoRAファイルを削除しますか？登録情報は残ります。'))return;const response=await fetch(apiUrl('/h3-mobile/api/loras/delete'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:item.filename})});if(!response.ok){message.textContent=await response.text();return;}await renderManager();});
}

function addRecord(value){const item=normalizeItem({id:uid(),...value}),library=loadLib();
 const existing=library.find(entry=>entry.filename===item.filename||entry.originalFilename===item.originalFilename);
 if(existing)return existing;
 library.push(item);saveLib(library);
 const projects=getProjectList();for(const project of projects){project.loraSelections=project.loraSelections||{};for(const ctx of CONTEXTS){project.loraSelections[ctx]=project.loraSelections[ctx]||{};project.loraSelections[ctx][item.id]={enabled:false,strength:item.defaultStrength,order:library.length-1};}}saveProjectList(projects);renderQuick();return item;}

async function handleUploadFiles(fileList,messageEl){
 const files=[...(fileList||[])].filter(Boolean);
 if(!files.length)return;
 // Register/resolve every target up front and mark them 待機中, so pending
 // files in a multi-file selection are visible immediately, and a
 // just-registered custom LoRA already has a row when its upload starts.
 const targets=[];const rejected=[];let added=0;
 for(const file of files){
  if(!file.name.toLowerCase().endsWith('.safetensors')){rejected.push(file.name);continue;}
  let item=loadLib().find(value=>value.originalFilename===file.name||value.filename===file.name);
  if(!item){
   const definition=catalogDefinition(file.name);
   item=definition?addRecord(catalogRecord(definition)):addRecord({name:autoName(file.name),filename:file.name,originalFilename:file.name,sha256:'',defaultStrength:1});
   added++;
  }
  targets.push({item,file});
 }
 for(const {item} of targets)setUploadState(item.id,{phase:'queued',loaded:0,total:0,since:Date.now()});
 if(messageEl)messageEl.textContent=`アップロード開始: ${targets.length}件${rejected.length?` / 対象外 ${rejected.length}件`:''}`;
 paintManager();
 let ok=0,failed=rejected.length;
 for(let index=0;index<targets.length;index++){
  const {item,file}=targets[index];
  if(messageEl)messageEl.textContent=`アップロード中 (${index+1}/${targets.length}): ${item.name}`;
  // one file failing never stops the rest of the selection
  const success=await runUpload(item,file);
  if(success)ok++;else failed++;
 }
 if(messageEl)messageEl.textContent=`アップロード完了: 成功 ${ok}件${added?` / 新規登録 ${added}件`:''}${failed?` / 失敗 ${failed}件`:''}${rejected.length?` / 対象外: ${rejected.join(', ')}`:''}`;
 renderQuick();
}
function bulkUploadFiles(files){return handleUploadFiles(files,q('#loraRestoreMsg'));}
function addFilesFromForm(files){return handleUploadFiles(files,q('#loraAddMsg'));}

// --- full-settings backup (schema v3) --------------------------------------
function blankImages(){return{image0:null,ref0:null,ref1:null,ref2:null,ref3:null};}
function sanitizeProject(project){
 const clone={...project};
 // Images live only in this device's IndexedDB and are never backed up. Null
 // every reference so a cross-device restore cannot point at a missing key.
 clone.images=blankImages();
 if(clone.batch&&typeof clone.batch==='object')clone.batch={...clone.batch,i2vFiles:[],refSets:[{files:[null,null,null,null]}]};
 return clone;
}
function loadPresets(){return loadJson(PRESET_KEY,null);}
function exportSettings(){
 const data={
  schema:BACKUP_SCHEMA,
  version:BACKUP_VERSION,
  exportedAt:new Date().toISOString(),
  activeProjectId:typeof getActiveProjectId==='function'?getActiveProjectId():null,
  projects:getProjectList().map(sanitizeProject),
  loraRegistry:loadLib().map(item=>({id:item.id,name:item.name,filename:item.filename,originalFilename:item.originalFilename,sha256:item.sha256||'',defaultStrength:item.defaultStrength})),
  generationPresets:loadPresets()
 };
 const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),anchor=document.createElement('a');
 anchor.href=url;anchor.download='h3-mobile-settings-backup.json';anchor.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 const message=q('#loraBackupMsg');if(message)message.textContent='全設定をJSONに保存しました。画像・LoRA本体・認証情報は含まれません。';
}
function normalizeBackup(data){
 if(!data||typeof data!=='object')return null;
 // Legacy LoRA-only backup v2: {version:2, library:[...], projectSelections:[...]}
 if(data.version===2&&Array.isArray(data.library)){
  const registry=data.library.map(stripUrlFields).map(normalizeItem);
  const backups=Array.isArray(data.projectSelections)?data.projectSelections:[];
  const projects=getProjectList().map(project=>{
   const backup=backups.find(value=>value.id===project.id)||backups.find(value=>value.name===project.name);
   const merged=sanitizeProject(project);
   if(backup?.loraSelections)merged.loraSelections=backup.loraSelections;
   else if(!backups.length&&data.selections)merged.loraSelections=clone(data.selections);
   return merged;
  });
  return{loraRegistry:registry,projects,generationPresets:null,activeProjectId:typeof getActiveProjectId==='function'?getActiveProjectId():null};
 }
 if((data.schema===BACKUP_SCHEMA||Number(data.version)>=3)&&Array.isArray(data.projects)){
  return{
   loraRegistry:Array.isArray(data.loraRegistry)?data.loraRegistry.map(stripUrlFields).map(normalizeItem):null,
   projects:data.projects.map(project=>sanitizeProject(project)),
   generationPresets:data.generationPresets&&typeof data.generationPresets==='object'?data.generationPresets:null,
   activeProjectId:data.activeProjectId||null
  };
 }
 return null;
}
async function importSettings(file){
 if(!file)return;
 const message=q('#loraBackupMsg');
 let raw;
 try{raw=JSON.parse(await file.text());}catch{if(message)message.textContent='JSONを読み込めませんでした。';return;}
 const normalized=normalizeBackup(raw);
 if(!normalized){if(message)message.textContent='対応していないバックアップ形式です。';return;}
 if(!confirm('現在の案件・生成設定・LoRA登録・プリセットをバックアップ内容で置き換えます。よろしいですか？（画像とLoRA本体は変更されません）'))return;
 try{
  if(normalized.loraRegistry)localStorage.setItem(LIB_KEY,JSON.stringify(normalized.loraRegistry.map(normalizeItem)));
  if(normalized.projects){
   localStorage.setItem(PROJECTS_KEY,JSON.stringify(normalized.projects));
   const active=normalized.activeProjectId&&normalized.projects.some(project=>project.id===normalized.activeProjectId)?normalized.activeProjectId:(normalized.projects[0]?.id||null);
   if(active)localStorage.setItem(ACTIVE_PROJECT_KEY,active);
  }
  if(normalized.generationPresets)localStorage.setItem(PRESET_KEY,JSON.stringify(normalized.generationPresets));
  localStorage.removeItem(CATALOG_VERSION_KEY);
  alert('全設定を復元しました。ページを再読み込みします。必要なLoRA本体は「現在のPod」から選び直してください。');
  location.reload();
 }catch(error){if(message)message.textContent='復元に失敗しました: '+error.message;}
}

function injectLoraPage(){
 const root=q('#h3LoraPage');if(!root||q('#h3LoraManager'))return;
 root.innerHTML=`<div class="card"><h2>LoRAを追加</h2><div class="small">.safetensors ファイルを選んでアップロードします（複数選択可）。未登録のファイルは自動でcustom LoRAとして登録されます。</div><label class="h3-lora-filepick" style="margin-top:10px"><span id="loraNewFileName">.safetensors を選択</span><input id="loraNewFiles" type="file" accept=".safetensors" multiple></label><div id="loraAddMsg" class="small" style="margin-top:8px"></div></div><div class="card"><div class="row"><h2 style="margin:0;flex:1">現在のPod</h2><button class="secondary h3-lora-compact" id="loraRefresh">更新</button></div><div class="small">「✓ 導入済み」はPod上に実ファイルがある場合のみ表示されます。localStorageだけでは判定しません。</div><div class="h3-lora-top-actions"><label class="secondary h3-lora-compact" style="text-align:center;cursor:pointer">不足ファイルをまとめてアップロード<input id="loraBulkFiles" type="file" accept=".safetensors" multiple style="display:none"></label></div><div id="loraPodSummary" class="small" style="margin-top:8px"></div><div id="loraRestoreMsg" class="small" style="margin-top:4px"></div><div id="h3LoraManager" class="h3-lora-manager"></div></div><div class="card"><h2>全設定バックアップ</h2><div class="small">案件・生成設定・LoRA登録・生成プリセットをJSONへ保存します。画像本体・LoRA本体・URL・APIキーは含みません。PC↔スマホの設定移行に使えます。</div><div class="h3-lora-top-actions"><button class="secondary" id="loraExport">全設定バックアップ</button><label class="secondary" style="text-align:center;cursor:pointer;padding:12px">全設定を復元<input id="loraImport" type="file" accept=".json,application/json" style="display:none"></label></div><div id="loraBackupMsg" class="small" style="margin-top:8px"></div></div>`;
 q('#loraNewFiles').onchange=async event=>{
  const input=event.target,count=input.files?.length||0;
  if(!count)return;
  q('#loraNewFileName').textContent=`${count} 件をアップロード中…`;
  try{await addFilesFromForm(input.files);}
  finally{input.value='';q('#loraNewFileName').textContent='.safetensors を選択';}
 };
 q('#loraRefresh').onclick=renderManager;
 q('#loraBulkFiles').onchange=async event=>{const input=event.target;try{await bulkUploadFiles(input.files);}finally{input.value='';}};
 q('#loraExport').onclick=exportSettings;
 q('#loraImport').onchange=event=>importSettings(event.target.files?.[0]);
}

function stripManaged(workflow){const names=new Set(loadLib().map(item=>item.filename));let changed=true;while(changed){changed=false;for(const [id,node] of Object.entries(workflow)){if(node?.class_type!=='LoraLoaderModelOnly')continue;const name=node.inputs?.lora_name,title=node._meta?.title||'';if(!names.has(name)&&!title.startsWith('H3 Mobile LoRA'))continue;const previous=node.inputs?.model;if(!Array.isArray(previous))continue;for(const other of Object.values(workflow)){const model=other?.inputs?.model;if(Array.isArray(model)&&String(model[0])===String(id))other.inputs.model=[String(previous[0]),previous[1]??0];}delete workflow[id];changed=true;break;}}}
function rewireDirectModel(workflow,fromId,toId,skip){for(const [id,node] of Object.entries(workflow)){if(skip.has(id))continue;const model=node?.inputs?.model;if(Array.isArray(model)&&String(model[0])===String(fromId))node.inputs.model=[String(toId),model[1]??0];}}
function applyLoraList(workflow,list){stripManaged(workflow);if(!list.length)return workflow;const turbo=Object.entries(workflow).find(([,node])=>node?.class_type==='MiniMaxH3TurboLoRA')?.[0],unet=Object.entries(workflow).find(([,node])=>node?.class_type==='UNETLoader')?.[0],anchor=turbo||unet;if(!anchor)return workflow;let previous=String(anchor);const added=new Set();list.forEach(({item,sel},index)=>{const id=`h3mobile_lora_${index}`;workflow[id]={inputs:{model:[previous,0],lora_name:item.filename,strength_model:Number(sel.strength)},class_type:'LoraLoaderModelOnly',_meta:{title:`H3 Mobile LoRA: ${item.name}`}};added.add(id);previous=id;});rewireDirectModel(workflow,String(anchor),previous,added);return workflow;}
function applyLoras(workflow,name){const ctx=ctxFromWorkflow(name);return ctx?applyLoraList(workflow,selected(ctx)):workflow;}
window.h3LoraSnapshot=ctx=>selected(ctx).map(({item,sel})=>({item:clone(item),sel:clone(sel)}));
window.h3ApplyLoraSnapshot=(workflow,snapshot)=>applyLoraList(workflow,Array.isArray(snapshot)?snapshot:[]);
async function assertInstalledForPrompt(baseFetch,input,init){if(!init?.body||typeof init.body!=='string')return;let body;try{body=JSON.parse(init.body);}catch{return;}const workflow=body?.prompt;if(!workflow)return;const nodes=Object.values(workflow).filter(node=>node?.class_type==='LoraLoaderModelOnly'),library=loadLib(),loras=nodes.map(node=>{const filename=node.inputs?.lora_name,item=library.find(value=>value.filename===filename);return{filename,name:item?.name||autoName(filename),strength:Number(node.inputs?.strength_model)};});const extra=body.extra_data?.h3_mobile;if(extra)extra.loras=loras;const required=[...new Set(loras.map(item=>item.filename).filter(Boolean))];if(!required.length){init.body=JSON.stringify(body);return;}const response=await baseFetch(apiUrl('/h3-mobile/api/loras/files'));if(!response.ok)return;const data=await response.json(),installed=new Set((data.files||[]).filter(item=>item.status==='installed'&&Number(item.size??item.downloaded)>0).map(item=>item.filename)),missing=required.filter(name=>!installed.has(name));if(missing.length)throw new Error('LoRA未導入: '+missing.join(', '));init.body=JSON.stringify(body);}
function wrapFetch(){const baseFetch=window.fetch.bind(window);window.fetch=async(input,init)=>{const url=typeof input==='string'?input:(input&&input.url)||'',match=url.match(/\/h3-mobile\/api\/workflow\/([^/?#]+)/);if(match){const response=await baseFetch(input,init);if(!response.ok)return response;try{const workflow=applyLoras(await response.clone().json(),decodeURIComponent(match[1]));return new Response(JSON.stringify(workflow),{status:response.status,statusText:response.statusText,headers:response.headers});}catch{return response;}}if(/\/prompt(?:[?#]|$)/.test(url))await assertInstalledForPrompt(baseFetch,input,init);return baseFetch(input,init);};}
function bindChanges(){qa('[data-mode],[data-variant],[data-batch-mode],[data-batch-variant]').forEach(button=>button.addEventListener('click',()=>setTimeout(renderQuick,0)));q('.nav[data-target="lora"]')?.addEventListener('click',renderManager);window.addEventListener('h3:project-changed',()=>renderQuick());}
function init(){seed();style();injectQuick();injectLoraPage();renderQuick();renderManager();bindChanges();wrapFetch();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
