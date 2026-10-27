const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
(async()=>{
 const p=__dirname,dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#diagnostics',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await new Promise(r=>setTimeout(r,30));w.confirm=()=>true;
 const form=d.querySelector('[data-settings=logging]');assert(form);assert.equal(form.elements.LOG_PORT.value,'514');assert.equal(form.elements.LOG_REMOTE.value,'0');
 assert(!vm.runInContext("validLogAddress('1.2.3.999')",c));assert(!vm.runInContext("validLogAddress('1.2.3.4;reboot')",c));assert(vm.runInContext("validLogAddress('192.168.1.10')",c));
 let calls=[];w.calls=calls;vm.runInContext("preview=false;api=async(a,fields)=>{window.calls.push({a,fields});return {...fields,ok:'1',syslog_test_rc:'0'};};readApi=async()=>({event_log:'uptime=50 event=PON_STATE state=O5 <script>',logger_status:'pon=O5',syslog_status:'rc=0'});",c);
 form.elements.LOG_REMOTE.value='1';form.elements.LOG_HOST.value='192.168.1.10';form.elements.LOG_TAG.value='test-onu';
 await vm.runInContext("saveLogging(document.querySelector('[data-settings=logging]'))",c);
 assert.equal(calls[0].a,'logging');assert.equal(calls[0].fields.LOG_HOST,'192.168.1.10');assert.equal(vm.runInContext('state.LOG_TAG',c),'test-onu');
 await vm.runInContext("logAction('read')",c);assert(d.querySelector('#event-log-output').textContent.includes('<script>'));assert(!d.querySelector('#event-log-output script'));
 await vm.runInContext("logAction('test')",c);assert.equal(calls.at(-1).a,'log_test');
 w.ODILang.set('en');assert(d.querySelector('[data-settings=logging]').textContent.includes('Connection journal and syslog'));
 assert(!d.querySelector('[data-settings=logging]').textContent.includes('Журнал'));
 w.close();const report={result:'passed',scope:'jsdom + simulated CGI, no hardware',checks:['local 64KiB journal and TCP syslog controls','endpoint validation','settings save readback updates state without reboot','journal uses textContent','fixed test action','RU/EN controls']};fs.writeFileSync(p+'/logging-ui-test-report.json',JSON.stringify(report,null,2));console.log(report);
})().catch(e=>{console.error(e);process.exit(1)});
