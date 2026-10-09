"""Read-only CGI telemetry against controlled command output; no ONU access."""
import json,os,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
from release import VERSION
import devpath
with tempfile.TemporaryDirectory(dir=P) as tmp:
 r=Path(tmp);(r/'log').touch()
 stub='''#!/usr/bin/python3
import sys,json,time
from pathlib import Path
r=Path(__file__).parent;a=sys.argv[1:]
with (r/'log').open('a') as f:f.write(json.dumps(a)+'\\n')
if 'set' in a or 'setenv' in a:sys.exit(99)
if a[:3]==['gpon','get','onu-state']:print('ONU State: 4')
elif a[:3]==['mib','get','84']:
 if len(a)==3:print('EntityID: 0x0101\\nEntityID: 0x0202')
 else:print('EntityID: '+a[3]+'\\nFwdOp: 0x02\\nrule PRI 0 VID 109\\nPassword: DO-NOT-EXPORT')
elif a[:2]==['mib','get']:
 if a[2]=='171':print('EntityID: 0x0001\\nFilter Inner : PRI 8,VID 4095, TPID 0\\nTreatment Outer : PRI 1,VID 109, TPID 4')
 else:print('No entries')
elif a[:2]==['get','loidauth']:print('LOID auth status: 0')
elif a[:2]==['get','sn']:print('Serial Number: DO-NOT-EXPORT')
elif a[0] in ['get','getenv']:print(a[1]+'=0')
else:print('value: -19.25 dBm')
'''
 for n in ['flash','nv','diag','omcicli']:(r/n).write_text(stub);(r/n).chmod(0o755)
 (r/'uuid').write_text('12345678-1234-1234-1234-123456789abc\n')
 lib=(P/'src/odi-diagnostics.sh').read_text().replace('/bin/diag',str(r/'diag')).replace('/bin/omcicli',str(r/'omcicli'))
 (r/'diagnostics.sh').write_text(lib)
 devbin=devpath.make(r)
 api=(P/'src/api.cgi').read_text().replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+devbin).replace('/tmp/odi-panel',str(r/'runtime')).replace('/etc/scripts/flash',str(r/'flash')).replace('/bin/nv',str(r/'nv')).replace('/etc/scripts/odi-diagnostics.sh',str(r/'diagnostics.sh')).replace('/proc/sys/kernel/random/uuid',str(r/'uuid')).replace('/etc/scripts/odi-mods-lib.sh',str(P/'src/odi-mods-lib.sh'))
 (r/'api.cgi').write_text(api)
 def read(query,user='admin'):
  p=subprocess.run(['/bin/sh',str(r/'api.cgi')],env={**os.environ,'REQUEST_METHOD':'GET','QUERY_STRING':query,'REMOTE_USER':user},capture_output=True,text=True,timeout=65)
  body=p.stdout.split('\n\n')[-1];result={}
  for line in body.splitlines():
   if '=' in line:
    key,h=line.split('=',1);result[key]=bytes.fromhex(h).decode()
  return p.stdout,result
 raw,out=read('diagnostics');assert out['ok']=='1';assert out['panel_version']==VERSION;assert 'VID 109' in out['me_84'] and 'FwdOp' in out['me_84'];assert out['me_84'].count('EntityID:')==2
 assert 'DO-NOT-EXPORT' not in raw and '[redacted]' in out['me_84'];assert 'ONU State: 4' in out['pon_state'];assert 'VID 4095' in out['me_171']
 commands=[json.loads(s) for s in (r/'log').read_text().splitlines()];assert all('set' not in a and 'setenv' not in a for a in commands);assert ['mib','get','84','0x0202'] in commands
 raw,out=read('operation');assert out['ok']=='1'
 raw,out=read('diagnostics','');assert '403' in raw
 (r/'runtime/write.lock').mkdir();raw,out=read('telemetry');assert '503' in raw
 (r/'runtime/firmware-phase').write_text('writing');(r/'runtime/firmware-error').write_text('READBACK')
 raw,out=read('operation');assert out['ok']=='1' and out['firmware_phase']=='writing' and out['firmware_error']=='READBACK'
 (r/'runtime/write.lock').rmdir()
 raw,out=read('mib=84;reboot');assert '400' in raw
 # A failed command has a bounded wait and an explicit error marker.
 (r/'diag').write_text('#!/bin/sh\nsleep 10\n');(r/'diag').chmod(0o755)
 raw,out=read('telemetry');assert out['panel_version']==VERSION;assert 'READ_ERROR' in out.get('pon_state',''),(raw,out)
 report={'result':'passed','scope':'host shell; fixed command fixtures; no device writes','checks':['ME enumeration and per-entity attributes','VLAN 109 and special VID preserved','serial/password redaction','no settings writes','authentication guard','write-lock guard','unknown queries rejected','bounded failed reads','operation status endpoint']}
 (P/'diagnostics-test-report.json').write_text(json.dumps(report,indent=2));print('Diagnostics read and redaction checks passed')
