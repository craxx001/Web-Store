
(() => {
  "use strict";
  const KEY="bhuwan_apis_config_v1";
  const DEFAULT=[
    {id:"info",name:"info api",description:"No description provided.",method:"GET",url:"https://info.bhuwanhex.bond/info?uid={uid}",params:[{name:"uid",type:"text",required:true}]},
    {id:"jwt",name:"jwt api",description:"No description provided.",method:"GET",url:"http://mp.mahihost.uk:9011/token?uid={uid}&password={password}",params:[{name:"uid",type:"text",required:true},{name:"password",type:"password",required:true}]},
    {id:"level",name:"Level info api",description:"No description provided.",method:"GET",url:"https://level-info-api-three.vercel.app/api/level-info?uid={uid}&region={region}",params:[{name:"uid",type:"text",required:true},{name:"region",type:"text",required:false,default:"ind"}]},
    {id:"ban",name:"Ban check api",description:"No description provided.",method:"GET",url:"https://ban.bhuwanhex.bond/check?uid={uid}",params:[{name:"uid",type:"text",required:true},{name:"region",type:"text",required:false,default:"ind"}]},
    {id:"outfit",name:"Outfit api",description:"No description provided.",method:"GET",url:"http://mp.mahihost.uk:9004/outfit-image?uid={uid}&key=bhuwan",params:[{name:"uid",type:"text",required:true}]}
  ];
  let apis=(()=>{try{const x=JSON.parse(localStorage.getItem(KEY));return Array.isArray(x)?x:DEFAULT}catch{return DEFAULT}})();
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const save=()=>localStorage.setItem(KEY,JSON.stringify(apis,null,2));
  const render=()=>{
    document.querySelector("#root").innerHTML=`
    <div class="doodle-wrap"><div class="doodle-card">
      <div class="tape-strip">★ API MANAGER ★</div>
      <div class="meta-row">
        <a class="btn btn-blue" href="index.html">← Back to APIs</a>
        <button class="btn btn-primary" id="new">＋ Add API</button>
      </div>
      <div class="hero-title" style="margin:20px 0 8px">Editable API Directory</div>
      <div class="card-desc">Add, edit or remove endpoints. Changes are saved in this browser's local storage.</div>
      <div id="list" class="grid"></div>
    </div></div>`;
    const list=document.querySelector("#list");
    list.innerHTML=apis.map(a=>`
      <div class="card">
        <div class="card-top"><div class="card-title">${esc(a.name)}</div><span class="badge badge-${String(a.method).toLowerCase()}">${esc(a.method)}</span></div>
        <div class="url-display">${esc(a.url)}</div>
        <div class="api-actions">
          <button class="btn btn-primary" data-edit="${esc(a.id)}">Edit</button>
          <a class="btn btn-blue" href="console.html?id=${encodeURIComponent(a.id)}">Test</a>
          <button class="btn btn-danger" data-del="${esc(a.id)}">Delete</button>
        </div>
      </div>`).join("") || `<div class="empty-state">No APIs configured.</div>`;
    document.querySelector("#new").onclick=()=>openEditor(null);
    list.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>openEditor(apis.find(a=>a.id===b.dataset.edit)));
    list.querySelectorAll("[data-del]").forEach(b=>b.onclick=()=>{
      if(confirm("Delete this API?")){apis=apis.filter(a=>a.id!==b.dataset.del);save();render();}
    });
  };
  function openEditor(api){
    const isNew=!api;
    const a=api||{id:"api-"+Date.now(),name:"New API",description:"No description provided.",method:"GET",url:"https://example.com/api?uid={uid}",params:[{name:"uid",type:"text",required:true}]};
    const overlay=document.createElement("div");
    overlay.style.cssText="position:fixed;inset:0;background:#0f172acc;z-index:1000;padding:20px;overflow:auto;display:flex;justify-content:center;align-items:flex-start";
    overlay.innerHTML=`
      <div class="doodle-card" style="max-width:900px;width:100%;margin-top:30px">
        <div class="tape-strip">★ EDIT API ★</div>
        <form id="editor">
          <div class="editor-grid">
            <div class="form-group"><label>Name</label><input name="name" required value="${esc(a.name)}"></div>
            <div class="form-group"><label>Method</label><select name="method"><option ${a.method==="GET"?"selected":""}>GET</option><option ${a.method==="POST"?"selected":""}>POST</option><option ${a.method==="PUT"?"selected":""}>PUT</option><option ${a.method==="PATCH"?"selected":""}>PATCH</option><option ${a.method==="DELETE"?"selected":""}>DELETE</option></select></div>
            <div class="form-group full"><label>Endpoint URL / template</label><input name="url" required value="${esc(a.url)}"><div class="small-note">Use placeholders such as {uid}, {password}, {region}. They become input fields in the Test Console.</div></div>
            <div class="form-group full"><label>Description</label><textarea name="description">${esc(a.description||"")}</textarea></div>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap;margin-top:10px">
            <button type="button" class="btn btn-blue" id="cancel">Cancel</button>
            <button class="btn btn-primary" type="submit">Save API</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector("#cancel").onclick=()=>overlay.remove();
    overlay.querySelector("#editor").onsubmit=e=>{
      e.preventDefault();
      const f=new FormData(e.currentTarget);
      const updated={...a,name:f.get("name"),method:f.get("method"),url:f.get("url"),description:f.get("description")};
      const names=[...updated.url.matchAll(/\{([^}]+)\}/g)].map(m=>m[1]);
      updated.params=[...new Set(names)].map(n=>({name:n,type:/pass|token|secret/i.test(n)?"password":"text",required:true}));
      if(isNew) apis.push(updated); else apis=apis.map(x=>x.id===updated.id?updated:x);
      save(); overlay.remove(); render();
    };
  }
  render();
})();
