// Visual regression on assets extracted from built SquashFS images.
// ASP values are synthetic and factory initializers are inert; this is not a Boa/ONU test.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright');
const p=__dirname,build=path.resolve(process.argv[2]),baseline=process.argv[3]&&path.resolve(process.argv[3]);
const version=fs.readFileSync(p+'/VERSION','utf8').trim(),en=JSON.parse(fs.readFileSync(p+'/native-en.json'));
function readBuild(dir){
 const raw=fs.readFileSync(dir+'/verified.pseudo'),marker=Buffer.from('#\n# START OF DATA - DO NOT MODIFY\n#\n'),split=raw.indexOf(marker),blob=raw.subarray(split+marker.length),files=new Map();
 for(const line of raw.subarray(0,split).toString().split('\n')){
  const a=line.split(/\s+/);if(a[1]==='R'&&a[0].startsWith('home/httpd/web/'))files.set('/'+a[0].slice(15),blob.subarray(+a[7],+a[7]+ +a[6]));
 }
 return files;
}
function renderASP(raw){return raw.toString()
 .replace(/<%\s*multilang\("(\d+)"\s*"[^"\n]+"\);\s*%>/g,(_,n)=>en[+n]||'')
 .replace(/<%\s*getInfo\("name"\);\s*%>/g,'Example ONU')
 .replace(/<%\s*cpuUtility\(\);\s*%>/g,'<tr bgcolor="#ddd"><td width="40%"><b>CPU Usage</b></td><td>1%</td></tr>')
 .replace(/<%\s*memUtility\(\);\s*%>/g,'<tr bgcolor="#ddd"><td width="40%"><b>Memory Usage</b></td><td>49%</td></tr>')
 .replace(/<%[\s\S]*?%>/g,'0')
 .replace(/<script\b(?![^>]*\bsrc\s*=)[^>]*>[\s\S]*?<\/script\s*>/gi,'')
 .replace(/\bonload\s*=\s*"[^"]*"/gi,'');}
let files,servedVersion;const requests=[];
const server=http.createServer((req,res)=>{
 if(req.method!=='GET'){res.writeHead(405);return res.end('Read-only visual fixture');}
 const url=new URL(req.url,'http://localhost');requests.push(url.pathname);let data=files.get(url.pathname),type;
 if(url.pathname==='/preview.html')data=fs.readFileSync(p+'/preview.html');
 if(url.pathname==='/code.asp')data='<html></html>';
 if(url.pathname==='/panel/api.cgi'){type='text/plain';data=Object.entries({ok:'1',csrf:'fixture',panel_version:servedVersion,pending:'0',sw_active:'0',sw_commit:'0'}).map(([k,v])=>k+'='+Buffer.from(v).toString('hex')).join('\n');}
 if(data===undefined){res.writeHead(404);return res.end('Missing fixture');}
 if(url.pathname.endsWith('.asp'))data=renderASP(data);
 res.setHeader('Content-Type',type||(url.pathname.endsWith('.css')?'text/css':url.pathname.endsWith('.js')?'application/javascript':'text/html; charset=utf-8'));res.end(data);
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_BIN});
 const checks=[],output=process.env.ODI_SCREENSHOT_DIR&&path.resolve(process.env.ODI_SCREENSHOT_DIR);if(output)fs.mkdirSync(output,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});await page.addInitScript(()=>localStorage.setItem('odi-panel-language','ru'));
  async function open(dir,v,section){files=readBuild(dir);servedVersion=v;await page.goto(origin+'/panel/index.html?v='+v+'#native-'+section);const frame=page.frameLocator('.native-frame');await frame.locator('table').first().waitFor({state:'attached'});await page.waitForTimeout(150);return frame;}
  if(baseline){const frame=await open(baseline,'1.9.9','status'),cell=frame.locator('td').filter({hasText:'Example ONU'});const font=await cell.evaluate(e=>getComputedStyle(e).fontSize);assert.equal(font,'16px','reproduce reported large legacy table text');checks.push({baseline:'1.9.9',tableFont:font});if(output)await page.screenshot({path:output+'/before.png',fullPage:true});}
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1000});
   for(const mode of ['compact','diagnostic']){
   for(const section of ['status','pon','lan','arp','ping','stats','pon-stats','password','timer']){
    const frame=await open(build,version,section);await frame.locator('.native-table').first().waitFor({state:'attached'});
    await page.locator('[data-layout-choice='+mode+']').click();await page.waitForTimeout(100);
    const metrics=await frame.locator('body').evaluate(body=>{const data=body.querySelector('.native-properties')||body.querySelector('table'),cell=data.querySelector('td,th');return {mode:document.compatMode,font:getComputedStyle(cell).fontSize,family:getComputedStyle(cell).fontFamily,available:body.clientWidth-parseFloat(getComputedStyle(body).paddingLeft)-parseFloat(getComputedStyle(body).paddingRight),tableWidth:data.getBoundingClientRect().width,overflow:document.documentElement.scrollWidth>innerWidth,oldFills:body.querySelectorAll('tr[bgcolor],td[bgcolor],th[bgcolor]').length};});
    assert.equal(metrics.mode,'CSS1Compat',section);assert.equal(metrics.font,'12px',section);assert(metrics.family.includes('Segoe UI'),section);assert.equal(metrics.oldFills,0,section);assert.equal(metrics.overflow,false,section+' child overflow');assert(Math.abs(metrics.tableWidth-metrics.available)<3,section+' full-width table');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),section+' shell overflow');
    const height=await page.locator('.native-frame').evaluate(e=>e.clientHeight);await page.waitForTimeout(200);assert.equal(await page.locator('.native-frame').evaluate(e=>e.clientHeight),height,section+' stable frame height');
    checks.push({width,mode,section,...metrics});if(output&&['status','lan','password'].includes(section))await page.screenshot({path:output+'/'+section+'-'+mode+'-'+width+'.png',fullPage:true});
   }
   }
  }
  await page.goto(origin+'/preview.html#native-status');const preview=page.frameLocator('.native-frame');await preview.locator('.native-properties').first().waitFor();
  assert.equal(await preview.locator('.native-properties td').first().evaluate(e=>getComputedStyle(e).fontSize),'12px');
  assert.equal(await preview.locator('tr[bgcolor],td[bgcolor],table[width]').count(),0);
  fs.writeFileSync(p+'/native-browser-test-report.json',JSON.stringify({result:'passed',version,scope:'Chromium on built assets; ASP values mocked, factory inline initializers disabled; no physical ONU, Boa or form submission test',browser:browser.version(),checks,standalonePreview:'same 12px typography and normalized tables',requestsOnlyGET:true},null,2));console.log('Built native pages: baseline reproduction,',checks.length-1,'desktop/mobile checks and standalone preview passed');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
