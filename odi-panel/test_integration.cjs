const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {JSDOM}=require('../tools/dom/node_modules/jsdom');
const p=__dirname,wait=()=>new Promise(r=>setTimeout(r,20));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#identity',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await wait();vm.runInContext("preview=false; window.posts=[]; api=async(a,params)=>{window.posts.push(params);Object.assign(state,params);}; load=async()=>render(); render();",c);
 let pass=()=>d.querySelector('[name=GPON_PLOAM_PASSWD]'),format=()=>d.querySelector('#ploam-format');
 // Nothing saved: no card may claim a pending reboot (unnamed buttons once matched an empty key).
 const saved=['Сохранено и проверено; ожидает перезагрузки.','Saved and verified; reboot pending.'],foot=id=>d.querySelector('[data-settings='+id+'] .card-foot small').textContent;
 vm.runInContext("state.pending_keys='';render();formStatus();",c);for(const id of ['auth','omci','versions','mac'])assert(!saved.includes(foot(id)),id+': '+foot(id));
 vm.runInContext("delete state.pending_keys;render();formStatus();",c);assert(!saved.includes(foot('auth')));
 vm.runInContext("state.pending_keys='LOID\\n';render();formStatus();",c);assert(saved.includes(foot('auth')));assert(!saved.includes(foot('omci')));
 assert.equal(vm.runInContext("ploamHex('0123456789','1')",c),'30313233343536373839');
 assert.throws(()=>vm.runInContext("ploamHex('коротко','1')",c));
 assert.throws(()=>vm.runInContext("ploamAscii('00000000000000000000')",c));
 pass().value='30313233343536373839';format().value='1';format().dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(pass().value,'0123456789');
 await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.at(-1).GPON_PLOAM_FORMAT,'1');assert.equal(w.posts.at(-1).GPON_PLOAM_PASSWD,'30313233343536373839');assert.equal(pass().value,'0123456789');
 // Incomplete password draft must survive saving a different section.
 pass().value='partial';d.querySelector('[name=OUI]').value='aabbcc';
 await vm.runInContext("save(document.querySelector('[data-settings=omci]'))",c);assert.equal(w.posts.at(-1).OUI,'aabbcc');assert(!('GPON_PLOAM_PASSWD' in w.posts.at(-1)));assert.equal(pass().value,'partial');assert.equal(format().value,'1');
 // Restored drafts use the same non-blocking format selector.
 format().value='0';format().dispatchEvent(new w.Event('change'));assert.equal(format().value,'0');assert.equal(pass().value,'partial');
 format().value='1';format().dispatchEvent(new w.Event('change'));assert.equal(format().value,'1');assert.equal(pass().value,'partial');
 d.querySelector('[data-settings=auth]').reset();assert.equal(pass().value,'0123456789');
 // A HEX value containing nonprintable bytes remains representable and reset works.
 vm.runInContext("state.GPON_PLOAM_PASSWD='00000000000000000000';state.GPON_PLOAM_FORMAT='1';render();",c);assert.equal(format().value,'0');format().value='1';format().dispatchEvent(new w.Event('change'));assert.equal(format().value,'1');assert.equal(pass().value,'00000000000000000000');
 let count=w.posts.length;await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.length,count);assert.equal(vm.runInContext('state.GPON_PLOAM_PASSWD',c),'00000000000000000000');
 format().value='0';format().dispatchEvent(new w.Event('change'));assert.equal(pass().value,'00000000000000000000');
 pass().value='30313233343536373839';format().value='1';format().dispatchEvent(new w.Event('change'));d.querySelector('[data-settings=auth]').reset();assert.equal(format().value,'0');assert.equal(pass().value,'00000000000000000000');
 vm.runInContext("state.GPON_PLOAM_PASSWD='4142434445464748495A';state.GPON_PLOAM_FORMAT='0';render();",c);assert.equal(vm.runInContext("controlChanged(document.querySelector('[name=GPON_PLOAM_PASSWD]'))",c),false);
 // Clearing a saved password reports a validation error, not an uncaught rejection.
 pass().value='';count=w.posts.length;await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.length,count);assert(d.getElementById('notice').classList.contains('error'));
 // Empty PLOAM readback must not block saving only LOID.
 vm.runInContext("state.GPON_PLOAM_PASSWD='';state.GPON_PLOAM_FORMAT='0';render();",c);assert.equal(vm.runInContext("controlChanged(document.querySelector('[name=GPON_PLOAM_PASSWD]'))",c),false);
 d.querySelector('[name=LOID]').value='loid-only';await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.deepEqual(Object.keys(w.posts.at(-1)),['LOID']);
 // Reproduce the reported empty HEX -> ASCII selector failure, then save ASCII.
 format().value='1';format().dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(format().value,'1');assert.equal(pass().dataset.format,'1');assert.equal(pass().value,'');assert.equal(pass().maxLength,10);assert(pass().required);
 count=w.posts.length;await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.length,count);
 pass().value='short';await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.length,count);
 pass().value='0123456789';await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.at(-1).GPON_PLOAM_FORMAT,'1');assert.equal(w.posts.at(-1).GPON_PLOAM_PASSWD,'30313233343536373839');assert.equal(pass().value,'0123456789');
 // Text already typed in the desired format is kept, including before HEX validates.
 vm.runInContext("state.GPON_PLOAM_FORMAT='0';render();",c);pass().value='ISPpass123';format().value='1';format().dispatchEvent(new w.Event('change'));assert.equal(pass().value,'ISPpass123');assert.equal(format().value,'1');
 await vm.runInContext("save(document.querySelector('[data-settings=auth]'))",c);assert.equal(w.posts.at(-1).GPON_PLOAM_PASSWD,Buffer.from('ISPpass123').toString('hex'));assert.equal(w.posts.at(-1).GPON_PLOAM_FORMAT,'1');
 assert(!d.querySelector('a[href="/gpon.asp"],a[href="/omci_info.asp"]'));w.close();
 const en=JSON.parse(fs.readFileSync(p+'/native-en.json'));
 for(const mode of ['0','1',null]){
  const html=fs.readFileSync(p+'/src/saveconf.asp','utf8').replace(/<%\s*multilang\("(\d+)"\s*"[^"]+"\);\s*%>/g,(_,n)=>en[+n]).replace(/<% checkWrite\("fiber-reset([01])"\); %>/g,(_,n)=>n===mode?'checked':'');
  const dom=new JSDOM(html,{url:'http://onu/saveconf.asp',runScripts:'dangerously'});await wait();const d=dom.window.document,f=d.forms.fiberResetConfig;
  if(mode===null){assert(f.elements.fiberreset.disabled);assert(f.querySelector('button').disabled);}else{
   assert.equal(f.elements.fiberreset.value,mode);const data=Object.fromEntries(new dom.window.FormData(f,f.querySelector('button')));assert.deepEqual(data,{fiberreset:mode,apply:'Apply Changes','submit-url':'/saveconf.asp'});assert.equal(f.getAttribute('action'),'/boaform/admin/formOmciInfo');
  }dom.window.close();
 }
 fs.writeFileSync(p+'/integration-test-report.json',JSON.stringify({result:'passed',environment:'jsdom + simulated API; no device writes',checks:['ASCII/HEX byte-preserving conversion','invalid/nonprintable ASCII rejected at save without changing stored bytes','paired password/display format save','empty HEX field can switch to ASCII before input','ASCII typed while HEX selected is retained on switch','empty and incomplete selected-format passwords cannot be submitted','unmodified empty PLOAM does not block LOID-only save','conversion error displayed without uncaught rejection','OUI save isolated from auth','incomplete auth draft survives neighboring save and format changes','reset restores original display safely','no additional GPON/OMCI window links','Fiber Reset original state 0/1, endpoint and submission tokens','unknown Fiber Reset state disables writes','no false pending-reboot status without saved keys']},null,2));console.log('Integrated parameter tests passed');
})().catch(e=>{console.error(e);process.exit(1)});
