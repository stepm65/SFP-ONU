import os,json,subprocess,tempfile
import devpath
from pathlib import Path
P=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(dir=P) as tmp:
 r=Path(tmp);store=r/'values.json';log=r/'calls.jsonl';devbin=devpath.make(r)
 fixture='''#!/usr/bin/python3
import sys,json
from pathlib import Path
r=Path(__file__).parent;a=sys.argv[1:];d=json.loads((r/'values.json').read_text());name=Path(sys.argv[0]).name
if name in ('flash','nv'):
 if a[0] in ('get','getenv'):print(a[1]+'='+d.get(a[1],''))
 else:d[a[1]]=a[2];(r/'values.json').write_text(json.dumps(d))
elif name=='diag':
 if d.get('_diag_fail') in a:sys.exit(7)
 with (r/'calls.jsonl').open('a') as f:f.write(json.dumps(a)+'\\n')
elif name=='omcicli':
 if a[:3]==['mib','get','84']:
  if len(a)==3:print('EntityID: 0x0101\\nEntityID: 0x0202')
  else:print('FwdOp: '+d.get(a[3],'0x01')+'\\n rule VID '+('100' if a[3]=='0x0101' else '200'))
 else:
  with (r/'calls.jsonl').open('a') as f:f.write(json.dumps(a)+'\\n')
'''
 for n in ['flash','nv','diag','omcicli']:(r/n).write_text(fixture);(r/n).chmod(0o755)
 def run(name,values,env=None,expected_rc=0):
  store.write_text(json.dumps(values));log.write_text('')
  s=(P/'src/anime'/name).read_text().replace('/etc/scripts/flash',str(r/'flash')).replace('/bin/nv',str(r/'nv')).replace('/bin/diag',str(r/'diag'))
  script=r/name;script.write_text(s)
  result=subprocess.run(['/bin/sh',str(script)],check=False,env={**os.environ,'PATH':str(r)+':'+devbin,**(env or {})},capture_output=True)
  assert result.returncode==expected_rc,(name,result.returncode,result.stderr)
  return [json.loads(l) for l in log.read_text().splitlines()],json.loads(store.read_text())
 calls,_=run('fix_speed.sh',{'LAN_SPEED_MODE':'1'});assert not calls
 calls,_=run('fix_speed.sh',{'LAN_SPEED_MODE':'6'});assert len(calls)==2 and all(c[-1]=='4194296' for c in calls)
 calls,_=run('fix_speed.sh',{'LAN_SPEED_MODE':'6','_diag_fail':'egress'},expected_rc=1);assert len(calls)==1
 _,v=run('fix_sw_ver.sh',{'OMCI_OLT_MODE':'3','sw_custom_version0':'CUSTOM','sw_version1':'FALLBACK'});assert v['OMCI_SW_VER1']=='CUSTOM' and v['OMCI_SW_VER2']=='FALLBACK'
 _,v=run('fix_sw_ver.sh',{'OMCI_OLT_MODE':'0','sw_custom_version0':'CUSTOM'});assert 'OMCI_SW_VER1' not in v
 env={'MOD_VLANS':'100','MOD_ENTITIES':'','MOD_FWDOP':'0x02'}
 calls,_=run('fix_vlan_tag.sh',{},env);assert len(calls)==1 and calls[0][3]=='0x0101'
 calls,_=run('fix_vlan_tag.sh',{'0x0101':'0x02'},env);assert not calls
 calls,_=run('fix_vlan_tag.sh',{},dict(env,MOD_VLANS='',MOD_ENTITIES='0x0202'));assert len(calls)==1 and calls[0][3]=='0x0202'
 calls,_=run('fix_vlan_fwdop.sh',{}, {'MOD_PAIRS':'0x0202:0x03'});assert len(calls)==1 and calls[0][3:] == ['0x0202','FwdOp','0x03']
 calls,_=run('fix_vlan_fwdop.sh',{}, {'MOD_PAIRS':'0x010:0x03'});assert not calls
 # The speed job must run independently of disabled or invalid VLAN settings.
 (r/'modslib').write_text((P/'src/odi-mods-lib.sh').read_text().replace('/var/config/odi-panel-mods.conf',str(r/'mods.conf')).replace('/tmp/odi-panel',str(r/'runtime')))
 runner=(P/'src/odi-mods-run.sh').read_text().replace('/etc/scripts/odi-mods-lib.sh',str(r/'modslib')).replace('/etc/scripts/fix_speed.sh',str(r/'fix_speed.sh')).replace('/tmp/odi-mods-running',str(r/'running')).replace('/tmp/odi-panel',str(r/'runtime')).replace('sleep 5',':').replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+str(r)+':'+devbin)
 (r/'runner.sh').write_text(runner)
 (r/'fix_speed.sh').chmod(0o755)
 for mode,expected in [('off',0),('fwdop',1)]:
  (r/'mods.conf').write_text('MOD_SPEED=1\nMOD_VLAN='+mode+'\nMOD_PAIRS=invalid-filter\nMOD_VLANS=invalid-filter\n')
  store.write_text(json.dumps({'LAN_SPEED_MODE':'6'}));log.write_text('')
  proc=subprocess.run(['/bin/sh',str(r/'runner.sh')],capture_output=True,timeout=15)
  assert not (r/'running').exists(),'runner lock directory not removed on exit'
  assert proc.returncode==expected,(mode,proc.returncode,proc.stderr)
  calls=[json.loads(l) for l in log.read_text().splitlines()]
  assert len(calls)==2 and all(c[-1]=='4194296' for c in calls)
  assert 'speed=0' in (r/'runtime/mods-status').read_text()
 logtest=r/'logtest.sh';logtest.write_text('. '+str(r/'modslib')+'\ni=0\nwhile [ $i -lt 45 ]; do mod_log "line $i"; i=$((i+1)); done\n')
 proc=subprocess.run(['/bin/sh',str(logtest)],capture_output=True,timeout=30,env={**os.environ,'PATH':devbin})
 assert proc.returncode==0,proc.stderr
 lines=(r/'runtime/mods.log').read_text().splitlines();assert len(lines)==40 and lines[-1].endswith('line 44') and lines[0].endswith('line 5'),lines[:2]
 assert not (r/'runtime/mods.log.new').exists(),'mod log temp file left behind'
 report={'result':'passed','cases':14,'path':'device command set only (device-commands.txt)','environment':'host POSIX shell; mocked flash/nv/diag/omcicli','checks':['LAN_SPEED_MODE only; two rate commands in mode 6','OMCI custom/fallback and mode guard','VLAN and entity filtering','skip equal FwdOp','exact entity matching, no substring writes','speed runs with disabled malformed VLAN filters','speed runs before rejection of an invalid active VLAN filter']}
 (P/'mods-test-report.json').write_text(json.dumps(report,indent=2));print(report)
