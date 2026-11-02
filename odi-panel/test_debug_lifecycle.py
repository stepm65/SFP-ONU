"""Real shell/FIFO lifecycle, simulated native CLI with persistent open writers."""
from pathlib import Path
import json,os,shlex,socket,subprocess,tempfile,threading,time
import devpath

P=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);debug=r/'debug';debug.mkdir();path=devpath.make(r);lib=devpath.logging_fixture(r)
 native=r/'omcilog';off=debug/'off';calls=[];handles=[];mode=0;mask='0xFFFFFFFF';location=str(native)
 server=socket.socket();server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1]
 def configure(m,filename):
  global mode,location
  mode=m
  if filename:
   for h in handles:h.close()
   handles.clear();location=filename
   for n in [filename,filename+'.par']:
    fd=os.open(n,os.O_RDWR|os.O_CREAT|os.O_TRUNC,0o600);handles.append(os.fdopen(fd,'w',buffering=1))
 def serve():
  while True:
   try:c,_=server.accept()
   except OSError:return
   with c:
    a=json.loads(c.recv(4096));calls.append(a)
    if a[:2]==['set','logfile']:
     configure(int(a[2]),a[4] if len(a)>4 else '')
     if mode==3:
      handles[0].write('33 63 59 0a 01 00 00 00\n')
      handles[1].write('0x3363 Ontg Reboot(0x0000)\n')
     reply=''
    else:reply='Mode:\n'+('Raw Mode Parsed Mode' if mode==3 else 'disabled')+'\nActionMask:\n'+mask+'\nLog File:\n'+location+'\n'
    c.sendall(reply.encode())
 thread=threading.Thread(target=serve,daemon=True);thread.start()
 cli=r/'cli';cli.write_text('#!/usr/bin/python3\nimport socket,json,sys\nwith socket.create_connection(("127.0.0.1",'+str(port)+')) as s:\n s.sendall(json.dumps(sys.argv[1:]).encode());s.shutdown(socket.SHUT_WR)\n while b:=s.recv(4096):sys.stdout.buffer.write(b)\n');cli.chmod(0o755)
 flash=r/'flash';flash.write_text('#!/bin/sh\nprintf "%s=FIXTURE\\n" "$2"\n');flash.chmod(0o755)
 diag=r/'diag';diag.write_text('#!/bin/sh\ncase "$*" in *onu-state*) echo "ONU state: Operation State(O5)";; *counter*) echo "Total RX OMCI: 2";; esac\n');diag.chmod(0o755)
 (Path(path)/'mknod').write_text('#!/usr/bin/python3\nimport os,sys\nassert sys.argv[2]=="p"\nos.mkfifo(sys.argv[1])\n')
 (Path(path)/'mknod').chmod(0o755)
 dl=r/'debuglib.sh';dl.write_text(dl.read_text().replace('/bin/omcicli',str(cli)).replace('/bin/diag',str(diag)).replace('/tmp/omcilog',str(native)).replace('/etc/scripts/odi-debug-ring.awk',str(P/'src/odi-debug-ring.awk')).replace('sleep 2;','sleep 12;'))
 runner=(P/'src/odi-debug.sh').read_text().replace('/etc/scripts/odi-log-lib.sh',lib).replace('/etc/scripts/odi-debug-lib.sh',str(dl)).replace('/tmp/omcilog',str(native)).replace('/etc/scripts/odi-debug-ring.awk',str(P/'src/odi-debug-ring.awk')).replace('/etc/scripts/flash',str(flash)).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path).replace('sleep 2;','sleep 12;')
 runner=runner.replace('/etc/scripts/odi-debug.sh',str(r/'runner'))
 (r/'runner').write_text(runner);(r/'runner').chmod(0o755)
 (r/'debug.conf').write_text('DEBUG_SECONDS=600\nDEBUG_REMOTE=0\nDEBUG_BOOT=0\nDEBUG_REGISTRATION=1\n')
 def until(test,seconds=75):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if test():return
   time.sleep(.1)
  raise AssertionError('condition timeout; status='+((debug/'status').read_text() if (debug/'status').exists() else 'missing'))
 def state():return (debug/'status').read_text() if (debug/'status').exists() else ''
 def stop(proc):
  (debug/'stop').touch();proc.wait(timeout=75)
  assert not (debug/'running').exists(),state()
  assert not native.exists() and not Path(str(native)+'.par').exists()
  assert location==str(off) and mode==0
  assert not (debug/'reboot-until').exists()
  (debug/'stop').unlink()
 configure(1,str(native))
 workers=[]
 try:
  with (r/'worker-errors').open('w') as err:
   proc=subprocess.Popen(['/bin/sh',str(r/'runner'),'worker','live'],stdout=err,stderr=err);workers.append(proc)
   until(lambda:'state=capturing' in state())
   until(lambda:(debug/'raw').exists() and '33 63' in (debug/'raw').read_text())
   until(lambda:(debug/'registration').exists() and 'Total RX OMCI' in (debug/'registration').read_text())
   (debug/'reboot-until').write_text('9999\n');stop(proc)
   assert calls[1]==['set','logfile','0','-1',str(off)],calls
   assert ['set','logfile','3','-1',str(native)] in calls
   assert not (debug/'reader-error').exists(),(debug/'reader-error').read_text()
   checks.append('live capture closes old descriptors, reopens both FIFOs explicitly, records RAW/parsed/registration, drains and removes FIFO on stop')
   (r/'debug.conf').write_text('DEBUG_SECONDS=600\nDEBUG_REMOTE=0\nDEBUG_BOOT=1\nDEBUG_REGISTRATION=0\n')
   proc=subprocess.Popen(['/bin/sh',str(r/'runner'),'worker','boot'],stdout=err,stderr=err);workers.append(proc)
   until(lambda:(debug/'ready').exists() and (debug/'boot-active').exists())
   assert 'state=capturing' not in state() or 'state=stopped' in state()
   configure(3,str(native))
   until(lambda:'state=capturing' in state())
   assert 'DEBUG_BOOT=0' in (r/'debug.conf').read_text()
   stop(proc)
   checks.append('boot FIFO-ready handshake precedes native startup; capturing requires readback; boot arm is consumed once')
   mask='0x7FFFFFFF'
   proc=subprocess.Popen(['/bin/sh',str(r/'runner'),'worker','live'],stdout=err,stderr=err);workers.append(proc)
   proc.wait(timeout=75)
   assert 'state=native_trace_setup_failed' in state()
   assert not (debug/'ready').exists() and not (debug/'running').exists()
   checks.append('wrong native action-mask readback refuses capturing and safely closes writers')
 finally:
  for proc in workers:
   if proc.poll() is None:
    (debug/'stop').touch()
    try:proc.wait(timeout=45)
    except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=20)
  for h in handles:h.close()
  server.close()
report={'result':'passed','scope':'actual host shell, real FIFOs and persistent native-writer fixture; not physical ONU','checks':checks}
(P/'debug-lifecycle-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
