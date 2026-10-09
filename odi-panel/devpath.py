"""A PATH that resolves only commands present on the SFU 240408 stick.

Host tests run the panel's shell scripts with this PATH, so a call to a command
the firmware lacks (mv, tr, head, od ...) fails on the host exactly as it would
on the device. Commands that could affect the host are replaced by failing stubs.
"""
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
NAMES = sorted({w for line in (P / 'device-commands.txt').read_text().splitlines()
                for w in line.split('#', 1)[0].split()})
# Real host tools the scripts legitimately use; everything else becomes a stub.
REAL = {'awk', 'cat', 'chmod', 'cksum', 'cmp', 'cp', 'diff', 'echo', 'egrep', 'expr',
        'fgrep', 'grep', 'kill', 'ls', 'md5sum', 'mkdir', 'ps', 'rm', 'sed', 'sh',
        'ash', 'sleep', 'tar', 'df'}
HOST_PATH = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'


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
            target.symlink_to(host)
        else:
            target.write_text(f'#!/bin/sh\necho "{name}: not available in host test sandbox" >&2\nexit 126\n')
            target.chmod(0o755)
    return str(d)
