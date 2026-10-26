const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {JSDOM}=require('../tools/dom/node_modules/jsdom');
const pause=()=>new Promise(r=>setTimeout(r,20));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(__dirname+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#profiles',runScripts:'outside-only'});
 const w=dom.window,d=w.document,c=dom.getInternalVMContext();w.confirm=()=>true;
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(__dirname+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await pause();
 let writes=[];w.fetch=async()=>{throw new Error('Preparing a profile must not access the device');};
 const before=vm.runInContext('JSON.stringify(state)',c);
 d.getElementById('prepare-eltex-profile').click();
 assert.equal(vm.runInContext('JSON.stringify(state)',c),before);
 const preset=JSON.parse(vm.runInContext('JSON.stringify(importedProfile)',c));
 assert.deepEqual(preset.settings,{OMCI_OLT_MODE:'0',OMCI_FAKE_OK:'0',VLAN_CFG_TYPE:'0'});
 assert.deepEqual(preset.mods,{MOD_SWVER:'0',MOD_VLAN:'off'});
 for(const key of ['GPON_SN','GPON_PLOAM_PASSWD','LOID','ELAN_MAC_ADDR','MAC_KEY','PON_VENDOR_ID','GPON_ONU_MODEL','HW_HWVER','OMCI_TM_OPT','OMCC_VER','LAN_SPEED_MODE'])assert(!Object.hasOwn(preset.settings,key));
 vm.runInContext("preview=false;state.OMCI_OLT_MODE='3';state.OMCI_FAKE_OK='1';state.VLAN_CFG_TYPE='1';state.MOD_VLAN='tag';state.MOD_SWVER='1';state.MOD_VLANS='200';paintProfile();",c);
 const identity=vm.runInContext('JSON.stringify(Object.fromEntries([...privateProfileKeys,"PON_VENDOR_ID","GPON_ONU_MODEL","LAN_SPEED_MODE"].map(k=>[k,state[k]])))',c);
 w.calls=writes;
 vm.runInContext("api=async(action,fields)=>{window.calls.push({action,fields:JSON.parse(JSON.stringify(fields))});Object.assign(state,fields);return {ok:'1'};};load=async()=>{};",c);
 // Opt out of changing VLAN source; only checked settings should be written.
 d.querySelector('[data-profile-key="VLAN_CFG_TYPE"]').checked=false;
 await vm.runInContext('applyProfile()',c);
 assert.deepEqual(JSON.parse(JSON.stringify(writes[0])),{action:'save',fields:{OMCI_OLT_MODE:'0',OMCI_FAKE_OK:'0'}});
 assert.equal(writes[1].action,'mods');assert.equal(writes[1].fields.MOD_VLAN,'off');assert.equal(writes[1].fields.MOD_SWVER,'0');assert.equal(writes[1].fields.MOD_VLANS,'200');
 assert.equal(vm.runInContext('JSON.stringify(Object.fromEntries([...privateProfileKeys,"PON_VENDOR_ID","GPON_ONU_MODEL","LAN_SPEED_MODE"].map(k=>[k,state[k]])))',c),identity);
 assert.equal(vm.runInContext('state.VLAN_CFG_TYPE',c),'1');
 vm.runInContext("ponHistory=[];lastObservedUptime=null;recordPonObservation({pon_state:'O5',sampled_uptime:'100'});recordPonObservation({pon_state:'O5',sampled_uptime:'110'});recordPonObservation({pon_state:'O5',sampled_uptime:''});recordPonObservation({pon_state:'O5',sampled_uptime:'5'});",c);
 const history=JSON.parse(vm.runInContext('JSON.stringify(ponHistory)',c));
 assert.equal(history.length,3);assert.equal(history[1].event,'uptime_reset');assert.equal(history[1].previous_uptime,'110');assert.equal(history[2].stage,'O5');
 vm.runInContext("recordPonObservation({pon_state:'O5',sampled_uptime:'10',pon_state_end:'O2',sampled_uptime_end:'12'});",c);
 assert.equal(vm.runInContext('ponHistory.at(-1).stage',c),'O2');
 assert.equal(vm.runInContext("latestReadings({pon_state:'O5',pon_state_end:'O2'}).pon_state",c),'O2');
 // Timer is read from the verified native form; login/error pages are not zero.
 for(const [html,expected] of [
  ['<form name="rebootTime"><input name="time" value="1"></form>','1'],
  ['<form name="rebootTime"><input name="time" value="00"></form>','0'],
  ['<form name="login"><input name="time" value="0"></form>','unavailable'],
  ['<form name="rebootTime"><input name="time" value="-1"></form>','unavailable']
 ]){w.fetch=async(url,opts)=>{assert.equal(url,'/rebootTime.asp');assert(!opts.method);return {ok:true,text:async()=>html};};assert.equal(await vm.runInContext('readRebootTimer()',c),expected);}
 w.fetch=async()=>{throw new Error('offline');};assert.equal(await vm.runInContext('readRebootTimer()',c),'unavailable');
 const report=vm.runInContext("safeDiagnostic({me_256:'SerialNum: PRIVATE\\nVendorId: TEST',me_47:'TPType: 1',reboot_timer_minutes:'1',DEVICE_TYPE:'0',pon_state:'O5',pon_state_end:'O2',sampled_uptime_end:'120',collection_incomplete:'1'})",c);
 assert(!JSON.stringify(report).includes('PRIVATE'));assert.equal(report.readings.me_47,'TPType: 1');assert.equal(report.readings.pon_state_end,'O2');assert.equal(report.readings.DEVICE_TYPE,'0');assert.equal(report.readings.reboot_timer_minutes,'1');
 const html=vm.runInContext("diagnosticTables({collection_incomplete:'1',reboot_timer_minutes:'unavailable',me_11:'EntityID: 0x0101',me_47:'EntityID: 0x0101',me_329:'No entries'})",c);
 assert(html.includes('ME 11')&&html.includes('ME 47')&&html.includes('ME 329'));assert(html.includes('rebootTime.asp'));
 w.close();
 fs.writeFileSync(__dirname+'/eltex198-test-report.json',JSON.stringify({result:'passed',scope:'jsdom; simulated API; no ONU/OLT hardware test',checks:['preset preparation has no device writes','only selected fields saved; credentials and port identity preserved','same O5 across reboot records uptime reset','empty uptime does not imply reboot','final state used after long collection','native timer read is read-only; unavailable differs from disabled','expanded MIB export redacts SerialNum','topology and incomplete collection are visible']},null,2));
 console.log('Eltex preset and disconnect diagnostics checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
