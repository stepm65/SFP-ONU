"""Actual asynchronous upload/worker on regular-file MTD fixtures; no device access."""
from pathlib import Path
import hashlib,io,json,os,shlex,subprocess,sys,tarfile,tempfile,time
import devpath
P=Path(__file__).resolve().parent
with tarfile.open(P.parent/'firmware/original/M110_sfp_ODI_SFU_240408.tar') as t:base={n:t.extractfile(n).read() for n in t.getnames()}
def archive(changes=None,extra=None):
 d={**base,**(changes or {})};d['md5.txt']=''.join(hashlib.md5(d[n]).hexdigest()+'  '+n+'\n' for n in ['fwu.sh','rootfs','uImage','fwu_ver','hw_ver']).encode();out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for n,v in list(d.items())+(extra or []):i=tarfile.TarInfo(n);i.size=len(v);t.addfile(i,io.BytesIO(v))
 return out.getvalue()
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);state=r/'state';state.mkdir();config=r/'config';config.mkdir();dev=r/'dev';dev.mkdir();bin=r/'bin';bin.mkdir();path=str(bin)+':'+devpath.make(r);store=r/'nv.json'
 store.write_text(json.dumps({'sw_active':'0','sw_commit':'0','sw_version0':'OLD','sw_version1':'OLD'}));(state/'token').write_text('abc-token')
 layout='dev: size erasesize name\n'+''.join(f'mtd{i+4}: {size} 00001000 "{name}"\n' for i,(name,size) in enumerate([('k0','0014c000'),('r0','00274000'),('k1','0014c000'),('r1','00274000')]))
 (r/'mtd').write_text(layout)
 for i in range(4,8):(dev/f'mtd{i}').write_bytes(b'ORIGINAL'+bytes([i]))
 (bin/'nv').write_text('''#!/usr/bin/python3
import json,sys
from pathlib import Path
p=Path(__file__).parent.parent/'nv.json';d=json.loads(p.read_text());a=sys.argv[1:]
if a[0]=='getenv':print(a[1]+'='+d[a[1]])
else:d[a[1]]=a[2];p.write_text(json.dumps(d))
''');(bin/'nv').chmod(0o755)
 (bin/'cmp').write_text('''#!/usr/bin/python3
import sys
from pathlib import Path
a,b=sys.argv[1:];x=sys.stdin.buffer.read() if a=='-' else Path(a).read_bytes();y=sys.stdin.buffer.read() if b=='-' else Path(b).read_bytes()
if x==y:sys.exit(0)
if x==y[:len(x)]:print('cmp: EOF on '+a,file=sys.stderr)
elif y==x[:len(y)]:print('cmp: EOF on '+b,file=sys.stderr)
else:print('files differ')
sys.exit(1)
''');(bin/'cmp').chmod(0o755)
 (r/'starter').write_text('''#!/usr/bin/python3
import sys,json,tarfile,time
from pathlib import Path
r=Path(__file__).parent;b=int(sys.argv[1]);mode=(r/'mode').read_text() if (r/'mode').exists() else ''
assert not (r/'state/write.lock/rootfs').exists() and not (r/'state/write.lock/uImage').exists()
print('Updating image',b,flush=True);(r/'writes').write_text(str(b))
if mode=='fail':sys.exit(1)
if mode=='pause':
 (r/'ready').touch();end=time.monotonic()+90
 while not (r/'continue').exists():
  if time.monotonic()>end:sys.exit(2)
  time.sleep(0.05)
with tarfile.open(sys.argv[2]) as t:
 for name,index in [('uImage',4),('rootfs',5)]:
  payload=t.extractfile(name).read()
  if mode=='corrupt' and name=='rootfs':payload=b'BROKEN'+payload[6:]
  (r/'dev'/('mtd'+str(index+2*b))).write_bytes(payload+b'\\xff'*64)
 p=r/'nv.json';d=json.loads(p.read_text());d['sw_version'+str(b)]=t.extractfile('fwu_ver').read().decode().strip();p.write_text(json.dumps(d))
''');(r/'starter').rename(r/'starter.py');(r/'starter').write_text('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(r/'starter.py'))+' "$@"\n');(r/'starter').chmod(0o755)
 replacements={'PATH=/bin:/sbin:/usr/bin:/usr/sbin':'PATH='+path,'STATE=/tmp/odi-panel':'STATE='+str(state),'NV=/bin/nv':'NV='+str(bin/'nv'),'MTD=/proc/mtd':'MTD='+str(r/'mtd'),'DEV=/dev':'DEV='+str(dev),'CONFIG=/var/config':'CONFIG='+str(config),'/etc/scripts/odi-fw-lib.sh':str(r/'lib.sh'),'/etc/scripts/odi-firmware-worker.sh':str(r/'worker.sh'),'/etc/scripts/odi-fw-stream.sh':str(r/'stream.sh'),'/etc/scripts/odi-fw-compare.sh':str(r/'compare.sh'),'/etc/scripts/fwu_starter.sh':str(r/'starter'),'[ -c "$DEV/$dev" ]':'[ -f "$DEV/$dev" ]','/tmp/odi-debug/running':str(r/'private-running'),'/tmp/odi-debug/starting':str(r/'private-starting')}
 for name,out in [('odi-fw-lib.sh','lib.sh'),('odi-fw-stream.sh','stream.sh'),('odi-fw-compare.sh','compare.sh'),('odi-firmware-worker.sh','worker.sh'),('upload.cgi','upload.cgi')]:
  text=(P/'src'/name).read_text()
  for a,b in replacements.items():text=text.replace(a,b)
  (r/out).write_text(text)
 def send(data=None,bank='1',token='abc-token',extra=None):
  payload=archive() if data is None else data;body=f'csrf={token}\nbank={bank}\n'.encode()+payload
  env={**os.environ,'REMOTE_USER':'admin','REQUEST_METHOD':'POST','CONTENT_TYPE':'application/octet-stream','CONTENT_LENGTH':str(len(body)),**(extra or {})}
  return subprocess.run(['/bin/sh',str(r/'upload.cgi')],input=body,capture_output=True,env=env,timeout=45*devpath.HOST_TIMEOUT_SCALE)
 def finish():
  until=time.monotonic()+90*devpath.HOST_TIMEOUT_SCALE
  while (state/'write.lock').exists():
   assert time.monotonic()<until,'worker timeout';time.sleep(0.05)
  return (state/'firmware-phase').read_text(),(state/'firmware-error').read_text()
 def case(name,data=None,error=None,mode=None):
  before=[(dev/f'mtd{i}').read_bytes() for i in range(4,8)];(r/'writes').unlink(missing_ok=True)
  if mode:(r/'mode').write_text(mode)
  else:(r/'mode').unlink(missing_ok=True)
  response=send(data);assert b'accepted=1' in response.stdout,(name,response.stdout,response.stderr)
  phase,actual=finish()
  if error:assert phase=='failed' and actual==error,(name,phase,actual,(state/'firmware-worker.log').read_text())
  else:assert phase=='verified',(name,phase,actual,(state/'firmware-worker.log').read_text())
  assert (dev/'mtd4').read_bytes()==before[0] and (dev/'mtd5').read_bytes()==before[1],name
  assert json.loads(store.read_text())['sw_active']==json.loads(store.read_text())['sw_commit']=='0'
  if error and mode not in ['corrupt','fail']:assert not (r/'writes').exists(),name
  checks.append(name)
 case('valid TAR verified in background without extracting kernel/rootfs')
 if len(sys.argv)>1:
  release=Path(sys.argv[1]).resolve()
  case('built release TAR verified in background',release.read_bytes())
 for name,kwargs in [('no authentication',{'extra':{'REMOTE_USER':''}}),('bad CSRF',{'token':'wrong'}),('active bank',{'bank':'0'}),('truncated body',{'extra':{'CONTENT_LENGTH':str(len(archive())+100)}})]:
  proc=send(**kwargs);assert b'accepted=1' not in proc.stdout and proc.returncode!=0,(name,proc.stdout);checks.append(name)
 (r/'private-running').mkdir();assert b'error=DEBUG_ACTIVE' in send().stdout;(r/'private-running').rmdir();checks.append('active private capture blocks update')
 (r/'private-starting').mkdir();assert b'error=DEBUG_ACTIVE' in send().stdout;(r/'private-starting').rmdir();checks.append('private capture preparation blocks update')
 bad=bytearray(base['uImage']);bad[128]^=1
 case('modified pinned kernel rejected',archive({'uImage':bytes(bad)}),'KERNEL')
 case('unreviewed updater rejected',archive({'fwu.sh':b'#!/bin/sh\nreboot\n'}),'UPDATER')
 case('wrong hardware rejected',archive({'hw_ver':b'OTHER\n'}),'HARDWARE')
 case('bad rootfs signature rejected',archive({'rootfs':b'nope'+base['rootfs'][4:]}),'ROOTFS')
 case('oversized rootfs rejected',archive({'rootfs':b'hsqs'+b'x'*2572288}),'ROOTFS')
 case('duplicate TAR entry rejected',archive(extra=[('rootfs',base['rootfs'])]),'ARCHIVE')
 case('TAR traversal rejected',archive(extra=[('../escape',b'x')]),'ARCHIVE')
 corrupt=bytearray(archive());offset=corrupt.find(base['rootfs'][:32]);corrupt[offset+32]^=1
 case('checksum error rejected before erase',bytes(corrupt),'CHECKSUM')
 (r/'mtd').write_text(layout.replace('00274000','00275000'));assert b'error=PARTITIONS' in send().stdout;(r/'mtd').write_text(layout);checks.append('unexpected MTD geometry rejected before job')
 (r/'mtd').write_text(layout.replace('"r1"','"boot"'));assert b'error=PARTITIONS' in send().stdout;(r/'mtd').write_text(layout);checks.append('missing target partition rejected before job')
 d=json.loads(store.read_text());d['sw_commit']='1';store.write_text(json.dumps(d));assert b'error=BOOT_STATE' in send().stdout;d['sw_commit']='0';store.write_text(json.dumps(d));checks.append('pending boot bank rejected')
 case('updater failure retains invalid-bank marker',error='WRITE',mode='fail');assert (config/'odi-invalid-bank1').exists()
 case('readback mismatch retains marker',error='READBACK',mode='corrupt');assert (config/'odi-invalid-bank1').exists()
 case('verified reinstall clears marker');assert not (config/'odi-invalid-bank1').exists()
 # Receiver has exited before the paused updater is released: no HTTP lifetime coupling.
 (r/'mode').write_text('pause');response=send();assert response.returncode==0 and b'protocol=3' in response.stdout
 until=time.monotonic()+90*devpath.HOST_TIMEOUT_SCALE
 while not (r/'ready').exists():assert time.monotonic()<until;time.sleep(0.05)
 assert (state/'firmware-phase').read_text()=='writing' and (state/'write.lock').exists()
 assert not (state/'write.lock/rootfs').exists() and not (state/'write.lock/uImage').exists()
 (r/'continue').touch();assert finish()[0]=='verified'
 checks.append('update continues after upload CGI/HTTP client exits; final bank remains unchanged')
 # Preserve the other direction as well: active bank 1 must survive a bank 0 update.
 d=json.loads(store.read_text());d['sw_active']=d['sw_commit']='1';store.write_text(json.dumps(d));(r/'mode').unlink()
 before=[(dev/f'mtd{i}').read_bytes() for i in [6,7]]
 response=send(bank='0');assert b'accepted=1' in response.stdout;assert finish()[0]=='verified'
 assert before==[(dev/f'mtd{i}').read_bytes() for i in [6,7]]
 assert json.loads(store.read_text())['sw_active']==json.loads(store.read_text())['sw_commit']=='1'
 checks.append('explicit bank 0 update preserves active bank 1 and boot selection')
report={'result':'passed','scope':'real upload CGI/background shell worker with exact target cmp diagnostic fixture and regular-file MTD; no physical flash','checks':checks}
if len(sys.argv)>1:report['release_sha256']=hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
(P/'firmware-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
