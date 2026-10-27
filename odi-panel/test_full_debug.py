"""Full private debug: real shell/CGI, streaming ring and loopback TCP fixtures."""
from pathlib import Path
import io,json,os,shlex,socket,subprocess,tarfile,tempfile,threading
import devpath
P=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);state=r/'runtime';state.mkdir();debug=r/'debug';debug.mkdir();path=devpath.make(r);lib=devpath.logging_fixture(r)
 # Preserve each native hex packet unchanged, including bytes that encode secrets.
 frames=[f'{i:04x}'+'31413132504c4f414d'+'00'*38 for i in range(3500)]
 source='\n'.join(frames)+'\n'
 process=subprocess.run(['/usr/bin/awk','-v','output='+str(debug/'raw'),'-v','wire='+str(debug/'wire'),'-v','errorfile='+str(debug/'reader-error'),'-f',str(P/'src/odi-debug-ring.awk')],input=source,text=True,capture_output=True,timeout=60*devpath.HOST_TIMEOUT_SCALE)
 assert process.returncode==0,process.stderr
 stored=(debug/'raw.1').read_text().splitlines()+(debug/'raw').read_text().splitlines()
 assert stored==frames[-len(stored):]
 assert all((debug/name).stat().st_size<=131072 for name in ['raw','raw.1','wire','wire.1'])
 checks.append('RAW ring retains complete native hex frames byte for byte at 128 KiB per file')
 parsed='PLOAM password: FAKE-PLOAM\nLOID password: FAKE-LOID\n'
 subprocess.run(['/usr/bin/awk','-v','output='+str(debug/'parsed'),'-v','errorfile='+str(debug/'reader-error'),'-f',str(P/'src/odi-debug-ring.awk')],input=parsed,text=True,check=True)
 assert (debug/'parsed').read_text()==parsed
 checks.append('parsed private trace is not redacted')
 token='test-token';(state/'token').write_text(token+'\n')
 fixture='''#!/bin/sh
R=ROOT
case "$1" in
 start) mkdir "$R/running";printf 'state=capturing\n' >"$R/status";printf 'GPON_PLOAM_PASSWD=FAKE-PLOAM\nSUSER_PASSWORD=FAKE-ADMIN\n' >"$R/credentials.txt";;
 stop) rm -r "$R/running";printf 'state=stopped\n' >"$R/status";;
 *) exit 2;;
esac
'''.replace('ROOT',shlex.quote(str(debug)))
 (r/'debug.sh').write_text(fixture);(r/'debug.sh').chmod(0o755)
 api=(P/'src/api.cgi').read_text().replace('/etc/scripts/odi-log-lib.sh',lib).replace('/etc/scripts/odi-mods-lib.sh',str(P/'src/odi-mods-lib.sh')).replace('/etc/scripts/odi-debug.sh',str(r/'debug.sh')).replace('/tmp/odi-panel',str(state)).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path)
 (r/'api').write_text(api)
 def request(action=None,fields=None,user='admin',csrf=token,query='debug_status'):
  body=b'' if action is None else ('action='+action+'\ncsrf='+csrf+'\n'+''.join(k+'='+v.encode().hex()+'\n' for k,v in (fields or {}).items())).encode()
  return subprocess.run(['/bin/sh',str(r/'api')],input=body,capture_output=True,timeout=45*devpath.HOST_TIMEOUT_SCALE,env={**os.environ,'REQUEST_METHOD':'GET' if action is None else 'POST','REMOTE_USER':user,'CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':'text/plain','QUERY_STRING':query}).stdout
 assert b'403 Forbidden' in request('debug_start',user='')
 assert b'403 Forbidden' in request('debug_export',csrf='wrong')
 assert b'400 Bad Request' in request('debug_config',{'DEBUG_SECONDS':'999999'})
 assert b'400 Bad Request' in request('debug_config',{'DEBUG_REMOTE':'1'})
 assert b'400 Bad Request' in request('debug_config',{'command':'reboot'})
 assert b'400 Bad Request' in request('debug_start',{'path':'/etc/passwd'})
 checks.append('full debug operations require admin session/CSRF and reject arbitrary paths or commands')
 assert b'ok=31' in request('debug_config',{'DEBUG_SECONDS':'60','DEBUG_REMOTE':'0','DEBUG_BOOT':'1'})
 assert 'DEBUG_BOOT=1' in (r/'debug.conf').read_text()
 assert b'debug_rc=30' in request('debug_start')
 assert b'409 Conflict' in request('debug_export')
 assert b'FAKE-PLOAM' not in request() and b'FAKE-ADMIN' not in request(query='logs')
 assert b'debug_rc=30' in request('debug_stop')
 raw=request('debug_export');assert b'application/x-tar' in raw
 with tarfile.open(fileobj=io.BytesIO(raw.split(b'\r\n\r\n',1)[1])) as archive:
  credentials=archive.extractfile('credentials.txt').read();assert b'FAKE-PLOAM' in credentials and b'FAKE-ADMIN' in credentials
  assert archive.extractfile('raw').read()==(debug/'raw').read_bytes()
  assert archive.extractfile('parsed').read()==parsed.encode()
 checks.append('stopped PRIVATE TAR includes exact RAW/parsed data and unmasked credential snapshot')
 checks.append('ordinary logs/status do not expose the private capture')
 # Full TCP syslog uses its explicit option and transmits complete records.
 server=socket.socket();server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1];received=[]
 def receiver():
  server.settimeout(30)
  with server.accept()[0] as conn:
   chunks=[]
   while part:=conn.recv(4096):chunks.append(part)
   received.append(b''.join(chunks))
 thread=threading.Thread(target=receiver,daemon=True);thread.start()
 (r/'nc').write_text('#!/usr/bin/python3\nimport sys,socket\nwith socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=2) as s:s.sendall(sys.stdin.buffer.read())\n');(r/'nc').chmod(0o755)
 dl=r/'debuglib.sh';dl.write_text(dl.read_text().replace('/bin/nc',str(r/'nc')).replace('sleep 2;','sleep 12;' if devpath.HOST_TIMEOUT_SCALE>1 else 'sleep 2;'))
 (r/'logging.conf').write_text(f'LOG_HOST=127.0.0.1\nLOG_PORT={port}\nLOG_TAG=debug-test\nLOG_REMOTE=0\n')
 (debug/'credentials-wire').write_text('-999|CREDENTIAL PLOAM=FAKE-PLOAM\n')
 (debug/'wire.1').unlink();(debug/'wire').write_text('1|'+frames[0]+'\n')
 source='PATH='+path+';export PATH;. '+shlex.quote(lib)+';remote=1;sent=-1001;debug_send'
 proc=subprocess.run(['/bin/sh','-c',source],capture_output=True,text=True,timeout=45*devpath.HOST_TIMEOUT_SCALE);assert proc.returncode==0,proc.stderr
 thread.join(30);server.close();assert received
 data=received[0];messages=[]
 while data:
  count,rest=data.split(b' ',1);count=int(count);messages.append(rest[:count]);data=rest[count:]
 assert len(messages)==2 and b'FAKE-PLOAM' in messages[0] and frames[0].encode() in messages[1]
 checks.append('explicit full syslog includes unredacted credentials and complete RAW frames with RFC 6587 framing')
report={'result':'passed','scope':'host shell/CGI, streaming ring, PRIVATE TAR and loopback TCP; native ONU FIFO/OMCI writer and boot activation require physical testing','checks':checks}
(P/'full-debug-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
