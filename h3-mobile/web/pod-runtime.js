(()=>{
  const el=document.querySelector('#runtime');
  if(!el) return;

  // app.js contains an older container-uptime timer. Stop it immediately so
  // the header is owned only by the PID1/container-uptime clock below.
  function disableLegacyRuntime(){
    try{
      if(typeof state!=='undefined'&&state?.runtimeTimer){
        clearInterval(state.runtimeTimer);
        state.runtimeTimer=null;
        state.runtimeSeconds=null;
      }
    }catch{}
  }
  disableLegacyRuntime();

  // ComfyUI stores /prompt extra_data inside history item.prompt[3].
  // Normalize that shape for the existing history renderer so prompt/settings
  // are restored for both single and batch H3 Mobile jobs.
  function installHistoryMetadataCompat(){
    const previousFetch=window.fetch.bind(window);
    window.fetch=async(input,init)=>{
      const r=await previousFetch(input,init);
      try{
        const url=typeof input==='string'?input:(input&&input.url)||'';
        if(!/\/history(?:\/|$|\?)/.test(url)||!r.ok)return r;
        const data=await r.clone().json();
        let changed=false;
        for(const item of Object.values(data||{})){
          if(!item||typeof item!=='object')continue;
          const h3=item?.prompt?.[3]?.h3_mobile||item?.prompt?.[3]?.extra_data?.h3_mobile||item?.prompt?.extra_data?.h3_mobile||item?.extra_data?.h3_mobile;
          if(!h3)continue;
          item.extra_data=item.extra_data||{};
          if(!item.extra_data.h3_mobile){item.extra_data.h3_mobile=h3;changed=true;}
        }
        if(!changed)return r;
        const headers=new Headers(r.headers);
        headers.delete('content-length');
        return new Response(JSON.stringify(data),{status:r.status,statusText:r.statusText,headers});
      }catch{return r;}
    };
    setTimeout(()=>{try{if(typeof loadHistory==='function')loadHistory();}catch{}},0);
  }
  installHistoryMetadataCompat();

  let startedAtMs=null;
  let fallbackBaseSeconds=null;
  let fallbackBaseNow=null;
  let timer=null;

  const fmt=n=>{
    n=Math.max(0,Math.floor(Number(n)||0));
    const h=Math.floor(n/3600),m=Math.floor((n%3600)/60),s=n%60;
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };

  function currentSeconds(){
    if(startedAtMs!=null) return (Date.now()-startedAtMs)/1000;
    if(fallbackBaseSeconds!=null&&fallbackBaseNow!=null) return fallbackBaseSeconds+(Date.now()-fallbackBaseNow)/1000;
    return null;
  }

  function render(){
    disableLegacyRuntime();
    const sec=currentSeconds();
    if(sec==null){el.textContent='Pod --:--:--';return;}
    el.textContent=`Pod ${fmt(sec)}`;
  }

  function ensureTimer(){
    if(timer) return;
    // Recalculate from Date.now() so Safari background throttling cannot
    // accumulate timer drift.
    timer=setInterval(render,1000);
  }

  // Primary (and only) source for the header clock: the pod's own PID1-based
  // uptime (/h3-mobile/api/runtime, /proc/1/stat + /proc/uptime, server-side).
  // RunPod REST (/h3-mobile/api/pod-runtime, extra_routes.py) is intentionally
  // NOT called here anymore: it required RUNPOD_API_KEY and returned 403 on
  // this pod, and was being polled every 30s for no benefit. The endpoint
  // itself is left in place server-side in case another caller needs it.
  // This is container-start time, not RunPod's official Pod start time.
  async function sync(){
    disableLegacyRuntime();
    try{
      const r=await fetch(typeof apiUrl==='function'?apiUrl('/h3-mobile/api/runtime'):'/h3-mobile/api/runtime',{cache:'no-store'});
      const j=await r.json();
      if(j.ok&&j.uptime_seconds!=null){
        startedAtMs=null;
        fallbackBaseSeconds=Number(j.uptime_seconds);
        fallbackBaseNow=Date.now();
      }
    }catch{}
    render();
    ensureTimer();
  }

  sync();
  setInterval(sync,30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
  window.addEventListener('pageshow',sync);
})();
