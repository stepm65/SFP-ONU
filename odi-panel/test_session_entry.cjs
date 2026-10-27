const fs=require('fs'),vm=require('vm'),assert=require('assert'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const files=['translations.js','i18n.js','native-menu.js','mods.js','uplink.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js'];
(async()=>{
 const p=__dirname,dom=new JSDOM(fs.readFileSync(p+'/src/index.html','utf8'),{url:'http://onu/panel/index.html?v=1.9.11#native-password',runScripts:'outside-only'}),w=dom.window,d=w.document,c=dom.getInternalVMContext(),urls=[];
 w.fetch=async url=>{urls.push(url);if(url==='/code.asp')return {ok:true,text:async()=>'<a target="view" href="/admin/logout.asp">Logout</a><a target="view" href="/multi_lang.asp">Language</a><a target="view" href="/password.asp">Password</a>'};return {ok:false,status:403,text:async()=>''};};
 for(const f of files)vm.runInContext(fs.readFileSync(p+'/src/'+f,'utf8'),c);
 await new Promise(r=>setTimeout(r,40));
 assert.equal(w.location.pathname,'/');assert.equal(w.location.search,'');assert.equal(w.location.hash,'#native-password');
 assert(urls.includes('/panel/api.cgi?state'));assert(d.querySelector('#auth-expired'));
 const signin=d.getElementById('sign-in');assert.equal(signin.getAttribute('href'),'/');assert.equal(signin.target,'_blank');
 await vm.runInContext('discoverNativeMenu()',c);
 assert(!d.querySelector('#section-nav [data-native=language]'));assert(!d.querySelector('#section-nav a[href*=logout]'));
 assert(d.querySelector('#logout'));assert(d.querySelector('#language'));
 const scripts=[...d.querySelectorAll('script[src]')].map(s=>s.getAttribute('src'));assert(scripts.every(s=>s.startsWith('/panel/')));assert(d.querySelector('link[rel=stylesheet]').getAttribute('href').startsWith('/panel/'));
 // A new sign-in can be checked without replacing any open form.
 d.getElementById('main').insertAdjacentHTML('beforeend','<input id="draft" value="unsaved">');const draft=d.getElementById('draft');
 w.fetch=async url=>{assert.equal(url,'/panel/api.cgi?state');return {ok:true,status:200,text:async()=> 'ok=31'};};
 await d.getElementById('retry-auth').onclick();assert.equal(d.getElementById('draft'),draft);assert.equal(draft.value,'unsaved');
 w.close();const report={result:'passed',scope:'jsdom, expired-session HTTP responses simulated; no physical Boa timeout test',checks:['old versioned deep link canonicalises to native root entry','all assets/CGI use absolute panel paths','expired-session sign-in banner survives initial load failure','reauthentication uses root in another tab and preserves draft','System omits language/logout duplicates; topbar controls remain']};fs.writeFileSync(p+'/session-entry-test-report.json',JSON.stringify(report,null,2));console.log(report);
})().catch(e=>{console.error(e);process.exit(1)});
