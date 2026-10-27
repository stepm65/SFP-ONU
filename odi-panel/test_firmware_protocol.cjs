const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
(async()=>{
 const p=__dirname,dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#firmware',runScripts:'outside-only'}),w=dom.window,c=dom.getInternalVMContext();
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8'),c);
 await new Promise(r=>setTimeout(r,25));
 let requests=[],samples=[{firmware_phase:'checking',firmware_status:'CHECKING bank=1',firmware_worker_alive:'1'},{firmware_phase:'writing',firmware_status:'WRITING bank=1',firmware_worker_alive:'1'},{firmware_phase:'verified',firmware_status:'VERIFIED bank=1'}];
 w.samples=samples;vm.runInContext("readApi=async q=>{if(q!=='operation')throw Error(q);return window.samples.shift();}",c);
 w.XMLHttpRequest=class{constructor(){this.upload={};}open(method,url){assert.equal(url,'/panel/upload.cgi');assert.equal(method,'POST');}setRequestHeader(){}send(){this.status=200;this.responseText='protocol=3\naccepted=1\nbank=1\nok=1\n';this.onload();}};
 w.events=[];const result=await vm.runInContext("sendFirmware(new Blob(['test']),'1',(k,v)=>window.events.push([k,v]),()=>{})",c);
 assert.equal(result.bank,'1');assert.deepEqual([...w.events.filter(x=>x[0]==='phase').map(x=>x[1])],['checking','writing','verified']);assert.equal(samples.length,0);
 vm.runInContext("readApi=async()=>({firmware_phase:'checking',firmware_status:'CHECKING bank=1',firmware_worker_alive:'0'})",c);
 await assert.rejects(vm.runInContext("monitorFirmware('1',()=>{})",c));
 vm.runInContext("state.firmware_status='WRITING bank=1';state.firmware_phase='readback';render()",c);assert(w.document.getElementById('resume-update'));assert(w.document.querySelector('#upload button[type=submit]').disabled);
 w.close();const report={result:'passed',scope:'jsdom + mocked XHR/worker status',checks:['accepted upload is not treated as verified flash','background phases are polled to verified bank','dead worker cannot report success','reload exposes resume monitoring and blocks duplicate upload']};fs.writeFileSync(p+'/firmware-protocol-test-report.json',JSON.stringify(report,null,2));console.log(report);
})().catch(e=>{console.error(e);process.exit(1)});
