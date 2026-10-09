"""Validate ELF structure, exact patch boundaries and source hash guard."""
from pathlib import Path
import struct,json,random,sys
from patch_boa import patch,ENTRIES,CGI,BASE
p=Path(__file__).resolve().parent;original=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else (p.parent.parent/'base/files/bin/boa').read_bytes();binary,report=patch(original)
ph,phsz,phn=0x34,32,8
headers=[struct.unpack_from('>8I',binary,ph+i*phsz) for i in range(phn)]
loads=[h for h in headers if h[0]==1]
for h in loads:assert h[1]%h[7]==h[2]%h[7] and h[1]+h[4]<=len(binary) and h[4]<=h[5]
for a,b in zip(loads,loads[1:]):assert a[2]+a[5]<=b[2]
changed=set(range(ph+7*phsz,ph+8*phsz))
for e in ENTRIES:changed.update(range(e-0x400000,e-0x400000+8))
assert all(a==b or n in changed for n,(a,b) in enumerate(zip(original,binary)))
try:patch(original[:-1]+b'x');raise AssertionError('unknown image accepted')
except AssertionError as e:assert str(e)=='Unexpected Boa binary; patch refused'

report_path=Path(sys.argv[2]) if len(sys.argv)>2 else p/'patch-test-report.json'
prior=json.loads(report_path.read_text()) if report_path.exists() else {}
if prior.get('patched_sha256')==report['patched_sha256']:
 report.update({k:v for k,v in prior.items() if k.endswith('_tests')})
report['static_tests']={'result':'passed','elf':'aligned non-overlapping RX segment; only declared entry hooks and unused program header changed','source_guard':'unknown source binary rejected'}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(report['static_tests'])
