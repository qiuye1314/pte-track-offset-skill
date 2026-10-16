#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# offset_fix_table.py — 生成「外挂偏移修正建议表」（用 SDK 语义纠正错误字段）
import re

SDK = "/sdcard/pte_work/sdk138/#U548c#U5e73SDK/AIOHeader.hpp"
lines = open(SDK, encoding="utf-8", errors="replace").read().split("\n")
CLS = {}; cur = None
pc = re.compile(r"^struct\s+(\w+)\s*:\s*(\w+)")
pm = re.compile(r"^\s*(?:struct\s+)?([\w:<>,\*\s]+?)\s+(\w+)\s*;\s*//\s*0x([0-9A-Fa-f]+)")
for ln in lines:
    mc = pc.match(ln)
    if mc:
        cur = mc.group(1); CLS.setdefault(cur, {"parent": mc.group(2), "members": []}); continue
    if cur is None: continue
    mm = pm.match(ln)
    if mm:
        CLS[cur]["members"].append((int(mm.group(3),16), mm.group(2), mm.group(1).strip()))

def chain(cls, limit=12):
    out=[]; c=cls
    while c in CLS and len(out)<limit: out.append(c); c=CLS[c]["parent"]
    return out

def find(cls, pat, exact=False):
    r = re.compile(pat, re.I)
    out=[]
    for c in chain(cls):
        for o,n,t in CLS[c]["members"]:
            if (n==pat if exact else r.search(n)):
                out.append((o,n,t,c))
    return out

def find_global(pat, exact=False):
    r = re.compile(pat, re.I)
    out=[]
    for c,d in CLS.items():
        for o,n,t in d["members"]:
            if (n==pat if exact else r.search(n)):
                out.append((o,n,t,c))
    return out

print("="*96)
print("外挂偏移修正建议表（基于 SDK 1.38 真实字段语义）")
print("="*96)

FIX = [
 ("kActorHeight",    0x10BC, "身高(float cm)",   "ASTExtraBaseCharacter", r"StandHalfHeight|CrouchHalfHeight|ProneHalfHeight"),
 ("kActorFeature",   0x3B9C, "玩家特征过滤",     "ASTExtraCharacter",     r"featureComs|InheritFeatureComs"),
 ("kActorAimVector", 0x1164, "朝向向量",         "ASTExtraBaseCharacter", r"AimVector|ForwardVector|ActorRotation"),
 ("kActorRotator",   0x01A8, "朝向 rotator",     "ASTExtraBaseCharacter", r"ActorRotation|^Rotation$"),
 ("kActorThrowableId",0x0794,"投掷物ID",         "ASTExtraBaseCharacter", r"ThrowGrenadeMode|CurrentThrowable|ThrowableID"),
 ("kBoneArray",      0x0848, "骨骼数组指针",     "USkinnedMeshComponent", r"BoneArray|ComponentSpaceBone|BoneTransform"),
 ("kControllerFov",  0x0688, "FOV",              "APlayerCameraManager",  r"^DefaultFOV$|^Fov$|DesiredFOV"),
 ("kCameraWorldPos", 0x0650, "相机世界位置",     "APlayerCameraManager",  r"LastFrameCameraCache|CameraCache"),
 ("kActorKillCount", 0x002C, "击杀数",           "AUAEPlayerState",       r"^Kills$|KillNum|KillCount"),
]

for name, old, desc, cls, pat in FIX:
    print("\n  %s  当前 0x%X  (%s)" % (name, old, desc))
    hits = find(cls, pat)
    if not hits:
        hits = find_global(pat)
    if hits:
        for o,n,t,c in hits[:5]:
            mark = "  <== 推荐" if (o,n,t,c)==hits[0] else ""
            print("      SDK: 0x%-6X %-40s [%s]%s" % (o,n,c,mark))
    else:
        print("      (SDK 未找到，需人工确认)")

# 额外：全量统计 SDK 里的关键类
print("\n" + "="*96)
print("SDK 关键类字段数")
print("="*96)
for c in ["AActor","ACharacter","APawn","AUAECharacter","ASTExtraCharacter",
          "ASTExtraBaseCharacter","ASTExtraPlayerState","ASTExtraGameStateBase",
          "ASTExtraShootWeapon","ASTExtraWeapon","USkinnedMeshComponent",
          "APlayerCameraManager","UWorld","ULevel","ASTExtraPlayerController"]:
    if c in CLS:
        n = len(CLS[c]["members"])
        print("  %-28s %4d 字段   父类=%s" % (c, n, CLS[c]["parent"]))
    else:
        print("  %-28s (不在 SDK)" % c)
