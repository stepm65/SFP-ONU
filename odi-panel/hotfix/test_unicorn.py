"""MIPS emulation including the unmodified native session lookup and CGI environment export."""
from pathlib import Path
import struct,json,sys
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_BIG_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import *
from patch_boa import patch,ENTRIES,CGI
p=Path(__file__).resolve().parent;original=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else (p.parent.parent/'base/files/bin/boa').read_bytes();binary,report=patch(original)
gp=int(report['gp'],16)
def got(delta):
 for i in range(8):
  h=struct.unpack_from('>8I',binary,0x34+i*32)
  if h[0]==1 and h[2]<=gp+delta<h[2]+h[4]:return struct.unpack_from('>I',binary,h[1]+gp+delta-h[2])[0]
 raise AssertionError('GOT outside file')
LOGIN_GLOBAL=got(-0x7578);STRCMP=got(-0x7dbc)
loads=[struct.unpack_from('>8I',binary,0x34+i*32) for i in range(8)];loads=[h for h in loads if h[0]==1]
for h in loads:assert h[1]%h[7]==h[2]%h[7] and h[1]+h[4]<=len(binary) and h[4]<=h[5]
for a,b in zip(loads,loads[1:]):assert a[2]+a[5]<=b[2]
changed=set(range(0x34+7*32,0x34+8*32))
for e in ENTRIES:changed.update(range(e-0x400000,e-0x400000+8))
assert all(a==b or n in changed for n,(a,b) in enumerate(zip(original,binary)))
paths=['/panel/api.cgi','/panel/upload.cgi','/status.asp','/share.js','/legacy.html','/boaform/formSaveConfig','/boaform/admin/formUpload','/boaform/admin/formOmciInfo','/other.cgi','/panel/api.cgi/','/panel/api.cgiX']
for path in report['allowed_paths']:
 paths += [path[:i] for i in range(len(path))]
 paths += [path[:i]+'X'+path[i+1:] for i in range(len(path))]

def cstr(u,a):
 out=bytearray()
 for i in range(256):
  b=u.mem_read(a+i,1)[0]
  if b==0:return out.decode('ascii')
  out.append(b)
 raise AssertionError('unterminated string')
def put32(u,a,n):u.mem_write(a,struct.pack('>I',n))
def setup(path,role):
 u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN)
 for h in loads:
  _,off,v,_,sz,mem,_,_=h;start=v&~4095;u.mem_map(start,((v+mem+4095)&~4095)-start);u.mem_write(v,binary[off:off+sz])
 u.mem_map(0x600000,0x4000);u.mem_map(0x700000,0x4000)
 u.mem_write(0x6000d4,path.encode()+b'\0');u.mem_write(0x600050,b'192.168.1.2\0');u.mem_write(0x6000bc,b'forged\0')
 put32(u,LOGIN_GLOBAL,0 if role=='none' else 0x600400)
 put32(u,0x600404,0 if role=='null-role' else 0x600500);put32(u,0x600408,0)
 u.mem_write(0x600410,(b'192.168.1.99' if role=='other-ip' else b'192.168.1.2')+b'\0')
 page={'user':'index_user.html','unknown':'/other.html','prefix':'/index.html.bad'}.get(role,'/index.html')
 u.mem_write(0x600500,page.encode()+b'\0')
 u.reg_write(UC_MIPS_REG_A0,0x600000);u.reg_write(UC_MIPS_REG_RA,0x12345678);u.reg_write(UC_MIPS_REG_SP,0x703f00);u.reg_write(UC_MIPS_REG_GP,0x11223344)
 return u
cases=0;export_cases=0
for entry in ENTRIES:
 for path in paths:
  for role in ['admin','user','none','other-ip','null-role','unknown','prefix']:
   u=setup(path,role);u.reg_write(UC_MIPS_REG_T9,entry);end=[];native_lookup=[]
   def hook(uc,addr,size,context):
    if addr==0x40ba2c:native_lookup.append(addr) # Actual factory search_login_list executes.
    if addr==STRCMP:
     a=cstr(uc,uc.reg_read(UC_MIPS_REG_A0));b=cstr(uc,uc.reg_read(UC_MIPS_REG_A1));uc.reg_write(UC_MIPS_REG_V0,0 if a==b else 1);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
    if addr in [CGI,entry+8]:end.append(addr);uc.emu_stop()
   h=u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry,0,count=3000)
   target=path in report['allowed_paths'];expected=CGI if target else entry+8
   assert end==[expected],(path,role,end)
   assert u.reg_read(UC_MIPS_REG_A0)==0x600000 and u.reg_read(UC_MIPS_REG_RA)==0x12345678 and u.reg_read(UC_MIPS_REG_SP)==0x703f00
   assert u.reg_read(UC_MIPS_REG_T9)==(CGI if target else entry)
   assert u.reg_read(UC_MIPS_REG_GP)==(0x11223344 if target else gp-entry)
   assert cstr(u,0x6000bc)==('boa-admin' if role=='admin' else '') if target else cstr(u,0x6000bc)=='forged'
   assert len(native_lookup)==(1 if target else 0)
   cases+=1
   if target:
    # Execute the actual complete_env function. Intercept only its string/allocation helpers.
    u.hook_del(h);put32(u,0x60007c,0x601000);put32(u,0x600080,0);put32(u,0x600024,1);u.mem_write(0x6000bc,(b'boa-admin\0' if role=='admin' else b'\0'))
    u.reg_write(UC_MIPS_REG_A0,0x600000);u.reg_write(UC_MIPS_REG_T9,0x40ef78);u.reg_write(UC_MIPS_REG_RA,0x603000)
    env=[]
    def envhook(uc,addr,size,ctx):
     if addr==0x603000:uc.emu_stop();return
     if addr==0x418d00:raise AssertionError('unexpected helper')
     if addr==ENV_GEN:
      key=cstr(uc,uc.reg_read(UC_MIPS_REG_A0));valptr=uc.reg_read(UC_MIPS_REG_A1);value=cstr(uc,valptr) if valptr else '';env.append((key,value));uc.reg_write(UC_MIPS_REG_V0,0x602000)
     elif addr==ITOA:uc.mem_write(0x602800,b'0\0');uc.reg_write(UC_MIPS_REG_V0,0x602800)
     else:return
     uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
    # Fixed helper addresses resolved from this exact binary's dynamic symbol table.
    def got(delta):
     for h in loads:
      if h[2]<=gp+delta<h[2]+h[4]:return struct.unpack_from('>I',binary,h[1]+gp+delta-h[2])[0]
    ENV_GEN=got(-0x7a00);ITOA=got(-0x7c14)
    u.hook_add(UC_HOOK_CODE,envhook);u.emu_start(0x40ef78,0,count=2000)
    assert ([v for k,v in env if k=='REMOTE_USER']==(['boa-admin'] if role=='admin' else [])),(role,env)
    export_cases+=1
report['unicorn_mips_tests']={'result':'passed','dispatcher_cases':cases,'native_environment_cases':export_cases,'scope':'actual dispatcher, native session lookup and native complete_env with libc/helper calls mocked','session_cases':['administrator','restricted user','no session','different source IP','null role','unknown role','role prefix spoof']}
(Path(sys.argv[2]) if len(sys.argv)>2 else p/'patch-test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(report['unicorn_mips_tests'])
