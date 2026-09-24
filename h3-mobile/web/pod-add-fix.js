(()=>{
let lock=false;
function addPodFromForm(){
  if(lock)return;
  lock=true;
  setTimeout(()=>{lock=false;},400);
  const nameEl=document.getElementById('newPodName');
  const urlEl=document.getElementById('newPodUrl');
  const msg=document.getElementById('podMessage');
  const name=(nameEl?.value||'').trim();
  let url=(urlEl?.value||'').trim();
  if(!name||!url){
    const text='Pod名とBase URLを入力してください。';
    if(msg) msg.textContent=text;
    alert(text);
    return;
  }
  url=url.replace(/\/+$/,'');
  const pods=typeof getPods==='function'?getPods():[];
  const pod={id:crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random(),name,baseUrl:url};
  pods.push(pod);
  if(typeof savePods==='function') savePods(pods);
  if(typeof getActivePod==='function'&&typeof setActivePod==='function'&&!getActivePod()) setActivePod(pod.id);
  if(nameEl) nameEl.value='';
  if(urlEl) urlEl.value='';
  if(msg) msg.textContent='Podを追加しました。';
  if(typeof renderPods==='function') renderPods();
  if(typeof reconnectPod==='function') reconnectPod();
}
window.h3AddPod=addPodFromForm;
function bind(){
  const btn=document.getElementById('addPod');
  if(!btn||btn.dataset.fixed==='1')return;
  btn.dataset.fixed='1';
  btn.type='button';
  btn.setAttribute('onclick','h3AddPod()');
  btn.style.width='100%';
  btn.style.minHeight='44px';
  btn.style.position='relative';
  btn.style.zIndex='4';
}
bind();
document.addEventListener('click',e=>{
  if(!e.target.closest('#addPod'))return;
  addPodFromForm();
},true);
})();
