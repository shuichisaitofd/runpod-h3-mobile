(()=>{
  if(!document.getElementById('add')){
    const b=document.createElement('button');
    b.id='add';
    b.type='button';
    b.hidden=true;
    b.style.display='none';
    document.body.appendChild(b);
  }
})();
