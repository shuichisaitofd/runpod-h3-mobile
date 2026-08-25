(()=>{
  const el=document.querySelector('#billing');
  if(!el) return;

  const ACCOUNTS_KEY='h3RunPodBillingAccountsV1';
  const ACTIVE_KEY='h3RunPodBillingActiveAccountV1';
  const POD_MAP_KEY='h3RunPodBillingPodMapV1';

  const fmtMoney=n=>'$'+Number(n).toFixed(2);
  const fmtRate=n=>'$'+Number(n).toFixed(3)+'/h';
  const fmtHM=n=>{
    const totalMin=Math.round(n*60);
    const h=Math.floor(totalMin/60);
    const m=totalMin%60;
    return `約${h}時間${m}分`;
  };
  const uid=()=>crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random();
  const loadJson=(key,fallback)=>{try{const v=JSON.parse(localStorage.getItem(key));return v??fallback;}catch{return fallback;}};
  const accounts=()=>{const v=loadJson(ACCOUNTS_KEY,[]);return Array.isArray(v)?v:[];};
  const saveAccounts=v=>localStorage.setItem(ACCOUNTS_KEY,JSON.stringify(v));
  const podMap=()=>{const v=loadJson(POD_MAP_KEY,{});return v&&typeof v==='object'&&!Array.isArray(v)?v:{};};
  const savePodMap=v=>localStorage.setItem(POD_MAP_KEY,JSON.stringify(v));
  const currentPodId=()=>{try{return typeof getActivePod==='function'?(getActivePod()?.id||null):null;}catch{return null;}};

  function activeAccount(){
    const list=accounts();
    const map=podMap();
    const podId=currentPodId();
    const mapped=podId?map[podId]:null;
    const activeId=mapped||localStorage.getItem(ACTIVE_KEY);
    return list.find(a=>a.id===activeId)||list[0]||null;
  }

  function setActiveAccount(id,bindCurrentPod=true){
    if(id)localStorage.setItem(ACTIVE_KEY,id);else localStorage.removeItem(ACTIVE_KEY);
    if(bindCurrentPod){
      const podId=currentPodId();
      if(podId){const map=podMap();if(id)map[podId]=id;else delete map[podId];savePodMap(map);}
    }
  }

  function render(data){
    const missingBillingKey=!!(data?.error&&(/RUNPOD_BILLING_API_KEY not set|account API key not provided/.test(String(data.error))));
    if(!data || !data.ok){
      el.textContent=missingBillingKey?'残高 アカウント未登録 / 残り -- / 使用額 --':'残高 -- / 残り -- / 使用額 --';
      el.classList.remove('billing-ok');
      el.title=data&&data.error?data.error:'RunPod APIから取得できませんでした';
      return;
    }
    if(data.balance==null){
      const podRate=data.cost_per_hour!=null?fmtRate(data.cost_per_hour):'--';
      el.textContent=`残高 アカウント未登録 / 残り -- / Pod ${podRate}`;
      el.classList.remove('billing-ok');
      el.title=data.error||'';
      return;
    }
    const balance=fmtMoney(data.balance);
    const remain=data.estimated_hours_remaining!=null?fmtHM(data.estimated_hours_remaining):'--';
    const rate=data.spend_rate!=null?fmtRate(data.spend_rate):'--';
    el.textContent=`残高 ${balance} / 残り ${remain} / 使用額 ${rate}`;
    el.classList.add('billing-ok');
    el.title=data.error||'';
  }

  async function requestBilling(key){
    const url=typeof apiUrl==='function'?apiUrl('/h3-mobile/api/pod-billing'):'/h3-mobile/api/pod-billing';
    if(key){
      const body=new URLSearchParams();
      body.set('billing_api_key',key);
      const r=await fetch(url,{method:'POST',body,cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      return r.json();
    }
    const r=await fetch(url,{cache:'no-store'});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function sync(){
    try{
      const acct=activeAccount();
      const data=await requestBilling(acct?.key||'');
      render(data);
    }catch{
      render(null);
    }
  }
  window.h3BillingSync=sync;

  function injectSettings(){
    const settings=document.querySelector('section.page[data-page="settings"]');
    if(!settings||document.querySelector('#billingAccountCard'))return;
    const card=document.createElement('div');
    card.className='card';
    card.id='billingAccountCard';
    card.innerHTML=`
      <h2>RunPod 残高・残り時間</h2>
      <div class="small">APIキーはこのブラウザにだけ保存します。Pod内には保存しません。ブラウザをリロードしたりPodをTerminateして作り直しても、このブラウザでは再入力不要です。</div>
      <label>使用するRunPodアカウント</label>
      <select id="billingAccountSelect"></select>
      <div class="grid2" style="margin-top:10px">
        <div><label>アカウント名</label><input id="billingAccountName" placeholder="例: RunPod メイン"></div>
        <div><label>API Key</label><input id="billingAccountKey" type="password" autocomplete="off" placeholder="rpa_..."></div>
      </div>
      <div class="actions" style="margin-top:10px">
        <button class="secondary" id="billingAccountDelete" type="button">削除</button>
        <button class="primary" id="billingAccountSave" type="button">保存して接続</button>
      </div>
      <div id="billingAccountMessage" class="small" style="margin-top:8px"></div>`;
    const podCard=[...settings.querySelectorAll('.card')].find(c=>c.querySelector('h2')?.textContent==='接続先Pod');
    settings.insertBefore(card,podCard||settings.firstChild);

    const select=card.querySelector('#billingAccountSelect');
    const name=card.querySelector('#billingAccountName');
    const key=card.querySelector('#billingAccountKey');
    const save=card.querySelector('#billingAccountSave');
    const del=card.querySelector('#billingAccountDelete');
    const msg=card.querySelector('#billingAccountMessage');

    function refresh(preferId=null){
      const list=accounts();
      const current=preferId||activeAccount()?.id||'';
      select.innerHTML='<option value="">＋ 新しいアカウント</option>'+list.map(a=>`<option value="${String(a.id).replace(/"/g,'&quot;')}">${String(a.name||'RunPod').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</option>`).join('');
      select.value=list.some(a=>a.id===current)?current:'';
      loadSelected();
    }

    function loadSelected(){
      const acct=accounts().find(a=>a.id===select.value)||null;
      name.value=acct?.name||'';
      key.value='';
      key.placeholder=acct?'登録済み（変更時のみ入力）':'rpa_...';
      del.disabled=!acct;
    }

    select.onchange=()=>{
      loadSelected();
      if(select.value){setActiveAccount(select.value,true);msg.textContent='このPodで使用するアカウントを切り替えました。';sync();}
    };

    save.onclick=async()=>{
      const selected=accounts().find(a=>a.id===select.value)||null;
      const apiKey=key.value.trim()||(selected?.key||'');
      const accountName=name.value.trim()||selected?.name||`RunPod ${accounts().length+1}`;
      if(!apiKey){msg.textContent='API Keyを入力してください。';return;}
      save.disabled=true;msg.textContent='API Keyを確認しています...';
      try{
        const data=await requestBilling(apiKey);
        if(data.balance==null||!data.account_id)throw new Error(data.error||'アカウント情報を取得できません');
        let list=accounts();
        let id=selected?.id||null;
        const same=list.find(a=>a.accountId===data.account_id);
        if(!id&&same)id=same.id;
        if(!id)id=uid();
        const record={id,name:accountName,key:apiKey,accountId:data.account_id};
        const idx=list.findIndex(a=>a.id===id);
        if(idx>=0)list[idx]=record;else list.push(record);
        saveAccounts(list);
        setActiveAccount(id,true);
        key.value='';
        refresh(id);
        render(data);
        msg.textContent='保存しました。次回からこのブラウザではAPI Keyの再入力は不要です。';
      }catch(e){
        msg.textContent=`接続失敗: ${e.message}`;
      }finally{save.disabled=false;}
    };

    del.onclick=()=>{
      const id=select.value;if(!id)return;
      const list=accounts().filter(a=>a.id!==id);saveAccounts(list);
      const map=podMap();for(const k of Object.keys(map))if(map[k]===id)delete map[k];savePodMap(map);
      if(localStorage.getItem(ACTIVE_KEY)===id)localStorage.removeItem(ACTIVE_KEY);
      refresh();msg.textContent='ブラウザから削除しました。';sync();
    };

    refresh();
  }

  injectSettings();
  sync();
  setInterval(sync,120000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();});
  document.addEventListener('click',e=>{
    if(e.target.closest?.('.switch-pod'))setTimeout(()=>{injectSettings();sync();const sel=document.querySelector('#billingAccountSelect');const acct=activeAccount();if(sel&&acct)sel.value=acct.id;},50);
  });
})();
