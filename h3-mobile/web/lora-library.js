(()=>{
'use strict';
const LIB_KEY='h3MobileLoraLibraryV1';
const SEL_KEY='h3MobileLoraSelectionsV1';
const SEEDED_KEY='h3MobileLoraSeededV1';
const DEFAULTS=[
 {id:'aio-v25',name:'HMNSFW AIO V2.5',filename:'HMNSFW-AIO-V2.5.safetensors',url:'https://huggingface.co/Hearmeman/minimax-h3-loras/resolve/main/HMNSFW-AIO-V2.5.safetensors',sha256:'a07732a84fd733085eb5d910f602f918fa7a3658117116927e4329f5951a9d2d',target:'ref',defaultStrength:0.4},
 {id:'motion-booster-v2',name:'H3 Motion Booster V2',filename:'H3_Motion_BoosterV2.safetensors',url:'https://huggingface.co/bilmemne13/1/resolve/main/H3_Motion_BoosterV2.safetensors',sha256:'f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3',target:'ref',defaultStrength:0.5},
 {id:'penisv2-epoch60',name:'PenisV2 epoch60',filename:'PenisV2_minimax-h3_epoch60.safetensors',url:'https://civarchive.com/api/download/models/3247473',sha256:'017dd1adddc1be3ec0605dd2e7de97138eb2c6c6ba24be402cf47f103ac1f1b3',target:'both',defaultStrength:0.4}
];
const CONTEXTS=['i2v','ref:03','ref:04','ref:05','ref:fast','ref:stable'];
const q=s=>document.querySelector(s);
const qa=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function uid(){return crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random();}
function loadJson(key,fallback){try{const v=JSON.parse(localStorage.getItem(key)||'null');return v??fallback;}catch{return fallback;}}
function loadLib(){const v=loadJson(LIB_KEY,[]);return Array.isArray(v)?v:[];}
function saveLib(v){localStorage.setItem(LIB_KEY,JSON.stringify(v));}
function loadSel(){const v=loadJson(SEL_KEY,{});return v&&typeof v==='object'?v:{};}
function saveSel(v){localStorage.setItem(SEL_KEY,JSON.stringify(v));}
function seed(){
 if(localStorage.getItem(SEEDED_KEY)==='1')return;
 const lib=loadLib();
 for(const d of DEFAULTS){if(!lib.some(x=>x.filename===d.filename))lib.push({...d});}
 saveLib(lib);
 const sel=loadSel();
 for(const ctx of CONTEXTS){
   sel[ctx]=sel[ctx]||{};
   for(const d of DEFAULTS){
     if(sel[ctx][d.id])continue;
     const enabled=(ctx!=='i2v'&&ctx!=='ref:03'&&(d.id==='aio-v25'||d.id==='motion-booster-v2'));
     sel[ctx][d.id]={enabled,strength:d.defaultStrength};
   }
 }
 saveSel(sel);localStorage.setItem(SEEDED_KEY,'1');
}
function ctxFromWorkflow(name){
 return name==='i2v'?'i2v':name==='ref2va_03'?'ref:03':name==='ref2va_04'?'ref:04':name==='ref2va_05'?'ref:05':name==='ref2va_06_fast'?'ref:fast':name==='ref2va_06_stable'?'ref:stable':null;
}
function currentCreateCtx(){return state?.mode==='ref'?`ref:${state.refVariant}`:'i2v';}
function currentBatchCtx(){
 const mode=q('[data-batch-mode].active')?.dataset.batchMode||'i2v';
 if(mode!=='ref2va')return'i2v';
 const v=q('#batchRefVariant [data-batch-variant].active')?.dataset.batchVariant||'04';
 return`ref:${v}`;
}
function applies(item,ctx){
 if(ctx==='i2v')return item.target==='i2v'||item.target==='both';
 return item.target==='ref'||item.target==='both';
}
function ensureSelection(ctx,item){
 const all=loadSel();all[ctx]=all[ctx]||{};
 if(!all[ctx][item.id]){all[ctx][item.id]={enabled:false,strength:Number(item.defaultStrength)||0};saveSel(all);}
 return all[ctx][item.id];
}
function setSelection(ctx,id,patch){
 const all=loadSel();all[ctx]=all[ctx]||{};all[ctx][id]={...(all[ctx][id]||{}),...patch};saveSel(all);
}
function selected(ctx){
 return loadLib().filter(x=>applies(x,ctx)).map((x,i)=>({item:x,sel:ensureSelection(ctx,x),order:i})).filter(x=>x.sel.enabled);
}
function style(){
 if(q('#h3LoraCss'))return;
 const s=document.createElement('style');s.id='h3LoraCss';s.textContent=`
 .h3-lora-quick{display:grid;gap:8px;margin-top:8px}.h3-lora-qrow{display:grid;grid-template-columns:auto 1fr 84px;gap:8px;align-items:center;padding:8px 0;border-top:1px solid #2b3240}.h3-lora-qrow:first-child{border-top:0}.h3-lora-qrow input[type=number]{margin:0}.h3-lora-qrow label{margin:0;font-weight:600}.h3-lora-muted{opacity:.65}
 .h3-lora-manager{display:grid;gap:10px}.h3-lora-item{border:1px solid #2b3240;border-radius:12px;padding:10px}.h3-lora-item .grid2{margin-top:8px}.h3-lora-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.h3-lora-actions button{flex:1;min-width:110px}.h3-lora-status{font-size:12px}.h3-lora-ok{color:#78d99b}.h3-lora-err{color:#ff8d8d}.h3-lora-form{border-top:1px solid #2b3240;margin-top:12px;padding-top:12px}.h3-lora-form input,.h3-lora-form select{margin-bottom:8px}
 `;
 document.head.appendChild(s);
}
function quickMarkup(ctx){
 const items=loadLib().filter(x=>applies(x,ctx));
 if(!items.length)return'<div class="small">このモード用のLoRAは登録されていません。</div>';
 return items.map(item=>{const s=ensureSelection(ctx,item);return`<div class="h3-lora-qrow" data-lora-id="${esc(item.id)}"><input class="h3-lora-on" type="checkbox" ${s.enabled?'checked':''}><label>${esc(item.name)}</label><input class="h3-lora-strength" type="number" step="0.01" inputmode="decimal" value="${esc(s.strength)}" aria-label="${esc(item.name)} strength"></div>`}).join('');
}
function bindQuick(root,ctx){
 root.querySelectorAll('.h3-lora-qrow').forEach(row=>{
   const id=row.dataset.loraId,on=row.querySelector('.h3-lora-on'),st=row.querySelector('.h3-lora-strength');
   on.onchange=()=>setSelection(ctx,id,{enabled:on.checked});
   st.oninput=()=>{const n=Number(st.value);if(Number.isFinite(n))setSelection(ctx,id,{strength:n});};
 });
}
function renderQuick(){
 const root=q('#h3LoraQuick');if(root){const ctx=currentCreateCtx();root.innerHTML=quickMarkup(ctx);bindQuick(root,ctx);}
 const b=q('#h3LoraBatchQuick');if(b){const ctx=currentBatchCtx();b.innerHTML=quickMarkup(ctx);bindQuick(b,ctx);}
 syncNotes();
}
function injectQuick(){
 const createActions=q('[data-page="create"] .card .actions')?.closest('.card');
 if(createActions&&!q('#h3LoraQuickCard')){
   const c=document.createElement('div');c.className='card';c.id='h3LoraQuickCard';c.innerHTML='<div class="row"><h2 style="margin:0;flex:1">LoRA</h2><span class="small">ON / strength</span></div><div id="h3LoraQuick" class="h3-lora-quick"></div>';
   createActions.parentNode.insertBefore(c,createActions);
 }
 const batchActions=q('#startBatch')?.closest('.card');
 if(batchActions&&!q('#h3LoraBatchQuickCard')){
   const c=document.createElement('div');c.className='card';c.id='h3LoraBatchQuickCard';c.innerHTML='<div class="row"><h2 style="margin:0;flex:1">LoRA</h2><span class="small">ON / strength</span></div><div id="h3LoraBatchQuick" class="h3-lora-quick"></div>';
   batchActions.parentNode.insertBefore(c,batchActions);
 }
}
function syncNotes(){
 const n=q('#modeNote');
 if(n){
  if(state.mode==='i2v')n.innerHTML='I2V: <b>Turbo + Sage / 4step固定</b>。追加LoRAは上のON / strength設定を使用します。';
  else{
   const map={ '03':'Turbo Enhanced', '04':'Sol-Attn + BlockCache Balanced', '05':'SLA + BlockCache Balanced', fast:'SLA + Spectrum（高速）', stable:'SLA + Spectrum（安定）'};
   n.innerHTML=`Ref2VA ${esc(refVariantLabel(state.refVariant))}: <b>${map[state.refVariant]||''}</b>。LoRAは上のON / strength設定を使用します。`;
  }
 }
 const b=q('#batchModeNote');if(b){const ctx=currentBatchCtx();b.innerHTML=ctx==='i2v'?'I2V: <b>Turbo + Sage / 4step固定</b>。LoRAは上の設定を使用します。':'Ref2VA: LoRAは上のON / strength設定を使用します。';}
}
async function podFiles(){
 try{const r=await fetch(apiUrl('/h3-mobile/api/loras/files'));if(!r.ok)throw new Error(await r.text());const d=await r.json();return new Map((d.files||[]).map(x=>[x.filename,x]));}catch{return new Map();}
}
function managerRow(item,fileMap){
 const f=fileMap.get(item.filename),status=f?.status||'missing';
 const st=status==='installed'?'Pod: 導入済み':status==='downloading'||status==='queued'?'Pod: ダウンロード中':status==='error'?'Pod: エラー':'Pod: 未導入';
 return`<div class="h3-lora-item" data-id="${esc(item.id)}">
 <div class="row"><b style="flex:1">${esc(item.name)}</b><span class="h3-lora-status ${status==='installed'?'h3-lora-ok':status==='error'?'h3-lora-err':''}">${st}</span></div>
 <div class="grid2"><div><label>LoRA名</label><input class="m-name" value="${esc(item.name)}"></div><div><label>ファイル名</label><input class="m-file" value="${esc(item.filename)}"></div></div>
 <label>ダウンロードURL</label><input class="m-url" value="${esc(item.url||'')}" placeholder="https://...">
 <div class="grid2"><div><label>対象</label><select class="m-target"><option value="ref" ${item.target==='ref'?'selected':''}>Ref2VA</option><option value="i2v" ${item.target==='i2v'?'selected':''}>I2V</option><option value="both" ${item.target==='both'?'selected':''}>両方</option></select></div><div><label>初期strength</label><input class="m-strength" type="number" step="0.01" inputmode="decimal" value="${esc(item.defaultStrength)}"></div></div>
 <div class="h3-lora-actions"><button class="secondary m-save">保存</button><button class="secondary m-up">↑</button><button class="secondary m-down">↓</button>${item.url?'<button class="secondary m-download">PodへDL</button>':''}<label class="secondary" style="text-align:center;cursor:pointer;padding:10px">ファイル送信<input class="m-upload" type="file" accept=".safetensors" style="display:none"></label><button class="secondary m-poddelete">Podから削除</button><button class="secondary m-delete">登録削除</button></div>
 <div class="small m-msg ${status==='error'?'h3-lora-err':''}">${status==='error'?esc(f?.error||'ダウンロード失敗'):''}</div></div>`;
}
async function renderManager(){
 const root=q('#h3LoraManager');if(!root)return;
 const files=await podFiles();const lib=loadLib();
 root.innerHTML=lib.length?lib.map(x=>managerRow(x,files)).join(''):'<div class="small">登録LoRAはありません。</div>';
 root.querySelectorAll('.h3-lora-item').forEach(row=>bindManagerRow(row));
}
function bindManagerRow(row){
 const id=row.dataset.id,msg=row.querySelector('.m-msg');
 const get=()=>loadLib(),find=()=>get().find(x=>x.id===id);
 row.querySelector('.m-save').onclick=()=>{const lib=get(),i=lib.findIndex(x=>x.id===id);if(i<0)return;const n=Number(row.querySelector('.m-strength').value);lib[i]={...lib[i],name:row.querySelector('.m-name').value.trim()||lib[i].name,filename:row.querySelector('.m-file').value.trim()||lib[i].filename,url:row.querySelector('.m-url').value.trim(),target:row.querySelector('.m-target').value,defaultStrength:Number.isFinite(n)?n:lib[i].defaultStrength};saveLib(lib);msg.textContent='保存しました。';renderQuick();};
 row.querySelector('.m-up').onclick=()=>move(id,-1);
 row.querySelector('.m-down').onclick=()=>move(id,1);
 row.querySelector('.m-delete').onclick=()=>{if(!confirm('このLoRA登録を削除しますか？'))return;saveLib(get().filter(x=>x.id!==id));const s=loadSel();for(const c of Object.keys(s||{}))delete s[c]?.[id];saveSel(s);renderManager();renderQuick();};
 row.querySelector('.m-download')?.addEventListener('click',async()=>{const x=find();if(!x)return;msg.textContent='ダウンロード開始中...';try{const r=await fetch(apiUrl('/h3-mobile/api/loras/download'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:x.url,filename:x.filename,sha256:x.sha256||''})});if(!r.ok)throw new Error(await r.text());const d=await r.json();msg.textContent=d.status==='installed'?'すでにPodへ導入済みです。':'Podでダウンロードを開始しました。';await renderManager();startManagerPolling();}catch(e){msg.textContent='失敗: '+e.message;msg.className='small m-msg h3-lora-err';}});
 row.querySelector('.m-upload').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;const x=find();const filename=(x?.filename||file.name).trim();msg.textContent='送信中...';try{const fd=new FormData();fd.append('file',file,file.name);const r=await fetch(apiUrl('/h3-mobile/api/loras/upload?filename='+encodeURIComponent(filename)),{method:'POST',body:fd});if(!r.ok)throw new Error(await r.text());msg.textContent='Podへ送信しました。';await renderManager();}catch(err){msg.textContent='失敗: '+err.message;msg.className='small m-msg h3-lora-err';}};
 row.querySelector('.m-poddelete').onclick=async()=>{const x=find();if(!x)return;if(!confirm('Pod上のLoRAファイルを削除しますか？登録情報は残ります。'))return;try{const r=await fetch(apiUrl('/h3-mobile/api/loras/delete'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:x.filename})});if(!r.ok)throw new Error(await r.text());await renderManager();}catch(e){msg.textContent='失敗: '+e.message;}};
}
function move(id,delta){
 const lib=loadLib(),i=lib.findIndex(x=>x.id===id),j=i+delta;if(i<0||j<0||j>=lib.length)return;[lib[i],lib[j]]=[lib[j],lib[i]];saveLib(lib);renderManager();renderQuick();
}
let managerPoll=null;
function startManagerPolling(){
 if(managerPoll)return;
 managerPoll=setInterval(async()=>{if(!q('#h3LoraManager'))return;const files=await podFiles();const active=[...files.values()].some(x=>x.status==='queued'||x.status==='downloading');await renderManager();if(!active){clearInterval(managerPoll);managerPoll=null;}},1800);
}
function injectSettings(){
 const page=q('[data-page="settings"]');if(!page||q('#h3LoraSettingsCard'))return;
 const c=document.createElement('div');c.className='card';c.id='h3LoraSettingsCard';
 c.innerHTML=`<h2>LoRA管理</h2><div class="small">登録情報はこのブラウザのlocalStorageに保存されます。Podを作り直しても残ります。LoRA本体は必要なものだけPodへダウンロード/送信します。</div><div id="h3LoraManager" class="h3-lora-manager" style="margin-top:10px"></div>
 <div class="h3-lora-form"><h3>LoRAを追加</h3><label>LoRA名</label><input id="loraNewName" placeholder="表示名"><label>ダウンロードURL</label><input id="loraNewUrl" placeholder="https://..."><div class="grid2"><div><label>ファイル名</label><input id="loraNewFile" placeholder="example.safetensors"></div><div><label>対象</label><select id="loraNewTarget"><option value="ref">Ref2VA</option><option value="i2v">I2V</option><option value="both" selected>両方</option></select></div></div><label>初期strength</label><input id="loraNewStrength" type="number" step="0.01" inputmode="decimal" value="1">
 <div class="h3-lora-actions"><button class="secondary" id="loraAddUrl">URLを登録</button><label class="secondary" style="text-align:center;cursor:pointer;padding:10px">ファイルから登録<input id="loraAddFile" type="file" accept=".safetensors" style="display:none"></label></div><div id="loraAddMsg" class="small"></div></div>
 <div class="h3-lora-actions"><button class="secondary" id="loraExport">設定を書き出す</button><label class="secondary" style="text-align:center;cursor:pointer;padding:10px">設定を読み込む<input id="loraImport" type="file" accept=".json,application/json" style="display:none"></label></div>`;
 const modelCard=q('#modelList')?.closest('.card');if(modelCard)modelCard.insertAdjacentElement('afterend',c);else page.prepend(c);
 q('#loraAddUrl').onclick=()=>addUrl();
 q('#loraAddFile').onchange=e=>addFile(e.target.files?.[0]);
 q('#loraExport').onclick=exportSettings;
 q('#loraImport').onchange=e=>importSettings(e.target.files?.[0]);
}
function newFields(){
 const name=q('#loraNewName').value.trim(),url=q('#loraNewUrl').value.trim(),filename=q('#loraNewFile').value.trim(),target=q('#loraNewTarget').value,n=Number(q('#loraNewStrength').value);
 return{name,url,filename,target,defaultStrength:Number.isFinite(n)?n:1};
}
function addRecord(x){
 const lib=loadLib();const item={id:uid(),name:x.name||x.filename,filename:x.filename,url:x.url||'',sha256:'',target:x.target||'both',defaultStrength:x.defaultStrength};lib.push(item);saveLib(lib);
 const s=loadSel();for(const ctx of CONTEXTS){s[ctx]=s[ctx]||{};s[ctx][item.id]={enabled:false,strength:item.defaultStrength};}saveSel(s);renderQuick();return item;
}
function addUrl(){
 const x=newFields(),m=q('#loraAddMsg');if(!x.name||!x.url||!x.filename){m.textContent='LoRA名・URL・ファイル名を入力してください。';return;}if(!x.filename.endsWith('.safetensors')){m.textContent='ファイル名は .safetensors にしてください。';return;}addRecord(x);m.textContent='URLを登録しました。Podへのダウンロードは一覧の「PodへDL」から行えます。';renderManager();
}
async function addFile(file){
 const x=newFields(),m=q('#loraAddMsg');if(!file)return;if(!x.name)x.name=file.name;if(!x.filename)x.filename=file.name;if(!x.filename.endsWith('.safetensors')){m.textContent='safetensorsファイルを選択してください。';return;}const item=addRecord(x);m.textContent='登録してPodへ送信中...';try{const fd=new FormData();fd.append('file',file,file.name);const r=await fetch(apiUrl('/h3-mobile/api/loras/upload?filename='+encodeURIComponent(item.filename)),{method:'POST',body:fd});if(!r.ok)throw new Error(await r.text());m.textContent='登録してPodへ送信しました。';await renderManager();}catch(e){m.textContent='登録は保存しました。Pod送信は失敗: '+e.message;}}
