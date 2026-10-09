const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const delay=()=>new Promise(r=>setTimeout(r,25));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(__dirname+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#mods',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 w.confirm=()=>true;
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(__dirname+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await delay();assert.equal(d.querySelectorAll('[data-settings^="mod-"]').length,3);
 let saved=JSON.parse(vm.runInContext('JSON.stringify(state)',c)),requests=[];
 w.apiStub=async(action,params)=>{if(action){assert.equal(action,'mods');requests.push({...params});Object.assign(saved,params);return {ok:'1'};}return {...saved};};
 vm.runInContext('preview=false;api=window.apiStub;restartLive=()=>{};',c);
 let vlan=d.querySelector('[data-settings="mod-vlan"]');
 assert(vlan.elements.MOD_PAIRS.disabled&&vlan.elements.MOD_VLANS.disabled);
 // A broken VLAN draft must not block speed or version saves, or be discarded.
 vlan.elements.MOD_VLAN.value='fwdop';vlan.elements.MOD_VLAN.dispatchEvent(new w.Event('change',{bubbles:true}));
 vlan.elements.MOD_PAIRS.value='incomplete-draft';vlan.elements.MOD_PAIRS.dispatchEvent(new w.Event('input',{bubbles:true}));
 const speed=d.querySelector('[data-settings="mod-speed"]');speed.elements.MOD_SPEED.value='1';speed.elements.MOD_SPEED.dispatchEvent(new w.Event('change',{bubbles:true}));
 speed.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await delay();
 assert.deepEqual(requests,[{MOD_SPEED:'1'}]);assert.equal(saved.MOD_VLAN,'off');
 vlan=d.querySelector('[data-settings="mod-vlan"]');assert.equal(vlan.elements.MOD_PAIRS.value,'incomplete-draft');assert.equal(vlan.elements.MOD_VLAN.value,'fwdop');assert(vm.runInContext('dirty',c));
 const versions=d.querySelector('[data-settings="mod-versions"]');versions.elements.MOD_SWVER.value='1';versions.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await delay();
 assert.deepEqual(requests.at(-1),{MOD_SWVER:'1'});assert.equal(d.querySelector('[name=MOD_PAIRS]').value,'incomplete-draft');
 const before=requests.length;await vm.runInContext('saveMods(document.querySelector("[data-settings=mod-vlan]"))',c);assert.equal(requests.length,before);
 vlan=d.querySelector('[data-settings="mod-vlan"]');vlan.elements.MOD_PAIRS.value='0x0101:0x02';
 await vm.runInContext('saveMods(document.querySelector("[data-settings=mod-vlan]"))',c);
 assert.deepEqual(requests.at(-1),{MOD_VLAN:'fwdop',MOD_PAIRS:'0x0101:0x02'});
 assert.equal(saved.MOD_SPEED,'1');assert.equal(saved.MOD_SWVER,'1');
 // Disabling VLAN sends only its selector, preserving its saved filters.
 vlan=d.querySelector('[data-settings="mod-vlan"]');vlan.elements.MOD_VLAN.value='off';vlan.elements.MOD_VLAN.dispatchEvent(new w.Event('change',{bubbles:true}));
 await vm.runInContext('saveMods(document.querySelector("[data-settings=mod-vlan]"))',c);assert.deepEqual(requests.at(-1),{MOD_VLAN:'off'});assert.equal(saved.MOD_PAIRS,'0x0101:0x02');
 assert.equal(vm.runInContext("numericMetric('pon get transceiver rx-power \\nRx Power: -inf  dBm\\nRTK.0> command:')",c),'-inf  dBm');
 assert.equal(vm.runInContext("numericMetric('pon get transceiver temperature \\nTemperature: 42.019531 C\\nRTK.0> command:')",c),'42.019531 C');
 fs.writeFileSync(__dirname+'/mods-ui-test-report.json',JSON.stringify({result:'passed',checks:['three independent save forms','speed-only and version-only requests','invalid adjacent VLAN draft preserved','active VLAN validation','inactive VLAN fields omitted','disabling preserves saved filters','SDK echo and prompt omitted from optical values']},null,2));
 w.close();console.log('Independent mod saves, draft preservation and optical parsing passed');
})().catch(e=>{console.error(e);process.exit(1)});
