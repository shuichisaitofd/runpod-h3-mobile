(()=>{
  const root=()=>document.querySelector('#historyList');
  const isLarge=()=>root()?.classList.contains('large-view');
  function thumbUrl(video){
    try{const u=new URL(video.src,location.href);const fn=u.searchParams.get('filename')||'';const sf=u.searchParams.get('subfolder')||'';const path=`/h3-mobile/api/thumbnail?filename=${encodeURIComponent(fn)}&subfolder=${encodeURIComponent(sf)}`;return typeof apiUrl==='function'?apiUrl(path):path;}catch{return '';}
  }
  function apply(){
    const r=root();if(!r)return;
    r.querySelectorAll('video.history-media').forEach(v=>{
      if(!v.dataset.h3Thumb){
        const img=document.createElement('img');img.className='thumb history-static-thumb';img.alt='thumbnail';img.src=thumbUrl(v);img.onclick=()=>v.click();v.insertAdjacentElement('beforebegin',img);v.dataset.h3Thumb='1';
      }
      const img=v.previousElementSibling?.classList?.contains('history-static-thumb')?v.previousElementSibling:null;
      if(isLarge()){v.style.display='block';if(img)img.style.display='none';}
      else{v.pause();v.style.display='none';if(img)img.style.display='block';}
    });
  }
  function init(){const r=root();if(!r)return;apply();new MutationObserver(()=>requestAnimationFrame(apply)).observe(r,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});document.querySelector('#historyListMode')?.addEventListener('click',()=>setTimeout(apply,0));document.querySelector('#historyLargeMode')?.addEventListener('click',()=>setTimeout(apply,0));}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
