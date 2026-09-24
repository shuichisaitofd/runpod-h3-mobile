(()=>{
const KEY='h3MobileLoraLibraryV1';
const extra={id:'default-fingering-v4',name:'Fingering v4',filename:'MM-H3.-.Fingering.v4.safetensors',originalFilename:'MM-H3.-.Fingering.v4.safetensors',sha256:'',defaultStrength:1};
try{
  const lib=JSON.parse(localStorage.getItem(KEY)||'[]');
  if(Array.isArray(lib)&&!lib.some(item=>item.filename===extra.filename)){
    lib.push(extra);
    localStorage.setItem(KEY,JSON.stringify(lib));
  }
}catch(e){}
if(typeof renderQuick==='function') renderQuick();
if(typeof renderManager==='function') renderManager();
})();
