(()=>{
  async function copyText(text, button){
    const value=String(text||'').trim();
    if(!value||value==='記録なし') return;
    try{
      await navigator.clipboard.writeText(value);
      const old=button.textContent;
      button.textContent='コピー済み';
      setTimeout(()=>button.textContent=old,1200);
    }catch{
      const ta=document.createElement('textarea');
      ta.value=value;
      ta.style.position='fixed';
      ta.style.opacity='0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      const old=button.textContent;
      button.textContent='コピー済み';
      setTimeout(()=>button.textContent=old,1200);
    }
  }

  function promptOnlyFromDetails(details){
    const body=details.querySelector('.small');
    if(!body) return '';
    let text=body.innerText||body.textContent||'';
    text=text.split(/\n解像度\s*:/)[0];
    text=text.split(/\nSeed\s*:/)[0];
    return text.trim();
  }

  function addDetailsCopyButtons(root=document){
    root.querySelectorAll('details').forEach(details=>{
      const summary=details.querySelector('summary');
      if(!summary||!summary.textContent.includes('プロンプト')) return;
      if(details.querySelector('.copy-prompt-btn')) return;
      const btn=document.createElement('button');
      btn.type='button';
      btn.className='secondary copy-prompt-btn';
      btn.textContent='プロンプトをコピー';
      btn.style.marginTop='8px';
      btn.style.padding='8px 10px';
      btn.onclick=()=>copyText(promptOnlyFromDetails(details),btn);
      details.appendChild(btn);
    });
  }

  function addEditorCopyButton(){
    const prompt=document.querySelector('#prompt');
    if(!prompt||document.querySelector('#copyPrompt')) return;
    const btn=document.createElement('button');
    btn.type='button';
    btn.id='copyPrompt';
    btn.className='secondary';
    btn.textContent='プロンプトをコピー';
    btn.style.marginTop='8px';
    btn.style.padding='8px 10px';
    btn.onclick=()=>copyText(prompt.value,btn);
    prompt.insertAdjacentElement('afterend',btn);
  }

  function init(){
    addEditorCopyButton();
    addDetailsCopyButtons();
    const observer=new MutationObserver(mutations=>{
      for(const m of mutations){
        for(const node of m.addedNodes){
          if(node.nodeType===1){
            if(node.matches?.('details')) addDetailsCopyButtons(node.parentElement||document);
            else addDetailsCopyButtons(node);
          }
        }
      }
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
