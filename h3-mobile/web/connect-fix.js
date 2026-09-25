(()=>{
  async function probe(url, ms){
    const ctl=new AbortController();
    const t=setTimeout(()=>ctl.abort(), ms||6000);
    try{
      const r=await fetch(url,{signal:ctl.signal,cache:'no-store'});
      return r.ok;
    }catch{
      return false;
    }finally{
      clearTimeout(t);
    }
  }
  async function health(){
    const statusEl=document.getElementById('status');
    const notice=document.getElementById('connectNotice');
    const paths=['/system_stats','/h3-mobile/api/runtime','/queue','/h3-mobile/api/models'];
    let ok=false;
    for(const path of paths){
      const url=typeof apiUrl==='function'?apiUrl(path):path;
      if(await probe(url,6000)){ok=true;break;}
    }
    if(ok){
      if(statusEl) statusEl.textContent='ComfyUI 接続中';
      if(notice){notice.className='notice ok';notice.textContent='ComfyUIへの接続は正常です。';}
    }else{
      if(statusEl) statusEl.textContent='未接続';
      if(notice){notice.className='notice danger';notice.textContent='ComfyUIへ接続できません。接続先PodのBase URLを確認してください。';}
    }
  }
  async function workflowStatus(){
    const el=document.getElementById('workflowStatus');
    if(!el) return;
    const names=['i2v','ref2va_04','ref2va_03','ref2va_05','ref2va_06_fast','ref2va_06_stable'];
    const results=await Promise.all(names.map(n=>{
      const url=typeof apiUrl==='function'?apiUrl(`/h3-mobile/api/workflow/${n}`):`/h3-mobile/api/workflow/${n}`;
      return probe(url,6000);
    }));
    if(results.every(Boolean)){
      el.className='notice ok';
      el.textContent='I2V / Ref2VA 03 / 04 / 05 / 06 高速 / 06 安定 API workflow 登録済み';
    }else if(results.some(Boolean)){
      el.className='notice ok';
      el.textContent='一部の API workflow が登録されています。';
    }else{
      el.className='notice danger';
      el.textContent='API workflowが確認できません。';
    }
  }
  window.health=health;
  window.workflowStatus=workflowStatus;
  health();
  workflowStatus();
})();