function exportSettings(){
 const data={version:1,library:loadLib(),selections:loadSel()};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='h3-lora-library.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function importSettings(file){
 if(!file)return;try{const d=JSON.parse(await file.text());if(!Array.isArray(d.library)||!d.selections)throw new Error('形式が違います');saveLib(d.library);saveSel(d.selections);localStorage.setItem(SEEDED_KEY,'1');renderQuick();renderManager();alert('LoRA設定を読み込みました');}catch(e){alert('読み込み失敗: '+e.message);}
}
function stripManaged(wf){
 const names=new Set([...DEFAULTS.map(x=>x.filename),...loadLib().map(x=>x.filename)]);
 let changed=true;
 while(changed){changed=false;for(const [id,node] of Object.entries(wf)){if(node?.class_type!=='LoraLoaderModelOnly')continue;const name=node.inputs?.lora_name,title=node._meta?.title||'';if(!names.has(name)&&!title.startsWith('H3 Mobile LoRA'))continue;const prev=node.inputs?.model;if(!Array.isArray(prev))continue;for(const other of Object.values(wf)){const m=other?.inputs?.model;if(Array.isArray(m)&&String(m[0])===String(id))other.inputs.model=[String(prev[0]),prev[1]??0];}delete wf[id];changed=true;break;}}
}
function rewireDirectModel(wf,fromId,toId,skip){
 for(const [id,node] of Object.entries(wf)){if(skip.has(id))continue;const m=node?.inputs?.model;if(Array.isArray(m)&&String(m[0])===String(fromId))node.inputs.model=[String(toId),m[1]??0];}
}
function applyLoras(wf,name){
 const ctx=ctxFromWorkflow(name);if(!ctx)return wf;stripManaged(wf);const list=selected(ctx);if(!list.length)return wf;
 const turbo=Object.entries(wf).find(([,n])=>n?.class_type==='MiniMaxH3TurboLoRA')?.[0];
 const unet=Object.entries(wf).find(([,n])=>n?.class_type==='UNETLoader')?.[0];
 const anchor=turbo||unet;if(!anchor)return wf;
 let prev=String(anchor);const added=new Set();
 list.forEach(({item,sel},i)=>{const id=`h3mobile_lora_${i}`;wf[id]={inputs:{model:[prev,0],lora_name:item.filename,strength_model:Number(sel.strength)},class_type:'LoraLoaderModelOnly',_meta:{title:`H3 Mobile LoRA: ${item.name}`}};added.add(id);prev=id;});
 rewireDirectModel(wf,String(anchor),prev,added);return wf;
}
async function assertInstalledForPrompt(baseFetch,input,init){
 if(!init?.body||typeof init.body!=='string')return;let body;try{body=JSON.parse(init.body);}catch{return;}const wf=body?.prompt;if(!wf)return;const required=[...new Set(Object.values(wf).filter(n=>n?.class_type==='LoraLoaderModelOnly').map(n=>n.inputs?.lora_name).filter(Boolean))];if(!required.length)return;
 const r=await baseFetch(apiUrl('/h3-mobile/api/loras/files'));if(!r.ok)return;const d=await r.json(),have=new Set((d.files||[]).map(x=>x.filename)),missing=required.filter(x=>!have.has(x));if(missing.length)throw new Error('LoRA未導入: '+missing.join(', '));
 const extra=body.extra_data?.h3_mobile;if(extra)extra.loras=Object.values(wf).filter(n=>n?.class_type==='LoraLoaderModelOnly').map(n=>({name:n.inputs.lora_name,strength:n.inputs.strength_model}));
 init.body=JSON.stringify(body);
}
function wrapFetch(){
 const baseFetch=window.fetch.bind(window);
 window.fetch=async(input,init)=>{
   const url=typeof input==='string'?input:(input&&input.url)||'';
   const m=url.match(/\/h3-mobile\/api\/workflow\/([^/?#]+)/);
   if(m){
     const r=await baseFetch(input,init);if(!r.ok)return r;try{const wf=applyLoras(await r.clone().json(),decodeURIComponent(m[1]));return new Response(JSON.stringify(wf),{status:r.status,statusText:r.statusText,headers:r.headers});}catch{return r;}
   }
   if(/\/prompt(?:[?#]|$)/.test(url))await assertInstalledForPrompt(baseFetch,input,init);
   return baseFetch(input,init);
 };
}
function bindModeChanges(){
 qa('[data-mode],[data-variant],[data-batch-mode],[data-batch-variant]').forEach(b=>b.addEventListener('click',()=>setTimeout(renderQuick,0)));
 qa('.nav[data-target="settings"]').forEach(b=>b.addEventListener('click',()=>setTimeout(renderManager,0)));
}
function init(){
 seed();style();injectQuick();injectSettings();renderQuick();renderManager();bindModeChanges();wrapFetch();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
