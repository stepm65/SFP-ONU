// Small CDP driver using the installed Chromium; no npm download or device access.
const fs=require('fs'),path=require('path'),cp=require('child_process');
module.exports=async function browserDriver(output){
 fs.mkdirSync(output,{recursive:true});
 const exe=process.env.CHROME_BIN||path.resolve(__dirname,'../../browser-cache/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe');
 const browser=cp.spawn(exe,['--headless','--no-sandbox','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+fs.mkdtempSync(path.join(output,'profile-')),'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 let ws;
 try{
  const endpoint=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(Error('Chromium startup timeout')),15000);browser.on('error',reject);browser.stderr.on('data',b=>{buf+=b;const m=buf.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1]);}});});
  const origin=endpoint.replace('ws://','http://').split('/devtools/')[0],targets=await(await fetch(origin+'/json/list')).json();
  ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r));
  let id=0;const pending=new Map(),errors=[];
  ws.addEventListener('message',e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)?.(d);pending.delete(d.id);}if(d.method==='Runtime.exceptionThrown'){const e=d.params.exceptionDetails;errors.push({message:e.exception?.description||e.text,url:e.url,line:e.lineNumber,column:e.columnNumber});}});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,t=setTimeout(()=>reject(Error('CDP timeout: '+method)),15000);pending.set(n,d=>{clearTimeout(t);d.error?reject(Error(d.error.message)):resolve(d.result);});ws.send(JSON.stringify({id:n,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await call('Runtime.enable');await call('Page.enable');
  return {call,evaluate,errors,close(){ws.close();browser.kill();}};
 }catch(e){ws?.close();browser.kill();throw e;}
};
