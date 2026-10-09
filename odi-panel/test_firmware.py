"""Exercise upload CGI on host files, with fake MTD and mocked native updater. Never uses a device."""
from pathlib import Path
import os,json,subprocess,tarfile,io,tempfile,hashlib,selectors,time
P=Path(__file__).resolve().parent
from release import VERSION
import devpath
with tarfile.open(P.parent/'firmware/original/M110_sfp_ODI_SFU_240408.tar') as t: base={n:t.extractfile(n).read() for n in t.getnames()}
def archive(changes=None,extra=None):
 d={**base,**(changes or {})};d['md5.txt']=''.join(hashlib.md5(d[n]).hexdigest()+'  '+n+'\n' for n in ['fwu.sh','rootfs','uImage','fwu_ver','hw_ver']).encode()
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for n,v in list(d.items())+(extra or []):
   i=tarfile.TarInfo(n);i.size=len(v);t.addfile(i,io.BytesIO(v))
 return out.getvalue()
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);state=r/'state';state.mkdir();(state/'token').write_text('abc-token');config=r/'config';config.mkdir();dev=r/'dev';dev.mkdir();bin=r/'bin';bin.mkdir();store=r/'nv.json';store.write_text(json.dumps({'sw_active':'0','sw_commit':'0','sw_version0':'OLD0','sw_version1':'OLD1'}))
 mtd=r/'mtd';layout='dev: size erasesize name\n'+''.join(f'mtd{i+4}: {sz} 00001000 "{name}"\n' for i,(name,sz) in enumerate([('k0','0014c000'),('r0','00274000'),('k1','0014c000'),('r1','00274000')]))
 mtd.write_text(layout)
 for i in range(4,8):(dev/f'mtd{i}').write_bytes(b'original'+bytes([i]))
 nv=bin/'nv';nv.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\np=Path('+repr(str(store))+');d=json.loads(p.read_text());a=sys.argv[1:]\nif a[0]=="getenv":print(a[1]+"="+d[a[1]])\nelse:d[a[1]]=a[2];p.write_text(json.dumps(d))\n');nv.chmod(0o755)
 cmp=bin/'cmp';cmp.write_text('''#!/usr/bin/python3
import sys
from pathlib import Path
a,b=map(Path,sys.argv[1:]);x=a.read_bytes();y=b.read_bytes()
if x==y:sys.exit(0)
if len(y)>len(x) and y[:len(x)]==x:print('cmp: EOF on '+str(a),file=sys.stderr)
else:print('files differ')
sys.exit(1)
''');cmp.chmod(0o755)
 starter=r/'starter';starter.write_text('''#!/usr/bin/python3
import sys,tarfile,json,time
from pathlib import Path
r=Path(__file__).parent;bank=int(sys.argv[1]);print('Updating image',bank,flush=True);(r/'writes').write_text(str(bank));mode=(r/'mode').read_text() if (r/'mode').exists() else ''
if mode=='fail':sys.exit(1)
if mode=='pause':
 (r/'ready').touch()
 until=time.monotonic()+10
 while not (r/'continue').exists():
  if time.monotonic()>until:sys.exit(2)
  time.sleep(0.01)
with tarfile.open(sys.argv[2]) as t:
 for name,idx in [('uImage',4),('rootfs',5)]:
  data=t.extractfile(name).read();data=(b'broken'+data[6:]) if mode=='corrupt' and name=='rootfs' else data
  (r/'dev'/('mtd'+str(idx+bank*2))).write_bytes(data+b'\\xff'*64)
 p=r/'nv.json';d=json.loads(p.read_text());d['sw_version'+str(bank)]=t.extractfile('fwu_ver').read().decode().strip();p.write_text(json.dumps(d))
''');starter.chmod(0o755)
 starter.rename(r/'starter.py');starter.write_text('#!/bin/sh\nexec /usr/bin/python3 '+str(r/'starter.py')+' "$@"\n')
 s=(P/'src/upload.cgi').read_text()
 for a,b in {'PATH=/bin:/sbin:/usr/bin:/usr/sbin':'PATH='+str(bin)+':'+devpath.make(r),'STATE=/tmp/odi-panel':'STATE='+str(state),'NV=/bin/nv':'NV='+str(nv),'MTD=/proc/mtd':'MTD='+str(mtd),'DEV=/dev':'DEV='+str(dev),'CONFIG=/var/config':'CONFIG='+str(config),'STARTER=/etc/scripts/fwu_starter.sh':'STARTER='+str(starter),'[ -c "$DEV/$dev" ]':'[ -f "$DEV/$dev" ]'}.items():s=s.replace(a,b)
 script=r/'upload.cgi';script.write_text(s)
 def run(name,data=None,bank='1',token='abc-token',env=None,expect=True,write=False,error=None):
  body=f'csrf={token}\nbank={bank}\n'.encode()+(archive() if data is None else data)
  if (r/'writes').exists():(r/'writes').unlink()
  before=[(dev/f'mtd{i}').read_bytes() for i in range(4,8)];commit_before=json.loads(store.read_text())['sw_commit']
  e=dict(os.environ,REMOTE_USER='admin',REQUEST_METHOD='POST',CONTENT_TYPE='application/octet-stream',CONTENT_LENGTH=str(len(body)));e.update(env or {})
  proc=subprocess.run(['/bin/sh',str(script)],input=body,capture_output=True,env=e,timeout=25)
  assert (b'ok=1' in proc.stdout)==expect,(name,proc.stdout,proc.stderr)
  assert (r/'writes').exists()==write,(name,'write contract',proc.stdout)
  assert (dev/'mtd4').read_bytes()==before[0] and (dev/'mtd5').read_bytes()==before[1],name
  if not write:assert [(dev/f'mtd{i}').read_bytes() for i in range(4,8)]==before,name
  assert json.loads(store.read_text())['sw_commit']==commit_before,name
  assert proc.stdout.count(b'Content-Type:')==1,(name,'single HTTP header block')
  if error:assert ('error='+error).encode() in proc.stdout,(name,'expected error '+error,proc.stdout)
  if expect:
   assert ('log='+('Updating image '+bank+'\n').encode().hex()+'\n').encode() in proc.stdout,(name,'updater log not streamed',proc.stdout)
   assert [line for line in proc.stdout.splitlines() if line.startswith(b'phase=')]==[b'phase=receiving',b'phase=checking',b'phase=writing',b'phase=readback',b'phase=verified'],(name,'actual milestone sequence')
  elif b'protocol=2' in proc.stdout:
   assert b'phase=failed' in proc.stdout and b'phase=verified' not in proc.stdout,(name,'streamed failure')
   assert b'Status:' not in proc.stdout,(name,'no HTTP headers inserted into response body')
  checks.append(name)
 run('authenticated explicit bank 1, readback, no switch',write=True)
 folder=f'release-{VERSION}-sfu'
 built=next((P.parent/folder).glob('*.tar'));run('built image accepted: '+folder,data=built.read_bytes(),write=True)
 altered_kernel=bytearray(base['uImage']);altered_kernel[128]^=1
 run('modified SFU kernel rejected',data=archive({'uImage':bytes(altered_kernel)}),expect=False,error='KERNEL')
 run('no authentication',env={'REMOTE_USER':''},expect=False)
 run('CSRF rejection',token='wrong',expect=False)
 run('active bank rejection',bank='0',expect=False)
 run('invalid bank rejection',bank='2',expect=False)
 (state/'write.lock').mkdir();run('concurrent operation blocked',expect=False);(state/'write.lock').rmdir()
 run('short/truncated upload',data=archive()[:-512],env={'CONTENT_LENGTH':str(len(archive())+len('csrf=abc-token\nbank=1\n'))},expect=False)
 d=json.loads(store.read_text());d['sw_commit']='1';store.write_text(json.dumps(d));run('pending boot into target blocked',expect=False);d['sw_commit']='0';store.write_text(json.dumps(d))
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for n,v in base.items():
   i=tarfile.TarInfo(n)
   if n=='rootfs':i.type=tarfile.SYMTYPE;i.linkname='/dev/mtd4';t.addfile(i)
   else:i.size=len(v);t.addfile(i,io.BytesIO(v))
 run('symlink archive rejected',data=out.getvalue(),expect=False)
 run('wrong kernel',data=archive({'uImage':b'wrong'}),expect=False)
 run('unreviewed updater',data=archive({'fwu.sh':b'#!/bin/sh\nreboot\n'}),expect=False)
 run('wrong hardware',data=archive({'hw_ver':b'OTHER\n'}),expect=False)
 run('bad squashfs signature',data=archive({'rootfs':b'nope'+base['rootfs'][4:]}),expect=False)
 run('oversized rootfs',data=archive({'rootfs':b'hsqs'+b'x'*2572288}),expect=False)
 run('duplicate TAR entry',data=archive(extra=[('rootfs',base['rootfs'])]),expect=False)
 run('TAR traversal rejected',data=archive(extra=[('../escape',b'x')]),expect=False)
 corrupted=bytearray(archive());at=corrupted.find(base['rootfs'][:32]);corrupted[at+32]^=1
 run('checksum failure before erase',data=bytes(corrupted),expect=False)
 mtd.write_text(layout.replace('"r1"','"boot"'));run('missing target partition',expect=False);mtd.write_text(layout)
 mtd.write_text(layout.replace('00274000','00275000'));run('unexpected partition geometry',expect=False);mtd.write_text(layout)
 (r/'mode').write_text('fail');run('native updater error retains invalid-bank marker',expect=False,write=True);assert (config/'odi-invalid-bank1').exists()
 (r/'mode').write_text('corrupt');run('readback mismatch retains invalid-bank marker',expect=False,write=True);assert (config/'odi-invalid-bank1').exists()
 (r/'mode').unlink();run('successful reinstall clears marker',write=True);assert not (config/'odi-invalid-bank1').exists()
 # Hold the updater at its entry: milestones must arrive before it returns.
 def paused(close_output=False):
  for name in ['ready','continue']:
   (r/name).unlink(missing_ok=True)
  (r/'mode').write_text('pause')
  body=b'csrf=abc-token\nbank=1\n'+archive();e=dict(os.environ,REMOTE_USER='admin',REQUEST_METHOD='POST',CONTENT_TYPE='application/octet-stream',CONTENT_LENGTH=str(len(body)))
  proc=subprocess.Popen(['/bin/sh',str(script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=e,bufsize=0)
  try:
   proc.stdin.write(body);proc.stdin.close()
   selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
   output=b'';until=time.monotonic()+8
   while b'phase=writing\n' not in output:
    assert time.monotonic()<until,'milestones buffered until updater exit'
    for key,_ in selector.select(0.2):output+=os.read(key.fileobj.fileno(),4096)
   selector.close()
   until=time.monotonic()+3
   while not (r/'ready').exists():
    assert time.monotonic()<until,'updater not started';time.sleep(0.01)
   assert proc.poll() is None and b'ok=1' not in output and b'phase=verified' not in output
   assert (config/'odi-invalid-bank1').exists() and (state/'write.lock').is_dir()
   if close_output:proc.stdout.close()
   (r/'continue').touch()
   proc.wait(timeout=10)
   if not close_output:
    output+=proc.stdout.read();assert b'phase=readback' in output and b'phase=verified' in output and b'ok=1' in output
   assert proc.returncode==0,(proc.returncode,proc.stderr.read())
   assert not (state/'write.lock').exists() and not (config/'odi-invalid-bank1').exists()
   assert (state/'firmware-phase').read_text()=='verified'
   assert json.loads(store.read_text())['sw_active']==json.loads(store.read_text())['sw_commit']=='0'
  finally:
   if proc.poll() is None:proc.kill();proc.wait()
   proc.stdout.close();proc.stderr.close();(r/'mode').unlink(missing_ok=True)
 paused();checks.append('milestones received while native updater is still running')
 paused(close_output=True);checks.append('closed progress pipe does not interrupt write or readback')
 # Reverse direction: active bank 1, write bank 0, with direct checks for bank 1 preservation.
 d=json.loads(store.read_text());d['sw_active']=d['sw_commit']='1';store.write_text(json.dumps(d));before=[(dev/f'mtd{i}').read_bytes() for i in [6,7]]
 body=b'csrf=abc-token\nbank=0\n'+archive();e=dict(os.environ,REMOTE_USER='admin',REQUEST_METHOD='POST',CONTENT_TYPE='application/octet-stream',CONTENT_LENGTH=str(len(body)))
 proc=subprocess.run(['/bin/sh',str(script)],input=body,capture_output=True,env=e,timeout=25);assert b'ok=1' in proc.stdout,proc.stdout;assert before==[(dev/f'mtd{i}').read_bytes() for i in [6,7]];assert json.loads(store.read_text())['sw_commit']=='1';checks.append('explicit bank 0 from active bank 1')
(P/'firmware-test-report.json').write_text(json.dumps({'result':'passed','environment':'host shell with device command set only (device-commands.txt), regular files emulating MTD, mocked nv/native updater/BusyBox cmp diagnostic','cases':len(checks),'checks':checks,'target_busybox_cmp_evidence':{'sha256':hashlib.sha256((P.parent/'base/files/bin/busybox').read_bytes()).hexdigest(),'EOF_format_address':'0x45063b','EOF_branch':'0x436480','stream_GOT_symbol':'stderr','output_GOT_symbol':'fprintf','review':'equal-prefix EOF diagnostic checked against supplied binary; unknown output fails closed'}},indent=2))
print(len(checks),'firmware cases passed')
