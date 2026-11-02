"""python hotfix/test_omci.py /path/to/exact/original/omci_app"""
import hashlib
import json
from pathlib import Path
import sys
from patch_omci import CHANGES, COMMAND, patch
from omci_emulator import emulate

original = Path(sys.argv[1]).read_bytes()
modified, report = patch(original)
# Native -f parser passes decimal base 10 to strtoul, not hexadecimal.
assert original[0x63b4:0x63b8] == bytes.fromhex('2406000a')
report['boot_mask_parser'] = 'strtoul base 10 at VA 0x4063b4; -1 sets UINT32_MAX; ffffffff would parse as zero'
before, after = emulate(original), emulate(modified)
assert ['system', 'echo 1 > /proc/load_reboot'] in before
assert ['system', COMMAND.decode()] in after
assert [x for x in before if x[0] not in ('printf','system')] == [x for x in after if x[0] not in ('printf','system')]
assert ['OMCI_ResponseMsg', 0, 1] in after
assert emulate(original, True) == emulate(modified, True) == [['feature_api',42],['feature_api',43]]
allowed = {i for o,a,b in CHANGES for i in range(o,o+len(a))}
assert len(original) == len(modified)
assert all(i in allowed for i,(a,b) in enumerate(zip(original,modified)) if a != b)
assert original[0x1e8bc:0x1e8bc+25] == modified[0x1e8bc:0x1e8bc+25]
for bad in (b'', original[:-1], modified, original[:-1]+bytes([original[-1]^1])):
    try: patch(bad)
    except ValueError: pass
    else: raise AssertionError('unrecognized input accepted')
report.update(result='passed', scope='native normal/custom handler executed under MIPS emulation; no physical ONU',
              checks=['successful response and task delay preserved', 'only normal reboot calls guarded script',
                      'custom feature 42/43 untouched', 'only three declared ranges changed',
                      'shared software-activation reboot command unchanged', 'unknown binary rejected'])
(Path(__file__).resolve().parents[1]/'omci-hook-test-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
