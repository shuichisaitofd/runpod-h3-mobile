(() => {
  const bottom = document.querySelector('.bottom');
  const isField = (el) => {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
    return tag === 'INPUT' && el.type !== 'file' && el.type !== 'button' && el.type !== 'checkbox' && el.type !== 'radio';
  };
  const sync = () => {
    const vv = window.visualViewport;
    const occluded = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
    const open = isField(document.activeElement) && occluded > 60;
    document.body.classList.toggle('kb-open', open);
    if (bottom) bottom.classList.toggle('kb-hidden', open);
  };
  window.addEventListener('focusin', sync);
  window.addEventListener('focusout', () => setTimeout(sync, 80));
  if (window.visualViewport) {
    visualViewport.addEventListener('resize', sync);
    visualViewport.addEventListener('scroll', sync);
  }
  window.addEventListener('resize', sync);
})();
