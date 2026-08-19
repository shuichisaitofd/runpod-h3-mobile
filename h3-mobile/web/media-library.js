(()=>{
const originalFetch=window.fetch.bind(window);
const ratioMap={
  '3:2 (Landscape Photo)':'3:2 (Photo)',
  '9:16 (Portrait)':'9:16 (Portrait Widescreen)',
  '16:9 (Landscape)':'16:9 (Widescreen)',
  '4:3 (Landscape Standard)':'4:3 (Standard)'
};
window.fetch=async(input,init)=>{
  try{
    const url=typeof input==='string'?input:(input&&input.url)||'';
    if(url.endsWith('/prompt')&&init?.body&&typeof init.body==='string'){
      const body=JSON.parse(init.body);
      const ar=body?.prompt?.['115']?.inputs?.aspect_ratio;
      if(ratioMap[ar]){
        body.prompt['115'].inputs.aspect_ratio=ratioMap[ar];
        init={...init,body:JSON.stringify(body)};
      }
    }
  }catch{}
  return originalFetch(input,init);
};
})();

(()=>{
const DB='h3-mobile-library',STORE='favorites',MAX=10;let target=null;
function au(path){return typeof apiUrl==='function'?apiUrl(path):path;}
function openDb(){return new Promise((res,rej)=>{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>r.result.createObjectStore(STORE,{keyPath:'id'});r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});}
async function allFav(){const db=await openDb();return new Promise((res,rej)=>{const r=db.transaction(STORE).objectStore(STORE).getAll();r.onsuccess=()=>res(r.result||[]);r.onerror=()=>rej(r.error);});}
async function putFav(x){const db=await openDb(),items=await allFav();if(items.length>=MAX&&!items.some(i=>i.id===x.id))throw new Error('お気に入りは10件までです');return new Promise((res,rej)=>{const r=db.transaction(STORE,'readwrite').objectStore(STORE).put(x);r.onsuccess=()=>res();r.onerror=()=>rej(r.error);});}
async function delFav(id){const db=await openDb();return new Promise((res,rej)=>{const r=db.transaction(STORE,'readwrite').objectStore(STORE).delete(id);r.onsuccess=()=>res();r.onerror=()=>rej(r.error);});}
function setInputFile(input,file){const dt=new DataTransfer();dt.items.add(file);input.files=dt.files;input.dataset.serverName='';input.dispatchEvent(new Event('change',{bubbles:true}));}
async function blobFromUrl(url,name){const r=await fetch(url);if(!r.ok)throw new Error('画像取得失敗');const b=await r.blob();return new File([b],name,{type:b.type||'image/jpeg'});}
async function choose(item){if(!target)return;const file=item.blob?new File([item.blob],item.name,{type:item.type||item.blob.type}):await blobFromUrl(au(item.url),item.filename);setInputFile(target,file);close();}
function css(){if(document.querySelector('#h3libcss'))return;const s=document.createElement('style');s.id='h3libcss';s.textContent='.h3lib-btn{margin-top:8px;padding:9px 10px!important}.h3lib-modal{position:fixed;inset:0;background:#000c;z-index:80;padding:18px;overflow:auto;box-sizing:border-box}.h3lib-box{width:100%;max-width:720px;margin:5vh auto;background:#171a21;border:1px solid #2b3240;border-radius:16px;padding:14px;box-sizing:border-box;overflow-x:hidden}.h3lib-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;width:100%}.h3lib-item{background:#11151c;border:1px solid #2b3240;border-radius:10px;padding:6px;min-width:0}.h3lib-item img{max-width:100%;width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px}.h3lib-item .name{font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:4px 0 3px}.h3lib-item button{width:100%;padding:6px 4px;margin-top:3px;box-sizing:border-box;font-size:11px;line-height:1.3;border-radius:8px}.h3lib-tabs{display:flex;gap:6px;margin:8px 0 12px;flex-wrap:wrap}@media(max-width:460px){.h3lib-modal{padding:10px}.h3lib-box{padding:8px}.h3lib-grid{gap:6px}.h3lib-item{padding:5px}}';document.head.appendChild(s);}
function close(){document.querySelector('#h3libmodal')?.remove();}
async function render(mode='uploaded'){const body=document.querySelector('#h3libbody');if(!body)return;body.innerHTML='<div class="small">読込中...</div>';let items=[];if(mode==='uploaded'){const r=await fetch(au('/h3-mobile/api/input-images'));const j=await r.json();items=j.images||[];}else items=await allFav();body.innerHTML=items.length?'':'<div class="small">まだありません。</div>';const g=document.createElement('div');g.className='h3lib-grid';for(const it of items){const d=document.createElement('div');d.className='h3lib-item';const url=it.url?au(it.url):(it.blob?URL.createObjectURL(it.blob):'');d.innerHTML=`<img src="${url}"><div class="name">${it.filename||it.name}</div><button class="secondary use">使う</button>${mode==='uploaded'?'<button class="secondary fav">☆ お気に入り</button>':'<button class="secondary del">削除</button>'}`;d.querySelector('.use').onclick=()=>choose(it);if(mode==='uploaded')d.querySelector('.fav').onclick=async()=>{try{const f=await blobFromUrl(au(it.url),it.filename);await putFav({id:crypto.randomUUID(),name:it.filename,type:f.type,blob:f,created:Date.now()});alert('お気に入りに保存しました');}catch(e){alert(e.message);}};else d.querySelector('.del').onclick=async()=>{await delFav(it.id);render('favorites');};g.appendChild(d);}body.appendChild(g);}
function open(input){target=input;css();close();const m=document.createElement('div');m.id='h3libmodal';m.className='h3lib-modal';m.innerHTML='<div class="h3lib-box"><div class="row"><b style="flex:1">画像を選択</b><button class="secondary" id="h3libclose">閉じる</button></div><div class="h3lib-tabs"><button class="secondary active" data-lib="uploaded">今回アップロード</button><button class="secondary" data-lib="favorites">お気に入り（最大10）</button></div><div id="h3libbody"></div></div>';document.body.appendChild(m);m.querySelector('#h3libclose').onclick=close;m.querySelectorAll('[data-lib]').forEach(b=>b.onclick=()=>{m.querySelectorAll('[data-lib]').forEach(x=>x.classList.toggle('active',x===b));render(b.dataset.lib);});render('uploaded');}
function addButton(input){if(!input||input.dataset.libReady)return;input.dataset.libReady='1';const b=document.createElement('button');b.type='button';b.className='secondary h3lib-btn';b.textContent='アップロード済み / お気に入りから選ぶ';b.onclick=e=>{e.preventDefault();e.stopPropagation();open(input);};input.insertAdjacentElement('afterend',b);}
function scan(){['#image0','#ref0','#ref1','#ref2','#batchI2VFiles'].forEach(s=>addButton(document.querySelector(s)));document.querySelectorAll('#batchRefList input[type=file]').forEach(addButton);}
function loadPromptLibrary(){if(document.querySelector('script[data-h3-prompt-library]'))return;const s=document.createElement('script');s.src='prompt-library.js';s.dataset.h3PromptLibrary='1';document.body.appendChild(s);}
function init(){css();scan();new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});loadPromptLibrary();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();