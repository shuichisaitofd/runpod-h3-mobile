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
function pauseHistoryVideos(){
  document.querySelectorAll('#historyList video.history-media').forEach(v=>{try{v.pause();}catch(e){}});
}
function resumeHistoryVideos(){
  const list=document.getElementById('historyList');
  if(!list||!list.classList.contains('large-view'))return;
  const vh=window.innerHeight;
  list.querySelectorAll('video.history-media').forEach(v=>{
    const r=v.getBoundingClientRect();
    const vis=Math.min(r.bottom,vh)-Math.max(r.top,0);
    if(r.height>0&&vis/r.height>=0.45){
      v.muted=localStorage.getItem('h3HistorySoundOn')==='0';
      const p=v.play();
      if(p&&p.catch)p.catch(()=>{v.muted=true;v.play().catch(()=>{});});
    }
  });
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
  pauseHistoryVideos();
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
  resumeHistoryVideos();
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
