"""MIPS handler execution with only external calls stubbed; no device claims."""
import io
import struct

def emulate(binary, custom=False):
    from elftools.elf.elffile import ELFFile
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2,
                                   UC_MIPS_REG_V0, UC_MIPS_REG_SP, UC_MIPS_REG_T9,
                                   UC_MIPS_REG_RA, UC_MIPS_REG_PC)
    elf = ELFFile(io.BytesIO(binary))
    segments = list(elf.iter_segments())
    tags = {t.entry.d_tag: t.entry.d_val for s in segments if s['p_type'] == 'PT_DYNAMIC'
            for t in s.iter_tags()}

    def offset(addr):
        seg = next(s for s in segments if s['p_type'] == 'PT_LOAD'
                   and s['p_vaddr'] <= addr < s['p_vaddr'] + s['p_filesz'])
        return addr - seg['p_vaddr'] + seg['p_offset']

    symbols = {}
    for i in range(tags['DT_MIPS_SYMTABNO']):
        name, value, _, _, _, _ = struct.unpack_from('>IIIBBH', binary, offset(tags['DT_SYMTAB']) + 16*i)
        start = offset(tags['DT_STRTAB']) + name
        symbols[binary[start:binary.index(b'\0', start)].decode()] = value
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_BIG_ENDIAN)
    for s in segments:
        if s['p_type'] != 'PT_LOAD':
            continue
        low = s['p_vaddr'] & ~4095
        high = (s['p_vaddr'] + s['p_memsz'] + 4095) & ~4095
        u.mem_map(low, high - low)
        u.mem_write(s['p_vaddr'], binary[s['p_offset']:s['p_offset'] + s['p_filesz']])
    stack, message, end = 0x700000, 0x600000, 0x800000
    for addr in [stack, message, end]:
        u.mem_map(addr, 0x10000)
    names = ['feature_api', 'OMCI_ResponseMsg', 'printf', 'putchar', 'OMCI_TaskDelay', 'system']
    hooks = {symbols[n]: n for n in names}
    events = []

    def text(addr):
        data = bytearray()
        for i in range(256):
            c = bytes(u.mem_read(addr + i, 1))
            if c == b'\0':
                return data.decode()
            data += c
        raise AssertionError('unterminated string')

    def hook(u, addr, size, _):
        if addr == end:
            u.emu_stop()
            return
        if addr not in hooks:
            return
        name = hooks[addr]
        a0, a1, a2 = [u.reg_read(reg) for reg in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2)]
        ret = 0
        if name == 'feature_api':
            events.append([name, a0])
            ret = 0x100 if custom else 0x101
        elif name == 'OMCI_ResponseMsg':
            assert a0 == message
            events.append([name, a1, a2])
        elif name in ['printf', 'system']:
            events.append([name, text(a0)])
        else:
            events.append([name, a0])
        u.reg_write(UC_MIPS_REG_V0, ret)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    u.hook_add(UC_HOOK_CODE, hook)
    entry = symbols['OMCI_OnReboot']
    u.reg_write(UC_MIPS_REG_A0, message)
    u.reg_write(UC_MIPS_REG_SP, stack + 0xff00)
    u.reg_write(UC_MIPS_REG_RA, end)
    u.reg_write(UC_MIPS_REG_T9, entry)
    u.emu_start(entry, end + 4, count=2000)
    assert u.reg_read(UC_MIPS_REG_PC) == end
    assert u.reg_read(UC_MIPS_REG_V0) == 0
    return events
