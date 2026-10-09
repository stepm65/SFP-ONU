const vm=require('vm');
const {JSDOM}=require('../tools/dom/node_modules/jsdom');
const fs=require('fs'),assert=require('assert'),path=require('path');
const src=path.join(__dirname,'src');
const pause=()=>new Promise(r=>setTimeout(r,15));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(src+'/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1',runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.confirm=()=>true;for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(src+'/'+f,'utf8'),dom.getInternalVMContext());
 await pause();let misses=[];
 for(const tab of ['native-recovery','overview','identity','vlan','link','firmware','mods','wan','diagnostics','profiles']){
  w.location.hash=tab;await pause();w.ODILang.set('en');await pause();
  const walker=d.createTreeWalker(d.querySelector('#main'),4);let n;while(n=walker.nextNode())if(/[а-яё]/i.test(n.nodeValue)&&!n.parentElement.closest('dd,pre,.mono'))misses.push([tab,n.nodeValue]);
 }
 assert.deepEqual(misses,[],'English translation coverage');
 assert(!d.querySelector('.sidebar a[href="/legacy.html"]'));
 w.location.hash='native-recovery';await pause();assert(d.querySelector('#section-nav a[href="#native-recovery"]'));assert(d.querySelector('#main button:disabled'));
 w.location.hash='identity';await pause();const loid=d.querySelector('[name=LOID]');loid.value='draft<secret>';loid.dispatchEvent(new w.Event('input',{bubbles:true}));
 const before=Array.from(d.querySelectorAll('input,select')).filter(e=>e.id!=='language').map(e=>[e.name,e.value,e.disabled]);
 w.ODILang.set('ru');await pause();w.ODILang.set('en');await pause();
 assert.deepEqual(Array.from(d.querySelectorAll('input,select')).filter(e=>e.id!=='language').map(e=>[e.name,e.value,e.disabled]),before);
 assert.equal(w.localStorage.getItem('odi-panel-language'),'en');assert.equal(d.documentElement.lang,'en');assert.equal(loid.value,'draft<secret>');
 const unsupported='Invalid value: GPON_SN';w.ODILang.set('ru');assert.equal(w.ODILang.t(unsupported),'Недопустимое значение: GPON_SN');
 w.location.hash='wan';await pause();
 const names=Array.from(d.querySelectorAll('[data-native]')).map(e=>e.dataset.native);assert(!names.includes('backup')&&!names.includes('gpon')&&names.includes('lan'));
 // Native form: submitted tokens and custom input values must survive both languages.
 const native=new JSDOM('<html><head></head><body><form name="factory" action="/boaform/test"><label>IP Address:</label><input name="ip" value="192.168.1.1"><select name="mode"><option>Enable</option><option value="0">Disable</option></select><input name="apply" type="submit" value="Apply Changes"><input name="reset" type="reset" value="Reset"></form></body></html>',{url:'http://onu/gpon.asp',runScripts:'outside-only'}),nw=native.window,nd=nw.document;
 for(const f of ['translations.js','i18n.js','native.js'])vm.runInContext(fs.readFileSync(src+'/'+f,'utf8'),native.getInternalVMContext());
 await pause();const tokens=()=>Array.from(nd.querySelector('form').elements).map(e=>[e.name,e.value]);
 const original=tokens();nw.ODILang.set('ru');await pause();assert.equal(nd.querySelector('[name=apply]').textContent,'Применить изменения');assert.equal(nd.querySelector('[name=apply]').value,'Apply Changes');
 nw.ODILang.set('en');await pause();assert.deepEqual(tokens(),original);assert.equal(nd.querySelector('[name=apply]').textContent,'Apply Changes');assert.equal(nd.querySelector('select[name=mode]').value,'Enable');
 fs.writeFileSync(__dirname+'/localization-test-report.json',JSON.stringify({result:'passed',environment:'jsdom; no visual layout engine',checks:['all nine extension tabs in English','language persistence','RU/EN switch preserves drafts and disabled fields','localized CGI errors','deduplicated original section links','native submit tokens unchanged','options without explicit value preserve original token']},null,2));
 w.close();nw.close();console.log('Localization and form-preservation checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
