const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const p=__dirname,en=JSON.parse(fs.readFileSync(p+'/native-en.json')),checks=[];
const routes=JSON.parse(fs.readFileSync(p+'/native-pages.json'));
for(const route of routes){
 const source=fs.readFileSync(route==='saveconf.asp'?p+'/src/saveconf.asp':p+'/../base/files/home/httpd/web/'+route,'utf8');
 const html=source.replace(/<%\s*multilang\("(\d+)"\s*"[^"\n]+"\);\s*%>/g,(_,n)=>en[+n]).replace(/<%[\s\S]*?%>/g,'0');
 const dom=new JSDOM(html,{url:'http://onu/panel/odi-native-'+route.replaceAll('/','_'),runScripts:'outside-only'}),w=dom.window,d=w.document;
 const forms=[...d.forms],fields=[...d.querySelectorAll('input,select,textarea')],tokens=forms.map(f=>[f.getAttribute('action'),f.method,[...new w.FormData(f)]]);
 if(fields.find(e=>e.type==='text'))fields.find(e=>e.type==='text').value='unsaved draft';
 const drafts=fields.map(e=>e.value),handlers=fields.map(e=>e.getAttribute('onclick'));
 vm.runInContext(fs.readFileSync(p+'/src/native.js','utf8'),dom.getInternalVMContext());w.prepareNativeLayout();
 assert.deepEqual([...d.forms],forms,route+' form identity');
 assert.deepEqual([...d.querySelectorAll('input,select,textarea')],fields,route+' field identity');
 assert.deepEqual(fields.map(e=>e.value),drafts,route+' drafts');
 assert.deepEqual(fields.map(e=>e.getAttribute('onclick')),handlers,route+' handlers');
 assert.deepEqual(forms.map(f=>[f.getAttribute('action'),f.method]),tokens.map(t=>t.slice(0,2)),route+' endpoints');
 assert(!d.querySelector('table[width],table[bgcolor],tr[bgcolor],td[bgcolor],th[bgcolor]'),route+' obsolete geometry and fills');
 assert([...d.querySelectorAll('table')].every(t=>t.classList.contains('native-table')),route+' themed tables');
 const wrappers=d.querySelectorAll('.native-table-scroll').length;w.prepareNativeLayout();assert.equal(d.querySelectorAll('.native-table-scroll').length,wrappers,route+' idempotence');
 if(route==='status.asp'){
  assert(d.querySelector('.native-properties .native-section'));
  assert(d.querySelector('.native-note tr[hidden]'));
 }
 checks.push(route);w.close();
}
fs.writeFileSync(p+'/native-theme-test-report.json',JSON.stringify({result:'passed',scope:'factory ASP markup fixtures in jsdom; layout normalization preserves existing forms, inputs, handlers and drafts',routes:checks},null,2));
console.log('Native theme preserves forms and drafts on',checks.length,'factory pages');
