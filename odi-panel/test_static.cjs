const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const project=__dirname;
let src=fs.readFileSync(path.join(project,'src/panel.js'),'utf8');
// Evaluate only declarations/pure render functions; no DOM, network or browser.
src=src.slice(0,src.indexOf("nativeNavigation();"));
const context={location:{protocol:'file:',search:'',hash:''},URLSearchParams,window:{},console,setTimeout,clearTimeout,document:{querySelector:()=>null,addEventListener:()=>{}},Object};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(project,'src/native-menu.js'),'utf8'),context);context.ODILang={t:s=>s,get:()=> 'ru'};vm.runInContext(fs.readFileSync(path.join(project,'src/firmware.js'),'utf8'),context);for(const file of ['diagnostics.js','profiles.js','ux.js','layout.js'])vm.runInContext(fs.readFileSync(path.join(project,'src/'+file),'utf8'),context);vm.runInContext(src,context);vm.runInContext('state={...demo}',context);
const rendered={};for(const tab of ['overview','identity','vlan','link','firmware'])rendered[tab]=vm.runInContext(tab+'()',context);
assert(rendered.link.includes('name="LAN_SPEED_MODE"'));assert(!rendered.link.includes('name="LAN_SDS_MODE"'));
assert(rendered.identity.includes('name="GPON_SN"'));assert(rendered.identity.includes('name="sw_custom_version0"'));
assert(rendered.firmware.includes('name="bank"'));assert(rendered.firmware.includes('id="upload"'));
assert.equal(vm.runInContext("decode(encode('A <&> 123'))",context),'A <&> 123');
assert.equal(vm.runInContext("decode('d0a0d0a3')",context),'РУ');
assert.equal(vm.runInContext("esc('<script>')",context),'&lt;script&gt;');
assert.throws(()=>vm.runInContext("encode('русский')",context));
assert(!src.includes('localStorage')&&!src.includes('eval('));
fs.writeFileSync(path.join(project,'rendered-tests.json'),JSON.stringify(rendered));console.log('Pure render and encoding checks passed');
