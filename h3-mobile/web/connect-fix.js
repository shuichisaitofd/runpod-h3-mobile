(()=>{
  async function probe(url, ms){
    const ctl=new AbortController();
    const t=setTimeout(()=>ctl.abort(), ms||7000);
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
      if(await probe(url,7000)){ok=true;break;}
    }
    if(ok){
      if(statusEl) statusEl.textContent='ComfyUI 接続中';
      if(notice){notice.className='notice ok';notice.textContent='ComfyUIへの接続は正常です。';}
    }else{
      if(statusEl) statusEl.textContent='未接続';
      if(notice){notice.className='notice danger';notice.textContent='ComfyUIへ接続できません。接続先PodのBase URLを確認してください。';}
    }
  }
  window.health=health;
  health();
})();
