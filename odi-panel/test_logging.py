"""Real shell and authenticated CGI; SDK fixture and loopback TCP receiver only."""
from pathlib import Path
import json,os,shlex,socket,subprocess,tempfile,threading,time
import devpath
P=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);state=r/'runtime';state.mkdir();path=devpath.make(r)
 lib=devpath.logging_fixture(r,state)
 (r/'stage').write_text('ONU State: 5\n');(r/'mode').write_text('lan_sds_mode = 6(2500BaseX)\n')
 (r/'diag').write_text('#!/bin/sh\ncat '+shlex.quote(str(r/'stage'))+'\n');(r/'diag').chmod(0o755)
 (r/'nc').write_text('''#!/usr/bin/python3
import socket,sys
assert len(sys.argv)==3, 'Target nc has no -w option'
with socket.create_connection((sys.argv[-2],int(sys.argv[-1])),timeout=2) as s:
 s.sendall(sys.stdin.buffer.read())
''');(r/'nc').chmod(0o755)
 # Keep tests on the firmware's restricted command PATH.
 loglib=Path(lib);loglib.write_text(loglib.read_text().replace('/bin/nc',str(r/'nc')))
 runner=(P/'src/odi-log-run.sh').read_text().replace('/etc/scripts/odi-log-lib.sh',lib).replace('/bin/diag',str(r/'diag')).replace('/proc/lan_sds/lan_sds_cfg',str(r/'mode')).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path)
 if devpath.HOST_TIMEOUT_SCALE>1:
  runner=runner.replace('sleep 2;','sleep 12;')
  loglib.write_text(loglib.read_text().replace('sleep 2;','sleep 12;'))
 (r/'runner').write_text(runner)
 def shell(source):return subprocess.run(['/bin/sh','-c','PATH='+path+'; export PATH; . '+shlex.quote(lib)+'; '+source],text=True,capture_output=True,timeout=30*devpath.HOST_TIMEOUT_SCALE)
 def run(mode='once'):
  return subprocess.run(['/bin/sh',str(r/'runner'),mode],text=True,capture_output=True,timeout=70*devpath.HOST_TIMEOUT_SCALE)
 assert shell("log_valid LOG_HOST 192.168.1.10 && ! log_valid LOG_HOST '1.2.3.4;reboot' && ! log_valid LOG_HOST 1.2.3.999 && ! log_valid LOG_PORT 65536 && ! log_valid LOG_TAG 'bad tag'").returncode==0
 checks.append('IPv4/port/tag validation rejects shell syntax and invalid values')
 (r/'logging.conf').write_text('LOG_LOCAL=1\nLOG_REMOTE=0\nLOG_PORT=514\nLOG_TAG=test-onu\n')
 p=run();assert p.returncode==0,p.stderr
 content=(state/'events.log').read_text();assert 'event=LOGGER_START boot=' in content and 'state=O5' in content and 'event=SFP_MODE mode=6' in content
 assert not (state/'read.lock').exists() and not (state/'logger.lock').exists()
 checks.append('background worker records boot/PON/SFP without a browser and releases locks')
 old='uptime=1 event=HEARTBEAT pon=O5 free_kb=1000\n';(state/'events.log').write_text(old*(32740//len(old)))
 assert shell("log_event 'event=HEARTBEAT "+'x'*220+"'").returncode==0
 assert (state/'events.log.1').exists()
 assert all((state/name).stat().st_size<=32768 for name in ['events.log','events.log.1'])
 assert sum((state/name).stat().st_size for name in ['events.log','events.log.1'])<=65536
 checks.append('rotation retains at most two 32 KiB files')
 assert shell("log_event 'event=SYSLOG_TEST;reboot'").returncode!=0
 checks.append('event text cannot introduce shell syntax')
 (state/'write.lock').mkdir();(r/'stage').write_text('ONU State: 2\n');p=run();assert p.returncode==0 and not (state/'read.lock').exists();(state/'write.lock').rmdir()
 checks.append('firmware/settings write lock prevents SDK polling')
 received=[];server=socket.socket();server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1]
 def receiver():
  server.settimeout(30)
  with server.accept()[0] as conn:
   chunks=[]
   while data:=conn.recv(4096):chunks.append(data)
   received.append(b''.join(chunks))
 thread=threading.Thread(target=receiver,daemon=True);thread.start()
 (r/'logging.conf').write_text(f'LOG_LOCAL=1\nLOG_REMOTE=1\nLOG_HOST=127.0.0.1\nLOG_PORT={port}\nLOG_TAG=test-onu\n')
 # A running worker does not block a manual test.
 (state/'logger.lock').mkdir();p=run('test');(state/'logger.lock').rmdir();assert p.returncode==0,p.stderr
 thread.join(timeout=30);server.close();assert received
 n,packet=received[0].split(b' ',1);assert int(n)==len(packet)
 assert packet.startswith(b'<134>1 - test-onu odi-panel - EVENT - uptime=') and packet.endswith(b'event=SYSLOG_TEST')
 assert b'password' not in packet and b'GPON_SN' not in packet
 checks.append('real TCP delivery uses RFC 5424 header and RFC 6587 octet counting')
 assert not (state/'syslog.lock').exists() and not (state/'logger-test.lock').exists()
 # Actual CGI configuration save, authentication, test isolation and clear.
 (state/'token').write_text('test-token\n')
 api=(P/'src/api.cgi').read_text().replace('/etc/scripts/odi-log-lib.sh',lib).replace('/etc/scripts/odi-mods-lib.sh',str(P/'src/odi-mods-lib.sh')).replace('/etc/scripts/odi-log-run.sh',str(r/'runner')).replace('/tmp/odi-panel',str(state)).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path)
 (r/'api').write_text(api)
 def request(action=None,fields=None,user='admin',token='test-token'):
  body='' if action is None else 'action='+action+'\ncsrf='+token+'\n'+''.join(k+'='+v.encode().hex()+'\n' for k,v in (fields or {}).items())
  return subprocess.run(['/bin/sh',str(r/'api')],input=body,text=True,capture_output=True,timeout=45*devpath.HOST_TIMEOUT_SCALE,env={**os.environ,'REMOTE_USER':user,'REQUEST_METHOD':'GET' if action is None else 'POST','QUERY_STRING':'logs','CONTENT_TYPE':'text/plain','CONTENT_LENGTH':str(len(body))}).stdout
 assert '403 Forbidden' in request('logging',{'LOG_LOCAL':'0'},user='')
 assert '403 Forbidden' in request('logging',{'LOG_LOCAL':'0'},token='wrong')
 assert '400 Bad Request' in request('logging',{'LOG_HOST':'1.2.3.999'})
 assert '400 Bad Request' in request('logging',{'LOG_REMOTE':'0','command':'reboot'})
 checks.append('logging CGI requires authentication and CSRF and rejects unknown fields')
 before=(r/'logging.conf').read_text();assert '400 Bad Request' in request('logging',{'LOG_HOST':'','LOG_REMOTE':'1'});assert (r/'logging.conf').read_text()==before
 raw=request('logging',{'LOG_REMOTE':'0','LOG_TAG':'saved-onu'});assert 'ok=31' in raw,raw
 assert 'LOG_TAG=saved-onu' in (r/'logging.conf').read_text() and 'LOG_LOCAL=1' in (r/'logging.conf').read_text()
 checks.append('partial configuration merges, validates and verifies saved values')
 raw=request();assert 'event_log=' in raw and 'logger_status=' in raw
 assert 'ok=31' in request('log_clear') and not (state/'events.log').exists() and not (state/'events.log.1').exists()
 assert 'syslog_test_rc=32' in request('log_test')
 checks.append('read, clear and disabled-remote test are fixed CGI operations')
report={'result':'passed','scope':'restricted POSIX shell, actual CGI, stateful SDK fixture and local TCP socket; no ONU or external server','checks':checks}
(P/'logging-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
