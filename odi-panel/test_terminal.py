#!/usr/bin/env python3
"""Terminal: off by default, timed enable, LAN only, CSRF, limits, abort, history.

Runs api.cgi on the host with the stick's command set (devpath); no ONU access.
"""
import json, os, re, subprocess, tempfile, threading, time
from pathlib import Path
import devpath

P = Path(__file__).resolve().parent
TOKEN = '12345678-1234-1234-1234-123456789abc'
checks = []


def main():
    with tempfile.TemporaryDirectory(dir=P) as temp:
        r = Path(temp)
        state = r / 'runtime'
        devbin = devpath.make(r)
        (r / 'uuid').write_text(TOKEN + '\n')
        term = (P / 'src/odi-terminal.sh').read_text()
        # Short limits keep the test fast; the device values are asserted below.
        assert 'TERM_TTL=900\n' in term and 'TERM_TIMEOUT=20\n' in term and 'TERM_MAX_BYTES=65536\n' in term
        term = term.replace('TERM_TIMEOUT=20\n', 'TERM_TIMEOUT=2\n').replace('TERM_MAX_BYTES=65536\n', 'TERM_MAX_BYTES=4096\n')
        (r / 'terminal.sh').write_text(term)
        api = (P / 'src/api.cgi').read_text()
        for a, b in {
            '/etc/scripts/odi-terminal.sh': str(r / 'terminal.sh'),
            '/etc/scripts/odi-log-lib.sh': devpath.logging_fixture(r, state),
            '/etc/scripts/odi-mods-lib.sh': str(P / 'src/odi-mods-lib.sh'),
            '/tmp/odi-panel': str(state),
            '/proc/sys/kernel/random/uuid': str(r / 'uuid'),
            'PATH=/bin:/sbin:/usr/bin:/usr/sbin': 'PATH=' + devbin,
        }.items():
            assert a in api, a
            api = api.replace(a, b)
        script = r / 'api.cgi'
        script.write_text(api)
        work = r / 'work'
        work.mkdir()

        def call(action=None, fields=None, addr='192.168.1.10', csrf=TOKEN, raw=None):
            body = '' if action is None else 'action=' + action + '\ncsrf=' + csrf + '\n' + ''.join(
                k + '=' + v.encode().hex() + '\n' for k, v in (fields or {}).items())
            if raw is not None:
                body = raw
            env = dict(os.environ, REMOTE_USER='admin', REMOTE_ADDR=addr,
                       REQUEST_METHOD='POST' if action or raw else 'GET', QUERY_STRING='state',
                       CONTENT_TYPE='text/plain', CONTENT_LENGTH=str(len(body)))
            p = subprocess.run(['sh', str(script)], input=body, text=True, capture_output=True, env=env,
                               timeout=30 * devpath.HOST_TIMEOUT_SCALE)
            return p.stdout

        def fields(out):
            d = {}
            for line in out.split('\r\n\r\n', 1)[-1].splitlines():
                if '=' in line and re.fullmatch(r'[a-z_0-9]+=[0-9a-f]*', line):
                    k, v = line.split('=', 1)
                    d[k] = bytes.fromhex(v).decode('latin-1')
            return d

        def status(out):
            return out.split('\r\n', 1)[0] if out.startswith('Status:') else 'Status: 200'

        def run(cmd, **kw):
            return call('terminal_run', {'command': cmd}, **kw)

        st = fields(call())
        assert st['terminal_remaining'] == '0' and st['terminal_lan'] == '1' and st['terminal_ttl'] == '900', st
        checks.append('state reports the terminal off by default with a 900 s window')
        assert '403' in status(run('echo hi')), 'runs while off'
        checks.append('commands are refused while the terminal is off')
        for addr in ('8.8.8.8', '172.32.0.1', '::ffff:100.64.0.1', ''):
            assert '403' in status(call('terminal_enable', addr=addr)), addr
        assert not (state / 'terminal/until').exists()
        assert '403' in status(call('terminal_enable', csrf='wrong'))
        assert '400' in status(call('terminal_enable', {'x': '1'}))
        checks.append('enable requires a local client address, the CSRF token and no parameters')
        for addr in ('192.168.1.10', '10.0.0.5', '172.20.1.1', '::ffff:192.168.0.2'):
            on = fields(call('terminal_enable', addr=addr))
            assert 895 <= int(on['terminal_remaining']) <= 900, on
        events = (state / 'events.log').read_text() if (state / 'events.log').exists() else ''
        assert 'terminal=enabled seconds=900' in events, events
        checks.append('enable opens a 15-minute window and logs a credential-free event')

        o = fields(run('echo hello; printf "%s\\n" "$((6*7))"'))
        assert o['terminal_rc'] == '0' and o['terminal_state'] == 'done' and o['terminal_output'] == 'hello\n42', o
        o = fields(run('cd ' + str(work) + ' && pwd'))
        assert o['terminal_cwd'] == str(work), o
        o = fields(run('pwd; exit 3'))
        assert o['terminal_output'] == str(work) and o['terminal_rc'] == '3', o
        o = fields(run('echo err >&2; cat /nonexistent'))
        assert 'err' in o['terminal_output'] and o['terminal_rc'] != '0', o
        checks.append('runs shell commands, keeps the working directory, returns exit code and stderr')

        assert '400' in status(call(raw='action=terminal_run\ncsrf=' + TOKEN + '\ncommand=' + 'echo\nx'.encode().hex() + '\n'))
        assert '400' in status(run('x' * 1025))
        assert '400' in status(call(raw='action=terminal_run\ncsrf=' + TOKEN + '\ncommand=6869\ncommand=6869\n'))
        assert '400' in status(run(''))
        checks.append('rejects multi-line, oversized, duplicate and empty commands')

        t = time.time()
        o = fields(run('sleep 47; echo never'))
        assert o['terminal_state'] == 'timeout' and 'never' not in o['terminal_output'], o
        assert time.time() - t < 8, time.time() - t
        time.sleep(1.5)
        assert 'sleep 47' not in subprocess.run(['ps', '-eo', 'args'], capture_output=True, text=True).stdout
        checks.append('a command over the time limit is stopped together with its child processes')

        o = fields(run("awk 'BEGIN{while(1)print \"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"}'"))
        assert o['terminal_truncated'] == '1' and len(o['terminal_output']) <= 4096, (o['terminal_truncated'], len(o['terminal_output']))
        assert (state / 'terminal/out').stat().st_size == 0
        checks.append('output is capped by ulimit -f and the RAM buffer is emptied after each command')

        result = {}
        worker = threading.Thread(target=lambda: result.update(fields(call('terminal_run', {'command': 'sleep 29'}))))
        worker.start()
        time.sleep(0.8)
        assert '409' in status(run('echo second'))
        k = fields(call('terminal_kill'))
        worker.join(10)
        assert not worker.is_alive() and result.get('terminal_state') == 'aborted', result
        assert k['ok'] == '1'
        checks.append('one command at a time; Abort stops the running command')

        hist = (state / 'terminal/history').read_text()
        assert 'echo hello' in hist and 'from=192.168.1.10' in hist
        events = (state / 'events.log').read_text()
        assert 'echo hello' not in events and 'sleep' not in events
        checks.append('command history stays in RAM and is not forwarded to the event log or syslog')

        (state / 'terminal/until').write_text('1\n')
        assert fields(call())['terminal_remaining'] == '0'
        assert '403' in status(run('echo late'))
        checks.append('the window expires by uptime; expired terminals refuse commands')

        fields(call('terminal_enable'))
        off = fields(call('terminal_disable'))
        assert off['terminal_remaining'] == '0' and '403' in status(run('echo off'))
        assert 'terminal=disabled' in (state / 'events.log').read_text()
        checks.append('disable closes the window immediately')

    report = {'result': 'passed', 'cases': len(checks), 'checks': checks,
              'path': 'device command set only (device-commands.txt)', 'environment': 'host POSIX shell; no ONU'}
    (P / 'terminal-test-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


main()
