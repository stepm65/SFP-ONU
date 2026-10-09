const {JSDOM}=require('../tools/dom/node_modules/jsdom'),fs=require('fs'),assert=require('assert');
(async()=>{
 const errors=[];const dom=new JSDOM(fs.readFileSync(__dirname+'/preview.html','utf8'),{url:'file:///preview.html',runScripts:'dangerously',beforeParse(w){w.addEventListener('error',e=>errors.push(e.message));}});
 await new Promise(r=>setTimeout(r,50));const w=dom.window,d=w.document;
 assert.equal(d.querySelector('h1').textContent,w.ODILang.get()==='ru'?'Управление ONU':'ONU management');
 w.location.hash='native-lan';await new Promise(r=>setTimeout(r,30));assert(d.querySelector('iframe[srcdoc]'));assert(d.querySelector('iframe').getAttribute('srcdoc').includes('name="ip"'));
 const pages=JSON.parse(fs.readFileSync(__dirname+'/native-preview.json'));
 for(const [name,s] of Object.entries(pages)){const doc=new JSDOM(s).window.document;assert(!doc.querySelector('script,[action],[formaction],[href],[src]'),name);for(const e of doc.querySelectorAll('input,select,button,textarea'))assert(e.disabled,name);for(const e of doc.querySelectorAll('*'))assert(!Array.from(e.attributes).some(a=>a.name.startsWith('on')),name);}
 assert.deepEqual(errors,[]);w.close();console.log('Standalone preview and inert native snapshots passed');
})().catch(e=>{console.error(e);process.exit(1)});
