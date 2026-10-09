const {JSDOM}=require('../tools/dom/node_modules/jsdom'),fs=require('fs'),vm=require('vm'),assert=require('assert');
const p=__dirname,english=JSON.parse(fs.readFileSync(p+'/native-en.json'));
const html=fs.readFileSync(p+'/src/saveconf.asp','utf8').replace(/<%\s*multilang\("(\d+)"\s*"[^"]+"\);\s*%>/g,(_,n)=>english[+n]);
let accept=true,questions=[],submitted=[];
const dom=new JSDOM(html,{url:'http://onu/saveconf.asp',runScripts:'dangerously',beforeParse(w){w.confirm=s=>{questions.push(s);return accept;};}}),w=dom.window,d=w.document;
d.addEventListener('submit',e=>{e.preventDefault();submitted.push({action:e.target.getAttribute('action'),data:Array.from(new w.FormData(e.target,e.submitter).entries())});});
d.querySelector('[name=save_cs]').click();assert.equal(submitted[0].action,'/boaform/formSaveConfig');assert(submitted[0].data.some(([k,v])=>k==='save_cs'&&v==='Backup...'));
d.querySelector('[name=reset]').click();assert(submitted[1].data.some(([k,v])=>k==='reset'&&v==='Reset'));assert(!submitted[1].data.some(([k])=>k==='reset0'));
d.querySelector('[name=reset0]').click();assert(submitted[2].data.some(([k,v])=>k==='reset0'&&v==='Reset'));assert(questions.at(-1).includes('все параметры'));
accept=false;d.querySelector('[name=reset0]').click();assert.equal(submitted.length,3);
assert.equal(d.querySelectorAll('.maintenance-card').length,5);assert(d.querySelector('.danger-card [name=reset0]'));w.close();
(async()=>{
 const dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#identity',runScripts:'outside-only'}),w=dom.window,d=w.document;
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8'),dom.getInternalVMContext());
 await new Promise(r=>setTimeout(r,20));assert.equal(d.querySelectorAll('[name=LOID]').length,1);assert.equal(d.querySelectorAll('[name=LOID_PASSWD]').length,1);assert(!d.querySelector('#main iframe'));assert(d.querySelector('.gpon-only [name=GPON_SN]'));
 const field=d.querySelector('[name=LOID]');field.value='shared-draft';field.dispatchEvent(new w.Event('input',{bubbles:true}));w.ODILang.set('en');assert.equal(field.value,'shared-draft');w.ODILang.set('ru');assert.equal(field.value,'shared-draft');w.close();
 fs.writeFileSync(p+'/layout-test-report.json',JSON.stringify({result:'passed',environment:'jsdom; no visual rendering engine',checks:['one shared LOID/password pair','GPON-only fields separated','no EPON iframe or disclosure','RU/EN retains auth draft','five aligned maintenance cards','original backup/reset/reset0 tokens and endpoint preserved','full reset requires confirmation; cancellation prevents submission'],real_resets_performed:false},null,2));console.log('Shared auth and maintenance action tests passed');
})().catch(e=>{console.error(e);process.exit(1)});
