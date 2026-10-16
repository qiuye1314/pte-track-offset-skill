#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ue4_track_tool.py — PUBG Mobile 追踪偏移一键抓取 + SDK 交叉校验 + 自动回填
#
# 用法:
#   python3 ue4_track_tool.py <libUE4.so> [--sdk <SDK目录>] [--patch <Offsets.h>]
#
# 原理:
#   追踪桩 = 4 指令 float3 getter：把 v3/v4/v5 搬到 v0/v1/v2 返回。
#   驱动在入口下 PTE 影子断点，把目标坐标写进 v3/v4/v5，桩再当"返回值"吐回。
#   机器码: fmov s2,s5 | fmov s1,s4 | fmov s0,s3 | ret
#          = a240201e 8140201e 6040201e c0035fd6
#   该形状在 3.3 亿字节 .text 里只出现 1~2 次 -> 稳定特征码。
import struct, mmap, sys, os, re, argparse, glob

SIG = bytes.fromhex("a240201e8140201e6040201ec0035fd6")

def elf_open(P):
    f = open(P, "rb"); mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    e_phoff = struct.unpack_from("<Q", mm, 0x20)[0]
    e_shoff = struct.unpack_from("<Q", mm, 0x28)[0]
    e_phentsize = struct.unpack_from("<H", mm, 0x36)[0]
    e_phnum     = struct.unpack_from("<H", mm, 0x38)[0]
    e_shentsize = struct.unpack_from("<H", mm, 0x3A)[0]
    e_shnum     = struct.unpack_from("<H", mm, 0x3C)[0]
    e_shstrndx  = struct.unpack_from("<H", mm, 0x3E)[0]
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i*e_phentsize
        t, fl = struct.unpack_from("<II", mm, o)
        po, pv, pp, fs, ms, al = struct.unpack_from("<QQQQQQ", mm, o+8)
        if t == 1: segs.append((pv, po, fs))
    def sh(i):
        o = e_shoff + i*e_shentsize
        v = struct.unpack_from("<IIQQQQIIQQ", mm, o)
        return dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5])
    secs = [sh(i) for i in range(e_shnum)]
    stt = secs[e_shstrndx]
    def sn(i):
        e = mm.find(b"\x00", stt["off"]+i); return mm[stt["off"]+i:e].decode()
    for s in secs: s["sname"] = sn(s["name"])
    return f, mm, segs, secs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("so"); ap.add_argument("--sdk"); ap.add_argument("--patch")
    a = ap.parse_args()

    f, mm, SEGS, secs = elf_open(a.so)
    def v2o(va):
        for b,o,s in SEGS:
            if b <= va < b+s: return o+(va-b)
        return None
    def sec_of(va):
        for s in secs:
            if s["addr"] and s["addr"] <= va < s["addr"]+s["size"]: return s["sname"]
        return "?"
    T = [s for s in secs if s["sname"] == ".text"][0]
    TLO, THI = T["addr"], T["addr"]+T["size"]
    def is_code(v): return TLO <= v < THI

    print("="*72); print("  PUBG Mobile 追踪偏移抓取"); print("="*72)
    print("so     : %s  (%d 字节)" % (a.so, os.path.getsize(a.so)))
    print(".text  : 0x%X .. 0x%X" % (TLO, THI))

    # [1] 特征码
    print("\n[1] 特征码扫描  %s" % SIG.hex())
    hits, pos, tail = [], 0, b""
    CH = 32*1024*1024
    while pos < T["size"]:
        n = min(CH, T["size"]-pos)
        buf = mm[T["off"]+pos: T["off"]+pos+n]
        if tail: buf = tail + buf
        bva = TLO + pos - len(tail)
        st = 0
        while True:
            k = buf.find(SIG, st)
            if k < 0: break
            hits.append(bva+k); st = k+1
        tail = buf[-16:]; pos += n
    hits = sorted(set(hits))
    for h in hits: print("     0x%08X  [%s]" % (h, sec_of(h)))
    if not hits:
        print("\n  !! 未命中：游戏可能大版本更新"); return 1

    # [2] 虚表反查
    print("\n[2] 虚表反查（R_AARCH64_RELATIVE, addend = 桩地址）")
    REL = {}
    for s in secs:
        if s["type"] != 4: continue
        cnt = s["size"]//24
        blob = mm[s["off"]:s["off"]+cnt*24]
        for ro, ri, ra in struct.iter_unpack("<QQq", blob):
            if (ri & 0xFFFFFFFF) == 1027: REL[ro] = ra

    def raw_is_zero(va):
        # 真·零：不在重定位表里，且文件字节为 0
        # （重定位项在 PIE 文件里本身就是 0，必须排除）
        if va in REL: return False
        o = v2o(va)
        return o is not None and mm[o:o+8] == b"\x00"*8

    def vtable_start(slot):
        x = slot - 8
        while x > slot - 0x10000:
            if raw_is_zero(x) and raw_is_zero(x-8):
                nxt = REL.get(x+8)
                if nxt is None:
                    o2 = v2o(x+8)
                    nxt = struct.unpack_from("<Q", mm, o2)[0] if o2 else 0
                if is_code(nxt):
                    return x + 8
            x -= 8
        return None

    best = None
    for h in hits:
        refs = [ro for ro, ra in REL.items() if ra == h]
        print("     桩 0x%08X -> %d 处引用" % (h, len(refs)))
        for r in refs:
            vt0 = vtable_start(r)
            idx = (r-vt0)//8 if vt0 else -1
            print("        槽 0x%X  虚表 0x%X  槽index=%s" % (r, vt0 if vt0 else 0, idx))
        if best is None or len(refs) > len(best[1]): best = (h, refs)

    # [3] SDK 校验
    if a.sdk:
        print("\n[3] SDK 交叉校验")
        cand = glob.glob(os.path.join(a.sdk, "**", "Offsets.hpp"), recursive=True)
        if not cand:
            print("     未找到 Offsets.hpp")
        else:
            txt = open(cand[0], "r", encoding="utf-8", errors="replace").read()
            blk = re.search(r"namespace\s+UEPointers\s*\{(.*?)\}", txt, re.S)
            anchors = {}
            if blk:
                for m in re.finditer(r"(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", blk.group(1)):
                    anchors[m.group(1)] = int(m.group(2), 16)
            print("     SDK: %s" % cand[0])
            for k, v in anchors.items(): print("       %-14s = 0x%X" % (k, v))
            REF = {"Names":0x16CA0898, "World":0x1771CC38, "Engine":0x17719B78,
                   "UObjectArray":0x173EE2B8, "ObjObjects":0x173EE2C8}
            same = [k for k,v in REF.items() if anchors.get(k) == v]
            print("     与已知锚点一致: %d/%d  %s" % (len(same), len(REF), sorted(same)))
            print("     => " + ("同一 build，SDK 其余偏移可直接采用" if len(same)>=3
                                else "build 不同，需重新 dump"))

    # [4] 输出 + 回填
    print("\n[4] 推荐值（写进 jni/include/game/Offsets.h）")
    print("     inline constexpr std::uint64_t kTrackShootFn = 0x%X;" % best[0])
    if len(hits) > 1:
        print("     备选: %s" % ", ".join("0x%X"%h for h in hits if h != best[0]))
    if a.patch and os.path.exists(a.patch):
        src = open(a.patch, "r", encoding="utf-8").read()
        new, n = re.subn(r"(kTrackShootFn\s*=\s*)0x[0-9A-Fa-f]+",
                         lambda m: m.group(1)+"0x%X"%best[0], src)
        if n > 0:
            open(a.patch, "w", encoding="utf-8").write(new)
            print("     已回填 %s（%d 处）" % (a.patch, n))
        else:
            print("     回填失败：%s 里没有 kTrackShootFn" % a.patch)

    mm.close(); f.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
