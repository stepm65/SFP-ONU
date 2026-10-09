const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
(async()=>{
 const dom=new JSDOM(fs.readFileSync(__dirname+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#firmware',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();w.confirm=()=>true;
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(__dirname+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await new Promise(r=>setTimeout(r,20));assert(d.querySelector('[name=bank]').disabled);
 vm.runInContext('preview=false;load=async()=>render();pauseLive=async()=>{};restartLive=()=>{};confirmAction=async()=>true;render();',c);
 w.ODILang.set('ru');
 const checks=[],requests=[];
 class MockXHR{
  constructor(){this.upload={};this.responseText='';this.status=200;requests.push(this);}
  open(method,url){assert.equal(method,'POST');assert.equal(url,'upload.cgi');}
  setRequestHeader(key,value){assert.equal(key,'Content-Type');assert.equal(value,'application/octet-stream');}
  send(body){this.body=body;}
  chunk(text){this.responseText+=text;this.onprogress();}
  finish(text=''){this.responseText+=text;this.onload();}
 }
 w.XMLHttpRequest=MockXHR;
 const form=()=>d.querySelector('#upload');
 assert.equal(form().elements.bank.value,'1');assert(form().elements.bank.options[0].disabled);checks.push('inactive bank choice and preview guards');
 async function begin(){Object.defineProperty(form().elements.binary,'files',{value:[new w.File(['TAR fixture'],'test.tar')],configurable:true});const done=form().onsubmit({preventDefault(){}});await new Promise(r=>setTimeout(r,0));return {done,request:requests.at(-1)};}
 const first=await begin(),x=first.request;
 const body=await new Promise(resolve=>{const r=new w.FileReader();r.onload=()=>resolve(r.result);r.readAsText(x.body);});assert(body.startsWith('csrf=preview\nbank=1\n'));checks.push('CSRF and target bank upload envelope');
 assert(form().querySelector('button').disabled);
 x.upload.onprogress({lengthComputable:true,loaded:50,total:100});assert.equal(d.querySelector('#upload-progress progress').value,50);assert(d.querySelector('#upload-detail').textContent.includes('50%'));checks.push('measured upload percentage');
 x.upload.onload();assert(d.querySelector('#upload-detail').textContent.includes('Ожидаем'));
 x.chunk('protocol=2\nphase=receiv');assert.equal(d.querySelector('#upload-progress').dataset.phase,'receiving');x.chunk('ing\nphase=checking\n');assert.equal(d.querySelector('#upload-progress').dataset.phase,'checking');assert(d.querySelector('#upload-phase').textContent.includes('2 / 5'));assert(!d.querySelector('#upload-progress progress').hasAttribute('value'));checks.push('split stream lines update before completion; flash has no invented percentage');
 x.chunk('phase=writing\n');assert.equal(d.querySelector('#upload-progress').dataset.phase,'writing');assert.equal(d.querySelectorAll('.progress-phases .done').length,2);assert(form().querySelector('button').disabled);
 w.ODILang.set('en');await new Promise(r=>setTimeout(r,0));assert(d.querySelector('#upload-phase').textContent.includes('Stage'));assert(d.querySelector('#upload-phase').textContent.includes('Flash write'));assert(!/[а-яё]/i.test(d.querySelector('#upload-progress').textContent));checks.push('RU/EN switch during update preserves current stage');
 x.chunk('log='+Buffer.from('<script>fixture</script>\n').toString('hex')+'\nphase=readback\n');assert.equal(d.querySelector('#upload-progress').dataset.phase,'readback');assert(d.querySelector('#upload-log').textContent.includes('<script>'));assert(!d.querySelector('#upload-log script'));checks.push('read-back stage and inert decoded log');
 x.finish('phase=verified\nbank=1\nok=1\n');await first.done;assert.equal(d.querySelector('#upload-progress').dataset.phase,'verified');assert.equal(d.querySelectorAll('.progress-phases .done').length,5);assert.equal(d.querySelector('#upload-progress progress').value,100);assert(d.querySelector('#upload-status').textContent.includes('Firmware installed'));assert(!d.querySelector('#refresh').disabled);checks.push('verified result and completed stages remain visible after state reload');
 const failed=await begin();assert.equal(d.querySelectorAll('#upload-progress').length,1);failed.request.chunk('phase=checking\nphase=writing\nphase=readback\n');failed.request.finish('phase=failed\nerror=READBACK\n');await failed.done;assert.equal(d.querySelector('#upload-progress').dataset.failed,'1');assert(d.querySelector('#upload-detail').textContent.includes('Read-back verification failed'));assert.equal(d.querySelectorAll('.progress-phases .done').length,3);assert(!form().querySelector('button').disabled);checks.push('read-back failure is explicit and does not show successful verification');
 const lost=await begin();assert.equal(d.querySelectorAll('#upload-progress').length,1);lost.request.chunk('phase=writing\n');lost.request.onerror();await lost.done;assert(d.querySelector('#upload-detail').textContent.includes('Connection to the stick was lost'));assert(d.querySelector('#upload-phase').textContent.includes('Flash write'));assert.equal(d.querySelector('#upload-progress').dataset.failed,'1');checks.push('lost connection retains last actual stage and requires checking bank state');
 const incomplete=await begin();incomplete.request.finish('phase=verified\nbank=1\n');await incomplete.done;assert.equal(d.querySelector('#upload-progress').dataset.failed,'1');checks.push('missing final ok cannot confirm success');
 const csrf=await begin();csrf.request.status=403;csrf.request.finish('error=CSRF\n');await csrf.done;assert(d.querySelector('#upload-detail').textContent.includes('Refresh the page'));checks.push('CSRF error is preserved instead of being misreported as sign-in failure');
 const old=await begin();old.request.finish('ok=1\nbank=1\n');await old.done;assert.equal(d.querySelector('#upload-progress').dataset.phase,'verified');checks.push('plain response from earlier CGI remains compatible');
 vm.runInContext("state.sw_commit='1';render();",c);assert(form().querySelector('button').disabled);
 vm.runInContext("state.sw_commit='0';state.bank_invalid1='1';render();",c);assert(d.querySelector('[data-bank="1"]').disabled);assert(!form().querySelector('button').disabled);checks.push('pending boot and invalid-bank controls; reinstall remains available');
 vm.runInContext("state.firmware_status='VERIFIED bank=1';render();",c);w.ODILang.set('ru');assert(d.querySelector('#main').textContent.includes('Запись проверена'));w.ODILang.set('en');assert(d.querySelector('#main').textContent.includes('Write verified'));
 fs.writeFileSync(__dirname+'/firmware-ui-test-report.json',JSON.stringify({result:'passed',environment:'jsdom with incremental XHR/upload byte fixtures; no real Boa, network or hardware',version:vm.runInContext('state.panel_version',c),checks},null,2));
 w.close();console.log('Firmware UI:',checks.length,'checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
