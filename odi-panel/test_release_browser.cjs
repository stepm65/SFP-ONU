// Browser checks and current documentation screenshots; all device requests are local fixtures.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const startBrowser=require('./browser_driver.cjs'),p=__dirname;
const wait=ms=>new Promise(r=>setTimeout(r,ms)),requests=[];let loggedOut=false;
const server=http.createServer((req,res)=>{
 requests.push(req.method+' '+req.url);
 if(req.method==='POST'){
  if(req.url!=='/boaform/admin/formLogout'){res.writeHead(405);return res.end();}
  let body='';req.on('data',b=>body+=b);req.on('end',()=>{const params=new URLSearchParams(body);assert.equal(params.get('save'),'Logout');assert.equal(params.get('submit-url'),'/');loggedOut=true;res.end('OK: logout successfully!');});return;
 }
 if(req.url.startsWith('/panel/api.cgi')){res.writeHead(loggedOut?403:200,{'Content-Type':'text/plain'});return res.end(loggedOut?'Authentication required':'ok=31\n');}
 res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(p+(loggedOut||req.url.startsWith('/login-preview.html')?'/login-preview.html':'/preview.html'),'utf8').replace('const preview =','let preview ='));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const b=await startBrowser(path.resolve(p,'../../browser-release')), {call,evaluate}=b,checks=[];
 const shots=path.resolve(p,'../docs/screenshots');
 try{
  await call('Page.navigate',{url:origin+'/#overview'});await wait(500);
  for(const lang of ['ru','en']){
   fs.mkdirSync(path.join(shots,lang),{recursive:true});
   for(const width of [390,768,1440]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
    await evaluate(`ODILang.set('${lang}')`);
    for(const tab of ['overview','identity','profiles','native-backup','firmware','diagnostics','native-password']){
     await evaluate(`dirty=false;location.hash='#${tab}';scrollTo(0,0)`);await wait(160);
     assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),`${lang} ${width} ${tab}: overflow`);
     assert(await evaluate("getComputedStyle(document.getElementById('diagnostic-rail')).display!=='none'"));
     assert.equal(await evaluate("document.querySelectorAll('#diagnostic-toggle,select#language').length"),0);
     if(tab==='profiles')assert.equal(await evaluate("document.querySelectorAll('#main iframe').length"),0);
     if(tab==='native-backup')assert(await evaluate("!!document.querySelector('#main .maintenance-frame')"));
     if(width===1440||width===390&&tab==='overview'){
      const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(shots,lang,(width===390?'mobile':tab)+'.png'),Buffer.from(shot.data,'base64'));
     }
     checks.push({lang,width,tab});
    }
   }
   await call('Page.navigate',{url:origin+'/login-preview.html'});await wait(200);await evaluate(`document.querySelector('[data-language=${lang}]').click()`);
   const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(shots,lang,'login.png'),Buffer.from(shot.data,'base64'));
   await call('Page.navigate',{url:origin+'/#overview'});await wait(400);
  }
  // Exercise real click, POST, root sign-in probe and root navigation in Chromium.
  await evaluate('preview=false;pauseLive();dirty=false;');await evaluate("document.getElementById('logout').click()");
  for(let i=0;i<50;i++){if(await evaluate("!!document.querySelector('form[name=cmlogin]')"))break;await wait(100);}
  assert(loggedOut);assert(await evaluate("!!document.querySelector('form[name=cmlogin]')"));assert.equal(await evaluate('location.pathname'),'/');assert(!requests.some(r=>r.includes('/admin/logout.asp')));assert.deepEqual(b.errors,[]);
  fs.writeFileSync(p+'/release-browser-test-report.json',JSON.stringify({result:'passed',scope:'Chromium preview and local factory logout fixture; no physical device',checks,logout:'POST, session verification and root sign-in navigation',scriptErrors:b.errors},null,2));console.log('Release browser: 42 responsive/language checks and logout navigation passed');
 }finally{await b.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
