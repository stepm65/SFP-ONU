const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const delay=()=>new Promise(r=>setTimeout(r,25));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(__dirname+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#identity',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 let answers=false,confirmations=0;w.confirm=()=>{confirmations++;return answers;};
 for(const f of ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'])vm.runInContext(fs.readFileSync(__dirname+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await delay();const loid=d.querySelector('[name=LOID]');loid.value='keep-this-draft';loid.dispatchEvent(new w.Event('input',{bubbles:true}));w.location.hash='vlan';await delay();assert.equal(w.location.hash,'#identity');assert.equal(d.querySelector('[name=LOID]'),loid);assert.equal(loid.value,'keep-this-draft');assert.equal(confirmations,1);
 answers=true;w.location.hash='vlan';await delay();assert(d.querySelector('[data-settings=vlan]'));
 assert.equal(vm.runInContext("ponStage('ONU State: 4')",c),'O4');assert.equal(vm.runInContext("ponStage('READ_ERROR rc=1 state: 5')",c),null);assert.equal(vm.runInContext("ponStage('ONU State: 5')",c),'O5');
 const raw='EntityID: 0x0101\nrule VID 100\nEntityID: 0x0202\nFilter Outer : PRI 8,VID 4095, TPID 0';w.raw=raw;assert.equal(vm.runInContext('mibRecords(window.raw).length',c),2);assert.equal(vm.runInContext('vlanRows({me_84:window.raw})[1].vid',c),4095);
 const uci=fs.existsSync(__dirname+'/work17/gpon')?fs.readFileSync(__dirname+'/work17/gpon','utf8'):String.raw`config gpon 'ploam'
 option nSerial '4142434412345678'
 option nPassword '0x30 0x31 0x32 0x33 0x34 0x35 0x36 0x37 0x38 0x39'
config gpon 'onu'
 option vendor_id 'ABCD'
 option equipment_id 'MODELX12\0\0'
 option ont_version 'HW1.0\0\0'
 option uvlan '100'`; w.uci=uci;const p=vm.runInContext('parseProfile(window.uci)',c);assert.equal(p.settings.PON_VENDOR_ID,'ABCD');assert.equal(p.settings.GPON_ONU_MODEL,'MODELX12');assert.equal(p.settings.HW_HWVER,'HW1.0');assert(/^[A-Z]{4}[A-F0-9]{8}$/.test(p.settings.GPON_SN));assert.equal(p.settings.GPON_PLOAM_PASSWD.length,20);assert.equal(p.metadata.uvlan,'100');assert(!Object.hasOwn(p.settings,'VLAN_MANU_TAG_VID'));assert(p.suggestions.includes('HW_HWVER'));
 w.DecompressionStream=global.DecompressionStream;w.TextDecoder=global.TextDecoder;
 const header=Buffer.alloc(512);header.write('etc/config/gpon');header.write(Buffer.byteLength(uci).toString(8).padStart(11,'0')+'\0',124);header[156]=48;const fixtureTar=Buffer.concat([header,Buffer.from(uci),Buffer.alloc((512-Buffer.byteLength(uci)%512)%512),Buffer.alloc(1024)]),gzPath=__dirname+'/../upload/01-GPON-KLN-RT-02.gz',gz=fs.existsSync(gzPath)?fs.readFileSync(gzPath):require('zlib').gzipSync(fixtureTar);
 w.gzFile={name:'reference.gz',size:gz.length,stream:()=>new Blob([gz]).stream()};const unpacked=await vm.runInContext('profileFileText(window.gzFile)',c);assert.equal(unpacked,uci);
 w.json=JSON.stringify({format:'odi-profile-v1',settings:{GPON_ONU_MODEL:'$(reboot)',LOID:'test',LOID_OLD:'bad',OTHER:'bad'}});const bad=vm.runInContext('parseProfile(window.json)',c);assert.equal(bad.settings.LOID,'test');assert(!Object.hasOwn(bad.settings,'LOID_OLD'));assert(bad.rejected.includes('GPON_ONU_MODEL'));
 w.xml='<Config><Dir Name="MIB_TABLE"><Value Name="LOID" Value="xml-id"/><Dir Name="SW_PORT_TBL"><Value Name="LOID" Value="wrong-chain"/></Dir></Dir></Config>';assert.equal(vm.runInContext('parseProfile(window.xml).settings.LOID',c),'xml-id');
 vm.runInContext("state.GPON_SN='SECRET12345678';state.GPON_PLOAM_PASSWD='PRIVATEPASSWORD';state.LOID_PASSWD='PASSWORD';",c);
 const exported=vm.runInContext("safeDiagnostic({me_257:'Serial Number: secret\\nHardware: test',runtime_sn:'SECRET12345678',csrf:'secret'})",c);assert(!JSON.stringify(exported).includes('SECRET'));assert(!JSON.stringify(exported).includes('PRIVATEPASSWORD'));assert(!JSON.stringify(exported).includes('PASSWORD'));assert(!exported.readings.runtime_sn);
 // Telemetry never replaces the DOM of an edited form.
 vm.runInContext("tab='overview';preview=false;state.csrf='test';",c);const form=d.querySelector('[data-settings=vlan]'),field=form.elements.VLAN_MANU_TAG_VID;field.value='777';const payload={ok:'1',pon_state:'ONU State: 4',sampled_uptime:'100',link_actual:'mode 6'};w.fetch=async()=>({ok:true,status:200,text:async()=>Object.entries(payload).map(([k,v])=>k+'='+Buffer.from(v).toString('hex')).join('\n')});await vm.runInContext('pollLive()',c);assert.equal(d.querySelector('[data-settings=vlan]'),form);assert.equal(field.value,'777');
 w.fetch=async()=>({ok:false,status:403,text:async()=> 'error='+Buffer.from('Authentication required').toString('hex')});await assert.rejects(()=>vm.runInContext("api('save',{VLAN_MANU_TAG_VID:'777'})",c));assert(d.querySelector('#auth-expired'));assert.equal(d.querySelector('[data-settings=vlan]'),form);assert.equal(field.value,'777');
 assert.equal(w.localStorage.length,0);w.close();
 fs.writeFileSync(__dirname+'/features17-test-report.json',JSON.stringify({result:'passed',environment:'jsdom and uploaded Lantiq UCI; no device writes',checks:['hash navigation cancellation keeps draft and DOM','accepted navigation proceeds','PON stage parser rejects failed read','VLAN entity and special VID parser','working GZ tar decompression and UCI SN/PLOAM mappings','Lantiq uvlan is reference only','suggested hardware mapping unchecked by default','whitelist rejects shell payload and mirrored fields','XML chain values ignored','sanitised export excludes secrets','polling preserves form DOM','auth expiry preserves edited form','no profile secrets in localStorage']},null,2));console.log('Version 1.7 profile, draft and telemetry checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
