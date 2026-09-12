(()=>{
'use strict';

const STORE_KEY='h3MobileGenerationPresetsV2';
const LEGACY_KEY='h3MobilePromptLibraryV1';
const STORE_VERSION=2;
const MAX=30;
let targetKind='normal';
const q=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>'\"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[char]));
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
  wrap.append(saveButton,openButton);
  textarea.insertAdjacentElement('afterend',wrap);
}
function init(){css();loadStore();addControls(q('#prompt'),'normal');addControls(q('#batchPrompt'),'batch');}
window.h3GenerationPresets={load:loadStore};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
