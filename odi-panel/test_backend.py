#!/usr/bin/env python3
"""Exercise CGI with simulated storage; no access to an ONU."""
import json,os,subprocess,tempfile,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent
from release import VERSION
import devpath
HOST=BASE.parent
initial={'LOID_OLD':'abc','LOID_PASSWD_OLD':'pass','OMCI_TM_OPT':'2','OUI':'001122','GPON_SN':'ODIX12345678','GPON_PLOAM_FORMAT':'0','GPON_PLOAM_PASSWD':'30313233343536373839','LOID':'abc','LOID_PASSWD':'pass','PON_VENDOR_ID':'ODIX','GPON_ONU_MODEL':'DFP-34X-2C2','HW_HWVER':'V2.0','HW_SERIAL_NO':'001','OMCI_OLT_MODE':'3','OMCI_FAKE_OK':'0','OMCC_VER':'160','OMCI_SW_VER1':'OLD0','OMCI_SW_VER2':'OLD1','ELAN_MAC_ADDR':'001122334455','MAC_KEY':'0'*32,'VLAN_CFG_TYPE':'0','VLAN_MANU_MODE':'0','VLAN_MANU_TAG_VID':'100','VLAN_MANU_TAG_PRI':'0','LAN_SPEED_MODE':'1','sw_active':'0','sw_commit':'0','sw_version0':'V1.1.8','sw_version1':'stock'}
fixture='''#!/usr/bin/python3
import json,sys
from pathlib import Path
root=Path(__file__).parent
p=root/'storage.json';d=json.loads(p.read_text());a=sys.argv[1:]
with (root/'calls.log').open('a') as f:f.write(json.dumps(a)+'\\n')
if a[0] in ('get','getenv','-g'):
 if a[1] in d:
  v=d[a[1]]
  if a[1]=='OUI' and d.get('_oui_commas') and len(v)==6:v=','.join(v[i:i+2] for i in range(0,6,2))
  print(a[1]+'='+v)
 else:print('GET fail')
elif a[0] in ('set','setenv','-s'):
 if d.get('_fail')==a[1] and a[2]=='FAIL':print('write failed');sys.exit(1)
 d[a[1]]=a[2];p.write_text(json.dumps(d));print(a[1]+'='+a[2])
elif a[0]=='-of':pass
'''
def exercise(shell,label):
 with tempfile.TemporaryDirectory(dir=BASE) as temp:
  r=Path(temp);(r/'storage.json').write_text(json.dumps(initial));(r/'calls.log').touch()
  devbin=devpath.make(r)
  for cmd in ['flash','nv','xml']:(r/cmd).write_text(fixture);(r/cmd).chmod(0o755)
  (r/'modslib').write_text((BASE/'src/odi-mods-lib.sh').read_text().replace('/var/config/odi-panel-mods.conf',str(r/'mods.conf')).replace('/var/config/odi-original-omci.conf',str(r/'original-omci.conf')).replace('/etc/scripts/flash',str(r/'flash')).replace('/tmp/odi-panel',str(r/'runtime')))
  (r/'uuid').write_text('12345678-1234-1234-1234-123456789abc\n')
  (r/'version').write_text('V1.1.8-240408\n');(r/'mode').write_text('lan_sds_mode = 1\n')
  (r/'mtd').write_text('mtd4: 0014c000 00001000 "k0"\nmtd5: 00274000 00001000 "r0"\nmtd6: 0014c000 00001000 "k1"\nmtd7: 00274000 00001000 "r1"\n')
  s=(BASE/'src/api.cgi').read_text()
  replace={'/etc/scripts/odi-mods-lib.sh':str(r/'modslib'),'/tmp/odi-panel':str(r/'runtime'),'/var/config/odi-original-omci.conf':str(r/'original-omci.conf'),'/var/config/odi-invalid-bank':str(r/'invalid-bank'),'/etc/scripts/flash':str(r/'flash'),'/bin/nv':str(r/'nv'),'/bin/xmlconfig':str(r/'xml'),'/proc/sys/kernel/random/uuid':str(r/'uuid'),'/etc/version':str(r/'version'),'/proc/lan_sds/lan_sds_cfg':str(r/'mode'),'/proc/mtd':str(r/'mtd')}
  replace['PATH=/bin:/sbin:/usr/bin:/usr/sbin']='PATH='+devbin
  for a,b in replace.items():
   assert a in s,a
   s=s.replace(a,b)
  script=r/'api.cgi';script.write_text(s)
  token='12345678-1234-1234-1234-123456789abc'
  total=0
  def call(action=None,fields=None,raw=None,user='admin',csrf=token):
   nonlocal total
   body='' if action is None else 'action='+action+'\ncsrf='+csrf+'\n'+''.join(k+'='+ (v if action=='bank' else v.encode().hex())+'\n' for k,v in (fields or {}).items())
   if raw is not None:body=raw
   env=dict(os.environ,REMOTE_USER=user,REQUEST_METHOD='POST' if action else 'GET',QUERY_STRING='state',CONTENT_TYPE='text/plain',CONTENT_LENGTH=str(len(body)))
   p=subprocess.run(shell+[str(script)],input=body,text=True,capture_output=True,env=env,timeout=20)
   total+=1
   return p.stdout,p.stderr
  def store():return json.loads((r/'storage.json').read_text())
  def good(*args,**kwargs):
   o,e=call(*args,**kwargs);assert 'ok=31' in o,(o,e);return o
  def bad(*args,**kwargs):
   before=store();o,e=call(*args,**kwargs);assert 'Status: 4' in o,(o,e);assert store()==before;return o
  bad(user='');o=good();assert 'csrf='+token.encode().hex() in o and store()==initial;assert 'panel_version='+VERSION.encode().hex() in o
  bad('save',{'LAN_SPEED_MODE':'4'},csrf='wrong')
  good('save',{'LAN_SPEED_MODE':'4'});assert store()['LAN_SPEED_MODE']=='4' and 'LAN_SDS_MODE' not in store()
  bad('save',{'LAN_SPEED_MODE':'8'})
  bad('save',{'OTHER':'1'})
  bad('save',{'GPON_ONU_MODEL':'$(touch /tmp/pwn)'})
  bad('save',{'VLAN_CFG_TYPE':'1','VLAN_MANU_MODE':'1','VLAN_MANU_TAG_VID':'4095'})
  good('save',{'VLAN_CFG_TYPE':'1','VLAN_MANU_MODE':'1','VLAN_MANU_TAG_VID':'123','VLAN_MANU_TAG_PRI':'7'})
  bad('save',{'GPON_PLOAM_PASSWD':'0'*20})
  good('save',{'GPON_PLOAM_PASSWD':'0'*20,'GPON_PLOAM_FORMAT':'0'})
  good('save',{'GPON_PLOAM_PASSWD':'30313233343536373839','GPON_PLOAM_FORMAT':'1'});assert store()['GPON_PLOAM_PASSWD']=='30313233343536373839' and store()['GPON_PLOAM_FORMAT']=='1'
  bad('save',{'GPON_PLOAM_PASSWD':'0123456789','GPON_PLOAM_FORMAT':'1'})
  bad('save',{'GPON_PLOAM_FORMAT':'2'})
  good('save',{'OUI':'aabbcc'});assert store()['OUI']=='aabbcc'
  bad('save',{'OUI':'aa:bb:cc'})
  d=store();d['_oui_commas']='1';d['OUI']='001122';(r/'storage.json').write_text(json.dumps(d))
  o=good();assert 'OUI='+'001122'.encode().hex()+'\n' in o,'OUI state must be 6 hex digits'
  good('save',{'OUI':'A8B9EB'});assert store()['OUI']=='a8b9eb'
  o=good();assert 'OUI='+'a8b9eb'.encode().hex()+'\n' in o
  d=store();del d['_oui_commas'];(r/'storage.json').write_text(json.dumps(d))
  bad('save',{'OUI':'xxxxxx'})
  bad('save',{'ELAN_MAC_ADDR':'112233445566'})
  good('save',{'ELAN_MAC_ADDR':'112233445566','MAC_KEY':'f'*32})
  good('save',{'LOID':'','sw_custom_version0':'CUSTOM0','sw_custom_version1':'CUSTOM1'})
  assert store()['LOID']==store()['LOID_OLD']=='' and store()['LOID_PASSWD']==store()['LOID_PASSWD_OLD']=='pass'
  good('save',{'LOID':'new-id','LOID_PASSWD':'new-pass'});assert store()['LOID']==store()['LOID_OLD']=='new-id' and store()['LOID_PASSWD']==store()['LOID_PASSWD_OLD']=='new-pass'
  d=store();d['_fail']='LOID_PASSWD_OLD';(r/'storage.json').write_text(json.dumps(d));before=store()
  o,e=call('save',{'LOID':'changed','LOID_PASSWD':'FAIL'});assert 'Status: 500' in o and store()==before,(o,e)
  bad('save',{'OMCI_SW_VER1':'hello'})
  bad('save',raw=f'action=save\ncsrf={token}\nLAN_SPEED_MODE=34\nLAN_SPEED_MODE=36\n')
  bad('save',raw=f'action=save\ncsrf={token}\nGPON_ONU_MODEL=00\n')
  bad('bank',{'bank':'2'});good('bank',{'bank':'1'});assert store()['sw_active']=='0' and store()['sw_commit']=='1'
  (r/'invalid-bank0').touch();bad('bank',{'bank':'0'});(r/'invalid-bank0').unlink()
  d=store();d['_fail']='HW_HWVER';(r/'storage.json').write_text(json.dumps(d));before=store()
  o,e=call('save',{'GPON_ONU_MODEL':'TEST','HW_HWVER':'FAIL'});assert 'Status: 500' in o and store()==before,(o,e,store())
  # Execute boot hook against the same simulated store using the actual shell.
  boot=(BASE/'src/odi-panel-boot.sh').read_text().replace('/etc/scripts/odi-mods-lib.sh',str(r/'modslib')).replace('/etc/scripts/flash',str(r/'flash')).replace('/bin/nv',str(r/'nv')).replace('/tmp/odi-panel',str(r/'runtime'))
  (r/'boot.sh').write_text(boot)
  bootenv=dict(os.environ,PATH=devbin)
  p=subprocess.run(shell+[str(r/'boot.sh')],capture_output=True,text=True,timeout=20,env=bootenv);assert p.returncode==0,p.stderr
  assert store()['OMCI_SW_VER1']=='CUSTOM0' and store()['OMCI_SW_VER2']=='CUSTOM1'
  d=store();d['OMCI_OLT_MODE']='1';d['sw_custom_version0']='OTHER';(r/'storage.json').write_text(json.dumps(d))
  subprocess.run(shell+[str(r/'boot.sh')],check=True,timeout=20,env=bootenv);assert store()['OMCI_SW_VER1']=='CUSTOM0'
  assert (r/'original-omci.conf').read_text()=='OMCI_SW_VER1=OLD0\nOMCI_SW_VER2=OLD1\n'
  assert not (r/'original-omci.conf.new').exists(),'version backup temp file left behind'
  bad('restore_versions')
  d=store();d['OMCI_OLT_MODE']='3';(r/'storage.json').write_text(json.dumps(d))
  good('restore_versions');assert store()['OMCI_SW_VER1']=='OLD0' and store()['OMCI_SW_VER2']=='OLD1' and store()['sw_custom_version0']==''
  # Each mod can be saved alone; empty disabled VLAN controls are not required.
  good('mods',{'MOD_SPEED':'1'})
  assert not list(r.glob('mods.conf.new*')),'mod config temp file left behind'
  assert 'MOD_SPEED=1\n' in (r/'mods.conf').read_text() and 'MOD_VLAN=off\n' in (r/'mods.conf').read_text()
  assert 'MOD_SPEED\n' in (r/'runtime/pending-keys').read_text()
  good('mods',{'MOD_SWVER':'1'});assert 'MOD_SPEED=1\n' in (r/'mods.conf').read_text()
  saved=(r/'mods.conf').read_text()
  bad('mods',{});bad('mods',{'MOD_VLAN':'tag'});assert (r/'mods.conf').read_text()==saved
  settings={'MOD_SPEED':'1','MOD_SWVER':'0','MOD_VLAN':'tag','MOD_VLANS':'100 200','MOD_ENTITIES':'','MOD_FWDOP':'0x02','MOD_PAIRS':''}
  good('mods',settings);assert 'MOD_VLANS=100 200' in (r/'mods.conf').read_text()
  saved=(r/'mods.conf').read_text()
  for changes in [{'MOD_VLANS':''},{'MOD_VLANS':'100;reboot'},{'MOD_SPEED':'2'},{'MOD_ENTITIES':'$(reboot)'},{'MOD_FWDOP':'0x100'},{'MOD_VLAN':'both'}]:
   bad('mods',{**settings,**changes});assert (r/'mods.conf').read_text()==saved
  good('mods',{**settings,'MOD_VLAN':'fwdop','MOD_PAIRS':'0x0101:0x02'})
  saved=(r/'mods.conf').read_text()
  good('mods',{'MOD_SPEED':'0'});assert (r/'mods.conf').read_text()==saved.replace('MOD_SPEED=1','MOD_SPEED=0')
  saved=(r/'mods.conf').read_text()
  bad('mods',{'MOD_PAIRS':''});assert (r/'mods.conf').read_text()==saved
  bad('mods',raw=f'action=mods\ncsrf={token}\nMOD_SPEED=31\nMOD_SPEED=30\n');assert (r/'mods.conf').read_text()==saved
  good('mods',{**settings,'MOD_VLAN':'off','MOD_VLANS':''})
  return {'shell':label,'path':'device command set only (device-commands.txt)','cgi_requests':total,'boot_hook_cases':2,'result':'passed'}
results=[exercise(['/bin/sh'],'host POSIX shell')]
(BASE/'backend-test-report.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
