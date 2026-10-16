# 踩坑记录（实测血泪）

## 1. 容器 PID 命名空间隔离

**现象**：容器里 `ls /proc/<游戏pid>` 报 No such file，`/proc/1/cmdline` 也读不到。

**原因**：DSH 容器跑在独立 PID namespace，看不到手机侧进程。

**解决**：拉 so、查进程一律走设备 shell：
```bash
adb-shell ls -d /data/app/*/com.tencent.tmgp.pubgmhd-*/lib/arm64/
adb-shell cp <path>/libUE4.so /sdcard/pte_work/libUE4.so
```

## 2. 静态链接被 zstd 卡住

**现象**：
```
ld.lld: error: libc.a(heap_zero_init.o):(.debug_str) is compressed with
ELFCOMPRESS_ZSTD, but lld is not built with zstd support
```

**原因**：NDK 的 libc.a 用了 ZSTD 压缩调试段，AIDE 版 lld 没编 zstd 支持。

**解决**：**改动态链接**，去掉 `-static` / `-static-libc++`：
```bash
# ✗ 错
clang++ ... -static -o out src.c
# ✓ 对
clang++ ... -o out src.c
```

## 3. 虚表起点判定踩坑（PIE 陷阱）

**现象**：用「往前找连续两个 0」定位虚表起点，结果全落在槽 index=0 或巨大的值。

**原因**：**PIE 文件里重定位项在文件中本身就是 0**！`[0,0]` 可能是重定位项而非真表头。

**解决**：判定「真零」必须排除重定位表：
```python
def raw_is_zero(va):
    if va in REL: return False          # ← 关键：排除重定位项
    o = v2o(va)
    return o is not None and mm[o:o+8] == b'\x00'*8
```

**实测正确结果**：
```
槽 0x140F1938  虚表 0x140EFEE0  槽index=843
槽 0x1422E460  虚表 0x1422CA08  槽index=843
槽 0x14436A20  虚表 0x14434FC8  槽index=843
```
三个虚表同槽 index=843 → 同一基类多子类，符合预期。

## 4. 特征码失效

**现象**：大版本更新后特征码 0 命中。

**原因**：桩被内联 / 编译器换寄存器顺序 / 加了 `paciasp`。

**解决**：
1. 先反汇编已知位置附近，看新形状
2. 放宽特征码：只匹配 `fmov s0,sN / fmov s1,sN+1 / fmov s2,sN+2 / ret` 的模式（N 可变）
3. 兜底：扫虚表第 843 槽附近指向「4~8 指令小函数」的项

## 5. SDK 搜不到原生虚函数

**现象**：`grep -r 'a0fb548' SDK目录` 空手而归。

**原因**：SDK 只收录 `$$exec` 反射桩，原生虚函数不在内。

**解决**：不要反复搜。直接走特征码 + 虚表反查。SDK 只用来：
- 校验 build 一致性（锚点对照）
- 查类字段偏移

## 6. readelf 解析 ELF 头偏移记错

**现象**：程序头解析全乱，段地址全错。

**正确偏移**（ELF64）：
```
e_phoff     = 0x20  (8字节)
e_shoff     = 0x28  (8字节)
e_phentsize = 0x36  (2字节)
e_phnum     = 0x38  (2字节)
e_shentsize = 0x3A  (2字节)
e_shnum     = 0x3C  (2字节)
e_shstrndx  = 0x3E  (2字节)
```
注意 `e_phentsize/e_phnum` 是 **2 字节**（H），不是 4 字节。

## 7. Python array('I') 平台差异

**现象**：`array.array('I')` 假设 4 字节，在某些平台不是。

**解决**：使用前检查：
```python
arr = array.array('I')
if arr.itemsize != 4:
    raise SystemExit('array I itemsize != 4')
```

## 8. 特征码命中多个时的取舍

**现象**：命中 0xA0FB548 和 0xBE33F44 两个。

**判定方法**：看虚表引用数
```
0xA0FB548 → 3 个虚表引用，全在同一槽 index=843  → 同一基类多子类（更可能是目标）
0xBE33F44 → 1 个虚表引用，槽 index=191          → 独立类
```
**结论**：优先取**虚表引用多、槽位一致**的那个。再用外挂源码里的已知值交叉确认。
