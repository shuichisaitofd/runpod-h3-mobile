(()=>{
  const el=document.querySelector('#billing');
  if(!el) return;

  const fmtMoney=n=>'$'+Number(n).toFixed(2);
  const fmtHours=n=>{
    if(n>=100) return Math.round(n)+'h';
    return n.toFixed(1)+'h';
  };

  function render(data){
    if(!data || !data.ok){
      el.textContent='残高 -- / 残り -- / 単価 --';
      el.classList.remove('billing-ok');
      el.title=data && data.error ? data.error : 'RunPod APIから取得できませんでした';
      return;
    }
    const balance=data.balance!=null?fmtMoney(data.balance):'--';
    const remain=data.estimated_hours_remaining!=null?fmtHours(data.estimated_hours_remaining):'--';
    const rate=data.cost_per_hour!=null?fmtMoney(data.cost_per_hour)+'/h':'--';
    // "概算" ("approximate") because other pods/storage on the same account
    // also draw from this balance, so remaining-time is only ever an estimate.
    el.textContent=`残高 ${balance} / 概算残り ${remain} / ${rate}`;
    el.classList.add('billing-ok');
    el.title=data.error||'';
  }

  async function sync(){
    try{
      const url=typeof apiUrl==='function'?apiUrl('/h3-mobile/api/pod-billing'):'/h3-mobile/api/pod-billing';
      const r=await fetch(url,{cache:'no-store'});
      const j=await r.json();
      render(j);
    }catch{
      render(null);
    }
  }

  sync();
  // Billing changes slowly; a coarse poll is enough and keeps load on the
  // RunPod API low.
  setInterval(sync,120000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
})();
