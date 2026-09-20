(()=>{
'use strict';

const STORE_KEY='h3MobileGenerationPresetsV2';
const LEGACY_KEY='h3MobilePromptLibraryV1';
const STORE_VERSION=2;
const MAX=30;
const CATALOG_KEY='prompt-library-v5';
const PENDING_KEY='h3PendingLibraryPrompt';
const LIBRARY_PAGE='prompt-library.html';
let targetKind='normal';
const q=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>'\']/g,char=>({'&':'&','<':'<','>':'>',"'":'&#39;','\"':'"'}[char]));
const uid=()=>crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random();

function parseJson(value,fallback){try{return JSON.parse(value||'null')??fallback;}catch{return fallback;}}
function normalizePreset(item){
  const legacy=item?.kind==='legacy'||(!item?.kind&&item?.text!=null);
  return {
    ...item,
    version:STORE_VERSION,
    id:String(item?.id||uid()),
    name:String(item?.name||'無題'),
    kind:legacy?'legacy':item?.kind==='batch'?'batch':'normal',
    prompt:String(item?.prompt??item?.text??''),
    created:Number(item?.created)||Date.now(),
    updated:Number(item?.updated)||Number(item?.created)||Date.now(),
  };
}
function writeStore(items){localStorage.setItem(STORE_KEY,JSON.stringify({version:STORE_VERSION,items:items.slice(0,MAX).map(normalizePreset)}));}
function loadStore(){
  const stored=parseJson(localStorage.getItem(STORE_KEY),null);
  if(stored){const items=Array.isArray(stored)?stored:stored.version===STORE_VERSION&&Array.isArray(stored.items)?stored.items:[];return items.map(normalizePreset).slice(0,MAX);}
  const old=parseJson(localStorage.getItem(LEGACY_KEY),[]);
  const migrated=Array.isArray(old)?old.map(item=>normalizePreset({...item,kind:'legacy',prompt:item?.text??item?.prompt??''})):[];
  writeStore(migrated);
  return migrated;
}
function capture(kind){const fn=kind==='batch'?window.h3CaptureBatchPreset:window.h3CaptureNormalPreset;return typeof fn==='function'?fn():null;}
function saveNew(kind){
  const snapshot=capture(kind);
  if(!snapshot){alert('現在の生成設定を取得できません');return;}
  const name=window.prompt('プリセット名',`生成プリセット ${loadStore().length+1}`);
  if(!name)return;
  const now=Date.now(),items=loadStore();
  items.unshift(normalizePreset({...snapshot,id:uid(),name:name.trim()||'無題',kind,created:now,updated:now}));
  writeStore(items);
  alert('生成プリセットを保存しました');
}
function loadCatalog(){
  const parsed=parseJson(localStorage.getItem(CATALOG_KEY),null);
  if(Array.isArray(parsed)) return {items:parsed, genres:[]};
  if(parsed && Array.isArray(parsed.items)) return {items:parsed.items, genres:Array.isArray(parsed.genres)?parsed.genres:[]};
  return {items:[], genres:[]};
}
function writeCatalog(catalog){
  localStorage.setItem(CATALOG_KEY, JSON.stringify({items:catalog.items, genres:catalog.genres}));
}
function saveToCatalog(kind){
  const snapshot=capture(kind);
  if(!snapshot){alert('現在の生成設定を取得できません');return;}
  const name=window.prompt('ライブラリ名', snapshot.mode==='i2v'?'I2V':'参照から動画');
  if(!name)return;
  const catalog=loadCatalog();
  catalog.items.unshift({
    title:name.trim()||'無題',
    genre:'その他',
    body:String(snapshot.prompt||''),
    source:'',
    tags:[],
    gen:snapshot
  });
  if(!catalog.genres.includes('その他')) catalog.genres.push('その他');
  writeCatalog(catalog);
  if(confirm('ライブラリに保存しました。ライブラリを開きますか？')) location.href=LIBRARY_PAGE;
}
function applyLibraryItem(data){
  if(!data) return false;
  const prompt=String(data.body||data.prompt||'');
  const gen=data.gen && typeof data.gen==='object' ? data.gen : null;
  const kind=gen && gen.kind==='batch' ? 'batch' : 'normal';
  const apply=kind==='batch'?window.h3ApplyBatchPreset:window.h3ApplyNormalPreset;
  if(typeof apply==='function' && gen){
    apply({...gen, prompt:gen.prompt||prompt});
    return true;
  }
  const field=q(kind==='batch'?'#batchPrompt':'#prompt');
  if(field){
    field.value=prompt;
    field.dispatchEvent(new Event('input',{bubbles:true}));
    field.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  }
  return false;
}
function consumePending(){
  const raw=localStorage.getItem(PENDING_KEY);
  if(!raw) return;
  try{
    const data=JSON.parse(raw);
    localStorage.removeItem(PENDING_KEY);
    applyLibraryItem(data);
  }catch{
    localStorage.removeItem(PENDING_KEY);
  }
}
function removePreset(id){writeStore(loadStore().filter(item=>item.id!==id));render();}
function applyPreset(item){
  const kind=item.kind==='legacy'?targetKind:item.kind;
  const fn=kind==='batch'?window.h3ApplyBatchPreset:window.h3ApplyNormalPreset;
  if(typeof fn!=='function'){alert('プリセットを適用できません');return;}
  fn(item.kind==='legacy'?{prompt:item.prompt}:item);
  close();
}
function overwritePreset(item){
  const snapshot=capture(targetKind);
  if(!snapshot||!confirm(`「${item.name}」を現在の設定で上書きしますか？`))return;
  const items=loadStore(),index=items.findIndex(value=>value.id===item.id);
  if(index<0)return;
  items[index]=normalizePreset({...snapshot,id:item.id,name:item.name,kind:targetKind,created:item.created,updated:Date.now()});
  writeStore(items);
  render();
}
function modeLabel(item){
  if(item.kind==='legacy')return'旧プロンプト';
  if(item.mode==='i2v')return'I2V';
  const labels={'03':'03','04':'04','05':'05',fast:'06 高速',stable:'06 安定'};
  return`Ref2VA ${labels[item.refVariant]||item.refVariant||''}`.trim();
}
function summary(item){
  const bits=[modeLabel(item)];
  if(item.steps!=null)bits.push(`${item.steps} steps`);
  if(item.megapixels!=null)bits.push(`${item.megapixels} MP`);
  if(Array.isArray(item.loras))bits.push(`LoRA ${item.loras.filter(lora=>lora.enabled).length}件`);
  return bits.join(' / ');
}
function close(){q('#h3presetmodal')?.remove();}
function css(){
  if(q('#h3presetcss'))return;
  const style=document.createElement('style');
  style.id='h3presetcss';
  style.textContent='.h3preset-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.h3preset-modal{position:fixed;inset:0;background:#000c;z-index:90;padding:18px;overflow:auto}.h3preset-box{max-width:760px;margin:5vh auto;background:#171a21;border:1px solid #2b3240;border-radius:16px;padding:14px}.h3preset-list{display:grid;gap:9px;margin-top:12px}.h3preset-item{background:#11151c;border:1px solid #2b3240;border-radius:12px;padding:10px}.h3preset-item .name{font-weight:700;margin-bottom:5px}.h3preset-item .meta{font-size:12px;color:#cbd2df}.h3preset-item .actions{display:flex;gap:8px;margin-top:8px}.h3preset-item button{flex:1;padding:8px}.h3preset-count{margin-left:auto}';
  document.head.appendChild(style);
}
function render(){
  const root=q('#h3presetlist');
  if(!root)return;
  const items=loadStore().filter(item=>item.kind==='legacy'||item.kind===targetKind);
  q('#h3presetcount').textContent=`${items.length} / ${MAX}`;
  root.innerHTML=items.length?'':'<div class="small">保存済みプリセットはありません。</div>';
  for(const item of items){
    const row=document.createElement('div');
    row.className='h3preset-item';
    row.innerHTML=`<div class="name">${esc(item.name)}</div><div class="meta">${esc(summary(item))}</div><div class="actions"><button class="secondary apply">適用</button><button class="secondary overwrite">上書き</button><button class="secondary delete">削除</button></div>`;
    row.querySelector('.apply').onclick=()=>applyPreset(item);
    row.querySelector('.overwrite').onclick=()=>overwritePreset(item);
    row.querySelector('.delete').onclick=()=>removePreset(item.id);
    root.appendChild(row);
  }
}
function open(kind){
  targetKind=kind;
  css();close();
  const modal=document.createElement('div');
  modal.id='h3presetmodal';modal.className='h3preset-modal';
  modal.innerHTML=`<div class="h3preset-box"><div class="row"><b style="flex:1">生成プリセット（${kind==='batch'?'一括':'通常'}）</b><span class="small h3preset-count" id="h3presetcount"></span><button class="secondary" id="h3presetclose">閉じる</button></div><div class="h3preset-list" id="h3presetlist"></div></div>`;
  document.body.appendChild(modal);
  q('#h3presetclose').onclick=close;
  modal.onclick=event=>{if(event.target===modal)close();};
  render();
}
function addControls(textarea,kind){
  if(!textarea||textarea.dataset.presetReady)return;
  textarea.dataset.presetReady='1';
  const wrap=document.createElement('div');wrap.className='h3preset-actions';
  const saveButton=document.createElement('button');saveButton.type='button';saveButton.className='secondary compact';saveButton.textContent='プリセット保存';saveButton.onclick=()=>saveNew(kind);
  const openButton=document.createElement('button');openButton.type='button';openButton.className='secondary compact';openButton.textContent='プリセット';openButton.onclick=()=>open(kind);
  const libSave=document.createElement('button');libSave.type='button';libSave.className='secondary compact';libSave.textContent='ライブラリへ';libSave.onclick=()=>saveToCatalog(kind);
  const libOpen=document.createElement('button');libOpen.type='button';libOpen.className='secondary compact';libOpen.textContent='ライブラリ';libOpen.onclick=()=>{location.href=LIBRARY_PAGE;};
  wrap.append(saveButton,openButton,libSave,libOpen);
  textarea.insertAdjacentElement('afterend',wrap);
}
function loadCatalogRaw(){
  try{return JSON.parse(localStorage.getItem(CATALOG_KEY)||'null');}catch{return null;}
}
function injectFullBackup(){
  const msg=q('#loraBackupMsg');
  if(!msg||q('#loraFullExport'))return;
  const card=document.createElement('div');
  card.className='card';
  card.innerHTML='<h2>一括バックアップ（設定 + プロンプト）</h2><div class="small">indexの全設定とプロンプトライブラリを1つのJSONにまとめます。上の「全設定バックアップ」はそのまま使えます。画像・LoRA本体・URL・APIキーは含みません。</div><div class="h3-lora-top-actions"><button class="secondary" id="loraFullExport">一括ダウンロード</button><label class="secondary" style="text-align:center;cursor:pointer;padding:12px">一括復元<input id="loraFullImport" type="file" accept=".json,application/json" style="display:none"></label></div><div id="loraFullBackupMsg" class="small" style="margin-top:8px"></div>';
  msg.closest('.card')?.insertAdjacentElement('afterend',card);
  q('#loraFullExport').onclick=exportFullBundle;
  q('#loraFullImport').onchange=event=>importFullBundle(event.target.files?.[0]);
}
function downloadJson(name,data){
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=name;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function exportFullBundle(){
  const settings={
    schema:'h3-mobile-settings',
    version:3,
    exportedAt:new Date().toISOString(),
    activeProjectId:localStorage.getItem('h3MobileActiveProjectId'),
    projects:parseJson(localStorage.getItem('h3MobileProjects'),[]),
    loraRegistry:parseJson(localStorage.getItem('h3MobileLoraLibraryV1'),[]),
    generationPresets:parseJson(localStorage.getItem('h3MobileGenerationPresetsV2'),null)
  };
  if(Array.isArray(settings.projects)){
    settings.projects=settings.projects.map(project=>{
      const copy={...project,images:{image0:null,ref0:null,ref1:null,ref2:null,ref3:null}};
      if(copy.batch&&typeof copy.batch==='object')copy.batch={...copy.batch,i2vFiles:[],refSets:[{files:[null,null,null,null]}]};
      return copy;
    });
  }
  const promptLibrary=loadCatalogRaw();
  const n=Array.isArray(promptLibrary)?promptLibrary.length:(promptLibrary&&Array.isArray(promptLibrary.items)?promptLibrary.items.length:0);
  downloadJson('h3-mobile-full-backup.json',{schema:'h3-mobile-full',version:1,exportedAt:settings.exportedAt,settings,promptLibrary});
  const el=q('#loraFullBackupMsg');
  if(el)el.textContent=`一括バックアップを保存しました（プロンプト ${n}件 + 全設定）。`;
}
async function importFullBundle(file){
  if(!file)return;
  const el=q('#loraFullBackupMsg');
  let raw;
  try{raw=JSON.parse(await file.text());}catch{if(el)el.textContent='JSONを読み込めませんでした。';return;}
  let settings=null, catalog=null;
  if(raw&&raw.schema==='h3-mobile-full'){
    settings=raw.settings||null;
    catalog=raw.promptLibrary??null;
  }else if(raw&&raw.schema==='h3-mobile-settings'){
    settings=raw;
  }else if(raw&&(Array.isArray(raw)||Array.isArray(raw.items))){
    catalog=raw;
  }else{
    if(el)el.textContent='対応していないバックアップ形式です。';
    return;
  }
  const parts=[];
  if(settings)parts.push('案件・生成設定・LoRA登録・プリセット');
  if(catalog!=null)parts.push('プロンプトライブラリ');
  if(!confirm(parts.join(' と ')+'をこのファイルで置き換えます。よろしいですか？（画像とLoRA本体は変更されません）'))return;
  if(settings){
    if(settings.loraRegistry)localStorage.setItem('h3MobileLoraLibraryV1',JSON.stringify(settings.loraRegistry));
    if(settings.projects){
      localStorage.setItem('h3MobileProjects',JSON.stringify(settings.projects));
      const active=settings.activeProjectId||settings.projects[0]?.id;
      if(active)localStorage.setItem('h3MobileActiveProjectId',active);
    }
    if(settings.generationPresets)localStorage.setItem('h3MobileGenerationPresetsV2',JSON.stringify(settings.generationPresets));
  }
  if(catalog!=null)localStorage.setItem(CATALOG_KEY,JSON.stringify(catalog));
  alert('一括復元しました。ページを再読み込みします。');
  location.reload();
}
function init(){
  css();
  loadStore();
  addControls(q('#prompt'),'normal');
  addControls(q('#batchPrompt'),'batch');
  consumePending();
  injectFullBackup();
  setTimeout(injectFullBackup,0);
  window.addEventListener('storage',event=>{
    if(event.key===PENDING_KEY && event.newValue) consumePending();
  });
}
window.h3GenerationPresets={load:loadStore};
window.h3ApplyLibraryPrompt=applyLibraryItem;
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
