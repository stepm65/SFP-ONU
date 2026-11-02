"""Exact SFU 240408 ONU-G Reboot hook. No other restart path is modified."""
import hashlib

ORIGINAL_SHA256 = '49be07183fcf11dbc2fea82ee914da5dcaead8e3049a8e770febf5c528617484'
COMMAND = b'exec /etc/scripts/odi-omci-reboot.sh'
MESSAGE = b'[omci] receive reboot, now rebooting...'
CHANGES = [
    (0x10c08, bytes.fromhex('0320f809'), b'\0'*4),  # printf only, not ResponseMsg
    (0x10c40, bytes.fromhex('2484e8bc'), bytes.fromhex('2484e894')),  # system argument
    (0x1e894, MESSAGE, COMMAND.ljust(len(MESSAGE), b'\0')),
]


def patch(binary):
    if len(binary) != 135028 or hashlib.sha256(binary).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Unrecognized omci_app; exact ODI SFU 240408 is required')
    result = bytearray(binary)
    for offset, old, new in CHANGES:
        if binary[offset:offset+len(old)] != old or len(old) != len(new):
            raise ValueError('Unexpected OMCI instruction/string at ' + hex(offset))
        result[offset:offset+len(old)] = new
    result = bytes(result)
    return result, {'original_sha256': ORIGINAL_SHA256,
                    'patched_sha256': hashlib.sha256(result).hexdigest(),
                    'ranges': [{'offset': hex(o), 'bytes': len(a)} for o,a,b in CHANGES],
                    'scope': 'normal ONU-G Reboot invokes a script; default executes the original proc reboot; feature_api 42/43 and software activation paths unchanged'}
