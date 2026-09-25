(()=>{
const KEY='h3MobileLoraLibraryV1';
const extra={id:'default-fingering-v4',name:'Fingering v4',filename:'MM-H3.-.Fingering.v4.safetensors',originalFilename:'MM-H3.-.Fingering.v4.safetensors',sha256:'',defaultStrength:1};
const removed=['Squirt_HM_v1.safetensors'];
try{
  const lib=JSON.parse(localStorage.getItem(KEY)||'[]');
  if(Array.isArray(lib)){
    const cleaned=lib.filter(item=>item && !removed.includes(item.filename));
    const names=new Set();
    const deduped=[];
    for(const item of cleaned){
      const key=(item.filename||'')+'|'+(item.id||'');
      if(names.has(item.filename)) continue;
      names.add(item.filename);
      deduped.push(item);
    }
    if(!deduped.some(item=>item.filename===extra.filename)) deduped.push(extra);
    localStorage.setItem(KEY,JSON.stringify(deduped));
  }
}catch(e){}
if(typeof renderQuick==='function') renderQuick();
if(typeof renderManager==='function') renderManager();
})();
