import shlex,struct,json
from pathlib import Path
header,blob=Path('base/original.pseudo').read_bytes().split(b'#\n# START OF DATA - DO NOT MODIFY\n#\n',1)
for line in header.decode().splitlines():
 a=shlex.split(line,comments=True)
 if a and a[1]=='R':
  p=Path('base/files')/a[0];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob[int(a[7]):int(a[7])+int(a[6])])
b=Path('base/files/lib/libmultilang_en.so').read_bytes();endian='>' if b[5]==2 else '<';phoff=struct.unpack_from(endian+'I',b,28)[0];psz,pnum=struct.unpack_from(endian+'HH',b,42);seg=[struct.unpack_from(endian+'8I',b,phoff+i*psz) for i in range(pnum)]
def off(a):
 for typ,o,v,_,s,*_ in seg:
  if typ==1 and v<=a<v+s:return o+a-v
 raise ValueError(hex(a))
table=[]
for i in range(2711):
 a=struct.unpack_from(endian+'I',b,off(0x29020)+i*4)[0]
 if not a:table.append('');continue
 o=off(a);table.append(b[o:b.index(b'\0',o)].decode())
Path('odi-panel/native-en.json').write_text(json.dumps(table,ensure_ascii=False))
