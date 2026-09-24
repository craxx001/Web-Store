
(() => {
  "use strict";

  const DEFAULT_APIS = [
    {
      id:"info",
      name:"info api",
      description:"No description provided.",
      method:"GET",
      url:"https://info.bhuwanhex.bond/info?uid={uid}",
      params:[{name:"uid",type:"text",required:true}]
    },
    {
      id:"jwt",
      name:"jwt api",
      description:"No description provided.",
      method:"GET",
      url:"http://mp.mahi host.uk:9011/token?uid={uid}&password={password}".replace("mahi host","mahihost"),
      params:[
        {name:"uid",type:"text",required:true},
        {name:"password",type:"password",required:true}
      ]
    },
    {
      id:"level",
      name:"Level info api",
      description:"No description provided.",
      method:"GET",
      url:"https://level-info-api-three.vercel.app/api/level-info?uid={uid}&region={region}",
      params:[
        {name:"uid",type:"text",required:true},
        {name:"region",type:"text",required:false,default:"ind"}
      ]
    },
    {
      id:"ban",
      name:"Ban check api",
      description:"No description provided.",
      method:"GET",
      url:"https://ban.bhuwanhex.bond/check?uid={uid}",
      params:[{name:"uid",type:"text",required:true},{name:"region",type:"text",required:false,default:"ind"}]
    },
    {
      id:"outfit",
      name:"Outfit api",
      description:"No description provided.",
      method:"GET",
      url:"http://mp.mahihost.uk:9004/outfit-image?uid={uid}&key=bhuwan",
      params:[{name:"uid",type:"text",required:true}]
    }
  ];

  const STORAGE_KEY = "bhuwan_apis_config_v1";
  const getApis = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return DEFAULT_APIS;
      const parsed = JSON.parse(saved);
      return Array.isArray(parsed) ? parsed : DEFAULT_APIS;
    } catch { return DEFAULT_APIS; }
  };

  const escapeHtml = s => String(s ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[c]));

  const pretty = value => {
    if (typeof value === "string") {
      try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
    }
    try { return JSON.stringify(value, null, 2); } catch { return String(value); }
  };

  const apiCount = getApis().length;

  function renderHome() {
    const apis = getApis();
    document.title = "NRZ APIS";
    document.querySelector("#root").innerHTML = `
      <div class="doodle-wrap">
        <div class="doodle-card">
          <div class="tape-strip">★ NRZRAVI APIS ★</div>

          <div class="doodle-nav">
            <a class="brand-link" href="index.html">
              <div class="brand-avatar">★</div>
              <div class="brand-info-text">
                <div class="brand-title">NRZRAVI APIS</div>
                <div class="brand-tagline">Test and manage APIs with raw power.</div>
              </div>
            </a>
            <div class="status-badge"><span class="live-dot"></span>Online</div>
          </div>

          <div class="doodle-hero">
            <div class="hero-title"><span class="marker-highlight">API DIRECTORY</span></div>
            <div class="hero-ribbon">
              <div class="ribbon-pill">Total APIs: <b>${apis.length}</b></div>
              <div class="ribbon-pill">Status: <b>Operational</b></div>
            </div>
          </div>

          <div class="search-box-wrap">
            <span style="font-size:1.2rem;position:absolute;left:14px;z-index:1">🔍</span>
            <input id="search" class="doodle-search-input" style="padding-left:44px" placeholder="Search endpoints, names, methods or descr" autocomplete="off">
          </div>

          <div id="api-grid" class="grid"></div>

          <div class="doodle-footer">
            <div class="social-row">
              <a class="btn btn-blue btn-sm" href="#" onclick="return false">☁ Discord</a>
              <a class="btn btn-primary btn-sm" href="#" onclick="return false">◉ GitHub</a>
              <a class="btn btn-danger btn-sm" href="#" onclick="return false">▶ YouTube</a>
            </div>
            <div style="color:var(--ink-muted);font-weight:700">Made with ❤️ by @nrzravi</div>
          </div>
        </div>
      </div>`;

    const grid = document.querySelector("#api-grid");
    const draw = () => {
      const q = (document.querySelector("#search").value || "").toLowerCase().trim();
      const filtered = apis.filter(a => `${a.name} ${a.description} ${a.method} ${a.url}`.toLowerCase().includes(q));
      grid.innerHTML = filtered.length ? filtered.map(apiCard).join("") :
        `<div class="card empty-state" style="grid-column:1/-1">No APIs found.</div>`;
    };
    document.querySelector("#search").addEventListener("input", draw);
    draw();
  }

  function apiCard(api) {
    return `
      <div class="card api-card">
        <div>
          <div class="card-top">
            <div class="card-title">${escapeHtml(api.name)}</div>
            <span class="badge badge-${String(api.method).toLowerCase()}">${escapeHtml(api.method)}</span>
          </div>
          <div class="url-display" style="margin-top:10px">${escapeHtml(api.url)}</div>
          <div class="card-desc" style="margin-top:8px">${escapeHtml(api.description || "No description provided for this endpoint.")}</div>
        </div>
        <div class="api-actions">
          <a class="btn btn-primary" href="console.html?id=${encodeURIComponent(api.id)}">Test API</a>
        </div>
      </div>`;
  }

  renderHome();
})();
