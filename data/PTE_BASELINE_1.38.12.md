# PTE 追踪偏移 · 基线报告（PUBGM 1.38.12）

> 生成时间：2026-10-16 16:51:04
> 生成方式：只读扫描 + SDK 交叉校验，**未修改任何现有工程文件**

## 一、目标指纹

| 项 | 值 |
|---|---|
| 包名 | com.tencent.tmgp.pubgmhd |
| 版本 | 1.38.12 (versionCode 15910) |
| 模块 | libUE4.so |
| 大小 | 381387456 字节 |
| MD5 | e33beba15fcc01ae0e589ffea2409ee0 |
| .text | 0x8FDC960 .. 0x13F128B8 |

## 二、追踪桩（核心）

| 项 | 值 |
|---|---|
| **kTrackShootFn** | **0xA0FB548** |
| 机器码 | a240201e 8140201e 6040201e c0035fd6 |
| 指令 | fmov s2,s5 / fmov s1,s4 / fmov s0,s3 / ret |
| 虚表槽 | 0x140F1938 / 0x1422E460 / 0x14436A20 |
| 虚表基址 | 0x140EFEE0 / 0x1422CA08 / 0x14434FC8 |
| 槽 index | 843 / 843 / 843 |
| 直接调用数 | 0（纯虚表间接派发）|
| 备选桩 | 0xBE33F44（index=191, 1 虚表）|

## 三、SDK 锚点校验（5/5 一致）

| 锚点 | 值 |
|---|---|
| Names | 0x16CA0898 |
| UObjectArray | 0x173EE2B8 |
| ObjObjects | 0x173EE2C8 |
| Engine | 0x17719B78 |
| World | 0x1771CC38 |

**结论：同一 build，SDK 其余字段偏移可直接采用。**

## 四、全量偏移校准（共 28 项）

**OK=20　需修正(MOVE)=6　存疑(??)=2　丢失(LOST)=0**

| 外挂常量 | 当前值 | 语义 | 判定 | SDK 建议 |
|---|---|---|---|---|
| kActorAiming | 0x1848 | 开镜 | OK | 0x1848 bIsGunADS [ASTExtraCharacter] |
| kActorBullets | 0x2058 | 当前子弹 | OK | 0x2058 CurBulletNumInClip [ASTExtraShootWeapon] |
| kActorBulletsMax | 0x205C | 弹匣容量 | OK | 0x205C CurMaxBulletNumInOneClip [ASTExtraShootWeapon] |
| kActorFiring | 0x2750 | 开火 | OK | 0x2750 bIsWeaponFiring [ASTExtraBaseCharacter] |
| kActorHeldWeapon | 0xDD0 | 手持武器 | OK | 0xDD0 RepWeaponID [ASTExtraWeapon] |
| kActorHp | 0x1060 | 血量 | OK | 0x1060 Health [ASTExtraCharacter] |
| kActorHpMax | 0x1068 | 血上限 | OK | 0x1068 HealthMax [ASTExtraCharacter] |
| kActorInVehicle | 0x1310 | 载具 | OK | 0x1310 CurrentVehicle [ASTExtraCharacter] |
| kActorIsAI | 0xB94 | 人机 | OK | 0xB94 bIsAI [AUAECharacter] |
| kActorIsHuman | 0xB50 | 真人 | OK | 0xB50 IsPossessed [AUAECharacter] |
| kActorName | 0xAF8 | 名字 | OK | 0xAF8 PlayerName [AUAECharacter] |
| kActorTeam | 0xB78 | 队伍 | OK | 0xB78 TeamID [AUAECharacter] |
| kActorUid | 0xB20 | UID | OK | 0xB20 PlayerUID [AUAECharacter] |
| kCameraPtr | 0x680 | 相机指针 | OK | 0x680 PlayerCameraManager [APlayerController] |
| kMatchPlayerCount | 0x141C | 剩余玩家 | OK | 0x141C AlivePlayerNum [ASTExtraGameStateBase] |
| kMatchRealPlayerCount | 0xD9C | 真人玩家 | OK | 0xD98 TotalPlayerNum [ASTExtraGameStateBase] |
| kMatchTeamCount | 0x148C | 剩余队伍 | OK | 0x148C AliveTeamNum [ASTExtraGameStateBase] |
| kMeshArray | 0x658 | Mesh组件 | OK | 0x658 Mesh [ACharacter] |
| kWorldGameState | 0xAD8 | GameState | OK | 0xAD8 GameState [UWorld] |
| kWorldLevel | 0xB8 | 关卡 | OK | 0xB8 PersistentLevel [UWorld] |
| kActorAimVector | 0x1164 | 朝向向量 | ?? | (无) |
| kActorFeature | 0x3B9C | 玩家特征 | MOVE | 0x1D78 InheritFeatureComs [ASTExtraCharacter] |
| kActorHeight | 0x10BC | 身高 | ?? | 0x3E70 StandHalfHeight [ASTExtraBaseCharacter] |
| kActorKillCount | 0x2C | 击杀数 | MOVE | 0x844 Kills [AUAEPlayerState] |
| kActorThrowableId | 0x794 | 投掷物 | MOVE | 0x3A80 ThrowGrenadeModeChangedDelegate [ASTExtraBaseCharacter] |
| kBoneArray | 0x848 | 骨骼数组 | MOVE | 0x838 ComponentSpaceBoneExtraTransform [USkinnedMeshComponent] |
| kCameraWorldPos | 0x650 | 相机位置 | MOVE | 0x640 CameraCache [APlayerCameraManager] |
| kControllerFov | 0x688 | FOV | MOVE | 0x5E8 DefaultFOV [APlayerCameraManager] |

