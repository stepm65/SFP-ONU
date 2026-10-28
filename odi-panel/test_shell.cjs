const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
(async()=>{
const p=__dirname,dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#identity',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
w.localStorage.setItem('odi-panel-layout','compact');
w.ODINativePreview={'/saveconf.asp':'<body>Backup form</body>'};
for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
await new Promise(r=>setTimeout(r,30));
assert.equal(d.body.dataset.layout,'diagnostic');assert(!d.getElementById('diagnostic-toggle'));assert(!d.getElementById('diagnostic-rail').hidden);assert(!d.querySelector('select#language'));
const draft=d.querySelector('[name=LOID]');draft.value='keep-draft';draft.dispatchEvent(new w.Event('input',{bubbles:true}));
for(const lang of ['en','ru']){d.querySelector('[data-language='+lang+']').click();assert.equal(d.documentElement.lang,lang);assert.equal(draft.value,'keep-draft');assert.equal(d.querySelector('#language [aria-pressed=true]').dataset.language,lang);}
vm.runInContext("dirty=false;location.hash='#profiles';render()",c);assert(!d.querySelector('#main iframe'));
vm.runInContext("location.hash='#native-backup';render()",c);assert.equal(w.location.hash,'#native-backup');assert(d.querySelector('#main .maintenance-frame'));assert(d.querySelector('#native-nav a[href="#native-password"]').classList.contains('active'));assert(d.querySelector('#section-nav a[href="#native-backup"]'));
const response=(status,body)=>({ok:status>=200&&status<300,status,text:async()=>body});let requests=[];
w.fetch=async(url,init={})=>{requests.push([url,init]);return url.includes('formLogout')?response(200,'OK: logout successfully!'):response(403,'Forbidden');};
await vm.runInContext('endDeviceSession()',c);assert.equal(requests.length,2);assert.equal(requests[1][0],'/');assert.equal(requests[0][0],'/boaform/admin/formLogout');assert.equal(requests[0][1].method,'POST');assert.equal(requests[0][1].body.get('save'),'Logout');assert.equal(requests[0][1].body.get('submit-url'),'/');
w.fetch=async(url)=>response(200,url.includes('formLogout')?'OK':'ok=31\n');await assert.rejects(vm.runInContext('endDeviceSession()',c));
w.fetch=async()=>response(500,'error');await assert.rejects(vm.runInContext('endDeviceSession()',c));
w.fetch=async()=>{throw new TypeError('Failed to fetch');};await assert.rejects(vm.runInContext('endDeviceSession()',c));
w.fetch=async(url)=>response(200,url.includes('formLogout')?'OK':'<form name="cmlogin"></form>');await vm.runInContext('endDeviceSession()',c);
requests=[];w.fetch=async()=>{requests.push(1);throw Error('must not fetch');};
vm.runInContext("preview=false;busy=false;dirty=true;confirmAction=async()=>false;",c);await vm.runInContext('logoutPanel({preventDefault(){}})',c);assert.equal(requests.length,0);assert(vm.runInContext('dirty',c));
vm.runInContext("dirty=false",c);d.querySelector('.native-frame').contentWindow.nativeDirty=true;await vm.runInContext('logoutPanel({preventDefault(){}})',c);assert.equal(requests.length,0);
w.close();fs.writeFileSync(p+'/shell-test-report.json',JSON.stringify({result:'passed',checks:['diagnostics always visible despite old compact preference','RU/EN buttons preserve unsaved fields','backup separated from Profiles and selected under System','logout posts stock endpoint and fields and verifies session removal','active session, HTTP errors and network errors never count as successful logout','unsaved panel and embedded form drafts can cancel logout']},null,2));console.log('Shell and logout checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
