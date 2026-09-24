const express = require("express");
const path = require("path");

const app = express();
app.use(express.json({limit:"32kb"}));

/*
  Add your APIs here.
  url can contain {uid}, {pass}, {region}, etc.
  The browser never calls the target API directly; this server does it,
  so browser CORS restrictions do not block the console.
*/
const APIS = [
  {
    id: "jwt",
    name: "jwt api",
    method: "GET",
    description: "JWT generation API",
    url: "https://jwt-gen-rho.vercel.app/token?uid={uid}&password={pass}",
    params: [
      {name:"uid", label:"uid", in:"query", required:true, placeholder:"Enter UID"},
      {name:"pass", label:"password", in:"query", required:true, placeholder:"Enter password"}
    ]
  }
  // Example:
  // {
  //   id:"ban-check", name:"Ban check api", method:"GET",
  //   url:"https://example.com/check?uid={uid}&region={region}",
  //   params:[
  //     {name:"uid",label:"uid",in:"query",required:true},
  //     {name:"region",label:"region",in:"query",required:false}
  //   ]
  // }
];

app.get("/api/config", (req,res)=>res.json(APIS));

app.post("/api/test/:id", async (req,res)=>{
  const api=APIS.find(x=>x.id===req.params.id);
  if(!api) return res.status(404).json({error:"API not found"});

  let target=api.url;
  for(const p of (api.params||[])){
    const value=String(req.body?.[p.name] ?? "");
    target=target.split("{"+p.name+"}").join(encodeURIComponent(value));
  }

  try{
    const upstream=await fetch(target,{method:api.method||"GET",redirect:"follow"});
    const text=await upstream.text();
    res.status(upstream.status);
    res.set("Content-Type", upstream.headers.get("content-type") || "application/json; charset=utf-8");
    res.send(text);
  }catch(err){
    res.status(502).json({error:err.message});
  }
});

app.use(express.static(path.join(__dirname,"public")));
app.get("*",(req,res)=>res.sendFile(path.join(__dirname,"public","index.html")));

const PORT=process.env.PORT||3000;
app.listen(PORT,()=>console.log(`Bhuwan APIs UI running on port ${PORT}`));
