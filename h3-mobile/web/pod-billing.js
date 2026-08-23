(()=>{
  const el=document.querySelector('#billing');
  if(!el) return;

  const fmtMoney=n=>'$'+Number(n).toFixed(2);
  const fmtRate=n=>'$'+Number(n).toFixed(3)+'/h';
  // Account-wide remaining time (balance / currentSpendPerHr), shown as
  // "約H時間M分" rather than a raw hour count.
  const fmtHM=n=>{
    const totalMin=Math.round(n*60);
    const h=Math.floor(totalMin/60);
    const m=totalMin%60;
    return `約${h}時間${m}分`;
  };

  function render(data){
    if(!data || !data.ok){
      el.textContent='残高 -- / 残り -- / 使用額 --';
      el.classList.remove('billing-ok');
      el.title=data && data.error ? data.error : 'RunPod APIから取得できませんでした';
      return;
    }
    const balance=data.balance!=null?fmtMoney(data.balance):'--';
    const remain=data.estimated_hours_remaining!=null?fmtHM(data.estimated_hours_remaining):'--';
    const rate=data.spend_rate!=null?fmtRate(data.spend_rate):'--';
    // spend_rate is the account-wide currentSpendPerHr (all pods/storage on
    // the account), which is what estimated_hours_remaining is derived
    // from - this pod's own cost_per_hour is auxiliary only and not shown
    // here.
    el.textContent=`残高 ${balance} / 残り ${remain} / 使用額 ${rate}`;
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
