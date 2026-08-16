(()=>{
  let observer=null;
  const root=()=>document.querySelector('#historyList');
  const isLarge=()=>root()?.classList.contains('large-view');

  function pauseAll(){
    root()?.querySelectorAll('video.history-media').forEach(v=>v.pause());
  }

  function observeVideos(){
    if(observer) observer.disconnect();
    observer=new IntersectionObserver(entries=>{
      for(const entry of entries){
        const v=entry.target;
        if(!(v instanceof HTMLVideoElement)) continue;
        if(isLarge() && entry.isIntersecting && entry.intersectionRatio>=0.45){
          v.muted=true;
          v.playsInline=true;
          v.loop=true;
          v.preload='auto';
          const p=v.play();
          if(p?.catch) p.catch(()=>{});
        }else{
          v.pause();
        }
      }
    },{threshold:[0,0.25,0.45,0.75,1]});

    root()?.querySelectorAll('video.history-media').forEach(v=>{
      v.muted=true;
      v.playsInline=true;
      v.loop=true;
      v.preload='auto';
      observer.observe(v);
    });
    if(!isLarge()) pauseAll();
  }

  function init(){
    const historyRoot=root();
    if(!historyRoot) return;
    observeVideos();
    new MutationObserver(()=>requestAnimationFrame(observeVideos)).observe(historyRoot,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    document.querySelector('#historyLargeMode')?.addEventListener('click',()=>setTimeout(observeVideos,0));
    document.querySelector('#historyListMode')?.addEventListener('click',()=>setTimeout(()=>{pauseAll();observeVideos();},0));
    document.addEventListener('visibilitychange',()=>{if(document.hidden) pauseAll();else observeVideos();});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
