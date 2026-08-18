(()=>{
const MAX=5;
const batch={mode:'i2v',refVariant:'04',i2vFiles:[],refSets:[{files:[null,null,null]}],running:false};
const q=s=>document.querySelector(s);
const qa=s=>[...document.querySelectorAll(s)];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function esc(v){return String(v??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[c]));}
function randSeed(){return Math.floor(Math.random()*999999999999999);}
function apiRatio(v){return {'2:3':'2:3 (Portrait Photo)','3:2':'3:2 (Landscape Photo)','9:16':'9:16 (Portrait)','16:9':'16:9 (Landscape)','1:1':'1:1 (Square)','4:3':'4:3 (Landscape Standard)','3:4':'3:4 (Portrait Standard)'}[v]||'3:4 (Portrait Standard)';}
async function jf(url,opts){const r=await fetch(url,opts);if(!r.ok){let t='';try{t=await r.text();}catch{}throw new Error(t||`${r.status} ${r.statusText}`);}return r.json();}
function au(path){return typeof apiUrl==='function'?apiUrl(path):path;}

// --- 案件（プロジェクト）ごとの一括生成タブ独立化 ---
// app.js側の案件管理(getProjects/saveProjects/getActiveProjectId)と、専用の
// IndexedDB(h3-mobile-projects/images, app.js側のsaveProjectImage等)を再利用する。
// 一括対象画像はFileオブジェクトをlocalStorageへ直接保存せず、単発側の参照画像と
// 同じ「Blobを専用DBへ保存し復元時にFileを再構築する」方式を、
// batch_i2v_{index} / batch_ref_{setIndex}_{slotIndex} というキーで拡張する。
// Starts suppressed: batch-v2.js's own bottom-of-file init call
// (setMode('i2v');render();) runs synchronously before app.js's async
// project-restore flow has a chance to call restoreBatchProjectState() below.
// Without this, that first render() would persist a blank batch state and
// clobber whatever was actually saved for the active project. Cleared once
// restoreBatchProjectState() finishes its first run (see its finally block).
let suppressBatchPersist=true;
function activeProjectId(){return typeof getActiveProjectId==='function'?getActiveProjectId():null;}
async function saveImg(key,file){if(typeof saveProjectImage!=='function')return;const id=activeProjectId();if(!id)return;try{await saveProjectImage(id,key,file);}catch{}}
async function loadImg(key){if(typeof loadProjectImage!=='function')return null;const id=activeProjectId();if(!id)return null;try{return await loadProjectImage(id,key);}catch{return null;}}
async function delImg(key){if(typeof deleteProjectImage!=='function')return;const id=activeProjectId();if(!id)return;try{await deleteProjectImage(id,key);}catch{}}
function persistBatchMeta(){
  if(suppressBatchPersist)return;
  const id=activeProjectId();if(!id)return;
  if(typeof getProjects!=='function'||typeof saveProjects!=='function')return;
  const projects=getProjects();
  const idx=projects.findIndex(p=>p.id===id);
  if(idx<0)return;
  projects[idx].batch={
    mode:batch.mode,refVariant:batch.refVariant,
    title:q('#batchTitle')?.value,prompt:q('#batchPrompt')?.value,
    sec:Number(q('#batchSec')?.value),
    steps:batch.mode==='ref2va'?(Number(q('#batchSteps')?.value)||null):(projects[idx].batch?.steps??null),
    mp:Number(q('#batchMp')?.value),ratio:q('#batchRatio')?.value,
    seedMode:q('#batchSeedMode')?.value,seed:Number(q('#batchSeed')?.value),
    refSize:q('#batchRefSize')?.value,
    i2vFiles:batch.i2vFiles.map(f=>({name:f.name,type:f.type})),
    refSets:batch.refSets.map(s=>({files:s.files.map(f=>f?{name:f.name,type:f.type}:null)}))
  };
  saveProjects(projects);
}
async function persistBatchImages(){
  if(suppressBatchPersist)return;
  if(!activeProjectId())return;
  for(let i=0;i<MAX;i++){
    const key=`batch_i2v_${i}`;
    const f=batch.i2vFiles[i];
    if(f)await saveImg(key,f);else await delImg(key);
  }
  for(let s=0;s<MAX;s++){
    for(let slot=0;slot<3;slot++){
      const key=`batch_ref_${s}_${slot}`;
      const f=batch.refSets[s]&&batch.refSets[s].files[slot];
      if(f)await saveImg(key,f);else await delImg(key);
    }
  }
}
async function restoreBatchProjectState(id){
  suppressBatchPersist=true;
  try{
    const projects=typeof getProjects==='function'?getProjects():[];
    const p=projects.find(x=>x.id===id);
    const b=p&&p.batch;
    batch.refVariant=(b&&b.refVariant)||'04';
    qa('#batchRefVariant [data-batch-variant]').forEach(x=>x.classList.toggle('active',x.dataset.batchVariant===batch.refVariant));
    setMode((b&&b.mode)||'i2v');
    q('#batchTitle').value=(b&&b.title!=null)?b.title:'一括生成';
    q('#batchPrompt').value=(b&&b.prompt)||'';
    if(b){
      if(b.sec!=null)q('#batchSec').value=b.sec;
      if(b.mp!=null)q('#batchMp').value=b.mp;
      if(batch.mode==='ref2va'){
        if(b.steps!=null)q('#batchSteps').value=b.steps;
        if(b.ratio)q('#batchRatio').value=b.ratio;
      }
      q('#batchSeedMode').value=b.seedMode||'sequence';
      q('#batchSeed').value=b.seed!=null?b.seed:12345;
      q('#batchRefSize').value=b.refSize||'max';
    }else{
      q('#batchMp').value=0.5;q('#batchSeedMode').value='sequence';q('#batchSeed').value=12345;q('#batchRefSize').value='max';
    }
    batch.i2vFiles=[];
    const i2vMeta=(b&&b.i2vFiles)||[];
    for(let i=0;i<i2vMeta.length;i++){
      const rec=await loadImg(`batch_i2v_${i}`);
      if(rec&&rec.blob)batch.i2vFiles.push(new File([rec.blob],rec.name||i2vMeta[i].name||'image.png',{type:rec.type||i2vMeta[i].type||'image/png'}));
    }
    const refMeta=(b&&b.refSets&&b.refSets.length)?b.refSets:[{files:[null,null,null]}];
    const newRefSets=[];
    for(let s=0;s<refMeta.length;s++){
      const files=[null,null,null];
      for(let slot=0;slot<3;slot++){
        const m=refMeta[s].files&&refMeta[s].files[slot];
        if(m){const rec=await loadImg(`batch_ref_${s}_${slot}`);if(rec&&rec.blob)files[slot]=new File([rec.blob],rec.name||m.name||'image.png',{type:rec.type||m.type||'image/png'});}
      }
      newRefSets.push({files});
    }
    batch.refSets=newRefSets.length?newRefSets:[{files:[null,null,null]}];
    render();
  }finally{
    suppressBatchPersist=false;
  }
}
window.restoreBatchProjectState=restoreBatchProjectState;
async function upload(file,index,slot=0){
  const safe=String(file.name||'image.png').replace(/[^a-zA-Z0-9._-]+/g,'_');
  const name=`h3batch_${Date.now()}_${index}_${slot}_${safe}`;
  let last=null;
  for(let attempt=1;attempt<=3;attempt++){
    try{
      const fd=new FormData();
      fd.append('image',file,name);
      fd.append('type','input');
      fd.append('overwrite','true');
      const d=await jf(au('/upload/image'),{method:'POST',body:fd});
      return d.name;
    }catch(e){
      last=e;
      if(attempt<3) await sleep(700*attempt);
    }
  }
  throw new Error(`画像アップロード失敗: ${safe} / ${last?.message||'Load failed'}`);
}
function seedFor(i){const mode=q('#batchSeedMode').value;const base=Number(q('#batchSeed').value)||0;if(mode==='fixed')return base;if(mode==='random')return randSeed();return base+i;}
function setMsg(text,type=''){const el=q('#batchMessage');el.textContent=text;el.className=`notice ${type}`.trim();el.classList.remove('hidden');}
function clearMsg(){q('#batchMessage').classList.add('hidden');}
function applyBatchVariantDefaults(){if(batch.mode!=='ref2va')return;if(batch.refVariant==='03'){q('#batchSteps').value=4;q('#batchModeNote').innerHTML='Ref2VA 03: <b>Turbo LoRA + TurboSampler + Sol-Attn(int8_qk) + FusedModulation</b> / Steps・MP変更可';}else{q('#batchSteps').value=14;q('#batchModeNote').innerHTML='Ref2VA 04: <b>Sol-Attn(int8_qk) + BlockCache Balanced</b> / Steps・MP変更可';}}
function setBatchVariant(v){if(batch.running)return;batch.refVariant=v;qa('#batchRefVariant [data-batch-variant]').forEach(b=>b.classList.toggle('active',b.dataset.batchVariant===v));applyBatchVariantDefaults();persistBatchMeta();}
qa('#batchRefVariant [data-batch-variant]').forEach(b=>{if(!b.disabled)b.onclick=()=>setBatchVariant(b.dataset.batchVariant);});
function setMode(mode){if(batch.running)return;batch.mode=mode;qa('[data-batch-mode]').forEach(b=>b.classList.toggle('active',b.dataset.batchMode===mode));const ref=mode==='ref2va';q('#batchI2VInputs').classList.toggle('hidden',ref);q('#batchRefInputs').classList.toggle('hidden',!ref);q('#batchStepsWrap').classList.toggle('hidden',!ref);q('#batchRefOptions').classList.toggle('hidden',!ref);q('#batchRatio').disabled=!ref;if(ref){q('#batchSec').value=6;q('#batchRatio').value='3:4';applyBatchVariantDefaults();}else{q('#batchSec').value=10;q('#batchRatio').value='元画像と同じ';q('#batchModeNote').innerHTML='I2V: <b>Turbo + Sage / 4step固定</b>'; }render();}
qa('[data-batch-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.batchMode));
function filePreview(file){return file?URL.createObjectURL(file):'';}
function renderI2V(){const root=q('#batchI2VList');root.innerHTML='';batch.i2vFiles.forEach((f,i)=>{const d=document.createElement('div');d.className='batch-item';d.innerHTML=`<img class="batch-thumb" src="${filePreview(f)}"><div class="batch-item-body"><b>${i+1}. ${esc(f.name)}</b><div class="small">Seed: ${seedFor(i)}</div></div><button class="secondary batch-remove" type="button">削除</button>`;d.querySelector('.batch-remove').onclick=()=>{if(batch.running)return;batch.i2vFiles.splice(i,1);render();persistBatchImages();};root.appendChild(d);});q('#batchI2VCount').textContent=`${batch.i2vFiles.length} / ${MAX}`;}
function refSetHtml(set,i){return `<div class="row"><b style="flex:1">セット ${i+1}</b><button class="secondary batch-remove-set" type="button">削除</button></div><div class="ref-slot-grid">${[0,1,2].map(slot=>{const f=set.files[slot];return `<label class="ref-slot ${f?'has-file':''}"><span>${slot===0?'参照1 メイン':'参照'+(slot+1)+' 任意'}</span>${f?`<img src="${filePreview(f)}"><small>${esc(f.name)}</small>`:'<b>＋ 選択</b>'}<input type="file" accept="image/*" data-set="${i}" data-slot="${slot}"></label>`}).join('')}</div><div class="small">Seed: ${seedFor(i)}</div>`;}
function renderRef(){const root=q('#batchRefList');root.innerHTML='';batch.refSets.forEach((set,i)=>{const d=document.createElement('div');d.className='batch-ref-set';d.innerHTML=refSetHtml(set,i);d.querySelector('.batch-remove-set').onclick=()=>{if(batch.running)return;if(batch.refSets.length===1)batch.refSets[0]={files:[null,null,null]};else batch.refSets.splice(i,1);render();persistBatchImages();};d.querySelectorAll('input[type=file]').forEach(inp=>inp.onchange=()=>{const f=inp.files[0]||null;batch.refSets[Number(inp.dataset.set)].files[Number(inp.dataset.slot)]=f;render();persistBatchImages();});root.appendChild(d);});q('#batchRefCount').textContent=`${batch.refSets.length} / ${MAX}`;q('#addBatchRefSet').disabled=batch.refSets.length>=MAX||batch.running;}
function validRefCount(){return batch.refSets.filter(s=>s.files[0]).length;}
function render(){renderI2V();renderRef();const n=batch.mode==='i2v'?batch.i2vFiles.length:validRefCount();q('#batchJobCount').textContent=`${n}件`;q('#startBatch').disabled=batch.running||n===0;q('#clearBatch').disabled=batch.running;persistBatchMeta();}
q('#batchI2VFiles').onchange=()=>{if(batch.running)return;batch.i2vFiles=[...batch.i2vFiles,...q('#batchI2VFiles').files].slice(0,MAX);q('#batchI2VFiles').value='';render();persistBatchImages();};
q('#addBatchRefSet').onclick=()=>{if(batch.running||batch.refSets.length>=MAX)return;batch.refSets.push({files:[null,null,null]});render();persistBatchImages();};
q('#clearBatch').onclick=()=>{if(batch.running)return;batch.i2vFiles=[];batch.refSets=[{files:[null,null,null]}];clearMsg();render();persistBatchImages();};
q('#batchSeedMode').onchange=render;q('#batchSeed').oninput=render;
['#batchTitle','#batchPrompt','#batchSec','#batchMp','#batchRatio','#batchRefSize','#batchSteps'].forEach(s=>q(s)?.addEventListener('input',persistBatchMeta));
q('#copyBatchPrompt').onclick=async()=>{const text=q('#batchPrompt').value.trim();if(!text)return;try{await navigator.clipboard.writeText(text);}catch{const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();}const b=q('#copyBatchPrompt'),old=b.textContent;b.textContent='コピー済み';setTimeout(()=>b.textContent=old,1000);};
function h3sc(text){return typeof h3StatusClass==='function'?h3StatusClass(text):'';}
// Fallback card factory, only used if app.js's jobCard() is somehow unavailable
// (app.js always loads before this file, so this path is not normally taken).
function progressCard(index,total,title,status='待機中'){const d=document.createElement('div');d.className='queue';d.dataset.batchIndex=String(index);d.innerHTML=`<div><b>${index+1}/${total} ${esc(title)}</b></div><div class="meta small"><span class="job-status ${h3sc(status)}">${status}</span><span class="elapsed">経過 0秒</span></div>`;return d;}
function setCardStatus(card,text){if(!card)return;const status=card.querySelector('.job-status');if(status){status.textContent=text;status.className=`job-status ${h3sc(text)}`.trim();}}
function setCardElapsed(card,text){if(!card)return;const el=card.querySelector('.elapsed');if(el)el.textContent=text;}
// Batch items are registered into the same state.jobs Map that single jobs use
// (app.js), so the shared /queue + /history polling in index.html's tick()
// determines 待機中/実行中/完了/失敗 and elapsed time uniformly for both —
// no separate batch-only status logic to keep in sync.
async function waitJobDone(id){for(;;){await sleep(300);if(typeof state==='undefined'||!state.jobs)return {result:null};const job=state.jobs.get(id);if(job&&job.done)return job;}}
async function buildI2V(image,index,cfg){const wf=await jf(au('/h3-mobile/api/workflow/i2v'));wf['114'].inputs.image=image;wf['119'].inputs.megapixels=cfg.mp;wf['105:104'].inputs.prompt=cfg.prompt;wf['105:111'].inputs.value=cfg.seconds;wf['105:15'].inputs.noise_seed=cfg.seed;wf['92'].inputs.filename_prefix='video/'+cfg.prefix;return {wf,extra:{...cfg,mode:'i2v',image0:image,batch:true,batch_index:index+1}};}
async function buildRef(names,index,cfg){const wf=await jf(au(`/h3-mobile/api/workflow/${batch.refVariant==='03'?'ref2va_03':'ref2va_04'}`));wf['137'].inputs.image=names[0];if(names[1])wf['139'].inputs.image=names[1];else{delete wf['139'];delete wf['136'].inputs['ref_images.ref_image_1'];}
if(names[2]){wf['h3mobile_ref3']={inputs:{image:names[2]},class_type:'LoadImage',_meta:{title:'参照画像3'}};wf['136'].inputs['ref_images.ref_image_2']=['h3mobile_ref3',0];}else delete wf['136'].inputs['ref_images.ref_image_2'];
wf['138'].inputs.value=cfg.prompt;wf['132'].inputs.value=cfg.seconds;wf['124'].inputs.steps=cfg.steps;wf['115'].inputs.aspect_ratio=apiRatio(cfg.ratio);wf['115'].inputs.megapixels=cfg.mp;wf['129'].inputs.noise_seed=cfg.seed;wf['136'].inputs.ref_image_size=cfg.ref_image_size;wf['92'].inputs.filename_prefix='video/'+cfg.prefix;return {wf,extra:{...cfg,mode:'ref2va',variant:batch.refVariant,image0:names[0],image1:names[1]||null,image2:names[2]||null,batch:true,batch_index:index+1}};}
async function queueOne(wf,extra){return jf(au('/prompt'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:wf,extra_data:{h3_mobile:extra}})});}
function safe(v){return String(v||'H3').replace(/[\\/:*?\"<>|]+/g,'_').slice(0,80);}
async function start(){
  if(batch.running)return;
  const prompt=q('#batchPrompt').value.trim();
  if(!prompt){setMsg('プロンプトを入力してください。','danger');return;}
  const jobs=batch.mode==='i2v'?batch.i2vFiles.map(f=>({file:f,title:f.name})):batch.refSets.filter(s=>s.files[0]).map((s,i)=>({set:s,title:`参照セット ${i+1}`}));
  if(!jobs.length){setMsg('生成する画像を選択してください。','danger');return;}
  const seconds=Math.max(1,Number(q('#batchSec').value)||1);
  const mp=Math.min(2,Math.max(.1,Number(q('#batchMp').value)||.5));
  const steps=Math.max(1,Number(q('#batchSteps').value)||(typeof defaultStepsForVariant==='function'?defaultStepsForVariant(batch.refVariant):14));
  const ratio=batch.mode==='i2v'?'元画像と同じ':q('#batchRatio').value;
  const refSize=q('#batchRefSize').value;
  const batchTitle=q('#batchTitle').value.trim()||'一括生成';
  batch.running=true;render();clearMsg();

  // Each batch run gets one wrapping .batch-group element (summary + all N job
  // cards) inserted as a single block into #queue — the SAME list single jobs
  // use. Job cards are still built with app.js's jobCard() unchanged, so
  // status color / elapsed timer / done-flag handling (state.jobs, job.card,
  // /queue+/history polling) is identical to single jobs; only the DOM
  // wrapper around them is new. Groups are prepended (not replacing anything),
  // so: (a) batch groups and single jobs interleave correctly by actual start
  // time, (b) a later run's group never removes/replaces an earlier group —
  // #queue (and each existing .batch-group already inside it) is never
  // cleared by anything, (c) 1..N order within the group is preserved because
  // cards are appended to the group in that order before the group itself is
  // inserted as one block.
  const group=document.createElement('div');
  group.className='batch-group';
  const summary=document.createElement('div');
  summary.className='batch-group-summary';
  summary.innerHTML=`<b>${esc(batchTitle)}</b><span class="batch-overall">0 / ${jobs.length}</span>`;
  group.appendChild(summary);
  const overallEl=summary.querySelector('.batch-overall');
  const note=document.createElement('div');
  note.className='small';
  note.style.margin='4px 0 8px';
  note.textContent='先に全画像をRunPodへ保存し、全ジョブをComfyUIのQueueへ1→2→3の順に投入します。生成自体はComfyUI側で順次処理されます。';
  group.appendChild(note);

  const modeLabel=batch.mode==='ref2va'?`Ref2VA ${batch.refVariant}`:'I2V';
  const cardSteps=batch.mode==='ref2va'?steps:null;
  const cards=jobs.map((j,i)=>{
    const c=typeof jobCard==='function'
      ?jobCard(`${batchTitle} ${i+1}`,modeLabel,seconds,cardSteps,ratio,mp,prompt,'準備中')
      :progressCard(i,jobs.length,j.title);
    group.appendChild(c);
    return c;
  });
  const queueEl=q('#queue');
  if(queueEl)queueEl.prepend(group);
  if(typeof page==='function')page('running');

  let ok=0,fail=0;
  const prepared=new Array(jobs.length);

  // iPhone/Safariで選択ファイルを長時間保持したときの Load failed を避けるため、全画像を先にアップロードする。
  for(let i=0;i<jobs.length;i++){
    try{
      setCardStatus(cards[i],'準備中');setCardElapsed(cards[i],'画像をRunPodへアップロード中');
      if(batch.mode==='i2v'){
        prepared[i]={image:await upload(jobs[i].file,i,0),title:jobs[i].title};
      }else{
        const names=[];
        for(let slot=0;slot<3;slot++){
          const f=jobs[i].set.files[slot];
          if(f) names[slot]=await upload(f,i,slot);
        }
        prepared[i]={names,title:jobs[i].title};
      }
      setCardStatus(cards[i],'待機中');setCardElapsed(cards[i],'アップロード完了・生成待ち');
    }catch(e){
      prepared[i]={error:e};
      fail++;
      if(typeof markJobCardFailed==='function')markJobCardFailed(cards[i]);
      else{setCardStatus(cards[i],'失敗');setCardElapsed(cards[i],e.message);}
    }
  }

  // Submit every job's /prompt request in strict 1→2→3 order BEFORE waiting
  // for any of them to finish generating. Each POST is awaited (so ComfyUI
  // receives them in this exact order — its queue is a priority heap keyed by
  // a monotonically increasing submission number, so sequential awaited POSTs
  // guarantee 1,2,3 execution order server-side), but waitJobDone() is
  // intentionally NOT called here — it no longer gates the next submission.
  // A /prompt failure for one job only fails that job's card and does not
  // stop the remaining jobs from being submitted.
  for(let i=0;i<jobs.length;i++){
    if(prepared[i]?.error)continue;
    const seed=seedFor(i);
    const prefix=safe(`${batchTitle}_${String(i+1).padStart(2,'0')}`);
    const card=cards[i];
    try{
      const cfg={title:`${batchTitle} ${i+1}`,batch_title:batchTitle,prompt,seconds,megapixels:mp,mp,steps:batch.mode==='ref2va'?steps:null,ratio,seed,ref_image_size:refSize,prefix};
      const built=batch.mode==='i2v'?await buildI2V(prepared[i].image,i,cfg):await buildRef(prepared[i].names,i,cfg);
      const queued=await queueOne(built.wf,built.extra);
      const startedAt=Date.now();
      const metaEl=card?.querySelector('.meta');
      if(metaEl)metaEl.insertAdjacentHTML('beforeend',`<span>prompt_id: ${esc(queued.prompt_id)}</span>`);
      if(typeof state!=='undefined'&&state.jobs)state.jobs.set(queued.prompt_id,{title:cfg.title,prompt,card,startedAt,phase:'queued'});
      prepared[i].promptId=queued.prompt_id;
    }catch(e){
      prepared[i].queueError=true;
      fail++;
      if(typeof markJobCardFailed==='function')markJobCardFailed(card);
      else{setCardStatus(card,'失敗');setCardElapsed(card,e.message);}
    }
  }

  // All jobs that could be queued are now registered in state.jobs; the
  // shared tick() (index.html) — via /queue + /history polling — owns their
  // 待機中/実行中/完了/失敗 status, color, and elapsed/completion time from
  // here on, exactly like single jobs. This phase only waits for each job's
  // job.done flag to learn the final success/failure tally and update the
  // group's overall counter as each one actually finishes (not as each is
  // submitted), matching what the counter showed before this change.
  let doneCount=prepared.filter(p=>p?.error||p?.queueError).length;
  if(overallEl)overallEl.textContent=`${doneCount} / ${jobs.length}`;
  await Promise.all(prepared.map(async p=>{
    if(!p||!p.promptId)return;
    const job=await waitJobDone(p.promptId);
    if(job.result==='execution_success')ok++;else fail++;
    doneCount++;
    if(overallEl)overallEl.textContent=`${doneCount} / ${jobs.length}`;
  }));

  batch.running=false;render();
  setMsg(`一括生成完了：成功 ${ok}件 / 失敗 ${fail}件`,fail?'':'ok');
  if(typeof loadHistory==='function')loadHistory();
}
q('#startBatch').onclick=start;
setMode('i2v');render();
})();
