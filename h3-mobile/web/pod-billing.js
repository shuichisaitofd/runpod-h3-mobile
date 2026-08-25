(()=>{
  const el=document.querySelector('#billing');
  if(!el) return;

  const fmtMoney=n=>'$'+Number(n).toFixed(2);
  const fmtRate=n=>'$'+Number(n).toFixed(3)+'/h';
  const fmtHM=n=>{
    const totalMin=Math.round(n*60);
    const h=Math.floor(totalMin/60);
    const m=totalMin%60;
    return `約${h}時間${m}分`;
  };

  function render(data){
    const missingBillingKey=!!(data?.error&&String(data.error).includes('RUNPOD_BILLING_API_KEY not set'));

    if(!data || !data.ok){
      el.textContent=missingBillingKey?'残高 キー未設定 / 残り -- / 使用額 --':'残高 -- / 残り -- / 使用額 --';
      el.classList.remove('billing-ok');
      el.title=data && data.error ? data.error : 'RunPod APIから取得できませんでした';
      return;
    }

    if(missingBillingKey){
      const podRate=data.cost_per_hour!=null?fmtRate(data.cost_per_hour):'--';
      el.textContent=`残高 キー未設定 / 残り -- / Pod ${podRate}`;
      el.classList.remove('billing-ok');
      el.title=data.error||'';
      return;
    }

    const balance=data.balance!=null?fmtMoney(data.balance):'--';
    const remain=data.estimated_hours_remaining!=null?fmtHM(data.estimated_hours_remaining):'--';
    const rate=data.spend_rate!=null?fmtRate(data.spend_rate):'--';
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
  setInterval(sync,120000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
})();
