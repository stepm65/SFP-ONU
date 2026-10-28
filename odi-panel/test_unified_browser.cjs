// Test actual computed styles in the offline preview or the built firmware web tree.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const startBrowser=require('./browser_driver.cjs'),p=__dirname;
const build=process.argv[2]&&path.resolve(process.argv[2]),version=fs.readFileSync(p+'/VERSION','utf8').trim();
const routes=JSON.parse(fs.readFileSync(p+'/native-pages.json')),en=JSON.parse(fs.readFileSync(p+'/native-en.json'));
const files=new Map(),requests=[],checks=[],output=path.resolve(p,'../../browser-unified');
if(build){
 const raw=fs.readFileSync(build+'/verified.pseudo'),marker=Buffer.from('#\n# START OF DATA - DO NOT MODIFY\n#\n'),at=raw.indexOf(marker),blob=raw.subarray(at+marker.length);
 for(const line of raw.subarray(0,at).toString().split('\n')){const a=line.split(/\s+/);if(a[1]==='R'&&a[0].startsWith('home/httpd/web/'))files.set('/'+a[0].slice(15),blob.subarray(+a[7],+a[7]+ +a[6]));}
}
function renderASP(raw){return raw.toString().replace(/<%\s*multilang\("(\d+)"\s*"[^"\n]+"\);\s*%>/g,(_,n)=>en[+n]||'').replace(/<%[\s\S]*?%>/g,'0').replace(/<script\b(?![^>]*\bsrc\s*=)[^>]*>[\s\S]*?<\/script\s*>/gi,'').replace(/\bonload\s*=\s*"[^"]*"/gi,'');}
function renderScript(raw){return raw.toString().replace(/<%\s*multilang\("(\d+)"\s*"[^"\n]+"\);\s*%>/g,(_,n)=>JSON.stringify(en[+n]||'').slice(1,-1).replaceAll("'","\\'")).replace(/<%[\s\S]*?%>/g,'0');}
const server=http.createServer((req,res)=>{
 requests.push(req.method+' '+req.url);if(req.method!=='GET'){res.writeHead(405);return res.end('Read-only browser test');}
 const url=new URL(req.url,'http://localhost'),name=url.pathname;let data,type;
 if(name==='/login-preview.html')data=fs.readFileSync(p+'/login-preview.html');
 else if(!build)data=fs.readFileSync(p+'/preview.html');
 else if(name==='/code.asp')data=routes.map(route=>'<a target="view" href="/'+route+'">Form</a>').join('');
 else if(name==='/panel/api.cgi'){type='text/plain';data=Object.entries({ok:'1',csrf:'fixture',panel_version:version,sw_active:'0',sw_commit:'0'}).map(([k,v])=>k+'='+Buffer.from(v).toString('hex')).join('\n');}
 else data=files.get(name==='/'?'/index.html':name);
 if(data===undefined){res.writeHead(404);return res.end('Missing fixture');}
 if(name.endsWith('.asp'))data=renderASP(data);
 else if(name.endsWith('.js')&&data.toString().includes('<%'))data=renderScript(data);
 res.setHeader('Content-Type',type||(name.endsWith('.css')?'text/css':name.endsWith('.js')?'application/javascript':'text/html; charset=utf-8'));res.end(data);
});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port,b=await startBrowser(output);
 const {call,evaluate}=b;
 async function settle(){await wait(100);if(build)await evaluate('pauseLive()');}
 async function frameReady(){for(let i=0;i<40;i++){if(await evaluate(`(()=>{const d=document.querySelector('.native-frame')?.contentDocument;return !!d?.querySelector('.native-table,.maintenance-card')&&d.body.classList.contains('embedded');})()`)){await wait(80);return;}await wait(50);}throw Error('Native frame did not become ready');}
 async function capture(name){const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(output,(build?'built-':'preview-')+name+'.png'),Buffer.from(shot.data,'base64'));}
 function measure(doc){
  const w=doc.defaultView,visible=e=>!!e.getClientRects().length&&w.getComputedStyle(e).visibility!=='hidden';
  const tiny=[];const walker=doc.createTreeWalker(doc.body,4);let n;
  while(n=walker.nextNode()){const e=n.parentElement;if(!e||!n.nodeValue.trim()||e.closest('script,style,svg,option')||!visible(e))continue;const size=parseFloat(w.getComputedStyle(e).fontSize);if(size<12)tiny.push({tag:e.tagName,class:e.className,size,text:n.nodeValue.slice(0,35)});}
  return {font:w.getComputedStyle(doc.body).fontSize,family:w.getComputedStyle(doc.body).fontFamily,overflow:doc.documentElement.scrollWidth>w.innerWidth,tiny};
 }
 try{
  await call('Page.navigate',{url:origin+'/#profiles'});await wait(600);
  if(build){await evaluate('pauseLive();state={...demo,...state};render();');await settle();}
  for(const width of [390,1440]){
   await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});
   for(const language of ['ru','en'])for(const rail of ['diagnostic']){
    await evaluate(`ODILang.set('${language}');`);
    for(const tab of ['overview','identity','vlan','link','mods','firmware','diagnostics','profiles','native-backup','native-password']){
     await evaluate(`dirty=false;location.hash='#${tab}'`);await settle();
     const m=await evaluate('('+measure.toString()+')(document)');assert(!m.overflow,`${width} ${language} ${rail} ${tab} shell overflow`);assert.deepEqual(m.tiny,[],`${width} ${language} ${rail} ${tab} small text: ${JSON.stringify(m.tiny)}`);
     assert(await evaluate(`Array.from(document.querySelectorAll('.card-head h2')).every(e=>getComputedStyle(e).fontSize==='16px')`),tab+' card heading');
     if(tab==='native-backup'){
      await frameReady();
      assert(await evaluate(`document.querySelector('.maintenance-frame').getBoundingClientRect().height>400`),'maintenance visible at first open');
      const native=await evaluate('('+measure.toString()+')(document.querySelector(".maintenance-frame").contentDocument)');assert.equal(native.font,m.font);assert.equal(native.family,m.family);assert.deepEqual(native.tiny,[]);assert(!native.overflow,'maintenance overflow');
      const sizes=await evaluate(`(()=>{const d=document.querySelector('.maintenance-frame').contentDocument;return [...d.querySelectorAll('button,input:not([type=hidden]):not([type=radio]),select')].filter(e=>e.getClientRects().length).map(e=>d.defaultView.getComputedStyle(e).fontSize)})()`);assert(sizes.every(s=>s==='14px'),JSON.stringify(sizes));
      if(language==='ru'&&rail==='diagnostic')await capture('profiles-'+width);
     }
     checks.push({width,language,rail,tab});
    }
   }
   // Every embedded factory template, including the forms not exposed by this OEM menu.
   for(const route of routes){
    await evaluate(`dirty=false;document.getElementById('main').innerHTML=nativeEmbed(${JSON.stringify('/'+route)},'Factory form');sizeNativeFrames()`);await frameReady();
    const m=await evaluate('('+measure.toString()+')(document.querySelector(".native-frame").contentDocument)');assert.equal(m.font,'14px',route);assert.deepEqual(m.tiny,[],route+' small text');assert(!m.overflow,route+' frame overflow');
    const fonts=await evaluate(`(()=>{const d=document.querySelector('.native-frame').contentDocument;return [...d.querySelectorAll('.native-table:not(.native-note) td,.native-table:not(.native-note) th')].filter(e=>e.getClientRects().length).map(e=>d.defaultView.getComputedStyle(e).fontSize)})()`);assert(fonts.every(s=>['14px','16px'].includes(s)),route+' inconsistent table scale: '+[...new Set(fonts)]);
    const sectionColors=await evaluate(`(()=>{const d=document.querySelector('.native-frame').contentDocument;return [...d.querySelectorAll('.native-section font')].map(e=>d.defaultView.getComputedStyle(e).color)})()`);assert(sectionColors.every(c=>c==='rgb(23, 39, 55)'),route+' unreadable section labels: '+sectionColors);
    const first=await evaluate(`document.querySelector('.native-frame').clientHeight`);await wait(130);assert.equal(await evaluate(`document.querySelector('.native-frame').clientHeight`),first,route+' unstable frame height');
    checks.push({width,route,font:m.font});if(['status.asp','tcpiplan.asp','saveconf.asp'].includes(route))await capture(route.replaceAll('/','_')+'-'+width);
   }
   await call('Page.navigate',{url:origin+'/login-preview.html'});await wait(150);
   const login=await evaluate('('+measure.toString()+')(document)');assert.equal(login.font,'14px');assert.deepEqual(login.tiny,[]);assert(!login.overflow,'login overflow');await capture('login-'+width);
   if(width===390){await call('Page.navigate',{url:origin+'/#profiles'});await wait(300);if(build){await evaluate('state={...demo,...state};render();');await settle();}}
  }
  assert.deepEqual(b.errors,[],JSON.stringify(b.errors.slice(0,5)));assert(requests.every(r=>r.startsWith('GET ')));
  const report={result:'passed',version,scope:build?'Chromium on extracted firmware web assets; synthetic ASP values, factory inline initializers disabled, no form submissions or physical ONU':'Chromium offline preview; no device access',checks,requestsOnlyGET:true,scriptErrors:b.errors};
  fs.writeFileSync(p+'/'+(build?'unified-browser':'unified-preview')+'-test-report.json',JSON.stringify(report,null,2));console.log('Unified style:',checks.length,'browser checks passed; build=',!!build);
 }finally{b.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
