// Inert preview documents use the same layout transformation as the device.
const fs=require('fs'),vm=require('vm'),{JSDOM}=require('../tools/dom/node_modules/jsdom');
const pages=JSON.parse(fs.readFileSync(0,'utf8'));
for(const [route,html] of Object.entries(pages)){
 const dom=new JSDOM(html,{runScripts:'outside-only'});
 vm.runInContext(fs.readFileSync(__dirname+'/src/native.js','utf8'),dom.getInternalVMContext());
 dom.window.prepareNativeLayout();pages[route]=dom.serialize();dom.window.close();
}
process.stdout.write(JSON.stringify(pages));
