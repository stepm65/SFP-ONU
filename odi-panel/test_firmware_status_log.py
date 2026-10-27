"""Exercise the actual operation CGI with flash-erase carriage-return logs."""
from pathlib import Path
import json, os, subprocess, tempfile

import devpath

project = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(dir=project) as tmp:
    root = Path(tmp)
    runtime = root / 'runtime'
    runtime.mkdir()
    (runtime / 'token').write_text('test-token\n')
    (runtime / 'firmware-status').write_text('VERIFIED bank=0\n')
    (runtime / 'firmware-phase').write_text('verified\n')
    (runtime / 'firmware-error').write_text('')
    log = b'Updating image 0\n' + b'Erasing 4 Kibyte @ 123000 -- 50 % complete.\r' * 1300 + b'Completed bank 0!'
    (runtime / 'firmware-update.log').write_bytes(log)
    for name in ('mods', 'log'):
        (root / name).write_text('# fixture\n')
    source = (project / 'src/api.cgi').read_text()
    for old, new in {
        'STATE=/tmp/odi-panel': 'STATE=' + str(runtime),
        '/etc/scripts/odi-mods-lib.sh': str(root / 'mods'),
        '/etc/scripts/odi-log-lib.sh': str(root / 'log'),
        'PATH=/bin:/sbin:/usr/bin:/usr/sbin': 'PATH=' + devpath.make(root),
    }.items():
        assert old in source
        source = source.replace(old, new)
    script = root / 'api.cgi'
    script.write_text(source)
    env = dict(os.environ, REMOTE_USER='boa-admin', REQUEST_METHOD='GET', QUERY_STRING='operation')
    result = subprocess.run(['/bin/sh', str(script)], env=env, capture_output=True, timeout=20 * devpath.HOST_TIMEOUT_SCALE, check=True)
    body = result.stdout.split(b'\r\n\r\n', 1)[1]
    fields = dict(line.split(b'=', 1) for line in body.splitlines())
    assert bytes.fromhex(fields[b'firmware_status'].decode()) == b'VERIFIED bank=0'
    assert bytes.fromhex(fields[b'firmware_phase'].decode()) == b'verified'
    returned = bytes.fromhex(fields[b'firmware_log'].decode())
    assert returned == log[-2048:], (len(returned), len(log[-2048:]), repr(returned[:100]), repr(log[-2048:][:100]))
    assert len(result.stdout) < 5000
    assert (runtime / 'firmware-update.log').read_bytes() == log
report = {'result': 'passed', 'scope': 'actual CGI with simulated state and 57 KB carriage-return erase log',
          'checks': ['status and verified phase preserved', 'most recent log limited to 2048 bytes', 'original log unchanged']}
(project / 'firmware-status-log-test-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