## 五、存疑/需修正项详情

- **kActorKillCount**（击杀数）当前 0x2C
  - SDK 建议 0x844
  - SDK 建议：0x844 Kills [AUAEPlayerState]
- **kActorHeight**（身高）当前 0x10BC
  - 偏移命中 DefaultSpeedValue，但语义应为 StandHalfHeight@0x3E70
  - SDK 建议：0x3E70 StandHalfHeight [ASTExtraBaseCharacter]
- **kActorFeature**（玩家特征）当前 0x3B9C
  - SDK 建议 0x1D78
  - SDK 建议：0x1D78 InheritFeatureComs [ASTExtraCharacter]
- **kActorAimVector**（朝向向量）当前 0x1164
  - SDK 无对应语义字段
  - SDK 建议：(无)
- **kBoneArray**（骨骼数组）当前 0x848
  - SDK 建议 0x838
  - SDK 建议：0x838 ComponentSpaceBoneExtraTransform [USkinnedMeshComponent]
- **kControllerFov**（FOV）当前 0x688
  - SDK 建议 0x5E8
  - SDK 建议：0x5E8 DefaultFOV [APlayerCameraManager]
- **kCameraWorldPos**（相机位置）当前 0x650
  - SDK 建议 0x640
  - SDK 建议：0x640 CameraCache [APlayerCameraManager]
- **kActorThrowableId**（投掷物）当前 0x794
  - SDK 建议 0x3A80
  - SDK 建议：0x3A80 ThrowGrenadeModeChangedDelegate [ASTExtraBaseCharacter]

## 六、新赛季适配用法

步骤 1：游戏更新后拉新 so

    adb-shell "su -c 'cp /data/app/*/com.tencent.tmgp.pubgmhd*/lib/arm64/libUE4.so /sdcard/pte_work/libUE4_new.so'"

步骤 2：重跑抓取（纯读，不带 --patch）

    python3 /sdcard/Download/pte_toolkit/ue4_track_tool.py /sdcard/pte_work/libUE4_new.so --sdk /sdcard

步骤 3：与本基线对撞

    - kTrackShootFn 变了 -> 直接替换该一行
    - index 843 还在 -> 虚表结构未动
    - SDK 锚点仍 5/5 -> 只需改少量偏移
    - 锚点不一致 -> 重新 dump SDK

## 七、已知语义错位（工程历史遗留，本次照实记录）

| 常量 | 工程值 | SDK 实际字段 | 建议值 |
|---|---|---|---|
| kActorHeight | 0x10BC | DefaultSpeedValue（移速） | 0x3E70 StandHalfHeight |
| kActorFeature | 0x3B9C | 本类无此字段 | 0x1D78 InheritFeatureComs |
| kActorAimVector | 0x1164 | VelocitySafety（速度安全） | 需人工确认 |
| kActorThrowableId | 0x0794 | 本类无此字段 | 0x3A90 ThrowGrenadeMode |
| kBoneArray | 0x0848 | 本类无此字段 | 0x838 ComponentSpaceBoneExtraTransform |
| kControllerFov | 0x0688 | 本类无此字段 | 0x5E8 DefaultFOV |
| kCameraWorldPos | 0x0650 | 本类无此字段 | 0x640 CameraCache |

---

## 附：锚点在文件中的落段说明

kGNameAnchor / kMatrixAnchor / kWorldAnchor / kPhysXInstance 均落在 **.bss**
（运行时填充的静态槽），ELF 文件里值为 0 属正常，非错误。
