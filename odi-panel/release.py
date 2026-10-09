"""The authoritative panel version and synchronisation of generated source labels."""
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parent
VERSION = (PROJECT / 'VERSION').read_text().strip()
assert re.fullmatch(r'\d+\.\d+\.\d+', VERSION), 'Invalid panel VERSION'


def sync_sources(check=False):
    rules = {
        'index.html': [
            (r'(?<=\?v=)\d+\.\d+\.\d+', VERSION, 13),
            (r'(?<=ODI Panel )\d+\.\d+\.\d+', VERSION, 1),
            (r'(?<=name="odi-panel-version" content=")\d+\.\d+\.\d+', VERSION, 1),
        ],
        'login-template.asp': [
            (r'(?<=ODI Panel )\d+\.\d+\.\d+', VERSION, 1),
            (r'(?<=name="odi-panel-version" content=")\d+\.\d+\.\d+', VERSION, 1),
        ],
        'api.cgi': [(r'(?m)^PANEL_VERSION=\d+\.\d+\.\d+$', 'PANEL_VERSION=' + VERSION, 1)],
    }
    for name, replacements in rules.items():
        path = PROJECT / 'src' / name
        original = updated = path.read_text()
        for pattern, replacement, expected_count in replacements:
            updated, count = re.subn(pattern, replacement, updated)
            assert count == expected_count, f'Unexpected version fields in {name}: {count}'
        if check:
            assert updated == original, f'Stale version in {name}; run python release.py'
        elif updated != original:
            path.write_text(updated)


if __name__ == '__main__':
    sync_sources()
    print('Panel version:', VERSION)
