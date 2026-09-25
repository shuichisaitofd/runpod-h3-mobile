(()=>{
  function clearOverlays(){
    const modal=document.getElementById('mediaModal');
    if(modal && !modal.classList.contains('hidden')){
      /* keep open only if it actually has media */
      if(!modal.querySelector('video,img,canvas')) modal.classList.add('hidden');
    }
    document.querySelectorAll('.media-modal.hidden').forEach(el=>{
      el.style.pointerEvents='none';
    });
  }
  async function h3Generate(ev){
    if(ev){ev.preventDefault();ev.stopPropagation();}
    const btn=document.getElementById('gen');
    if(btn) btn.disabled=false;
    if(typeof buildAndQueue!=='function'){
      alert('生成処理が読み込めていません。ページを再読み込みしてください。');
      return;
    }
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
    }
  }
  function bind(){
    clearOverlays();
    const btn=document.getElementById('gen');
    if(!btn || btn.dataset.clickFix==='1') return;
    btn.dataset.clickFix='1';
    btn.disabled=false;
    btn.type='button';
    btn.addEventListener('click',h3Generate);
  }
  window.h3Generate=h3Generate;
  bind();
  document.addEventListener('DOMContentLoaded',bind);
})();
