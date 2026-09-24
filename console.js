
(() => {
  "use strict";
  const STORAGE_KEY = "bhuwan_apis_config_v1";
  const DEFAULT_APIS = [
    {id:"info",name:"info api",description:"No description provided.",method:"GET",url:"https://info.bhuwanhex.bond/info?uid={uid}",params:[{name:"uid",type:"text",required:true}]},
    {id:"jwt",name:"jwt api",description:"No description provided.",method:"GET",url:"http://mp.mahihost.uk:9011/token?uid={uid}&password={password}",params:[{name:"uid",type:"text",required:true},{name:"password",type:"password",required:true}]},
    {id:"level",name:"Level info api",description:"No description provided.",method:"GET",url:"https://level-info-api-three.vercel.app/api/level-info?uid={uid}&region={region}",params:[{name:"uid",type:"text",required:true},{name:"region",type:"text",required:false,default:"ind"}]},
    {id:"ban",name:"Ban check api",description:"No description provided.",method:"GET",url:"https://ban.bhuwanhex.bond/check?uid={uid}",params:[{name:"uid",type:"text",required:true},{name:"region",type:"text",required:false,default:"ind"}]},
    {id:"outfit",name:"Outfit api",description:"No description provided.",method:"GET",url:"http://mp.mahihost.uk:9004/outfit-image?uid={uid}&key=bhuwan",params:[{name:"uid",type:"text",required:true}]}
  ];
  const apis = (() => { try { const x=JSON.parse(localStorage.getItem(STORAGE_KEY)); return Array.isArray(x)?x:DEFAULT_APIS; } catch{return DEFAULT_APIS;} })();
  const esc = s => String(s ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const paramsFromUrl = url => {
    const found = [...String(url).matchAll(/\{([^}]+)\}/g)].map(m=>m[1]);
    return [...new Set(found)];
  };
  const id = new URLSearchParams(location.search).get("id");
  const api = apis.find(a=>a.id===id) || apis[0];

  function render() {
    if (!api) {
      document.querySelector("#root").innerHTML=`<div class="doodle-wrap"><div class="doodle-card"><div class="empty-state">No API configured.</div></div></div>`;
      return;
    }
    const params = (api.params && api.params.length) ? api.params : paramsFromUrl(api.url).map(name=>({name,type:"text",required:true}));
    document.querySelector("#root").innerHTML = `
      <div class="doodle-wrap">
        <div class="doodle-card">
          <div class="tape-strip">★ TEST CONSOLE ★</div>
          <div class="meta-row">
            <a class="btn btn-blue" href="index.html">← Back to all APIs</a>
            <span class="badge badge-${String(api.method).toLowerCase()}">${esc(api.method)}</span>
          </div>

          <div style="margin:22px 0 10px">
            <div class="hero-title" style="text-align:left">${esc(api.name)}</div>
            <div class="card-desc" style="margin-top:8px">${esc(api.description || "No description provided.")}</div>
          </div>

          <div class="code-box" style="margin:20px 0">${esc(api.url)}</div>

          <div class="doodle-card test-console" style="margin:0">
            <div class="card-title" style="margin-bottom:16px">Test Parameters</div>
            <form id="testForm">
              ${params.map(p=>`
                <div class="form-group">
                  <label>${esc(p.name)} ${p.required ? '<span style="color:#ef4444">*</span>' : ''} <span style="color:#64748b;font-size:.9rem">(query)</span></label>
                  <input type="${p.type==="password"?"password":"text"}" name="${esc(p.name)}" ${p.required?"required":""} value="${esc(p.default||"")}" placeholder="${p.required?"":"Optional"}" autocomplete="off">
                </div>`).join("")}
              <button class="btn btn-primary" id="sendBtn" type="submit" style="width:100%">SEND REQUEST</button>
            </form>
          </div>

          <div id="responseArea"></div>

          <div class="console" id="console">
            <div class="log-line info">Ready. Click "Send Request" to test endpoint.</div>
          </div>
        </div>
      </div>`;

    document.querySelector("#testForm").addEventListener("submit", sendRequest);
  }

  const log = (text, cls="info") => {
    const box=document.querySelector("#console");
    const row=document.createElement("div");
    row.className="log-line "+cls;
    row.textContent=text;
    box.appendChild(row);
    box.scrollTop=box.scrollHeight;
  };

  function makeUrl(values) {
    let url = api.url;
    for (const [key,val] of Object.entries(values)) {
      url = url.replaceAll(`{${key}}`, encodeURIComponent(val ?? ""));
    }
    return url;
  }

  async function sendRequest(e) {
    e.preventDefault();
    const btn=document.querySelector("#sendBtn");
    const form=new FormData(e.currentTarget);
    const values={};
    for (const [k,v] of form.entries()) values[k]=v;

    btn.disabled=true;
    btn.innerHTML='<span class="spinner"></span> Executing Request...';
    document.querySelector("#responseArea").innerHTML="";
    log("Dispatching "+api.method+" request to endpoint...");

    try {
      let url=makeUrl(values);
      let options={method:api.method,headers:{"Accept":"application/json, text/plain, */*"}};

      if (api.method !== "GET" && api.method !== "HEAD") {
        options.headers["Content-Type"]="application/json";
        const body={...values};
        options.body=JSON.stringify(body);
      }

      const started=Date.now();
      const response=await fetch(url,options);
      const elapsed=Date.now()-started;
      const text=await response.text();
      let display=text;
      try { display=JSON.stringify(JSON.parse(text),null,2); } catch {}
      log(`Status: ${response.status} - Response received! (${elapsed} ms)`, response.ok?"success":"error");

      document.querySelector("#responseArea").innerHTML=`
        <div class="doodle-card response-box" style="margin:16px 0 0">
          <div class="meta-row">
            <div class="card-title">Server Response</div>
            <span class="badge ${response.ok?'badge-get':'badge-delete'}">STATUS ${response.status}</span>
          </div>
          <pre class="code-box">${esc(display)}</pre>
        </div>`;
    } catch(err) {
      log("Request failed: "+err.message,"error");
      document.querySelector("#responseArea").innerHTML=`
        <div class="doodle-card response-box" style="margin:16px 0 0">
          <div class="card-title danger-text">Request Error</div>
          <div class="code-box" style="margin-top:12px">${esc(err.message)}\n\nIf this is a browser CORS error, the target API must allow your site's origin, or you need a same-origin server-side proxy.</div>
        </div>`;
    } finally {
      btn.disabled=false;
      btn.textContent="SEND REQUEST";
    }
  }

  render();
})();
