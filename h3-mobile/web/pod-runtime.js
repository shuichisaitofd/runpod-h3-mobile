(()=>{
  const el=document.querySelector('#runtime');
  if(!el) return;

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
    const sec=currentSeconds();
    if(sec==null){el.textContent='Pod --:--:--';return;}
    el.textContent=`Pod ${fmt(sec)}`;
  }

  function ensureTimer(){
    if(timer) return;
    // setInterval自体を時計として使わず、毎回 Date.now() から再計算する。
    // Safariがバックグラウンドでタイマーを間引いても累積誤差しない。
    timer=setInterval(render,1000);
  }

  async function sync(){
    try{
      const r=await fetch('/h3-mobile/api/pod-runtime',{cache:'no-store'});
      const j=await r.json();
      if(j.ok){
        const parsed=j.started_at?Date.parse(j.started_at):NaN;
        if(Number.isFinite(parsed)){
          startedAtMs=parsed;
          fallbackBaseSeconds=null;
          fallbackBaseNow=null;
        }else if(j.uptime_seconds!=null){
          fallbackBaseSeconds=Number(j.uptime_seconds);
          fallbackBaseNow=Date.now();
        }
        render();
        ensureTimer();
        return;
      }
    }catch{}
    render();
  }

  sync();
  setInterval(sync,30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
  window.addEventListener('pageshow',sync);
})();
