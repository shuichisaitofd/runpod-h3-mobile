(()=>{
  const tabs=document.getElementById('tabs');
  let add=document.getElementById('add');
  if(!add){
    add=document.createElement('button');
    add.id='add';
    add.type='button';
    add.hidden=true;
    add.style.display='none';
    (tabs||document.body).appendChild(add);
  }else if(tabs && add.parentNode!==tabs){
    tabs.appendChild(add);
  }
  const orig=Element.prototype.insertBefore;
  Element.prototype.insertBefore=function(node,ref){
    if(ref && ref.parentNode!==this) return this.appendChild(node);
    return orig.call(this,node,ref);
  };
})();
