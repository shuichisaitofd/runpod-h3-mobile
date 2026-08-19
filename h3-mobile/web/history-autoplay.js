(()=>{
  let observer=null;
  const root=()=>document.querySelector('#historyList');
  const isLarge=()=>root()?.classList.contains('large-view');

  // Single global 音声ON/音声OFF preference for 大サムネ playback, shared by
  // every video in that view (no per-video controls). Persisted across visits;
  // absent key = first-time use = ON by default. Does not affect 小サムネ/list
  // behavior (those never autoplay/unmute regardless of this flag) and has no
  // effect on generation itself — playback-only, in the browser.
  const SOUND_KEY='h3HistorySoundOn';
  let soundOn=localStorage.getItem(SOUND_KEY)!=='0';
  let toggleBtn=null;

  function pauseAll(){
    root()?.querySelectorAll('video.history-media').forEach(v=>v.pause());
  }

  function updateToggleLabel(){
    if(!toggleBtn)return;
    toggleBtn.textContent=soundOn?'🔊 音声ON':'🔇 音声OFF';
  }

  function updateToggleVisibility(){
    if(!toggleBtn)return;
    toggleBtn.classList.toggle('hidden',!isLarge());
  }

  function buildToggleButton(){
    let b=document.querySelector('#historySoundToggle');
    if(b)return b;
    const tools=document.querySelector('.history-tools');
    if(!tools)return null;
    b=document.createElement('button');
    b.type='button';
    b.id='historySoundToggle';
    b.className='secondary hidden';
    b.onclick=()=>setSoundOn(!soundOn);
    const viewToggle=tools.querySelector('.view-toggle');
    if(viewToggle&&viewToggle.nextSibling)tools.insertBefore(b,viewToggle.nextSibling);
    else tools.appendChild(b);
    return b;
  }

  function setSoundOn(on){
    soundOn=on;
    localStorage.setItem(SOUND_KEY,on?'1':'0');
    updateToggleLabel();
    reapplySound();
  }

  // One playback helper shared by both the intersection-driven autoplay and
  // the gesture-unlock retry below, so there is only one place that decides
  // muted state / play() / the iOS Safari fallback.
  function playWithCurrentSoundPref(v){
    v.muted=!soundOn;
    const p=v.play();
    if(p?.catch)p.catch(()=>{
      // iOS Safari (and others) block autoplay-with-sound before any user
      // gesture has happened on the page yet. Fall back to a silent autoplay
      // so existing preview behavior is never broken; the gesture listener
      // below re-applies 音声ON with sound as soon as the user taps anything.
      if(!v.muted){
        v.muted=true;
        v.play().catch(()=>{});
      }
    });
  }

  // Re-apply the current 音声ON/OFF preference to whatever is actually
  // playing right now in 大サムネ view. Called after the toggle is flipped,
  // and after the first user gesture on the page (to unlock sound that an
  // earlier autoplay-with-sound attempt had to fall back to muted for).
  function reapplySound(){
    if(!isLarge())return;
    root()?.querySelectorAll('video.history-media').forEach(v=>{
      if(v.paused)return;
      playWithCurrentSoundPref(v);
    });
  }

  function observeVideos(){
    if(observer) observer.disconnect();
    observer=new IntersectionObserver(entries=>{
      for(const entry of entries){
        const v=entry.target;
        if(!(v instanceof HTMLVideoElement)) continue;
        if(isLarge() && entry.isIntersecting && entry.intersectionRatio>=0.45){
          v.playsInline=true;
          v.loop=true;
          v.preload='auto';
          playWithCurrentSoundPref(v);
        }else{
          v.pause();
        }
      }
    },{threshold:[0,0.25,0.45,0.75,1]});

    root()?.querySelectorAll('video.history-media').forEach(v=>{
      v.playsInline=true;
      v.loop=true;
      v.preload='auto';
      v.muted=!soundOn;
      observer.observe(v);
    });
    if(!isLarge()) pauseAll();
  }

  function init(){
    const historyRoot=root();
    if(!historyRoot) return;
    toggleBtn=buildToggleButton();
    updateToggleLabel();
    updateToggleVisibility();
    observeVideos();
    new MutationObserver(()=>requestAnimationFrame(observeVideos)).observe(historyRoot,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    document.querySelector('#historyLargeMode')?.addEventListener('click',()=>setTimeout(()=>{updateToggleVisibility();observeVideos();},0));
    document.querySelector('#historyListMode')?.addEventListener('click',()=>setTimeout(()=>{updateToggleVisibility();pauseAll();observeVideos();},0));
    document.addEventListener('visibilitychange',()=>{if(document.hidden) pauseAll();else observeVideos();});
    // First user interaction anywhere on the page unlocks audio in browsers
    // (iOS Safari included) that blocked the initial autoplay-with-sound
    // attempt. Cheap/idempotent, so no need to unregister after one use.
    ['pointerdown','touchend','click'].forEach(evt=>document.addEventListener(evt,()=>{if(soundOn)reapplySound();},{passive:true}));
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
