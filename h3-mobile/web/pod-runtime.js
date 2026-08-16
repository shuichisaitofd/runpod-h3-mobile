(()=>{
  const el=document.querySelector('#runtime');
  if(!el) return;
  let sec=null,timer=null;
  const fmt=n=>{n=Math.max(0,Math.floor(Number(n)||0));const h=Math.floor(n/3600),m=Math.floor((n%3600)/60),s=n%60;return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;};
  const render=()=>{if(sec!=null)el.textContent=`Pod ${fmt(sec)}`;};
  async function sync(){
    try{
      const r=await fetch('/h3-mobile/api/pod-runtime',{cache:'no-store'});
      const j=await r.json();
      if(j.ok&&j.uptime_seconds!=null){sec=Number(j.uptime_seconds);render();if(!timer)timer=setInterval(()=>{sec++;render();},1000);return;}
    }catch{}
    if(sec==null) el.textContent='Pod --:--:--';
  }
  sync();setInterval(sync,60000);
})();
