const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const {JSDOM}=require('../tools/dom/node_modules/jsdom');
const p=__dirname,ours={window:{}};vm.createContext(ours);vm.runInContext(fs.readFileSync(p+'/src/mackey.js','utf8'),ours);
const generate=ours.window.ODIMacKey.generate;
const vectors=JSON.parse(fs.readFileSync(p+'/upstream/odi-tools/reference-vectors.json','utf8'));
for(const {mac,key} of vectors){
 assert.equal(generate(mac),key);assert.equal(key,crypto.createHash('md5').update('hsgq1.9a'+mac.toUpperCase()).digest('hex'));
 for(const value of [mac.match(/../g).join(':'),mac.match(/../g).join('-'),mac.match(/..../g).join('.')])assert.equal(generate(value),key);
}
for(const invalid of ['','xyz','00112233445','00112233445566','00:11-22:33:44:55',';reboot','00 11 22 33 44 55'])assert.throws(()=>generate(invalid));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#identity',runScripts:'outside-only'}),w=dom.window;
 let network=0;w.fetch=()=>{network++;throw Error('unexpected network');};
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8'),dom.getInternalVMContext());
 await new Promise(r=>setTimeout(r,20));const mac=w.document.querySelector('[name=ELAN_MAC_ADDR]'),key=w.document.querySelector('[name=MAC_KEY]');
 mac.value='00:11:22:33:44:55';w.document.getElementById('generate-mackey').click();assert.equal(mac.value,'001122334455');assert.equal(key.value,generate(mac.value));assert.equal(network,0);
 w.ODILang.set('en');assert.equal(key.value,generate(mac.value));assert(w.document.querySelector('[data-settings=mac] button[type=submit]').disabled);
 assert.equal(w.document.querySelectorAll('[data-tab=wan]').length,1);assert.equal(w.document.querySelectorAll('[data-native=wanmode],[data-native=wan],[data-native=epon]').length,0);
 assert(!w.document.body.textContent.includes('Panel 1.0'));w.close();
 fs.writeFileSync(p+'/mackey-test-report.json',JSON.stringify({result:'passed',source_algorithm_vectors:64,accepted_formats:['bare','colon','hyphen','dotted'],invalid_inputs_rejected:7,ui:'local fill, no fetch, no save; normalized MAC and derived key retained through RU/EN switch',navigation:'single WAN entry; no separate EPON or WAN Mode entries'},null,2));console.log('MACKEY reference comparison and local UI tests passed');
})().catch(e=>{console.error(e);process.exit(1)});
