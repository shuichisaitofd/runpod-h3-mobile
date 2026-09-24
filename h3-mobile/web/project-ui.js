function visibleProjects(){
  return getProjects().map(p=>({...p,archived:!!p.archived})).filter(p=>!p.archived);
}
function isProjectPage(){
  return !!document.querySelector('.page[data-page="projects"].active');
}
function syncManageButton(){
  const btn=document.getElementById('openProjects');
  if(!btn)return;
  btn.textContent=isProjectPage()?'閉じる':'管理';
}
function renderProjectSettings(){
  const activeRoot=$('#projectActiveList'), archiveRoot=$('#projectArchiveList');
  if(!activeRoot||!archiveRoot)return;
  const projects=getProjects().map(p=>({...p,archived:!!p.archived}));
  const activeId=getActiveProjectId();
  const vis=projects.filter(p=>!p.archived), arc=projects.filter(p=>p.archived);
  activeRoot.innerHTML=vis.length?vis.map(p=>`<div class="model-item" style="margin-bottom:8px"><div class="row"><div class="model-name" style="flex:1">${p.name}${p.id===activeId?'（使用中）':''}</div><button class="secondary compact" data-proj-use="${p.id}">使う</button><button class="secondary compact" data-proj-rename="${p.id}">改名</button><button class="secondary compact" data-proj-archive="${p.id}">アーカイブ</button></div></div>`).join(''):'<div class="small">表示中の案件はありません。</div>';
  archiveRoot.innerHTML=arc.length?arc.map(p=>`<div class="model-item" style="margin-bottom:8px"><div class="row"><div class="model-name" style="flex:1">${p.name}</div><button class="secondary compact" data-proj-restore="${p.id}">表示に戻す</button><button class="secondary compact" data-proj-delete="${p.id}">削除</button></div></div>`).join(''):'<div class="small">アーカイブはありません。</div>';
}
function renderProjectTabs(){
  const select=$('#projectSelect');
  if(!select)return;
  const projects=visibleProjects();
  let activeId=getActiveProjectId();
  if(!projects.some(p=>p.id===activeId)){
    activeId=projects[0]?.id||null;
    if(activeId)setActiveProjectId(activeId);
  }
  select.innerHTML=projects.map(p=>`<option value="${p.id}" ${p.id===activeId?'selected':''}>${p.name}</option>`).join('');
  if(!select.dataset.bound){
    select.dataset.bound='1';
    select.onchange=()=>switchProject(select.value);
  }
  renderProjectSettings();
  syncManageButton();
}
async function archiveProject(id){
  const projects=getProjects();
  if(projects.filter(p=>!p.archived).length<=1){alert('表示中の案件は最低1件必要です');return;}
  const p=projects.find(x=>x.id===id);if(!p)return;
  if(!confirm(`${p.name}をアーカイブしますか？ヘッダーのプルダウンから消えます。`))return;
  p.archived=true;saveProjects(projects);
  if(getActiveProjectId()===id){
    const next=projects.find(x=>!x.archived);
    if(next)await switchProject(next.id);
    else renderProjectTabs();
  }else renderProjectTabs();
}
async function restoreProject(id){
  const projects=getProjects();
  const p=projects.find(x=>x.id===id);if(!p)return;
  p.archived=false;saveProjects(projects);
  await switchProject(id);
}
function renameProject(id){
  const projects=getProjects();
  const p=projects.find(x=>x.id===id);if(!p)return;
  const name=prompt('新しい案件名',p.name);if(!name)return;
  p.name=name.trim();saveProjects(projects);renderProjectTabs();
}
function openProjectSettings(){
  if(isProjectPage()) page('create');
  else page('projects');
  renderProjectSettings();
  syncManageButton();
  window.scrollTo(0,0);
}
const origPage=page;
page=function(name){
  origPage(name);
  if(name==='projects') renderProjectSettings();
  syncManageButton();
};
$('#addProject')&&($('#addProject').onclick=async()=>{
  const n=prompt('案件名','案件');if(!n)return;
  const rec=newProjectRecord(n.trim());
  rec.archived=false;
  const projects=getProjects();
  projects.push(rec);saveProjects(projects);
  await switchProject(rec.id);
});
const projectPage=$('#projectActiveList')?.closest('.page');
if(projectPage&&!projectPage.dataset.bound){
  projectPage.dataset.bound='1';
  projectPage.addEventListener('click',e=>{
    const use=e.target.closest('[data-proj-use]');
    const rename=e.target.closest('[data-proj-rename]');
    const archive=e.target.closest('[data-proj-archive]');
    const restore=e.target.closest('[data-proj-restore]');
    const del=e.target.closest('[data-proj-delete]');
    if(use){switchProject(use.dataset.projUse);page('create');}
    if(rename)renameProject(rename.dataset.projRename);
    if(archive)archiveProject(archive.dataset.projArchive);
    if(restore)restoreProject(restore.dataset.projRestore);
    if(del)deleteProject(del.dataset.projDelete);
  });
}
(function setupProjectHeader(){
  if(!document.getElementById('h3ProjectUiCss')){
    const css=document.createElement('style');
    css.id='h3ProjectUiCss';
    css.textContent='.project-tabs{align-items:center}.project-tabs select{width:auto!important;flex:1;min-width:0}#openProjects{position:relative;z-index:6;flex:0 0 auto;margin-top:0!important}';
    document.head.appendChild(css);
  }
  const btn=document.getElementById('openProjects');
  if(btn){
    btn.setAttribute('onclick','openProjectSettings()');
    btn.onclick=openProjectSettings;
  }
  document.querySelectorAll('.nav[data-target="projects"]').forEach(b=>b.remove());
  const nav=document.querySelector('.bottomin');
  if(nav) nav.style.gridTemplateColumns='repeat(6,1fr)';
  syncManageButton();
})();
window.openProjectSettings=openProjectSettings;
window.renderProjectTabs=renderProjectTabs;
renderProjectTabs();
if(!document.querySelector('script[src^="job-timer.js"]')){
  const s=document.createElement('script');
  s.src='job-timer.js';
  document.body.appendChild(s);
}
