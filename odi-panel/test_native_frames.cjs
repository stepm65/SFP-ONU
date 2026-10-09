// Geometry fixtures model a quirks body that tracks its viewport; jsdom has no layout engine.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const p=__dirname,checks=[];
(async()=>{
 const dom=new JSDOM('<!doctype html><main><iframe class="native-frame" style="border:1px solid"></iframe></main>',{url:'http://onu/panel/index.html',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 let nextID=0,layoutHeight=520,bodyMeasurements=0,frameWrites=0;const raf=new Map(),observers=[];
 w.requestAnimationFrame=fn=>{raf.set(++nextID,fn);return nextID;};w.cancelAnimationFrame=id=>raf.delete(id);
 class Observer{constructor(cb){this.cb=cb;this.targets=[];this.closed=false;observers.push(this);}observe(target){this.targets.push(target);}disconnect(){this.closed=true;}fire(){if(!this.closed)this.cb();}}
 w.ResizeObserver=Observer;w.ODILang={apply(){},t:s=>s};vm.runInContext('const preview=false;',c);
 vm.runInContext(fs.readFileSync(p+'/src/native-menu.js','utf8'),c);
 const fit=()=>vm.runInContext('sizeNativeFrames()',c),flush=()=>{const jobs=[...raf.values()];raf.clear();for(const job of jobs)job();};
 const frame=d.querySelector('iframe');frame.getClientRects=()=>[{height:parseFloat(frame.style.height)||500}];
 fit();assert.equal(observers.length,0);flush();assert.equal(frame.style.height,'');checks.push('empty loading document is not observed or expanded');
 function prepare(frame){
  const child=frame.contentDocument;child.open();child.write('<html><head></head><body style="margin:0;padding:24px"><form name="tcpip" action="/boaform/formTcpipLanSetup" method="POST"><input name="ip" value="192.168.1.1"><input name="mask" value="255.255.255.0"><input name="submit-url" type="hidden" value="/tcpiplan.asp"><input name="binary" type="file"><button name="save" value="Apply Changes">Apply</button></form></body></html>');child.close();
  Object.defineProperty(child,'readyState',{value:'interactive',configurable:true});
  child.body.getBoundingClientRect=()=>{bodyMeasurements++;return {height:parseFloat(frame.style.height)||500};};
  const realCreate=child.createElement.bind(child);child.createElement=(...args)=>{const el=realCreate(...args);if(args[0]==='div')el.getBoundingClientRect=()=>({height:layoutHeight});return el;};
  return child;
 }
 const child=prepare(frame),form=child.forms.tcpip,field=form.elements.ip;field.value='192.168.10.1';
 const selected=[new child.defaultView.File(['chosen'],'private.cfg')];Object.defineProperty(form.elements.binary,'files',{value:selected});let clicks=0;form.elements.save.onclick=()=>{clicks++;return false;};child.defaultView.nativeDirty=true;
 {const proto=Object.getPrototypeOf(frame.style),own=Object.getOwnPropertyDescriptor(frame.style,'height'),desc=own||Object.getOwnPropertyDescriptor(proto,'height');Object.defineProperty(frame.style,'height',{get(){return desc.get.call(this);},set(value){frameWrites++;desc.set.call(this,value);},configurable:true});}
 frame.dispatchEvent(new w.Event('odi-native-ready'));flush();assert.equal(frame.style.height,'570px');assert.equal(bodyMeasurements,0);assert.equal(observers.length,1);assert.equal(observers[0].targets[0].className,'odi-native-content');checks.push('interactive native-ready fits content before window load, with body padding and frame border');
 for(let i=0;i<80;i++){observers[0].fire();flush();}
 assert.equal(frame.style.height,'570px');assert.equal(frameWrites,1);assert.equal(bodyMeasurements,0);checks.push('80 repeated notifications cannot create the old viewport-plus-24 growth loop');
 assert.strictEqual(child.forms.tcpip,form);assert.strictEqual(form.elements.ip,field);assert.equal(field.value,'192.168.10.1');assert.strictEqual(form.elements.binary.files,selected);assert(child.defaultView.nativeDirty);assert.equal(form.getAttribute('action'),'/boaform/formTcpipLanSetup');assert.equal(form.method,'post');assert.equal(form.elements['submit-url'].value,'/tcpiplan.asp');form.elements.save.click();assert.equal(clicks,1);checks.push('native form identity, drafts, selected files, handlers and submitted tokens survive fitting');
 for(let i=0;i<5;i++){fit();frame.dispatchEvent(new w.Event('load'));}flush();assert.equal(observers.length,1);assert.equal(child.querySelectorAll('.odi-native-content').length,1);checks.push('repeated binding and load events do not duplicate wrappers or observers');
 layoutHeight=810;for(let i=0;i<10;i++)observers[0].fire();assert.equal(raf.size,1);flush();assert.equal(frame.style.height,'860px');layoutHeight=330;observers[0].fire();flush();assert.equal(frame.style.height,'380px');checks.push('content growth and shrinkage resize once per animation frame');
 let visible=false;frame.getClientRects=()=>visible?[{}]:[];layoutHeight=900;observers[0].fire();flush();assert.equal(frame.style.height,'380px');visible=true;observers[0].fire();flush();assert.equal(frame.style.height,'950px');checks.push('hidden forms are measured when their disclosure becomes visible');
 const firstObserver=observers[0];prepare(frame);frame.dispatchEvent(new w.Event('odi-native-ready'));flush();assert(firstObserver.closed);assert.equal(observers.filter(o=>!o.closed).length,1);checks.push('navigation within an iframe disconnects the old document observer');
 const current=observers.at(-1);frame.remove();fit();assert(current.closed);assert.equal(vm.runInContext('nativeFrameBindings.size',c),0);assert.equal(raf.size,0);checks.push('leaving the page releases observers, events and queued measurements');
 const other=d.createElement('iframe');other.className='native-frame';other.style.border='1px solid';d.querySelector('main').append(other);other.getClientRects=()=>[{}];prepare(other);w.ResizeObserver=undefined;fit();flush();assert.equal(other.style.height,'950px');layoutHeight=410;w.dispatchEvent(new w.Event('resize'));flush();assert.equal(other.style.height,'460px');checks.push('resize fallback works without ResizeObserver');
 other.remove();fit();w.close();
 // The child reports readiness at DOMContentLoaded, while preserving its factory initializer.
 const embedded=new JSDOM('<!doctype html><iframe></iframe>',{url:'http://onu/panel/index.html',runScripts:'outside-only'}),pw=embedded.window,pf=pw.document.querySelector('iframe'),cw=pf.contentWindow,cc=cw.document;
 let ready=0;pf.addEventListener('odi-native-ready',()=>ready++);pw.ODILang={get:()=> 'ru'};cw.ODILang={t:s=>s,watch(){},set(){}};cw.alert=()=>{};cw.confirm=()=>true;
 cc.body.innerHTML='<form action="/boaform/formTcpipLanSetup"><input type="submit" name="save" value="Apply Changes"></form>';
 cw.eval(fs.readFileSync(p+'/src/native.js','utf8'));cc.dispatchEvent(new cw.Event('DOMContentLoaded'));assert.equal(ready,1);assert(cc.body.classList.contains('embedded'));assert.equal(cc.querySelector('button').value,'Apply Changes');checks.push('native child announces parsed and prepared controls without waiting for load');pw.close();
 fs.writeFileSync(p+'/native-frames-test-report.json',JSON.stringify({result:'passed',environment:'jsdom with intrinsic-content/quirks-viewport geometry and observer fixtures; no browser layout engine or device',checks},null,2));
 console.log('Native frame sizing:',checks.length,'checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
