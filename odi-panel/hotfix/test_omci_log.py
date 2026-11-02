"""Run the original MIPS log setter with libc calls observed in emulation."""
from pathlib import Path
import sys,io,struct,json,hashlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_BIG_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import *
binary=Path(sys.argv[1]).read_bytes()
assert hashlib.sha256(binary).hexdigest() == '150377a291ca622f0b3d09f0ef2ed0369240a974a5d19fc765e0686fd6024c19'
elf=ELFFile(io.BytesIO(binary));segments=list(elf.iter_segments())
tags={t.entry.d_tag:t.entry.d_val for s in segments if s['p_type']=='PT_DYNAMIC' for t in s.iter_tags()}
def offset(v):
    s=next(s for s in segments if s['p_type']=='PT_LOAD' and s['p_vaddr']<=v<s['p_vaddr']+s['p_filesz'])
    return v-s['p_vaddr']+s['p_offset']
symbols=[]
for i in range(tags['DT_MIPS_SYMTABNO']):
    name,value,size,info,other,section=struct.unpack_from('>IIIBBH',binary,offset(tags['DT_SYMTAB'])+16*i)
    start=offset(tags['DT_STRTAB'])+name;name=binary[start:binary.index(b'\0',start)].decode()
    symbols.append(dict(name=name,value=value,size=size,section=section,info=info))
byname={s['name']:s for s in symbols}
base=0x100000;scratch=0x600000;stack=0x700000;end=0x800000
def run(mode,filename):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN)
    for s in segments:
        if s['p_type']!='PT_LOAD':continue
        v=base+s['p_vaddr'];low=v&~4095;high=(v+s['p_memsz']+4095)&~4095
        u.mem_map(low,high-low);u.mem_write(v,binary[s['p_offset']:s['p_offset']+s['p_filesz']])
    u.mem_map(scratch,0x10000);u.mem_map(stack,0x10000);u.mem_map(end,4096)
    def set32(addr,n):u.mem_write(addr,struct.pack('>I',n&0xffffffff))
    def get32(addr):return struct.unpack('>I',u.mem_read(addr,4))[0]
    def text(addr):
        buf=bytearray()
        while (c:=bytes(u.mem_read(addr+len(buf),1)))!=b'\0':buf+=c
        return bytes(buf)
    externals={'gInfo':scratch+0x1000,'gUsrLogLevel':scratch+0x2000}
    got=tags['DT_PLTGOT'];local=tags['DT_MIPS_LOCAL_GOTNO'];first=tags['DT_MIPS_GOTSYM'];hooks={}
    for i in range(2,local):set32(base+got+i*4,get32(base+got+i*4)+base)
    for i in range(first,len(symbols)):
        s=symbols[i];ptr=base+got+4*(local+i-first)
        if s['name'] in externals:set32(ptr,externals[s['name']])
        elif s['value']:
            set32(ptr,s['value']+base)
            if s['section']=='SHN_UNDEF' or s['section']==0:hooks[s['value']+base]=s['name']
    for name,handle in [('pLogFile',0x1111),('pLogFileParsed',0x2222)]:set32(base+byname[name]['value'],handle)
    set32(externals['gInfo']+0x144,1)
    u.mem_write(scratch,filename.encode()+b'\0');events=[]
    def hook(u,addr,size,user):
        if addr==end:u.emu_stop();return
        if addr not in hooks:return
        name=hooks[addr];a0=u.reg_read(UC_MIPS_REG_A0);a1=u.reg_read(UC_MIPS_REG_A1);ret=0
        if name=='fclose':events.append(['close',a0])
        elif name=='fopen':
            events.append(['open',text(a0).decode(),text(a1).decode()]);ret=0x3000+len(events)*16
        elif name=='strcpy':u.mem_write(a0,text(a1)+b'\0');ret=a0
        elif name=='strcat':u.mem_write(a0+len(text(a0)),text(a1)+b'\0');ret=a0
        else:raise AssertionError('Unexpected imported call: '+name)
        u.reg_write(UC_MIPS_REG_V0,ret);u.reg_write(UC_MIPS_REG_PC,u.reg_read(UC_MIPS_REG_RA))
    u.hook_add(UC_HOOK_CODE,hook)
    entry=base+byname['omci_wrapper_setLogToFile']['value']
    u.reg_write(UC_MIPS_REG_A0,mode);u.reg_write(UC_MIPS_REG_A1,0xffffffff);u.reg_write(UC_MIPS_REG_A2,scratch)
    u.reg_write(UC_MIPS_REG_SP,stack+0xff00);u.reg_write(UC_MIPS_REG_RA,end);u.reg_write(UC_MIPS_REG_T9,entry)
    u.emu_start(entry,end+4,count=10000)
    assert u.reg_read(UC_MIPS_REG_PC)==end
    assert get32(externals['gInfo']+0x144)==mode
    return events

old=run(3,'');fixed=run(3,'/tmp/omcilog');stopped=run(0,'/tmp/odi-debug/off')
assert old==[],old
assert fixed[:2]==[['close',0x1111],['close',0x2222]],fixed
assert [x[1] for x in fixed if x[0]=='open']==['/tmp/omcilog','/tmp/omcilog.par'],fixed
assert [x[1] for x in stopped if x[0]=='open']==['/tmp/odi-debug/off','/tmp/odi-debug/off.par'],stopped
report={'result':'passed','scope':'original MIPS library emulation, libc file operations stubbed; no device',
                  'binary_sha256':hashlib.sha256(binary).hexdigest(),'without_filename':old,'with_filename':fixed,'stop_to_regular_files':stopped}
(Path(__file__).resolve().parents[1]/'omci-log-native-test-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
