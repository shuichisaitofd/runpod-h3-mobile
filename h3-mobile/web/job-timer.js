(()=>{
  function fmt(sec){
    sec=Math.max(0,Math.round(Number(sec)||0));
    const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;
    if(h) return `${h}時間${String(m).padStart(2,'0')}分${String(s).padStart(2,'0')}秒`;
    if(m) return `${m}分${String(s).padStart(2,'0')}秒`;
    return `${s}秒`;
  }
  function statusText(card){
    return (card.querySelector('.job-status')?.textContent||'').trim();
  }
  function stamp(card){
    if(!card.dataset.t0) card.dataset.t0=String(Date.now());
    const st=statusText(card);
    if(st==='実行中' && !card.dataset.run0) card.dataset.run0=String(Date.now());
  }
  function paint(){
    document.querySelectorAll('#queue .queue').forEach(card=>{
      stamp(card);
      const el=card.querySelector('.elapsed');
      if(!el) return;
      const st=statusText(card);
      if(/^完了|^失敗/.test(st) || /^生成 |^停止 /.test(el.textContent||'')) return;
      if(st==='実行中'){
        el.textContent='経過 '+fmt((Date.now()-Number(card.dataset.run0||card.dataset.t0))/1000);
      }else{
        el.textContent='待機 '+fmt((Date.now()-Number(card.dataset.t0))/1000);
      }
    });
  }
  function setStatus(card,text){
    if(!card) return;
    const status=card.querySelector('.job-status') || [...card.querySelectorAll('.meta span')].find(x=>/^(準備中|待機中|実行中|完了|失敗)$/.test((x.textContent||'').trim()));
    if(status){
      status.textContent=text;
      status.className=`job-status ${typeof h3StatusClass==='function'?h3StatusClass(text):''}`.trim();
    }
    if(text==='実行中') stamp(card);
  }
  function terminal(item){
    const msgs=item?.status?.messages;
    if(Array.isArray(msgs)){
      for(const m of msgs){
        if(Array.isArray(m)&&['execution_success','execution_error','execution_interrupted'].includes(m[0])) return m[0];
      }
    }
    if(item?.status?.completed===true) return 'execution_success';
    const outputs=item?.outputs||{};
    const hasOutput=Object.values(outputs).some(node=>['videos','images','gifs','files','audio'].some(k=>Array.isArray(node?.[k])&&node[k].length));
    return hasOutput?'execution_success':null;
  }
  function au(path){return typeof apiUrl==='function'?apiUrl(path):path;}
  async function tick(){
    paint();
    if(typeof state==='undefined'||!state.jobs) return;
    const active=[...state.jobs.entries()].filter(([id,job])=>job&&!job.done);
    if(!active.length) return;
    let running=new Set(), pending=new Set();
    try{
      const qr=await fetch(au('/queue'));
      if(qr.ok){
        const q=await qr.json();
        (q.queue_running||[]).forEach(it=>{if(Array.isArray(it)&&it[1]) running.add(it[1]);});
        (q.queue_pending||[]).forEach(it=>{if(Array.isArray(it)&&it[1]) pending.add(it[1]);});
      }
    }catch{}
    for(const [id,job] of active){
      if(running.has(id)){
        if(!job.executionStartedAt) job.executionStartedAt=Date.now();
        job.phase='running';
        setStatus(job.card,'実行中');
        continue;
      }
      if(pending.has(id)){
        job.phase='queued';
        setStatus(job.card,'待機中');
        continue;
      }
      try{
        const r=await fetch(au('/history/'+encodeURIComponent(id)));
        if(!r.ok) continue;
        const data=await r.json();
        const item=data?.[id]||Object.values(data||{})[0];
        if(!item) continue;
        const t=terminal(item);
        if(!t){
          if(!job.executionStartedAt) job.executionStartedAt=Date.now();
          job.phase='running';
          setStatus(job.card,'実行中');
          continue;
        }
        job.done=true;
        job.result=t;
        const fallback=Math.max(0,(Date.now()-(job.executionStartedAt||job.startedAt||Date.now()))/1000);
        const sec=(typeof historyExecutionSeconds==='function' && historyExecutionSeconds(item)!=null)?historyExecutionSeconds(item):fallback;
        const el=job.card?.querySelector('.elapsed');
        if(t==='execution_success'){
          setStatus(job.card,'完了');
          if(el) el.textContent='生成 '+fmt(sec);
        }else{
          setStatus(job.card,'失敗');
          if(el) el.textContent='停止 '+fmt(sec);
        }
      }catch{}
    }
    paint();
  }
  window.h3Tick=tick;
  window.h3PaintTimers=paint;
  setInterval(paint,1000);
  setInterval(tick,2000);
  const start=()=>{
    const root=document.getElementById('queue');
    if(root && !root.dataset.timerBound){
      root.dataset.timerBound='1';
      new MutationObserver(()=>paint()).observe(root,{childList:true});
    }
    paint();
  };
  start();
  document.addEventListener('DOMContentLoaded',start);
})();
