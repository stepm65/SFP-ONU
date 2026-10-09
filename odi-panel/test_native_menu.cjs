const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const scripts=['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'];
const pause=()=>new Promise(r=>setTimeout(r,25));
async function app(hash='wan'){
 const dom=new JSDOM(fs.readFileSync(__dirname+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?preview=1#'+hash,runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext();
 w.confirm=()=>true;
 for(const f of scripts)vm.runInContext(fs.readFileSync(__dirname+'/src/'+f,'utf8').replace('const preview =','let preview ='),c);
 await pause();vm.runInContext('restartLive=()=>{};',c);
 return {w,d,c,close:()=>w.close()};
}
(async()=>{
 const {w,d,c,close}=await app();
 assert.equal(w.location.hash,'#vlan');assert(d.querySelector('[data-settings=vlan]'));
 assert(!d.querySelector('#section-nav [data-tab=wan]'));assert(!d.querySelector('iframe'));
 const requests=[];
 async function menu(html,status=200){w.fetch=async(url,init)=>{requests.push({url,...init});assert.equal(url,'/code.asp');assert(!init.method);return {ok:status===200,status,text:async()=>html};};vm.runInContext('preview=false;',c);await vm.runInContext('discoverNativeMenu()',c);}
 // M110 menu has no PON WAN even though the SDK contains its templates.
 const stock='<a target="view" href="status.asp">Status</a><a target="view" href="/tcpiplan.asp">LAN</a><a target="view" href="/gpon.asp">GPON</a><a target="view" href="/vlan.asp">VLAN</a>';
 const vlan=d.querySelector('[data-settings=vlan]'),vid=vlan.elements.VLAN_MANU_TAG_VID;vid.value='109';
 await menu(stock+'<script>var unused="/boaform/formWanRedirect?redirect-url=/multi_wan_generic.asp&if=pon";</script>');
 assert.equal(vm.runInContext('nativeWan.pon',c),null);assert.equal(vm.runInContext('nativeWan.mode',c),null);
 assert.equal(d.querySelector('[data-settings=vlan]'),vlan);assert.equal(vid.value,'109');assert(!d.querySelector('#section-nav [data-tab=wan]'));
 for(const hash of ['wan','native-wan','native-wanmode']){w.history.replaceState(null,'','#'+hash);vm.runInContext('render()',c);assert.equal(w.location.hash,'#vlan');assert(!d.querySelector('iframe'));}
 // Only an actual same-origin factory menu link enables the matching form.
 const pon='/boaform/formWanRedirect?if=pon&redirect-url=/multi_wan_generic.asp';
 await menu(stock+'<a target="view" href="'+pon.replace('&','&amp;')+'">PON WAN</a>');
 assert.equal(vm.runInContext('nativeWan.pon',c),pon);assert.equal(vm.runInContext('nativeWan.mode',c),null);assert(d.querySelector('#section-nav [data-tab=wan]'));
 w.history.replaceState(null,'','#wan');vm.runInContext('render()',c);
 assert.equal(d.querySelectorAll('iframe').length,1);assert.equal(d.querySelector('iframe').getAttribute('src'),pon);
 w.ODILang.set('en');await pause();assert(d.querySelector('#main').textContent.includes('Factory WAN sections'));assert(!/[а-яё]/i.test(d.querySelector('#main').textContent));
 // WAN Mode is enabled independently; it must not resurrect PON WAN.
 await menu(stock+'<a target="view" href="/admin/wanmode.asp">WAN Mode</a>');vm.runInContext('render()',c);
 assert.equal(vm.runInContext('nativeWan.pon',c),null);assert.equal(d.querySelectorAll('iframe').length,1);assert.equal(d.querySelector('iframe').getAttribute('src'),'/admin/wanmode.asp');
 await menu(stock+'<a target="view" href="/boaform/admin/formWanRedirect?redirect-url=/multi_wan_generic.asp&amp;if=pon">PON WAN</a>');
 assert(vm.runInContext('nativeWan.pon.endsWith("&if=pon")',c));
 // Foreign URLs and unrelated WAN media cannot enable PON forms.
 await menu(stock+'<a target="view" href="https://other.example/boaform/formWanRedirect?if=pon">PON WAN</a><a target="view" href="/boaform/formWanRedirect?if=eth">Ethernet WAN</a>');vm.runInContext('render()',c);
 assert.equal(vm.runInContext('nativeWan.pon',c),null);assert.equal(vm.runInContext('nativeWan.mode',c),null);assert.equal(w.location.hash,'#vlan');assert(!d.querySelector('iframe'));
 assert(requests.every(r=>r.url==='/code.asp'&&!r.method));close();
 for(const status of [403,404]){const a=await app();a.w.fetch=async()=>({ok:false,status});vm.runInContext('preview=false;',a.c);await vm.runInContext('discoverNativeMenu()',a.c);assert.equal(vm.runInContext('nativeWan.pon',a.c),null);assert(!a.d.querySelector('#section-nav [data-tab=wan]'));a.close();}
 fs.writeFileSync(__dirname+'/native-menu-test-report.json',JSON.stringify({result:'passed',environment:'jsdom with stock menu fixtures; no device writes',checks:['SDK templates do not enable hidden WAN forms','M110-style menu defaults to VLAN','legacy WAN bookmarks cannot load unlisted forms','stock menu discovery preserves edited form nodes','PON and WAN Mode are enabled independently by same-origin menu links','query order and administrative menu URLs preserved','WAN pages translated in RU/EN','foreign links and non-PON WAN links rejected','403 and missing-menu fallback hides forms','menu discovery performs GET only']},null,2));
 console.log('Factory-menu WAN visibility and read-only discovery checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
