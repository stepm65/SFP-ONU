// Chromium check on the self-contained preview; no device API requests.
const fs=require('fs'),http=require('http'),path=require('path'),cp=require('child_process'),assert=require('assert');
const p=__dirname,out=path.resolve(p,'../../browser-profiles');fs.mkdirSync(out,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(p+'/preview.html'));});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const profile=path.join(out,'browser-'+Date.now()),exe=process.env.CHROME_BIN||path.resolve(p,'../../browser-cache/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe');
 const browser=cp.spawn(exe,['--headless','--no-sandbox','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});let ws;
 try{
  const endpoint=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(Error('Browser startup timeout')),15000);browser.stderr.on('data',chunk=>{buf+=chunk;const m=buf.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1]);}});browser.on('error',reject);});
  const httpOrigin=endpoint.replace('ws://','http://').split('/devtools/')[0];const targets=await(await fetch(httpOrigin+'/json/list')).json();
  ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r));
  let id=0;const pending=new Map(),errors=[];ws.addEventListener('message',e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)?.(d);pending.delete(d.id);}if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.text);});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,t=setTimeout(()=>reject(Error('CDP timeout '+method)),12000);pending.set(n,d=>{clearTimeout(t);d.error?reject(Error(d.error.message)):resolve(d.result);});ws.send(JSON.stringify({id:n,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await call('Runtime.enable');await call('Page.enable');await call('Page.navigate',{url:'http://127.0.0.1:'+server.address().port+'/#profiles'});await wait(600);
  const checks=[];
  for(const width of [390,1440]){
   await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
   for(const language of ['ru','en'])for(const layout of ['diagnostic']){
    await evaluate(`ODILang.set('${language}');`);await wait(80);
    assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'page overflow '+width+' '+language+' '+layout);
    await evaluate("document.querySelector('[data-profile-preset=huawei]').click()");await wait(100);
    assert(await evaluate('document.querySelectorAll("[data-profile-key]").length===1'));
    await evaluate(`openProfile(parseProfile(JSON.stringify({format:'odi-profile-v1',name:'Example profile',settings:{GPON_SN:'TEST12345678',OMCI_TM_OPT:'0',OUI:'AABBCC',LAN_SPEED_MODE:'4'},mods:{MOD_SPEED:'1'}})))`);
    assert(await evaluate('document.querySelectorAll(".profile-group").length===4'));
    assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'comparison overflow');
    checks.push({width,language,layout});
    await evaluate("document.querySelector('#close-profile').click();scrollTo(0,0)");
    await evaluate("location.hash='diagnostics'");await wait(100);
    assert(await evaluate("Boolean(document.querySelector('[data-settings=logging]'))"));
    assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'logging controls overflow');
    await evaluate("location.hash='profiles'");await wait(100);
   }
   await evaluate("ODILang.set('ru');scrollTo(0,0)");
   const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,'profiles-'+width+'.png'),Buffer.from(shot.data,'base64'));
  }
  await evaluate("document.getElementById('profile-name').value='Keep draft';document.getElementById('profile-name').dispatchEvent(new Event('input'));document.querySelector('[data-language=en]').click()");assert.equal(await evaluate("document.getElementById('profile-name').value"),'Keep draft');
  assert.deepEqual(errors,[]);fs.writeFileSync(p+'/profiles-browser-test-report.json',JSON.stringify({result:'passed',scope:'Chromium preview: profiles and logging controls, no ONU/OLT',checks,draftPreserved:true,scriptErrors:errors},null,2));console.log('Chromium: profiles and logging at 4 layout/language/width combinations passed');
 }finally{ws?.close();browser.kill();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
