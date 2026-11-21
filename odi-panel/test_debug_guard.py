"""Real restricted-shell handler and authenticated CGI; reboot target is a fixture."""
from pathlib import Path
import json, os, shlex, subprocess, tempfile
import devpath

P=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp); state=r/'runtime';state.mkdir();debug=r/'debug';debug.mkdir()
 path=devpath.make(r);lib=devpath.logging_fixture(r,state)
 # Stable uptime isolates expiration from slow host process creation.
 with Path(lib).open('a') as f:f.write('\nlog_tick() { printf 1000; }\n')
 handler=(P/'src/odi-omci-reboot.sh').read_text().replace('/etc/scripts/odi-log-lib.sh',lib).replace('/proc/load_reboot',str(r/'reboot')).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path)
 (r/'handler').write_text(handler)
 def run():
  (r/'reboot').write_text('')
  p=subprocess.run(['/bin/sh',str(r/'handler')],capture_output=True,text=True,timeout=30*devpath.HOST_TIMEOUT_SCALE)
  assert p.returncode==0,p.stderr
  return (r/'reboot').read_text()
 assert run()=='1\n'
 (debug/'status').write_text('state=capturing\nstarted_uptime=950\nseconds=600\n')
 (debug/'reboot-until').write_text('1100\n');assert run()==''
 assert 'decision=skipped remaining=100' in (debug/'reboot-events').read_text()
 for value in ['1000','999','1301','0','-1','1000;reboot','999999999999999999']:
  (debug/'reboot-until').write_text(value);assert run()=='1\n',value
 (debug/'reboot-until').write_text('1100');(debug/'status').write_text('state=stopped\n');assert run()=='1\n'
 checks.append('disabled, expired, excessive, malformed and stopped sessions execute original reboot; armed capture skips it')
 (state/'token').write_text('test-token\n')
 api=(P/'src/api.cgi').read_text().replace('/etc/scripts/odi-terminal.sh',str(P/'src/odi-terminal.sh')).replace('/etc/scripts/odi-log-lib.sh',lib).replace('/etc/scripts/odi-mods-lib.sh',str(P/'src/odi-mods-lib.sh')).replace('/tmp/odi-panel',str(state)).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+path)
 (r/'api').write_text(api)
 def request(action, token='test-token', user='admin', extra=''):
  body=f'action={action}\ncsrf={token}\n'+extra
  return subprocess.run(['/bin/sh',str(r/'api')],input=body,text=True,capture_output=True,timeout=45*devpath.HOST_TIMEOUT_SCALE,env={**os.environ,'REMOTE_USER':user,'REQUEST_METHOD':'POST','CONTENT_TYPE':'text/plain','CONTENT_LENGTH':str(len(body))}).stdout
 assert '403 Forbidden' in request('debug_guard_start',user='')
 assert '403 Forbidden' in request('debug_guard_start',token='wrong')
 assert '400 Bad Request' in request('debug_guard_start',extra='duration=999\n')
 assert '409 Conflict' in request('debug_guard_start')
 (debug/'running').mkdir();(debug/'status').write_text('state=capturing\nstarted_uptime=950\nseconds=600\n')
 assert 'ok=31' in request('debug_guard_start');assert (debug/'reboot-until').read_text()=='1300\n'
 (debug/'status').write_text('state=capturing\nstarted_uptime=950\nseconds=60\n')
 assert 'ok=31' in request('debug_guard_start');assert (debug/'reboot-until').read_text()=='1010\n'
 (debug/'stop').touch();assert '409 Conflict' in request('debug_guard_start');(debug/'stop').unlink()
 assert 'ok=31' in request('debug_guard_stop');assert not (debug/'reboot-until').exists()
 checks.append('authenticated CSRF-protected fixed CGI actions limit probe to five minutes and capture deadline; stop removes RAM state')
 # Exact state strings from this user's hardware plus rejection cases.
 for sample,want in [('ONU state: Initial State(O1)','O1'),('ONU state: Serial Number State(O3)','O3'),('ONU state: Operation State(O5)','O5'),('ONU State: 5','O5'),('ONU State: O7','O7'),('error O5',''),('ONU state: 15','')]:
  (r/'state').write_text(sample+'\n')
  cmd='PATH='+path+';export PATH;. '+shlex.quote(lib)+';log_pon_state '+shlex.quote(str(r/'state'))
  result=subprocess.run(['/bin/sh','-c',cmd],text=True,capture_output=True,timeout=30*devpath.HOST_TIMEOUT_SCALE)
  assert result.stdout.strip()==want,(sample,result.stdout,result.stderr)
 checks.append('actual SDK O1/O3/O5 strings and legacy formats recognized; unrelated digits rejected')
report={'result':'passed','scope':'restricted host shell, real handler and CGI with simulated uptime/reboot destination; no physical device','checks':checks}
(P/'debug-guard-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
