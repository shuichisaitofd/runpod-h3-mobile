(()=>{
  let observer=null;
  const root=()=>document.querySelector('#historyList');
  const isLarge=()=>root()?.classList.contains('large-view');

  function pauseAll(){
    root()?.querySelectorAll('video.history-media').forEach(v=>v.pause());
  }

  function ensureSoundButton(v){
    if(v.dataset.h3SoundReady) return;
    v.dataset.h3SoundReady='1';
    const wrap=document.createElement('div');
    wrap.className='h3-history-video-wrap';
    v.parentNode?.insertBefore(wrap,v);
    wrap.appendChild(v);
    const b=document.createElement('button');
    b.type='button';
    b.className='secondary h3-history-sound';
    b.textContent='🔇 音声OFF';
    b.onclick=async e=>{
      e.preventDefault();
      e.stopPropagation();
      v.muted=!v.muted;
      b.textContent=v.muted?'🔇 音声OFF':'🔊 音声ON';
      if(!v.muted){
        try{await v.play();}catch{
          v.muted=true;
          b.textContent='🔇 音声OFF';
        }
      }
    };
    wrap.appendChild(b);
  }

  function setButtonVisibility(v){
    const wrap=v.closest('.h3-history-video-wrap');
    const b=wrap?.querySelector('.h3-history-sound');
    if(b) b.style.display=isLarge()?'block':'none';
  }

  function observeVideos(){
    if(observer) observer.disconnect();
    observer=new IntersectionObserver(entries=>{
      for(const entry of entries){
        const v=entry.target;
        if(!(v instanceof HTMLVideoElement)) continue;
        setButtonVisibility(v);
        if(isLarge() && entry.isIntersecting && entry.intersectionRatio>=0.45){
          v.playsInline=true;
          v.loop=true;
          v.preload='auto';
          const p=v.play();
          if(p?.catch) p.catch(()=>{
            // Safari blocks automatic playback with sound. Fall back to muted autoplay;
            // the user can tap the sound button to enable audio for this preview.
            if(!v.muted){
              v.muted=true;
              const b=v.closest('.h3-history-video-wrap')?.querySelector('.h3-history-sound');
              if(b) b.textContent='🔇 音声OFF';
              v.play().catch(()=>{});
            }
          });
        }else{
          v.pause();
        }
      }
    },{threshold:[0,0.25,0.45,0.75,1]});

    root()?.querySelectorAll('video.history-media').forEach(v=>{
      if(!v.dataset.h3SoundReady) v.muted=true;
      v.playsInline=true;
      v.loop=true;
      v.preload='auto';
      ensureSoundButton(v);
      setButtonVisibility(v);
      observer.observe(v);
    });
    if(!isLarge()) pauseAll();
  }

  function init(){
    const historyRoot=root();
    if(!historyRoot) return;
    const style=document.createElement('style');
    style.textContent='.h3-history-video-wrap{position:relative}.h3-history-video-wrap>video{width:100%}.h3-history-sound{position:absolute;right:8px;bottom:8px;z-index:3;padding:7px 10px!important;font-size:12px;background:rgba(10,12,16,.82)!important;backdrop-filter:blur(6px)}';
    document.head.appendChild(style);
    observeVideos();
    new MutationObserver(()=>requestAnimationFrame(observeVideos)).observe(historyRoot,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    document.querySelector('#historyLargeMode')?.addEventListener('click',()=>setTimeout(observeVideos,0));
    document.querySelector('#historyListMode')?.addEventListener('click',()=>setTimeout(()=>{pauseAll();observeVideos();},0));
    document.addEventListener('visibilitychange',()=>{if(document.hidden) pauseAll();else observeVideos();});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
