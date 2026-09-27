(()=>{
const LIB='h3MobileLoraLibraryV1';
function loadLib(){try{const v=JSON.parse(localStorage.getItem(LIB)||'[]');return Array.isArray(v)?v:[];}catch{return [];}}
function saveLib(list){localStorage.setItem(LIB,JSON.stringify(list));}
function isActive(item){return item&&item.active!==false;}
function setActive(id,on){
  const list=loadLib();
  const item=list.find(x=>x.id===id);
  if(!item)return;
  item.active=!!on;
  saveLib(list);
}
function wrap(name){
  const orig=window[name];
  if(typeof orig!=='function'||orig._h3ActiveWrapped)return;
  const wrapped=function(ctx){
    const snap=orig(ctx);
    if(!Array.isArray(snap))return snap;
    const lib=loadLib();
    return snap.filter(row=>{
      const item=lib.find(x=>x.id===row.id||x.filename===row.filename);
      return !item||isActive(item);
    });
  };
  wrapped._h3ActiveWrapped=true;
  window[name]=wrapped;
}
function decorateManager(){
  document.querySelectorAll('#h3LoraManager .h3-lora-item, .h3-lora-manager .h3-lora-item').forEach(row=>{
    if(row.querySelector('.m-active-fix'))return;
    const id=row.dataset.id; if(!id)return;
    const item=loadLib().find(x=>x.id===id);
    const on=isActive(item);
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='h3-lora-toggle m-active-fix'+(on?' active':'');
    btn.textContent=on?'ON':'OFF';
    btn.style.marginLeft='6px';
    btn.onclick=()=>{
      const next=!isActive(loadLib().find(x=>x.id===id));
      setActive(id,next);
      btn.textContent=next?'ON':'OFF';
      btn.classList.toggle('active',next);
      row.style.opacity=next?'':'0.55';
      if(typeof renderQuick==='function') renderQuick();
      filterQuick();
    };
    const name=row.querySelector('.h3-lora-name, .h3-lora-summary');
    (name||row).appendChild(btn);
    row.style.opacity=on?'':'0.55';
  });
}
function filterQuick(){
  const lib=loadLib();
  document.querySelectorAll('.h3-lora-qrow').forEach(row=>{
    const id=row.dataset.loraId;
    const item=lib.find(x=>x.id===id);
    row.style.display=(!item||isActive(item))?'':'none';
  });
}
function boot(){
  wrap('h3LoraSnapshot');
  wrap('h3LoraPresetSnapshot');
  decorateManager();
  filterQuick();
}
boot();
setInterval(boot,1200);
})();
