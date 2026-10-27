"""Real shell/CGI with a stateful SDK fixture; never opens a real device."""
import json,os,shlex,subprocess,tempfile
from pathlib import Path
import devpath
P=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(dir=P) as temp:
 r=Path(temp);state=r/'runtime';state.mkdir();devbin=devpath.make(r)
 (r/'scenario').write_text('normal');(r/'rate-in').write_text('1048568');(r/'rate-out').write_text('1048568');(r/'calls').write_text('')
 fixture='''#!/bin/sh
R=ROOT
printf '%s\n' "$*" >>"$R/calls"
scenario=$(cat "$R/scenario")
case "$*" in
 'bandwidth get ingress port all'|'bandwidth get egress port all')
  if [ "$scenario" = hang ] && [ "$3" = ingress ]; then sleep 30; fi
  if [ "$scenario" = read-fail ]; then exit 7; fi
  if [ "$3" = ingress ]; then rate=$(cat "$R/rate-in");else rate=$(cat "$R/rate-out");fi
  echo "$*"
  if [ "$scenario" = bad-format ]; then echo "rate:$rate";exit 0;fi
  echo "port: 0 rate:$rate"
  [ "$scenario" = partial ] || echo "port: 2 rate:$rate"
  echo 'RTK.0> command:';;
 'bandwidth set ingress port all rate 4194296'|'bandwidth set egress port all rate 4194296')
  [ "$scenario" != write-fail ] || exit 7
  if [ "$scenario" != no-change ]; then
   if [ "$3" = ingress ];then echo 4194296 >"$R/rate-in";else echo 4194296 >"$R/rate-out";fi
  fi;;
 'port set auto-nego port all ability asy-flow-control') [ "$scenario" != flow-fail ] || exit 7;;
 'port get auto-nego port all ability') echo 'asymmetric ability fixture';;
 'port get status port all') echo '0 Up 2500M Full Dis Dis';;
 *) echo 'Unexpected SDK command' >&2;exit 99;;
esac
'''.replace('ROOT',shlex.quote(str(r)))
 (r/'diag').write_text(fixture);(r/'diag').chmod(0o755)
 (r/'flash').write_text('#!/bin/sh\n[ "$1:$2" = get:LAN_SPEED_MODE ] && echo LAN_SPEED_MODE=6\n');(r/'flash').chmod(0o755)
 lib=(P/'src/odi-mods-lib.sh').read_text().replace('/var/config/odi-panel-mods.conf',str(r/'mods.conf')).replace('/tmp/odi-panel',str(state))
 (r/'lib.sh').write_text(lib)
 replacements={'/etc/scripts/odi-mods-lib.sh':str(r/'lib.sh'),'/tmp/odi-panel':str(state),'/etc/scripts/flash':str(r/'flash'),'/bin/diag':str(r/'diag'),'/proc/lan_sds/lan_sds_cfg':str(r/'mode'),'PATH=/bin:/sbin:/usr/bin:/usr/sbin':'PATH='+devbin}
 source=(P/'src/odi-uplink.sh').read_text()
 for a,b in replacements.items():source=source.replace(a,b)
 if devpath.HOST_TIMEOUT_SCALE > 1:
  source=source.replace('sleep 3;', 'sleep 18;').replace('-lt 20 ]', '-lt 120 ]')
 helper=r/'uplink.sh';helper.write_text(source);helper.chmod(0o755)
 def configure(speed='1',flow='0',mode='4',scenario='normal',rate='1048568'):
  (r/'mods.conf').write_text('MOD_SPEED='+speed+'\nMOD_FLOWCONTROL='+flow+'\nMOD_SPEED_WATCH=0\nMOD_VLAN=off\n')
  (r/'mode').write_text('lan_sds_mode = '+mode+'(fixture)\n');(r/'scenario').write_text(scenario)
  for side in ['in','out']:(r/('rate-'+side)).write_text(rate)
  (r/'calls').write_text('')
 def run(operation='apply',expected=0):
  proc=subprocess.run(['/bin/sh',str(helper),operation,'boot'],capture_output=True,text=True,timeout=45*devpath.HOST_TIMEOUT_SCALE)
  assert proc.returncode==expected,(proc.returncode,proc.stderr,(state/'uplink-status').read_text() if (state/'uplink-status').exists() else '')
  assert not (state/'write.lock').exists() and not (state/'uplink.lock').exists()
  return dict(line.split('=',1) for line in (state/'uplink-status').read_text().splitlines())
 def writes():return [line for line in (r/'calls').read_text().splitlines() if ' set ' in ' '+line+' ']
 configure();out=run();assert out['speed']=='verified' and len(writes())==2;checks.append('mode 6 saved / actual mode 4: both real ports verified after writes')
 (r/'calls').write_text('');out=run();assert out['rates_match']=='1' and not writes();checks.append('idempotent application makes no repeated bandwidth writes')
 configure();out=run('check');assert out['speed']=='not-applied' and not writes();checks.append('read-only check never writes SDK settings')
 configure(speed='0');out=run();assert out['speed']=='off' and not writes();checks.append('disabled correction does not change limits')
 configure(mode='1');out=run(expected=3);assert out['speed']=='waiting-2.5g' and not writes();checks.append('saved 2.5G with actual 1G cannot report applied')
 for scenario in ['write-fail','no-change','bad-format','partial']:
  configure(scenario=scenario);out=run(expected=1);assert out['speed']=='failed';checks.append(scenario+' cannot report successful verification')
 configure(speed='0',flow='1');out=run();assert writes()==['port set auto-nego port all ability asy-flow-control'] and out['flow']=='command-ok';assert 'Dis Dis' in (state/'uplink-ports').read_text();checks.append('flow is opt-in; command success does not claim negotiated PAUSE')
 configure(speed='0',flow='1',scenario='flow-fail');out=run(expected=1);assert out['flow']=='failed';checks.append('flow failure is explicit')
 configure(scenario='hang');out=run('check',expected=1);assert out['error']=='bandwidth_read';checks.append('hung SDK reads have a bounded timeout and release locks')
 configure();(state/'read.lock').mkdir()
 proc=subprocess.run(['/bin/sh',str(helper),'apply','boot'],capture_output=True);assert proc.returncode==75 and not writes() and not (state/'write.lock').exists();(state/'read.lock').rmdir();checks.append('diagnostics lock blocks uplink writes')
 # Authenticate the actual CGI and exercise its fixed no-parameter actions.
 token='12345678-1234-1234-1234-123456789abc';(state/'token').write_text(token+'\n')
 api=(P/'src/api.cgi').read_text().replace('/etc/scripts/odi-mods-lib.sh',str(r/'lib.sh')).replace('/etc/scripts/odi-uplink.sh',str(helper)).replace('/tmp/odi-panel',str(state)).replace('PATH=/bin:/sbin:/usr/bin:/usr/sbin','PATH='+devbin)
 cgi=r/'api.cgi';cgi.write_text(api)
 def request(action,user='admin',csrf=token,extra=''):
  body='action='+action+'\ncsrf='+csrf+'\n'+extra
  proc=subprocess.run(['/bin/sh',str(cgi)],input=body,text=True,capture_output=True,timeout=45*devpath.HOST_TIMEOUT_SCALE,env={**os.environ,'REMOTE_USER':user,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':'text/plain'})
  return proc.stdout
 configure();assert '403 Forbidden' in request('uplink_apply',user='') and not writes();assert '403 Forbidden' in request('uplink_apply',csrf='wrong') and not writes();checks.append('CGI requires authenticated administrator and CSRF token')
 assert '400 Bad Request' in request('uplink_apply',extra='command=7265626f6f74\n') and not writes();checks.append('CGI rejects arbitrary command/port/rate parameters')
 raw=request('uplink_apply');assert 'ok=31' in raw and 'uplink_rc=30' in raw and len(writes())==2,raw;checks.append('CGI applies and returns verified status without exposing shell commands')
 (r/'calls').write_text('');raw=request('uplink_check');assert 'ok=31' in raw and not writes();checks.append('CGI check remains read-only')
report={'result':'passed','scope':'host POSIX shell + real CGI, stateful mocked flash/SDK; no ONU access','checks':checks}
(P/'uplink-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
