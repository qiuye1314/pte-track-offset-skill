#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# export_baseline.py - 把 PTE 追踪偏移导出成机器可读基线 JSON
#
#   python3 export_baseline.py <libUE4.so> [--sdk-dir DIR] [--offsets Offsets.h]
#                              [--label 1.38.12] [--out baseline.json]
#
# 只做只读分析, 不写任何工程文件。产出的 JSON 是给 diff_baseline.py 对比用的。
import struct, mmap, sys, os, re, json, glob, hashlib, argparse

SIG = bytes.fromhex("a240201e8140201e6040201ec0035fd6")
EXPECT_KEY = 843   # 已验证的虚表槽 index, 跨子类应一致

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
    secs = []
    for i in range(e_shnum):
        o = e_shoff + i*e_shentsize
        v = struct.unpack_from("<IIQQQQIIQQ", mm, o)
        secs.append(dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5]))
    stt = secs[e_shstrndx]
    for s in secs:
        e = mm.find(b"\x00", stt["off"]+s["name"])
        s["sname"] = mm[stt["off"]+s["name"]:e].decode("utf-8","replace")
    return f, mm, segs, secs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("so")
    ap.add_argument("--sdk-dir", default=None)
    ap.add_argument("--offsets", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--out", default="baseline.json")
    a = ap.parse_args()

    f, mm, SEGS, secs = elf_open(a.so)
    def v2o(va):
        for b,o,s in SEGS:
            if b <= va < b+s: return o+(va-b)
        return None
    def sec_of(va):
        for s in secs:
            if s["addr"] and s["size"] and s["addr"] <= va < s["addr"]+s["size"]:
                return s["sname"]
        return None
    T = [s for s in secs if s["sname"] == ".text"]
    if not T:
        print("no .text"); return 1
    T = T[0]; TLO, THI = T["addr"], T["addr"]+T["size"]

    # [1] 特征码
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

    # [2] 虚表反查
    REL = {}
    for s in secs:
        if s["type"] != 4: continue
        blob = mm[s["off"]: s["off"] + (s["size"]//24)*24]
        for ro, ri, ra in struct.iter_unpack("<QQq", blob):
            if (ri & 0xFFFFFFFF) == 1027: REL[ro] = ra
    def raw_is_zero(va):
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
                if TLO <= nxt < THI: return x + 8
            x -= 8
        return None

    stubs = []
    for h in hits:
        refs = sorted([ro for ro, ra in REL.items() if ra == h])
        entries = []
        for r in refs:
            vt0 = vtable_start(r)
            entries.append(dict(slot_hex="0x%X"%r,
                                vtable_hex=("0x%X"%vt0) if vt0 else None,
                                index=((r-vt0)//8) if vt0 else None))
        o = v2o(h)
        stubs.append(dict(addr=h, addr_hex="0x%08X"%h, section=sec_of(h),
                          machine_code=mm[o:o+16].hex(), refs=len(refs),
                          indexes=[e["index"] for e in entries], entries=entries))
    primary = None
    for s in stubs:
        if s["refs"] >= 1 and EXPECT_KEY in s["indexes"]:
            primary = s; break
    if primary is None and stubs:
        primary = max(stubs, key=lambda x: x["refs"])

    # [3] SDK 锚点
    anchors = {}
    if a.sdk_dir:
        cand = glob.glob(os.path.join(a.sdk_dir, "**", "Offsets.hpp"), recursive=True)
        if cand:
            txt = open(cand[0], "r", encoding="utf-8", errors="replace").read()
            blk = re.search(r"namespace\s+UEPointers\s*\{(.*?)\}", txt, re.S)
            if blk:
                for m in re.finditer(r"(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", blk.group(1)):
                    anchors[m.group(1)] = int(m.group(2), 16)

    # [4] 工程常量全量导出
    consts = {}
    if a.offsets and os.path.exists(a.offsets):
        src = open(a.offsets, "r", encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"k(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", src):
            consts[m.group(1)] = int(m.group(2), 16)
        for m in re.finditer(r"k(\w+)\s*\[\s*\]\s*=\s*\{([^}]*)\}", src):
            consts[m.group(1)] = [int(x,16) for x in re.findall(r"0x[0-9A-Fa-f]+", m.group(2))]
        mv = re.search(r'kVersionTag\s*=\s*"([^"]*)"', src)
        if mv: consts["VersionTag"] = mv.group(1)

    h = hashlib.md5()
    with open(a.so,"rb") as fp:
        for chunk in iter(lambda: fp.read(8*1024*1024), b""): h.update(chunk)

    out = dict(
        schema="pte-baseline/1",
        label=a.label or os.path.basename(a.so),
        generated_by="export_baseline.py",
        target=dict(
            module=os.path.basename(a.so), size=os.path.getsize(a.so), md5=h.hexdigest(),
            text_lo="0x%X"%TLO, text_hi="0x%X"%THI,
        ),
        signature=SIG.hex(),
        stubs=[dict(addr_hex=s["addr_hex"], section=s["section"],
                    machine_code=s["machine_code"], refs=s["refs"],
                    indexes=s["indexes"],
                    entries=[dict(slot=e["slot_hex"], vtable=e["vtable_hex"],
                                  index=e["index"]) for e in s["entries"]]) for s in stubs],
        primary=dict(addr_hex=primary["addr_hex"], refs=primary["refs"],
                     indexes=primary["indexes"],
                     index_stable=(len(set(primary["indexes"]))==1),
                     matches_expected_index=(EXPECT_KEY in primary["indexes"])) if primary else None,
        sdk_anchors=dict((k, "0x%X"%v) for k,v in sorted(anchors.items())),
        game_offsets=dict((k, ("0x%X"%v) if isinstance(v,int) else v) for k,v in sorted(consts.items())),
    )
    with open(a.out, "w", encoding="utf-8") as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print("wrote %s" % a.out)
    print("  hits=%d  primary=%s  anchors=%d  consts=%d"
          % (len(hits), primary["addr_hex"] if primary else "NONE",
             len(anchors), len(consts)))
    mm.close(); f.close()
    return 0 if primary else 2

if __name__ == "__main__":
    sys.exit(main())
