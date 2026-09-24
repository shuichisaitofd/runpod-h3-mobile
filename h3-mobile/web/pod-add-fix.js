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
function rebuild(){
  const name=document.getElementById('newPodName');
  const url=document.getElementById('newPodUrl');
  const oldBtn=document.getElementById('addPod');
  if(!name||!url||!oldBtn)return;
  if(document.getElementById('podAddForm')){
    document.getElementById('podAddForm').onsubmit=e=>{e.preventDefault();addPodFromForm();};
    return;
  }
  const card=oldBtn.closest('.card')||name.closest('.card');
  const form=document.createElement('form');
  form.id='podAddForm';
  form.addEventListener('submit',e=>{e.preventDefault();addPodFromForm();});
  const grid=name.closest('.grid2');
  const actions=oldBtn.closest('.actions');
  const msg=document.getElementById('podMessage');
  if(grid) form.appendChild(grid);
  const btn=document.createElement('button');
  btn.id='addPod';
  btn.type='submit';
  btn.className='primary';
  btn.textContent='追加';
  btn.style.width='100%';
  btn.style.marginTop='10px';
  btn.style.minHeight='48px';
  btn.style.position='relative';
  btn.style.zIndex='8';
  form.appendChild(btn);
  if(actions&&actions.parentNode) actions.remove();
  if(msg) form.appendChild(msg);
  if(card) card.appendChild(form);
  else name.parentNode.appendChild(form);
}
rebuild();
document.addEventListener('click',e=>{
  if(e.target.closest('#addPod')) addPodFromForm();
},true);
})();
