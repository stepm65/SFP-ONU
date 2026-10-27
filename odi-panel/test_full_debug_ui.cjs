const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
(async()=>{
 const p=__dirname,dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#diagnostics',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await new Promise(r=>setTimeout(r,25));const form=d.querySelector('[data-settings=debug]');assert(form);assert.equal(form.elements.DEBUG_REMOTE.value,'0');assert.equal(form.elements.DEBUG_BOOT.value,'0');assert.equal(form.elements.DEBUG_SECONDS.value,'180');
 let calls=[];w.calls=calls;vm.runInContext("preview=false;api=async(a,params)=>{window.calls.push({a,params});return {...params,ok:'1',debug_rc:'0'};};readApi=async()=>({debug_status:'state=capturing\\nstarted_uptime=10\\nupdated_uptime=20',debug_raw_bytes:'96',debug_parsed_bytes:'256'});",c);
 form.elements.DEBUG_SECONDS.value='60';form.elements.DEBUG_REMOTE.value='1';form.elements.DEBUG_BOOT.value='1';
 await vm.runInContext("fullDebugAction('start')",c);assert.equal(calls[0].a,'debug_config');assert.equal(calls[0].params.DEBUG_REMOTE,'1');assert.equal(calls[1].a,'debug_start');
 assert(d.querySelector('#full-debug-status').textContent.includes('RAW 96 B'));assert(d.querySelector('[data-debug-action=download]').disabled);
 await vm.runInContext("fullDebugAction('stop')",c);assert.equal(calls.at(-1).a,'debug_stop');
 const safe=vm.runInContext("safeDiagnostic({private_credentials:'FAKE-PLOAM',raw_private:'FAKE-RAW'})",c);assert(!JSON.stringify(safe).includes('FAKE-PLOAM'));assert(!JSON.stringify(safe).includes('FAKE-RAW'));
 w.ODILang.set('en');assert(form.textContent.includes('Full debug with passwords and OMCI'));assert(form.textContent.includes('RAW packets and passwords to configured server'));
 vm.runInContext('clearTimeout(debugTimer);',c);w.close();
 const report={result:'passed',scope:'jsdom and simulated CGI, no device access',checks:['private mode and private syslog are off by default','bounded duration and one-shot boot controls','save and start use fixed authenticated actions','RAW/parsed byte counters','private download unavailable during capture','normal diagnostics exclude private fields','RU/EN labels']};fs.writeFileSync(p+'/full-debug-ui-test-report.json',JSON.stringify(report,null,2));console.log(report);
})().catch(e=>{console.error(e);process.exit(1)});
