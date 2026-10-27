"""A PATH that resolves only commands present on the SFU 240408 stick.

Host tests run the panel's shell scripts with this PATH, so a call to a command
the firmware lacks (mv, tr, head, od ...) fails on the host exactly as it would
on the device. Commands that could affect the host are replaced by failing stubs.
"""
from pathlib import Path
import shutil
import shlex
import sys

P = Path(__file__).resolve().parent
NAMES = sorted({w for line in (P / 'device-commands.txt').read_text().splitlines()
                for w in line.split('#', 1)[0].split()})
# Real host tools the scripts legitimately use; everything else becomes a stub.
REAL = {'awk', 'cat', 'chmod', 'cksum', 'cmp', 'cp', 'diff', 'echo', 'egrep', 'expr',
        'fgrep', 'grep', 'kill', 'ls', 'md5sum', 'mkdir', 'ps', 'rm', 'sed', 'sh',
        'ash', 'sleep', 'tar', 'df'}
HOST_PATH = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
# MSYS process creation is much slower than Linux; this is a host-test budget,
# never the firmware's command or collection timeout.
HOST_TIMEOUT_SCALE = 6 if sys.platform == 'cygwin' else 1


def logging_fixture(root, state=None):
    root = Path(root)
    state = Path(state) if state is not None else root / 'runtime'
    target = root / 'loglib.sh'
    debuglib = root / 'debuglib.sh'
    debuglib.write_text((P / 'src/odi-debug-lib.sh').read_text()
                        .replace('/var/config/odi-panel-debug.conf', str(root / 'debug.conf'))
                        .replace('/tmp/odi-debug', str(root / 'debug')))
    target.write_text((P / 'src/odi-log-lib.sh').read_text()
                      .replace('/var/config/odi-panel-logging.conf', str(root / 'logging.conf'))
                      .replace('/etc/scripts/odi-debug-lib.sh', str(debuglib))
                      .replace('/tmp/odi-panel', str(state)))
    return str(target)


def make(root):
    """Create <root>/devbin and return its path."""
    d = Path(root) / 'devbin'
    d.mkdir(exist_ok=True)
    for name in NAMES:
        target = d / name
        if target.exists() or target.is_symlink():
            continue
        host = shutil.which('dash' if name in ('sh', 'ash') else name, path=HOST_PATH) if name in REAL else None
        if host:
            if sys.platform == 'cygwin':
                if name == 'mkdir':
                    # MSYS mkdir -p probes inaccessible ancestors above the
                    # managed workspace, even when the target already exists.
                    # Python handles existing directories without that probe.
                    target.write_text('#!/usr/bin/python3\nimport os,sys\na=sys.argv[1:]\np="-p" in a\ntry:\n for x in a:\n  if x != "-p":\n   if p: os.makedirs(x,exist_ok=True)\n   else: os.mkdir(x)\nexcept OSError as e:\n print(e,file=sys.stderr);sys.exit(1)\n')
                    target.chmod(0o755)
                    continue
                # MSYS may copy executables instead of making symlinks. Those
                # copies lose adjacent DLLs under this deliberately limited PATH.
                target.write_text('#!/bin/sh\nexec '+shlex.quote(host)+' "$@"\n')
                target.chmod(0o755)
            else:
                target.symlink_to(host)
        else:
            target.write_text(f'#!/bin/sh\necho "{name}: not available in host test sandbox" >&2\nexit 126\n')
            target.chmod(0o755)
    return str(d)
