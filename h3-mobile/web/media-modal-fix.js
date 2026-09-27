(()=>{
function requestMediaFullscreen(){
  const el=document.querySelector('#modalBody')?.firstElementChild;
  if(!el)return;
  try{
    if(el.requestFullscreen)el.requestFullscreen();
    else if(el.webkitEnterFullscreen)el.webkitEnterFullscreen();
    else if(el.webkitRequestFullscreen)el.webkitRequestFullscreen();
    else if(el.msRequestFullscreen)el.msRequestFullscreen();
  }catch(err){}
}
function showFs(on){
  const btn=document.getElementById('modalFullscreen');
  if(!btn)return;
  btn.classList.toggle('hidden',!on);
}
const origOpen=window.openMedia;
window.openMedia=function(view,isVideo){
  if(typeof origOpen==='function') origOpen(view,isVideo);
  else{
    const body=document.getElementById('modalBody');
    if(body) body.innerHTML=isVideo?`<video controls autoplay playsinline src="${view}"></video>`:`<img src="${view}" alt="output">`;
    document.getElementById('mediaModal')?.classList.remove('hidden');
  }
  showFs(true);
};
const origClose=window.closeMedia;
window.closeMedia=function(){
  if(typeof origClose==='function') origClose();
  else{
    document.getElementById('mediaModal')?.classList.add('hidden');
    const body=document.getElementById('modalBody');
    if(body) body.innerHTML='';
  }
  showFs(false);
};
const modal=document.getElementById('mediaModal');
const closeBtn=document.getElementById('modalClose');
const fsBtn=document.getElementById('modalFullscreen');
if(closeBtn) closeBtn.onclick=()=>window.closeMedia();
if(fsBtn) fsBtn.onclick=requestMediaFullscreen;
if(modal){
  modal.onclick=e=>{
    if(!e.target.closest('video,img,button')) window.closeMedia();
  };
}
window.requestMediaFullscreen=requestMediaFullscreen;
})();
