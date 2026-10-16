#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# sdk_verify2.py — 深度验证：处理指针链、全类搜索、世界/矩阵链校验
import re

SDK = "/sdcard/pte_work/sdk138/#U548c#U5e73SDK/AIOHeader.hpp"
OFF = "/sdcard/pte_work/ex/pte#U8ffd#U9501#U6f0f#U6253#U6e90/jni/include/game/Offsets.h"

src = open(OFF, encoding="utf-8", errors="replace").read()
plugin = {}
for m in re.finditer(r"k(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", src):
    plugin[m.group(1)] = int(m.group(2), 16)

lines = open(SDK, encoding="utf-8", errors="replace").read().split("\n")
CLS = {}; cur = None
pat_cls = re.compile(r"^struct\s+(\w+)\s*:\s*(\w+)")
pat_mem = re.compile(r"^\s*(?:struct\s+)?([\w:<>,\*\s]+?)\s+(\w+)\s*;\s*//\s*0x([0-9A-Fa-f]+)")
for ln in lines:
    mc = pat_cls.match(ln)
    if mc:
        cur = mc.group(1); CLS.setdefault(cur, {"parent": mc.group(2), "members": []}); continue
    if cur is None: continue
    mm = pat_mem.match(ln)
    if mm:
        CLS[cur]["members"].append((int(mm.group(3),16), mm.group(2), mm.group(1).strip()))

def chain(cls, limit=14):
    out=[]; c=cls
    while c in CLS and len(out)<limit: out.append(c); c=CLS[c]["parent"]
    return out
def lookup(cls, off):
    for c in chain(cls):
        for o,n,t in CLS[c]["members"]:
            if o==off: return c,n,t
    return None

# 全局偏移索引
BYOFF = {}
for c,d in CLS.items():
    for o,n,t in d["members"]:
        BYOFF.setdefault(o, []).append((c,n,t))

print("="*80)
print("A. 未命中的 Actor 偏移：全局搜索最接近的字段")
print("="*80)
MISS = ["ActorClassId","ActorKillCount","ActorRotator","ActorThrowableId",
        "ActorHeldWeapon","ActorBullets","ActorBulletsMax","ActorKillPtr",
        "ActorCoordZ","ActorAimVector","ActorHeight","ActorFeature"]
for k in MISS:
    if k not in plugin: continue
    off = plugin[k]
    near = sorted(BYOFF.get(off, []), key=lambda x: len(x[0]))[:4]
    print("\n  %-20s 0x%-6X" % (k, off))
    if near:
        for c,n,t in near: print("       精确: %-34s [%s]" % (n, c))
    else:
        # 找最近的偏移
        cands=[]
        for o, lst in BYOFF.items():
            if abs(o-off) <= 8:
                for c,n,t in lst: cands.append((abs(o-off), o, c, n, t))
        cands.sort()
        for d,o,c,n,t in cands[:4]:
            print("       邻近 ±%d: 0x%-5X %-28s [%s]" % (d,o,n,c))

print("\n" + "="*80)
print("B. 指针链验证（外挂的二级偏移）")
print("="*80)
# kActorKillPtr 0x2988 -> +kActorKillCount 0x2C
for base, inner, desc in [
    ("ActorKillPtr","ActorKillCount","击杀数"),
    ("ActorWeaponPtr","WeaponCurrent","武器"),
]:
    b = plugin.get(base); i = plugin.get(inner)
    if b is None: continue
    r = lookup("ASTExtraCharacter", b)
    if r:
        c,n,t = r
        print("  %s 0x%X -> %s.%s  (类型 %s)" % (base, b, c, n, t))
        # 如果类型是结构体，进去找 inner
        mt = re.match(r"(?:struct\s+)?(\w+)", t)
        if mt and mt.group(1) in CLS and i is not None:
            r2 = lookup(mt.group(1), i)
            if r2:
                c2,n2,t2 = r2
                print("      + 0x%X -> %s.%s  (%s)  <<< %s" % (i, c2, n2, t2, desc))

print("\n" + "="*80)
print("C. 世界 / 关卡 / GameState 链验证")
print("="*80)
for cls, pairs in [
    ("UWorld", [("WorldObjectArray",0xa0),("WorldObjectCount",0xa8),("WorldLevel",0xb8),("WorldGameState",0xad8)]),
    ("ULevel", [("WorldObjectArray",0xa0),("WorldObjectCount",0xa8)]),
    ("AGameStateBase", [("MatchTeamCount",0x148c),("MatchPlayerCount",0x141c),("MatchRealPlayerCount",0xd9c)]),
]:
    print("\n  --- %s ---" % cls)
    for k, off in pairs:
        r = lookup(cls, off)
        if r:
            c,n,t = r
            print("    0x%-6X  %-28s [%s]" % (off, n, c))
        else:
            cands=[]
            for o,lst in BYOFF.items():
                if abs(o-off)<=0x10:
                    for cc,nn,tt in lst: cands.append((abs(o-off),o,cc,nn))
            cands.sort()
            s = "; ".join("±%d:0x%X %s.%s"%(d,o,cc,nn) for d,o,cc,nn in cands[:3])
            print("    0x%-6X  (未命中)  %s" % (off, s))

print("\n" + "="*80)
print("D. 骨骼 / 武器属性链")
print("="*80)
for cls, pairs in [
    ("ACharacter", [("MeshArray",0x658)]),
    ("USkeletalMeshComponent", [("BoneArray",0x848),("BoneArrayOld",0x838)]),
    ("ASTExtraShootWeapon", [("WeaponPropPage",0xc80),("WeaponBulletSpd",0x15d4),
                             ("WeaponRecoilX",0x1ed8),("WeaponRecoilY",0x1ee4)]),
    ("ASTExtraPlayerController", [("ControllerFov",0x688),("CameraPtr",0x680),("CameraWorldPos",0x650),
                                  ("CameraYaw",0x670),("CrosshairX",0x600),("CrosshairY",0x604)]),
]:
    print("\n  --- %s ---" % cls)
    for k, off in pairs:
        r = lookup(cls, off)
        if r:
            c,n,t = r; print("    0x%-6X  %-30s [%s]" % (off, n, c))
        else:
            print("    0x%-6X  (未命中)" % off)
