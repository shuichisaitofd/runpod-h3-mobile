const STORAGE_KEY="prompt-library-v5";
const PENDING_KEY="h3PendingLibraryPrompt";
const DEFAULT_GENRES=["正常位","騎乗位","立位","手マン","ディルド","フェラ","胸部","その他"];
const GENRE_COLORS={"正常位":"#3b82f6","騎乗位":"#f43f5e","立位":"#f59e0b","手マン":"#8b5cf6","ディルド":"#14b8a6","フェラ":"#ec4899","胸部":"#22c55e","その他":"#9ca3af"};
const EXTRA=["#0ea5e9","#84cc16","#a855f7","#ef4444","#06b6d4"];
const $=id=>document.getElementById(id);
let items=[], genres=[...DEFAULT_GENRES], activeGenre="すべて", editIndex=null;
let dragItemFrom=null, dragGenreFrom=null;

function toast(msg){const el=$("toast");el.textContent=msg;el.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>el.classList.remove("show"),1600);}
function unique(list){const out=[];for(const g of list){const n=String(g||"").trim();if(n&&!out.includes(n))out.push(n);}return out;}
function genreColor(name){if(GENRE_COLORS[name])return GENRE_COLORS[name];let h=0;for(const ch of name)h=(h*31+ch.charCodeAt(0))>>>0;return EXTRA[h%EXTRA.length];}
function escapeHtml(s){return String(s||"").replace(/[&<>"']/g,m=>({"&":"&","<":"<",">":">",'"':'"',"'":'&#39;'}[m]));}
function normalize(x){return{title:String(x.title||""),genre:String(x.genre||"その他").trim()||"その他",body:String(x.body||""),source:String(x.source||""),tags:Array.isArray(x.tags)?x.tags.filter(t=>["冒","単","参"].includes(t)):[],gen:x.gen&&typeof x.gen==="object"?x.gen:null};}
function load(){
  try{
    const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null");
    if(Array.isArray(parsed)) items=parsed.map(normalize);
    else if(parsed&&Array.isArray(parsed.items)){
      items=parsed.items.map(normalize);
      if(Array.isArray(parsed.genres)) genres=unique(parsed.genres.concat(DEFAULT_GENRES));
    }
  }catch(e){}
  genres=unique(genres.concat(items.map(x=>x.genre), DEFAULT_GENRES));
}
function save(){localStorage.setItem(STORAGE_KEY,JSON.stringify({items,genres}));}
function loraSummary(gen){
  if(!gen||!Array.isArray(gen.loras)) return "本文のみ";
  const on=gen.loras.filter(l=>l.enabled);
  return (gen.mode||"")+" / "+(gen.seconds||"?")+"s / LoRA "+(on.length?on.map(l=>(l.filename||l.id)+" "+Number(l.strength).toFixed(2)).join(", "):"なし");
}
function filtered(){
  const q=($("search").value||"").toLowerCase().replace(/\s+/g," ").trim();
  return items.map((it,i)=>({it,i})).filter(({it})=>{
    if(activeGenre!=="すべて"&&it.genre!==activeGenre) return false;
    if(!q) return true;
    return (it.title+" "+it.body).toLowerCase().includes(q);
  });
}
function moveItem(i, dir){
  const j=i+dir;
  if(j<0||j>=items.length) return;
  [items[i], items[j]]=[items[j], items[i]];
  save(); render();
}
function moveGenre(name, dir){
  const i=genres.indexOf(name);
  if(i<0) return;
  const j=i+dir;
  if(j<0||j>=genres.length) return;
  [genres[i], genres[j]]=[genres[j], genres[i]];
  save(); renderGenreManager(); render();
}
function renderFilters(){
  const used=["すべて", ...genres.filter(g=>items.some(it=>it.genre===g)||DEFAULT_GENRES.includes(g)||genres.includes(g))];
  const seen=unique(used);
  $("filters").innerHTML=seen.map(g=>{
    const on=activeGenre===g?"on":"";
    const color=g==="すべて"?"":genreColor(g);
    const style=g==="すべて"?"":(on?`background:${color};color:#fff`:`background:${color}22;color:${color}`);
    return `<button class="chip ${on}" data-genre="${escapeHtml(g)}" style="${style}">${escapeHtml(g)}</button>`;
  }).join("");
}
function render(){
  renderFilters();
  const rows=filtered();
  $("list").innerHTML=rows.length?rows.map(({it,i})=>`
    <article class="item" draggable="true" data-index="${i}">
      <div class="handle" title="ドラッグで並び替え">⋮⋮</div>
      <span class="dot" style="background:${genreColor(it.genre)}"></span>
      <div class="meta">
        <div class="title">${escapeHtml(it.title)}</div>
        <div class="sub"><span class="badge ${it.gen?"":"off"}">${it.gen?"設定あり":"本文のみ"}</span> ${(it.tags||[]).join(" ")} ${escapeHtml(loraSummary(it.gen))}</div>
      </div>
      <div class="actions">
        <button class="btn primary" data-h3="${i}">H3で使う</button>
        <button class="btn" data-copy="${i}">コピー</button>
        <button class="btn" data-edit="${i}">編集</button>
        <button class="btn" data-up="${i}">↑</button>
        <button class="btn" data-down="${i}">↓</button>
      </div>
    </article>`).join(""):'<p class="hint">なし。作成画面の「ライブラリへ」か、JSON読込で追加できます。</p>';
}
function fillGenres(selected){
  $("editGenre").innerHTML=genres.map(g=>`<option value="${escapeHtml(g)}">${escapeHtml(g)}</option>`).join("");
  $("editGenre").value=genres.includes(selected)?selected:"その他";
}
function openEdit(i){
  editIndex=i;
  const creating=i===-1;
  $("modalTitle").textContent=creating?"追加":"編集";
  $("editTitle").value=creating?"":items[i].title;
  $("editBody").value=creating?"":items[i].body;
  fillGenres(creating?"その他":items[i].genre);
  const tags=creating?[]:(items[i].tags||[]);
  $("tagBo").checked=tags.includes("冒");
  $("tagTan").checked=tags.includes("単");
  $("tagSan").checked=tags.includes("参");
  $("deleteBtn").style.display=creating?"none":"";
  $("modalBg").classList.add("open");
}
function sendToH3(it){
  localStorage.setItem(PENDING_KEY, JSON.stringify({title:it.title, body:it.body, prompt:it.body, gen:it.gen||null, ts:Date.now()}));
  location.href="index.html";
}
function deleteGenre(name){
  if(name==="その他"){toast("その他は削除できません");return;}
  const n=items.filter(it=>it.genre===name).length;
  if(!confirm("「"+name+"」を削除しますか？"+(n?"\n"+n+"件は「その他」へ移動します。":""))) return;
  items=items.map(it=>it.genre===name?{...it,genre:"その他"}:it);
  genres=genres.filter(g=>g!==name);
  if(!genres.includes("その他")) genres.push("その他");
  if(activeGenre===name) activeGenre="すべて";
  save(); renderGenreManager(); render(); toast("削除しました");
}
function renderGenreManager(){
  $("genreList").innerHTML=unique(genres.concat(items.map(x=>x.genre))).map(g=>{
    const n=items.filter(it=>it.genre===g).length;
    return `<div class="genre-row" draggable="true" data-genre-name="${escapeHtml(g)}">
      <div class="handle" title="ドラッグで並び替え">⋮⋮</div>
      <span class="dot" style="background:${genreColor(g)}"></span>
      <div class="name">${escapeHtml(g)}</div>
      <div class="hint" style="margin:0">${n}件</div>
      <button class="btn" data-genre-up="${escapeHtml(g)}">↑</button>
      <button class="btn" data-genre-down="${escapeHtml(g)}">↓</button>
      ${g==="その他"?"":`<button class="btn danger" data-del-genre="${escapeHtml(g)}">削除</button>`}
    </div>`;
  }).join("");
}

$("search").oninput=render;
$("filters").onclick=e=>{const c=e.target.closest("[data-genre]");if(!c)return;activeGenre=c.dataset.genre;render();};
$("list").onclick=async e=>{
  const h3=e.target.closest("[data-h3]");
  const copy=e.target.closest("[data-copy]");
  const edit=e.target.closest("[data-edit]");
  const up=e.target.closest("[data-up]");
  const down=e.target.closest("[data-down]");
  if(h3) sendToH3(items[Number(h3.dataset.h3)]);
  if(copy){try{await navigator.clipboard.writeText(items[Number(copy.dataset.copy)].body);}catch(err){} toast("コピーしました");}
  if(edit) openEdit(Number(edit.dataset.edit));
  if(up) moveItem(Number(up.dataset.up), -1);
  if(down) moveItem(Number(down.dataset.down), 1);
};
$("list").addEventListener("dragstart", e=>{
  const card=e.target.closest(".item");
  if(!card) return;
  dragItemFrom=Number(card.dataset.index);
  card.classList.add("dragging");
});
$("list").addEventListener("dragend", e=>{
  const card=e.target.closest(".item");
  if(card) card.classList.remove("dragging");
  dragItemFrom=null;
});
$("list").addEventListener("dragover", e=>{
  e.preventDefault();
  const card=e.target.closest(".item");
  if(!card || dragItemFrom==null) return;
  const to=Number(card.dataset.index);
  if(to===dragItemFrom) return;
  const moved=items.splice(dragItemFrom,1)[0];
  items.splice(to,0,moved);
  dragItemFrom=to;
  save();
  render();
});
$("addBtn").onclick=()=>openEdit(-1);
$("cancelBtn").onclick=()=>$("modalBg").classList.remove("open");
$("saveBtn").onclick=()=>{
  const title=$("editTitle").value.trim();
  if(!title){toast("タイトルを入力");return;}
  const tags=[];
  if($("tagBo").checked) tags.push("冒");
  if($("tagTan").checked) tags.push("単");
  if($("tagSan").checked) tags.push("参");
  const next={title, genre:$("editGenre").value, body:$("editBody").value, tags, source:editIndex>=0?(items[editIndex].source||""):"", gen:editIndex>=0?items[editIndex].gen:null};
  if(editIndex===-1) items.unshift(normalize(next));
  else items[editIndex]=normalize(next);
  save(); $("modalBg").classList.remove("open"); render(); toast("保存しました");
};
$("deleteBtn").onclick=()=>{
  if(editIndex==null||editIndex<0) return;
  if(!confirm("削除しますか？")) return;
  items.splice(editIndex,1); save(); $("modalBg").classList.remove("open"); render();
};
$("addGenreBtn").onclick=()=>{
  const name=$("newGenre").value.trim();
  if(!name) return;
  if(!genres.includes(name)) genres.push(name);
  fillGenres(name); $("newGenre").value=""; save(); render();
};
$("deleteGenreBtn").onclick=()=>deleteGenre($("editGenre").value);
$("genreBtn").onclick=()=>{renderGenreManager();$("genreBg").classList.add("open");};
$("genreClose").onclick=()=>$("genreBg").classList.remove("open");
$("genreList").onclick=e=>{
  const del=e.target.closest("[data-del-genre]");
  const up=e.target.closest("[data-genre-up]");
  const down=e.target.closest("[data-genre-down]");
  if(del) deleteGenre(del.dataset.delGenre);
  if(up) moveGenre(up.dataset.genreUp, -1);
  if(down) moveGenre(down.dataset.genreDown, 1);
};
$("genreList").addEventListener("dragstart", e=>{
  const row=e.target.closest(".genre-row");
  if(!row) return;
  dragGenreFrom=row.dataset.genreName;
  row.classList.add("dragging");
});
$("genreList").addEventListener("dragend", e=>{
  const row=e.target.closest(".genre-row");
  if(row) row.classList.remove("dragging");
  dragGenreFrom=null;
});
$("genreList").addEventListener("dragover", e=>{
  e.preventDefault();
  const row=e.target.closest(".genre-row");
  if(!row || !dragGenreFrom) return;
  const toName=row.dataset.genreName;
  if(toName===dragGenreFrom) return;
  const from=genres.indexOf(dragGenreFrom);
  const to=genres.indexOf(toName);
  if(from<0||to<0) return;
  const moved=genres.splice(from,1)[0];
  genres.splice(to,0,moved);
  dragGenreFrom=toName;
  save();
  renderGenreManager();
  render();
});
$("exportBtn").onclick=()=>{
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([JSON.stringify({items,genres},null,2)],{type:"application/json"}));
  a.download="prompt-library.json"; a.click();
};
$("importBtn").onclick=()=>$("fileInput").click();
$("fileInput").onchange=async e=>{
  const file=e.target.files[0]; if(!file) return;
  try{
    const parsed=JSON.parse(await file.text());
    if(Array.isArray(parsed)) items=parsed.map(normalize);
    else if(parsed&&Array.isArray(parsed.items)){
      items=parsed.items.map(normalize);
      if(Array.isArray(parsed.genres)) genres=unique(parsed.genres.concat(DEFAULT_GENRES));
    }else throw new Error("bad");
    genres=unique(genres.concat(items.map(x=>x.genre),DEFAULT_GENRES));
    save(); render(); toast("読み込みました");
  }catch(err){toast("JSONが違います");}
  e.target.value="";
};
load(); render();
