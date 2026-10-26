#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect_source_target.py — 判定一份 PUBG/和平精英 源码面向哪个游戏/版本

用法:
    python3 detect_source_target.py <工程目录>
    python3 detect_source_target.py <工程目录> --so <libUE4.so>

输出: 包名候选 / 偏移指纹命中 / 疑似版本 / 追踪形态 / 建议写回组

设计原则:
    拿到源码先判游戏, 再动代码。判错一次浪费几小时, 判对只花 5 分钟。
"""
import os
import re
import sys
import argparse

PACKAGES = {
    "com.tencent.tmgp.pubgmhd": "和平精英 (国服)",
    "com.tencent.igce":         "体验服 = 国际服 IGCE 包 (与国际服同构)",
    "com.tencent.ig":           "PUBG MOBILE 国际服",
    "com.rekoo.pubgm":          "台服",
    "com.pubg.krmobile":        "韩服",
    "com.vng.pubgmobile":       "越南服",
}

# UWorld 锚点指纹 -> (版本判定, 自身链, 矩阵锚点)
UWORLD_FP = {
    0x1771CC38: ("和平精英 (较新版本)", "0xc0/0x88/0x30/0x3540", 0x176E6EE0),
    0x15772758: ("和平精英 (旧版, 已废弃)", "未知", None),
    0xF621D90:  ("PUBG 4.6 国际服",   "0x38/0x78/0x30/0x28D8", 0xF5F4370),
    0xF1D5F70:  ("PUBG 4.5 国际服",   "矩阵 +0xC0 +0x590",      0xF1D5F70),
}

MATRIX_FP = {
    0x176E6EE0: "和平精英",
    0xF5F4370:  "PUBG 4.6 国际服",
}

# 追踪函数偏移 -> 归属
TRACK_FP = {
    0x0A0FB548: ("和平精英 1.38", "fmov 返回值桩", "s3/s4/s5"),
    0x06FF841C: ("PUBG 4.6 国际服", "双 float3 参数函数", "s0/s1/s2"),
    0x06235980: ("体验服 IGCE 4.7.3 (与国际服同构)", "读全局坐标对象", "s0/s1/s2"),
}

FMOV_STUB = bytes.fromhex("a240201e8140201e6040201ec0035fd6")

CODE_EXT = (".h", ".hpp", ".c", ".cc", ".cpp", ".cxx")


def walk_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(CODE_EXT):
                yield os.path.join(dirpath, f)


def read_text(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return ""


def scan_packages(files):
    hits = {}
    for p in files:
        txt = read_text(p)
        for pkg, name in PACKAGES.items():
            if pkg in txt:
                hits.setdefault(pkg, {"name": name, "files": []})
                hits[pkg]["files"].append(os.path.relpath(p))
    return hits


def scan_offsets(files):
    """抓所有 0x... 字面量, 统计指纹命中"""
    score = {}
    matrix = {}
    for p in files:
        txt = read_text(p)
        for m in re.finditer(r"0[xX]([0-9a-fA-F]{4,10})", txt):
            v = int(m.group(1), 16)
            if v in UWORLD_FP:
                score[v] = score.get(v, 0) + 1
            if v in MATRIX_FP:
                matrix[v] = matrix.get(v, 0) + 1
    return score, matrix


def scan_track_fn(files):
    hits = {}
    for p in files:
        txt = read_text(p)
        for m in re.finditer(r"0[xX]0?([0-9a-fA-F]{6,10})", txt):
            v = int(m.group(1), 16)
            if v in TRACK_FP:
                hits[v] = hits.get(v, 0) + 1
    return hits


def scan_release_tag(files, so_path=None):
    tags = set()
    pat = re.compile(r"Release(\d+\.\d+(?:\.\d+)?)")
    for p in files:
        for m in pat.finditer(read_text(p)):
            tags.add(m.group(1))
    if so_path and os.path.isfile(so_path):
        try:
            with open(so_path, "rb") as fh:
                blob = fh.read()
            for m in re.finditer(rb"Release(\d+\.\d+(?:\.\d+)?)", blob):
                tags.add(m.group(1).decode("ascii", "replace"))
        except Exception:
            pass
    return sorted(tags)


def check_fmov_stub(so_path):
    if not so_path or not os.path.isfile(so_path):
        return None
    try:
        with open(so_path, "rb") as fh:
            blob = fh.read()
    except Exception:
        return None
    idx = blob.find(FMOV_STUB)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="工程目录 (约定含 src/ 或 jni/)")
    ap.add_argument("--so", default=None, help="可选: libUE4.so 路径, 用于查版本串与 fmov 桩")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print("目录不存在:", args.root)
        return 2

    files = list(walk_files(args.root))
    print("=" * 60)
    print("  源码归属判定")
    print("=" * 60)
    print("扫描代码文件: %d 个\n" % len(files))

    verdicts = []

    # ---- 1. 包名 ----
    pkgs = scan_packages(files)
    print("[1] 包名")
    if pkgs:
        for pkg, info in sorted(pkgs.items()):
            print("    %-26s %s" % (pkg, info["name"]))
            for f in info["files"][:4]:
                print("        %s" % f)
            verdicts.append(info["name"])
    else:
        print("    (未找到包名, 可能是纯偏移文件)")
    print()

    # ---- 2. 偏移指纹 ----
    uw, mx = scan_offsets(files)
    print("[2] 偏移指纹")
    if uw:
        for v, n in sorted(uw.items(), key=lambda kv: -kv[1]):
            name, chain, mat = UWORLD_FP[v]
            print("    UWorld 0x%X  x%d  -> %s" % (v, n, name))
            print("        自身链 %s" % chain)
            verdicts.append(name)
    else:
        print("    (UWorld 锚点未命中已知指纹, 可能是新版本, 需人工核对)")
    if mx:
        for v, n in sorted(mx.items(), key=lambda kv: -kv[1]):
            print("    矩阵   0x%X  x%d  -> %s" % (v, n, MATRIX_FP[v]))
    print()

    # ---- 3. 追踪函数 ----
    tf = scan_track_fn(files)
    print("[3] 追踪函数")
    if tf:
        for v, n in sorted(tf.items(), key=lambda kv: -kv[1]):
            game, shape, group = TRACK_FP[v]
            print("    kTrackShootFn 0x%X  x%d" % (v, n))
            print("        归属   %s" % game)
            print("        形态   %s" % shape)
            print("        写回组 %s  <-- 必须用这个" % group)
            verdicts.append(game)
    else:
        print("    (未找到已知追踪偏移, 需按 skill 重新抓)")
    print()

    # ---- 4. 版本串 ----
    tags = scan_release_tag(files, args.so)
    print("[4] 版本串 (Release x.y.z)")
    print("    %s" % (", ".join(tags) if tags else "(未找到)"))
    print()

    # ---- 5. fmov 桩 ----
    print("[5] fmov 返回值桩")
    stub = check_fmov_stub(args.so)
    if stub is None:
        print("    (未提供 so, 跳过)")
    elif stub >= 0:
        print("    存在 @ 文件偏移 0x%X  -> 国服那种返回值桩形态" % stub)
    else:
        print("    不存在  -> 不是返回值桩形态, 写回组必须实测")
    print()

    # ---- 结论 ----
    print("=" * 60)
    print("  结论")
    print("=" * 60)
    if verdicts:
        uniq = []
        for v in verdicts:
            if v not in uniq:
                uniq.append(v)
        print("疑似归属: %s" % " / ".join(uniq))
        if len(uniq) > 1:
            print("!! 出现多个候选, 说明工程里混着两套偏移, 必须人工确认")
            print("!! 混用时最常见的症状: 绘制正常但追踪不生效")
    else:
        print("无法判定, 请人工核对包名与 UWorld 锚点")

    if tf:
        v = max(tf, key=lambda k: tf[k])
        print("建议写回组: %s" % TRACK_FP[v][2])
    print()
    print("下一步: 按 references/source_attribution.md 的对照表逐项替换, 不要跳项。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
