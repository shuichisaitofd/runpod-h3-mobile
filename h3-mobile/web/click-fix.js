(()=>{
  let busy=false;
  function clearOverlays(){
    const modal=document.getElementById('mediaModal');
    if(modal && !modal.classList.contains('hidden') && !modal.querySelector('video,img,canvas')){
      modal.classList.add('hidden');
    }
    document.querySelectorAll('.media-modal.hidden').forEach(el=>{
      el.style.pointerEvents='none';
    });
  }
  async function h3Generate(ev){
    if(ev){ev.preventDefault();ev.stopPropagation();}
    if(busy) return;
    if(typeof buildAndQueue!=='function'){
      alert('生成処理が読み込めていません。ページを再読み込みしてください。');
      return;
    }
    busy=true;
    const btn=document.getElementById('gen');
    if(btn) btn.disabled=true;
    try{
      await buildAndQueue();
    }catch(e){
      const queue=document.getElementById('queue');
      if(queue){
        const d=document.createElement('div');
        d.className='notice danger';
        d.textContent=e.message||String(e);
        queue.prepend(d);
      }
      if(typeof page==='function') page('running');
    }finally{
      busy=false;
      if(btn) btn.disabled=false;
    }
  }
  function refreshRunning(){
    if(typeof updateJobTimers==='function') updateJobTimers();
    if(typeof tick==='function') tick();
    if(typeof loadHistory==='function') loadHistory();
  }
  function bind(){
    clearOverlays();
    const btn=document.getElementById('gen');
    if(btn){
      btn.disabled=false;
      btn.type='button';
      btn.onclick=h3Generate;
    }
    const refresh=document.getElementById('refreshQueue');
    if(refresh) refresh.onclick=refreshRunning;
  }
  window.h3Generate=h3Generate;
  bind();
  document.addEventListener('DOMContentLoaded',bind);
})();
