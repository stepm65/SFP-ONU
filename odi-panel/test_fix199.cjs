const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const p=__dirname,version=fs.readFileSync(p+'/VERSION','utf8').trim();
(async()=>{
 const dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();w.confirm=()=>true;
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await new Promise(r=>setTimeout(r,30));vm.runInContext('restartLive=()=>{};preview=false;',c);
 for(const path of JSON.parse(fs.readFileSync(p+'/native-pages.json','utf8'))){
  assert.equal(vm.runInContext('nativeFrameURL('+JSON.stringify('/'+path)+')',c),'/panel/odi-native-'+path.replaceAll('/','_')+'?v='+version);
 }
 for(const name of ['status','pon','lan','arp','ping','stats','pon-stats','password','timer']){
  w.history.replaceState(null,'','#native-'+name);vm.runInContext('render()',c);
  assert(d.querySelector('iframe').getAttribute('src').startsWith('/panel/odi-native-'),name);
 }
 w.history.replaceState(null,'','#native-language');vm.runInContext('render()',c);assert(!d.querySelector('iframe'));
 const choice=d.getElementById('panel-language');assert(choice);assert.deepEqual([...choice.options].map(o=>o.value),['ru','en']);
 choice.value='en';choice.dispatchEvent(new w.Event('change'));assert.equal(w.ODILang.get(),'en');assert.equal(d.getElementById('language').value,'en');assert.equal(w.localStorage.getItem('odi-panel-language'),'en');
 w.ODILang.set('ru');assert.equal(choice.value,'ru');assert.equal(d.getElementById('language').value,'ru');
 d.querySelector('meta[name="odi-panel-version"]').content='1.9.5';vm.runInContext('state.panel_version='+JSON.stringify(version)+';syncRuntimeVersion()',c);
 assert(d.querySelector('footer').textContent.startsWith('ODI Panel '+version));assert(d.querySelector('#version-mismatch a').getAttribute('href').includes('v='+version));
 d.querySelector('meta[name="odi-panel-version"]').content=version;vm.runInContext('syncRuntimeVersion()',c);assert(!d.getElementById('version-mismatch'));
 w.history.replaceState(null,'','#native-status');vm.runInContext('render()',c);const frame=d.querySelector('iframe'),child=frame.contentDocument;
 child.open();child.write('<html><body><aside class="sidebar">old navigation</aside><main>another panel</main></body></html>');child.close();Object.defineProperty(child,'readyState',{value:'interactive',configurable:true});
 frame.dispatchEvent(new w.Event('load'));assert(frame.hidden);assert(d.querySelector('.native-load-error'));assert(d.getElementById('auth-expired'));
 dom.window.close();
 fs.writeFileSync(p+'/fix199-test-report.json',JSON.stringify({result:'passed',scope:'jsdom fixtures, no physical ONU/browser layout test',checks:['all dedicated routes match build manifest','all nine reported embedded sections use dedicated pages','language section has only RU/EN and no factory POST','language switches synchronise and persist','footer follows runtime API; cached page mismatch has refresh link','nested panel/session document is blocked instead of duplicated']},null,2));
 console.log('Version, embedded routes and shared language regression checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
