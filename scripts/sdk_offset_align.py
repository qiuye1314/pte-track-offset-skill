#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# sdk_offset_align.py — 用 SDK 全量校准外挂偏移，输出「外挂偏移 <-> SDK 语义」映射表
import re, sys, json

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

# 全局偏移 -> (类,字段,类型)
BYOFF = {}
for c,d in CLS.items():
    for o,n,t in d["members"]:
        BYOFF.setdefault(o, []).append((c,n,t))

# ---- 外挂偏移 -> 期望的 SDK 语义关键词 ----
EXPECT = {
 "ActorName":       ("名字",   ["PlayerName","Name"]),
 "ActorUid":        ("UID",    ["PlayerUID","UID","PlayerID"]),
 "ActorIsHuman":    ("真人",   ["IsPossessed","bIsHuman","IsHuman"]),
 "ActorIsAI":       ("人机",   ["bIsAI","IsAI"]),
 "ActorIsAIPro":    ("高级AI", ["AIModelType","AIType"]),
 "ActorTeam":       ("队伍",   ["TeamID","Team","TeamNum"]),
 "ActorHp":         ("血量",   ["Health","HP","Hp"]),
 "ActorHpMax":      ("血量上限",["HealthMax","MaxHealth","HpMax"]),
 "ActorFiring":     ("开火",   ["bIsWeaponFiring","Firing","IsFiring"]),
 "ActorAiming":     ("开镜",   ["bIsGunADS","ADS","IsAiming"]),
 "ActorWeaponPtr":  ("武器指针",["CurrentUsingWeapon","Weapon"]),
 "ActorInVehicle":  ("载具",   ["CurrentVehicle","Vehicle"]),
 "ActorAction":     ("动作",   ["PawnState","Action","State"]),
 "ActorHeldWeapon": ("手持武器ID",["RepWeaponID","WeaponID"]),
 "ActorBullets":    ("子弹",   ["CurBulletNumInClip","BulletNum"]),
 "ActorBulletsMax": ("弹匣容量",["CurMaxBulletNumInOneClip","MaxBullet"]),
 "ActorKillPtr":    ("击杀指针",["Kill","Killed"]),
 "ActorKillCount":  ("击杀数", ["KillNum","KillCount","Kills"]),
 "ActorHeight":     ("身高",   ["Height","BodyHeight","CharacterHeight"]),
 "ActorFeature":    ("特征",   ["Feature","bIsPlayer","CharacterType"]),
 "ActorAimVector":  ("朝向",   ["AimVector","ForwardVector","Rotation","Rotator"]),
 "ActorRotator":    ("朝向rotator",["Rotation","Rotator","ActorRotation"]),
 "ActorThrowableId":("投掷物", ["Throwable","Grenade","Projectile"]),
 "ActorCoordZ":     ("坐标Z",  ["Location","RelativeLocation","Coord"]),
 "MeshArray":       ("Mesh组件",["Mesh","MeshComponent"]),
 "BoneArray":       ("骨骼数组",["BoneArray","BoneTransform","ComponentSpaceBone"]),
 "ControllerFov":   ("FOV",    ["Fov","FOV","FieldOfView"]),
 "CameraPtr":       ("相机",   ["PlayerCameraManager","CameraManager","Camera"]),
 "CameraWorldPos":  ("相机位置",["CameraLocation","CameraPos","Location"]),
 "WorldLevel":      ("关卡",   ["PersistentLevel","Level"]),
 "WorldGameState":  ("GameState",["GameState"]),
 "MatchTeamCount":  ("剩余队伍",["AliveTeamNum","TeamNum"]),
 "MatchPlayerCount":("剩余玩家",["AlivePlayerNum","PlayerNum","AlivePlayer"]),
 "MatchRealPlayerCount":("真人玩家",["PlayerNum","RealPlayerNum"]),
}

print("="*92)
print("SDK 全量校准：外挂偏移 <-> SDK 语义")
print("="*92)
print("%-22s %-8s %-38s %-6s %s" % ("外挂常量","偏移","SDK 字段(所属类)","判定","说明"))
print("-"*92)

rows=[]
for k, (desc, kws) in EXPECT.items():
    if k not in plugin: continue
    off = plugin[k]
    # 1) 先在全局找精确偏移，优先字段名匹配关键词
    best = None
    for c,n,t in BYOFF.get(off, []):
        score = 0
        for kw in kws:
            if kw.lower() in n.lower(): score += 10
        if score > 0 and (best is None or score > best[0]):
            best = (score, c, n, t)
    if best:
        _,c,n,t = best
        rows.append((k, off, "%s.%s"%(c,n), "OK", desc))
        continue
    # 2) 精确偏移存在但不匹配关键词 -> 找该偏移上"最像"的
    cands = BYOFF.get(off, [])
    if cands:
        c,n,t = min(cands, key=lambda x: len(x[0]))
        rows.append((k, off, "%s.%s"%(c,n), "??", "偏移在,名不匹配("+desc+")"))
        continue
    # 3) 全局按关键词找（偏移可能变了）
    found=[]
    for o, lst in BYOFF.items():
        for c,n,t in lst:
            for kw in kws:
                if kw.lower()==n.lower() or (len(kw)>5 and kw.lower() in n.lower()):
                    found.append((abs(o-off), o, c, n, t)); break
    found.sort()
    if found:
        d,o,c,n,t = found[0]
        rows.append((k, off, "%s.%s@0x%X"%(c,n,o), "MOVE", "SDK建议 0x%X (差%d)"%(o,d)))
    else:
        rows.append((k, off, "(SDK无匹配)", "LOST", desc))

for k, off, sdkf, verdict, note in rows:
    print("%-22s 0x%-6X %-38s %-6s %s" % (k, off, sdkf[:38], verdict, note))

ok   = sum(1 for r in rows if r[3]=="OK")
mv   = sum(1 for r in rows if r[3]=="MOVE")
qq   = sum(1 for r in rows if r[3]=="??")
lost = sum(1 for r in rows if r[3]=="LOST")
print("-"*92)
print("统计: OK=%d  需修正(MOVE)=%d  名不匹配(??)=%d  未找到(LOST)=%d  总=%d"
      % (ok, mv, qq, lost, len(rows)))
