"""Generate a standalone preview; native forms are inert snapshots, not an ASP emulator."""
from pathlib import Path
import json,re
from bs4 import BeautifulSoup
p=Path(__file__).resolve().parent
from release import VERSION, sync_sources
sync_sources(check=True)
root=p.parent/'base/files/home/httpd/web';en=json.loads((p/'native-en.json').read_text())
css=(p/'src/native.css').read_text();pages={}
files=['status.asp','status_pon.asp','tcpiplan.asp','wanmode.asp','multi_wan_generic.asp','gpon.asp','epon.asp','vlan.asp','omci_info.asp','arptable.asp','ping.asp','saveconf.asp','password.asp','rebootTime.asp','reboot.asp','upgrade.asp','stats.asp','admin/pon-stats.asp']
for name in files:
 s=((p/'src/saveconf.asp') if name=='saveconf.asp' else root/name).read_text()
 s=re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>','',s,flags=re.I)
 s=re.sub(r'<%\s*multilang\("(\d+)"\s*"[^"\n]+"\);\s*%>',lambda m:en[int(m[1])],s)
 s=re.sub(r'<%[\s\S]*?%>','',s)
 soup=BeautifulSoup(s,'html.parser')
 if soup.body:soup.body['class']=list(soup.body.get('class',[]))+['embedded']
 for node in soup.find_all(['script','iframe','object','embed','link','base','meta']):node.decompose()
 for node in soup.find_all(True):
  for a in list(node.attrs):
   if a.lower().startswith('on') or a in ['action','formaction','src','href','target']:del node[a]
  if node.name in ['input','button','select','textarea']:node['disabled']='disabled'
  if node.name=='input' and node.get('type','text') in ['submit','button','reset']:
   node.name='button';node.string=node.get('value','');node['type']='button'
 style=soup.new_tag('style');style.string=css
 if soup.head:soup.head.append(style)
 pages['/'+name]=str(soup)
pages['/boaform/formWanRedirect?redirect-url=/multi_wan_generic.asp&if=pon']=pages['/multi_wan_generic.asp']
s=(p/'src/index.html').read_text().replace('?v='+VERSION,'').replace('<link rel="stylesheet" href="panel.css">','<style>'+(p/'src/panel.css').read_text()+'</style>')
s=s.replace('<script defer src="translations.js"></script>','<script>window.ODINativePreview='+json.dumps(pages,ensure_ascii=False).replace('</','<\\/')+';</script><script defer src="translations.js"></script>')
for file in ['translations.js','i18n.js','native-menu.js','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js','panel.js']:
 script=(p/'src'/file).read_text().replace("const preview = location.protocol", "const preview = true || location.protocol")
 s=s.replace('<script defer src="'+file+'"></script>','<script>'+script.replace('</script','<\\/script')+'</script>')
# Inline scripts were originally deferred. Move them to the end of the body.
scripts=re.findall(r'<script>[\s\S]*?</script>',s);s=re.sub(r'<script>[\s\S]*?</script>','',s)
s=s.replace('</body>', ''.join(scripts)+'</body>')
(p/'preview.html').write_text(s)
(p/'native-preview.json').write_text(json.dumps(pages,ensure_ascii=False))

# Use the same login template as both firmware routes. This preview cannot log in.
login=(p/'src/login-template.asp').read_text()
login=login.replace('<% passwd2xmit(); %>', 'return false;')
login=re.sub(r'<script src="md5.js"[^>]*></script>', '', login)
login=login.replace('action="/boaform/admin/formLogin"', 'action="#"').replace('onsubmit="setpass()"', 'onsubmit="return false"')
login=login.replace('id="submit">', 'id="submit" disabled>')
assert '<%' not in login
(p/'login-preview.html').write_text(login)
