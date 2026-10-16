#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# diff_baseline.py - 新赛季基线 vs 已有基线, 自动出"该改什么"的差异表
#
#   python3 diff_baseline.py --base baseline_1.38.12.json --new baseline_new.json
#
# 两步用法（新赛季）:
#   1) python3 export_baseline.py libUE4_new.so --sdk-dir <新SDK> --offsets <新Offsets.h> \
#          --label "PUBGM 1.40" --out baseline_new.json
#   2) python3 diff_baseline.py --base data/baseline_1.38.12.json --new baseline_new.json
#
# 只读, 不改任何文件。
import json, sys, argparse

def load(p):
    with open(p, encoding="utf-8") as fp: return json.load(fp)
def toi(v):
    return int(v, 16) if isinstance(v, str) and v.startswith("0x") else v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--new", required=True)
    ap.add_argument("--json", action="store_true", help="额外输出机器可读 diff")
    a = ap.parse_args()
    B, N = load(a.base), load(a.new)

    print("="*78)
    print("  PTE 基线对撞: %s  ->  %s" % (B.get("label"), N.get("label")))
    print("="*78)

    # --- 1. so 指纹 ---
    tb, tn = B["target"], N["target"]
    print("\n[1] 模块指纹")
    same_md5 = tb.get("md5") == tn.get("md5")
    print("    base md5=%s  size=%d" % (tb.get("md5"), tb.get("size", 0)))
    print("    new  md5=%s  size=%d" % (tn.get("md5"), tn.get("size", 0)))
    print("    => %s" % ("同一份 so, 无需改动" if same_md5 else "so 已更新, 以下差异全部生效"))

    # --- 2. 追踪桩 ---
    print("\n[2] 追踪桩（kTrackShootFn 的来源）")
    pb, pn = B.get("primary") or {}, N.get("primary") or {}
    changed = pb.get("addr_hex") != pn.get("addr_hex")
    print("    base 主桩 %-10s refs=%s indexes=%s" % (pb.get("addr_hex"), pb.get("refs"), pb.get("indexes")))
    print("    new  主桩 %-10s refs=%s indexes=%s" % (pn.get("addr_hex"), pn.get("refs"), pn.get("indexes")))
    if changed:
        print("    >> 必改: kTrackShootFn  %s  ->  %s" % (pb.get("addr_hex"), pn.get("addr_hex")))
    else:
        print("    >> 追踪桩未变, kTrackShootFn 可沿用")
    ib, iN = pb.get("indexes") or [], pn.get("indexes") or []
    if ib and iN and set(ib) == set(iN):
        print("    >> 虚表槽 index 一致(%s) -> 虚表结构未动, 稳" % sorted(set(iN)))
    elif ib and iN:
        print("    >> 虚表槽 index 变了 %s -> %s : 基类虚表重排, 需复核选靶链" % (sorted(set(ib)), sorted(set(iN))))
    if not pn.get("matches_expected_index", True):
        print("    !! 注意: 新桩 index 不等于 843, 特征码可能命中了同类不同基类的桩, 人工确认")
    # 命中数健康检查
    print("    命中数: base=%d new=%d  (期望 1~2)" % (len(B.get("stubs",[])), len(N.get("stubs",[]))))

    # --- 3. SDK 锚点 ---
    print("\n[3] SDK 锚点")
    ab, an = B.get("sdk_anchors") or {}, N.get("sdk_anchors") or {}
    akeys = sorted(set(ab) | set(an))
    if not akeys:
        print("    (无锚点数据: 生成基线时未给 --sdk-dir)")
    agree = 0
    for k in akeys:
        s = "OK  " if ab.get(k) == an.get(k) else "MOVE"
        if ab.get(k) == an.get(k): agree += 1
        print("    %-14s %-12s -> %-12s %s" % (k, ab.get(k, "-"), an.get(k, "-"), s))
    atotal = len(akeys)
    if akeys:
        print("    => 一致 %d/%d : %s" % (agree, atotal,
              "同一 build, 未列出的字段偏移可直接沿用" if agree >= max(3, atotal*0.6)
              else "build 差异大, 建议重新 dump SDK"))

    # --- 4. 全量字段偏移 ---
    print("\n[4] 字段偏移全量对撞")
    gb, gn = B.get("game_offsets") or {}, N.get("game_offsets") or {}
    keys = sorted(set(gb) | set(gn))
    same, diff, added, dropped = [], [], [], []
    for k in keys:
        if k not in gb: added.append(k); continue
        if k not in gn: dropped.append(k); continue
        vb, vn = toi(gb[k]), toi(gn[k])
        (diff if vb != vn else same).append((k, gb[k], gn[k]))
    print("    未变 %d  变化 %d  新增 %d  移除 %d  (共 %d)" % (len(same), len(diff), len(added), len(dropped), len(keys)))
    if diff:
        print("\n    %-26s %-12s -> %-12s" % ("常量", "旧", "新"))
        print("    " + "-"*54)
        for k, vb, vn in diff:
            try:
                delta = toi(vn) - toi(vb)
                ds = " (%+d)" % delta if isinstance(toi(vn), int) and isinstance(toi(vb), int) else ""
            except Exception:
                ds = ""
            print("    k%-25s %-12s -> %-12s%s" % (k, vb, vn, ds))
    if added:   print("    新增: %s" % ", ".join("k"+k for k in added))
    if dropped: print("    移除: %s" % ", ".join("k"+k for k in dropped))

    # --- 5. 行动清单 ---
    print("\n" + "="*78)
    print("  行动清单")
    print("="*78)
    acts = []
    if same_md5: acts.append("  - so 完全相同: 什么都不用改, 直接复用旧偏移")
    if changed:  acts.append("  - [必改] kTrackShootFn = %s" % pn.get("addr_hex"))
    if diff:     acts.append("  - [必改] 上表 %d 个字段偏移按新值替换" % len(diff))
    if iN and ib and set(ib) != set(iN):
        acts.append("  - [复核] 虚表 index 重排, 选靶/骨骼链要重新验证")
    if atotal and agree < atotal:
        acts.append("  - [复核] SDK 锚点有变动(%d/%d), 重新 dump 一份新 SDK 再做语义校准" % (agree, atotal))
    if not acts: acts.append("  - 无结构性变化")
    for x in acts: print(x)
    print("\n  提醒: 本工具只读, 不会替你写进 Offsets.h。改完记得跑一遍 build_gateway.sh 验证。")
    if a.json:
        print("\n[json]"); print(json.dumps(dict(
            base=B.get("label"), new=N.get("label"), so_same=same_md5,
            track_changed=changed, track_new=pn.get("addr_hex"),
            index_same=bool(ib and iN and set(ib)==set(iN)),
            anchors_agree=agree, anchors_total=len(keys),
            changed_offsets=dict((k, [vb, vn]) for k, vb, vn in diff)), indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
