"""Exact-image MIPS dispatcher repair. No device access; only produces a new file."""
from pathlib import Path
import hashlib,struct,json,sys
EXPECTED='7b36c74a388e1ed47767e297d510dfcdf3f1cf1ea8eb5cd01e79a33da87949ad'
PROFILES={
 EXPECTED:{'name':'ODI SFU 240408','gp':0x487a70}
}
BASE=0x500000
ENTRIES=[0x4110ec,0x410fd0] # GET/ASP dispatcher and POST/form dispatcher
CGI=0x40f710

def patch(original):
 source_sha=hashlib.sha256(original).hexdigest()
 assert source_sha in PROFILES,'Unexpected Boa binary; patch refused'
 profile=PROFILES[source_sha]
 b=bytearray(original);ph=struct.unpack_from('>I',b,28)[0];sz,n=struct.unpack_from('>HH',b,42)
 assert (ph,sz,n)==(0x34,32,8)
 headers=[struct.unpack_from('>8I',b,ph+i*sz) for i in range(n)]
 assert headers[7][0]==0 and not any(h[0]==1 and h[2]<=BASE<h[2]+h[5] for h in headers)
 def offset(v):
  for h in headers:
   if h[0]==1 and h[2]<=v<h[2]+h[4]:return h[1]+v-h[2]
  raise ValueError(hex(v))
 def I(op,rs,rt,imm):return (op<<26)|(rs<<21)|(rt<<16)|(imm&65535)
 def J(addr):return (2<<26)|((addr>>2)&0x3ffffff)
 code=[];labels={};branches=[];loads=[];meta=[]
 def label(s):labels[s]=len(code)*4
 def branch(op,rs,rt,dest):branches.append((len(code),dest));code.append(I(op,rs,rt,0));code.append(0)
 def stringptr(reg,name):code.append(I(15,0,reg,BASE>>16));loads.append((len(code),reg,name));code.append(0)
 for num,entry in enumerate(ENTRIES):
  start=BASE+len(code)*4;prefix=str(num)+'_'
  for idx,path in enumerate(['api','upload']):
   label(prefix+path)
   code.append(I(9,4,8,0xd4)) # t0 = req->request_uri
   stringptr(9,path)
   label(prefix+path+'_loop')
   code += [I(36,8,10,0),I(36,9,11,0)]
   branch(5,10,11,prefix+('upload' if idx==0 else 'fallback'))
   branch(4,10,0,prefix+'cgi')
   code += [I(9,8,8,1),I(9,9,9,1)]
   branch(4,0,0,prefix+path+'_loop')
  label(prefix+'cgi')
  # The factory session login never fills req->user (REMOTE_USER).
  # Resolve the actual native login record; only its administrator landing page
  # can mint the synthetic CGI principal. Never derive it from HTTP input.
  code += [I(40,4,0,0xbc),I(9,29,29,-32),I(43,29,31,28),I(43,29,4,24),I(43,29,28,20)]
  search=0x40ba2c
  code += [I(15,0,25,(search+0x8000)>>16),I(9,25,25,search),(25<<21)|(31<<11)|9,0]
  code += [I(35,29,28,20),I(35,29,4,24),I(35,29,31,28),I(9,29,29,32)]
  branch(4,2,0,prefix+'execute')
  code.append(I(35,2,8,4)) # server-created login record: landing-page pointer
  branch(4,8,0,prefix+'execute')
  stringptr(9,'admin_page')
  label(prefix+'role_loop');code += [I(36,8,10,0),I(36,9,11,0)]
  branch(5,10,11,prefix+'execute')
  branch(4,10,0,prefix+'grant')
  code += [I(9,8,8,1),I(9,9,9,1)]
  branch(4,0,0,prefix+'role_loop')
  label(prefix+'grant')
  for i,char in enumerate(b'boa-admin\0'):
   code += [I(9,0,8,char),I(40,4,8,0xbc+i)]
  label(prefix+'execute')
  # Tail call must set t9 to the original PIC entry; return address stays untouched.
  code += [I(15,0,25,(CGI+0x8000)>>16),I(9,25,25,CGI),25<<21|8,0]
  label(prefix+'fallback');o=offset(entry);old=bytes(b[o:o+8]);assert struct.unpack('>2I',old)[0]==0x3c1c0007
  code += list(struct.unpack('>2I',old))+[J(entry+8),0]
  b[o:o+8]=struct.pack('>2I',J(start),0)
  meta.append({'entry':hex(entry),'stub':hex(start),'original':old.hex(),'replacement':bytes(b[o:o+8]).hex()})
 data=b''
 for name,path in [('api',b'/panel/api.cgi\0'),('upload',b'/panel/upload.cgi\0'),('admin_page',b'/index.html\0')]:labels[name]=len(code)*4+len(data);data+=path
 for at,dest in branches:code[at]|=((labels[dest]-(at+1)*4)//4)&65535
 for at,reg,name in loads:code[at]=I(9,reg,reg,labels[name])
 payload=struct.pack('>'+str(len(code))+'I',*code)+data
 start=(len(b)+4095)&~4095;b.extend(b'\0'*(start-len(b)));b.extend(payload)
 struct.pack_into('>8I',b,ph+7*sz,1,start,BASE,BASE,len(payload),len(payload),5,4096)
 report={'base_sha256':source_sha,'base_profile':profile['name'],'gp':hex(profile['gp']),'patched_sha256':hashlib.sha256(b).hexdigest(),'entries':meta,'new_segment_offset':start,'new_segment_vaddr':BASE,'new_segment_size':len(payload),'allowed_paths':['/panel/api.cgi','/panel/upload.cgi'],'authentication':'Existing auth_authorize remains before dispatch. Native search_login_list must return an administrator record (/index.html) before exporting REMOTE_USER=boa-admin; other sessions retain empty REMOTE_USER and CGI denies access.','device_tested':False}
 return bytes(b),report
if __name__=='__main__':
 src,dst=map(Path,sys.argv[1:]);out,report=patch(src.read_bytes());dst.write_bytes(out);dst.chmod(0o755);dst.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
