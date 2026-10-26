
---

## ★ 第 0 步（最重要）：先判定源码属于哪个游戏

**任何源码到手，先跑判定，再动一行代码。**

```bash
python3 scripts/detect_source_target.py <工程目录> [--so libUE4.so]
```

它输出：包名候选 / UWorld+矩阵偏移指纹 / 追踪函数归属 / 版本串 / fmov 桩在不在 / 建议写回组。

**判错一次的代价是几小时乱试，判对只花 5 分钟。**

| 包名 | 游戏 |
|---|---|
| com.tencent.tmgp.pubgmhd | 和平精英（国服） |
| com.tencent.ig | PUBG MOBILE 国际服 |
| com.tencent.igce | 国际服 IGCE 包 |
| com.rekoo.pubgm | 台服 |
| com.pubg.krmobile | 韩服 |
| com.vng.pubgmobile | 越南服 |

全文：`pte_track_doc(section="attrib")`　脚本：`pte_track_doc(section="detect")`

**驱动对接（换驱动 = 对接驱动，不是改常量）**：`pte_track_doc(section="driver")`
—— RT/Paradise ABI 对照、7 步对接流程、fd 从哪来、Paradise 记录污染坑、验证清单。

**这次调试的全过程复盘（14 轮、前 12 轮全错、换基底后 2 轮打通）**：
`pte_track_doc(section="retro")` —— 含症状映射表 + 失败尝试速查，避免重走。

**排查铁律：参数怎么调都不对时，先回头确认「游戏/版本判对了吗」，不要继续调参数。**

**版本更新后改什么：** 改的是**偏移（地址类）**，写回组（语义类）通常不变。
先重抓 UWorld/矩阵/坐标/骨骼/追踪偏移；只有反汇编发现追踪函数**入口形态变了**，
才需要重新判定写回组。详见 `pte_track_doc(section="intl46")` 第十节。
---
name: pte-track-offset-mobile
description: PUBG Mobile(和平精英) 追踪偏移(PTE shadow 子弹追踪)抓取与 SDK 反查方法论：从 libUE4.so 用特征码+虚表反查定位原生虚函数断点，用 UE4Dump SDK 交叉校验 build 一致性并校准全量字段偏移，一键流水线拉so→抓偏移→回填→NDK编译。当用户要「抓追踪偏移」「PTE追踪」「漏打追踪断点」「和平精英1.38偏移」「用SDK找偏移」「CalShoot地址」「kTrackShootFn」「子弹追踪怎么实现」或提到 com.tencent.tmgp.pubgmhd 追踪/断点/shadow/810/811/812 时使用。
whenToUse: 用户要在一款 UE4 手游上抓「追踪类断点偏移」（原生虚函数，不在 SDK 反射表里）、要用现成 SDK 校准字段偏移、要把偏移抓取接进自动构建流水线、或问「SDK 能不能找到某个偏移」时。
metadata:
  version: 1.5.4
  author: 老大
  upstream: PUBG Mobile 1.38.12 (com.tencent.tmgp.pubgmhd) 追踪外挂源码逆向 + UE4Dump SDK 对照
  dshHome: /root/.dsh/skills/pte-track-offset-mobile
  artifacts: /sdcard/Download/pte_toolkit/
---

# PUBG Mobile 追踪偏移抓取技能（PTE Shadow 断点）

> 目标读者：拿到一份 UE4 手游外挂源码 / 要自己挖追踪断点 / 游戏更新后偏移全废需要重抓的人。
> 核心价值：**把「追踪偏移怎么抓」从玄学变成 10 秒可复现的流程**，并说清 SDK 能帮什么、不能帮什么。

## 零、一句话结论（先记这个，避免走弯路）

**UE4Dump SDK 里找不到追踪偏移。** SDK 的 script.json 收录 60020 个函数，**100% 是 $$exec 反射桩**（UFunction 的 ProcessEvent 跳板），而追踪断点是**原生 C++ 虚函数**，不注册进反射表。

- **SDK 负责**：引擎锚点（GWorld/GNames/Engine）+ 13000+ 类的字段偏移 → **直接抄**
- **二进制负责**：追踪桩这类原生虚函数 → **特征码扫 + 虚表反查**
- **SDK 的间接价值**：验证 build 一致性，证明那些字段偏移能不能用

## 一、追踪断点的本质（理解了才会抓）

追踪桩是一个 **4 指令 float3 getter**：

    fmov s2, s5      ; 0x1E2040A2
    fmov s1, s4      ; 0x1E204081
    fmov s0, s3      ; 0x1E204060
    ret              ; 0xD65F03C0

把 v3/v4/v5 搬到 v0/v1/v2 返回。

**整个「子弹追踪」的机关**：

    驱动在函数入口下 PTE 影子断点
          ↓
    游戏调用它 → 断点触发
          ↓
    驱动把目标坐标写进 v3/v4/v5（只改影子寄存器，物理内存不动）
          ↓
    桩函数执行 → 把 v3/v4/v5 当「返回值」吐回 v0/v1/v2
          ↓
    调用者拿去做弹道计算 → 子弹飞向目标

**为什么用 PTE shadow 而不是 inline hook**：函数本来就在，只篡改返回寄存器 → 游戏读自己的代码段做 CRC 校验时**读到的还是原版**。

## 二、抓取四步法（核心流程）

### 第 1 步：特征码扫描

    特征码 = a240201e 8140201e 6040201e c0035fd6
    含义   = fmov s2,s5 | fmov s1,s4 | fmov s0,s3 | ret

在 3.3 亿字节的 .text 里，这个形状**只出现 1~2 次** → 稀有度极高，可作稳定特征码。

### 第 2 步：虚表反查（确认是虚函数）

特征码命中的地址**没有任何 BL 直接调用** → 说明是间接调用。用 ELF 重定位表反查：

    扫 R_AARCH64_RELATIVE 重定位项，找 addend == 桩地址
    → 得到「函数指针存放位置」（都在 .data.rel.ro = 虚表区）

### 第 3 步：重建虚表边界

Itanium ABI 虚表头布局：

    [-16] offset_to_top   （通常 0）
    [-8]  typeinfo        （无 RTTI 时为 0）
    [0]   首虚函数

从槽位往前找**最近的一对连续零**（且不在重定位表里、+8 是代码指针）→ 那就是虚表起点，(槽位-起点)/8 就是**槽 index**。

### 第 4 步：SDK 交叉校验

拿 SDK 的 Offsets.hpp 锚点跟二进制对照，判断是不是同一 build：

    Names / World / Engine / UObjectArray / ObjObjects
    5/5 一致 → 同一 build，SDK 其余偏移可直接用

## 三、SDK 用法（什么时候查 SDK，什么时候不能查）

| 要查什么 | 查 SDK 吗 | 怎么查 |
|---|---|---|
| GWorld / GNames / GEngine 锚点 | ✅ 能 | Offsets.hpp 的 UEPointers 命名空间 |
| 某类的某字段偏移 | ✅ 能 | AIOHeader.hpp 搜类名，成员带 // 0x偏移 |
| 类继承关系 | ✅ 能 | AIOHeader.hpp 的 struct X : Y |
| 对象/类名单 | ✅ 能 | Objects.txt |
| **追踪桩这类原生虚函数** | ❌ **不能** | 走特征码 + 虚表反查 |
| 非反射的原生函数 | ❌ 不能 | 同上 |

**为什么 SDK 只收 exec 桩**：IDA 的 dump 脚本按 UObject 反射表遍历函数，$$exec 是每个 UFunction 的 ProcessEvent 跳板，天然收录；原生 C++ 虚函数不在反射表里，收不到。

## 四、偏移校准（SDK 最有价值的用法）

把外挂/工程的偏移逐个跟 SDK 对撞，**能抓出语义错位的偏移**。

实例（PUBG 1.38.12 实测）：

| 常量 | 工程值 | SDK 实际字段 | 问题 |
|---|---|---|---|
| kActorHeight | 0x10BC | DefaultSpeedValue（默认移速） | 注释写「身高」，实际是移速 |
| kActorFeature | 0x3B9C | HighWalkSpeed（高速移速） | 注释写「特征值」，实际是移速 |
| kActorAimVector | 0x1164 | VelocitySafety | 不是朝向向量 |

SDK 给出的正确替代：

    kActorHeight    0x10BC → 0x3E70  StandHalfHeight       [ASTExtraBaseCharacter]
    kActorFeature   0x3B9C → 0x1D78  InheritFeatureComs    [ASTExtraCharacter]
    kActorKillCount 0x002C → 0x0844  Kills                 [AUAEPlayerState]
    kBoneArray      0x0848 → 0x0838  ComponentSpaceBoneExtraTransform
    kControllerFov  0x0688 → 0x05E8  DefaultFOV            [APlayerCameraManager]
    kCameraWorldPos 0x0650 → 0x0640  CameraCache           [APlayerCameraManager]

**判定规则**：
- 偏移精确命中 + 字段名语义吻合 → **OK，直接用**
- 偏移命中但字段名不吻合 → **?? 存疑，查正确字段**
- 偏移在 SDK 里对应的是派生类字段 → **正常**（工程直接跨类访问）

## 五、一键流水线

    cd /sdcard/pte_work
    sh build_gateway.sh              # 全流程：拉so → 抓偏移 → 回填 → 编译
    sh build_gateway.sh --skip-pull  # 跳过拉 so
    sh build_gateway.sh --skip-build # 只抓偏移不编译

四步：
1. 从设备拉当前 libUE4.so
2. 特征码扫追踪偏移 + 虚表反查 + SDK 交叉校验
3. 自动回填 Offsets.h 的 kTrackShootFn
4. NDK 全量编译 + 链接

## 六、常见坑

> ⚠️ **完整坑集见 [`references/rt_pte_pitfalls_full.md`](references/rt_pte_pitfalls_full.md)**（15 个坑，按危害排序）
> 下一节「六点五」是最要命的 5 个，先看这个。

### 六点五、RT 驱动实战 · 最要命的 5 个坑（必读）

**坑 A（最坑）：编译没加 `-O2`**
```
症状：转视角时绘制抖动、人物脱框、UI 卡顿（跟任何开关都无关）
根因：手写 clang 命令忘了 -O → 默认 -O0 → 性能差 3~5 倍 → 帧率低
修法：编译和链接都加 -O2
验证：-O2 编出来体积会明显更小（本例小 590KB）
```
**教训**：症状与任何开关无关 → 先查全局因素（编译优化），别往功能上猜。

**坑 B：命令用 608（硬件断点）而不是 615（PTE 幽灵页）**
```
608 = 硬件断点 → per-thread → 射击线程对不上就永远 0 命中
615 = HOOK_ATTACH → 进程级全线程 → 正确
```

**坑 C：617 必须调，不调驱动不工作**
```
615 只是「挂断点」，驱动默认不做任何事。
必须用 617 设模式：rot[2]=2 捕获 / rot[2]=4 写回（改 V3/V4/V5）
```

**坑 D：结构体多一个字段就全错**
```c
// 正确：无 is_write_regs，reg_count @16，总 352 字节
// 用 static_assert 在编译期卡住 ABI
static_assert(sizeof(HOOK_STATUS) == 72, "HookStatus ABI");
```

**坑 E：坐标必须用骨骼世界坐标**
```cpp
// ❌ z = 坐标.Z + (205.0f - 部位高度*2.0f);   // 像素值，子弹固定偏一边
// ✅ 部位坐标 = 对象信息.敌人信息.骨骼坐标[部位索引];  // [0]头 [1]胸 [2]臀
```

### 其他坑（简表）

1. **容器 PID 命名空间隔离**：容器里看不到手机进程（/proc/<pid> 不存在），拉 so 要走 adb-shell cp。
2. **静态链接被 zstd 卡**：NDK 的 libc.a 用了 ELFCOMPRESS_ZSTD，lld 不支持 → 改**动态链接**（不加 -static）。
3. **虚表起点判定**：PIE 文件里重定位项本身是 0，必须**排除重定位表里的位置**再找「真零」。
4. **特征码失效**：大版本更新后桩可能被内联/改写 → 用虚表反查兜底（找第 843 槽指向该桩的虚表）。
5. **别把 SDK 当万能**：SDK 查不到原生虚函数，别反复搜。
6. **通道必须是 socket**：`/dev/null` 全部 ENOTTY；RT 只 hook socket 的 ioctl。
7. **PTE 是页级断点**：1 页 21 个函数全拦；用「静置 vs 开枪」判定地址对不对。
8. **static 变量跨对象共用**：分帧轮转优化会让「敌人A只更新[0][1]、敌人B只更新[2][3]」→ 骨骼红绿参半 + 追踪失效。
9. **选靶必须在骨骼更新之后**：否则读到上一个敌人的旧骨骼 → 胸/臀错位。
10. **概率要按「发」算**：按帧掷骰会让「50% 打 30 发只中 5 发」。
11. **健康检查用 armed 要加冷却**：写回模式下驱动本来就报 armed=0，不加冷却会每帧重装。
12. **修好功能可能变慢**：PhysX 偏移修好后射线真开始算，帧率暴跌 → 射线要按需计算。
13. **PhysX 绘制「画什么」**：准心命中哪个物体就画它的【全部三角形】，不是画附近所有。
14. **别把原版能用的改坏**：改前 diff 原版，确认只改必要的地方；改前先备份。
15. **UI 挪位置别动逻辑**：原样摘出 → 新位置粘贴 → 只调索引/缩进。

### 快速排查表

| 症状 | 优先排查 |
|---|---|
| 抖动/脱框/卡顿 | **编译有没有 -O2** |
| 断点装了不命中 | 命令是不是 615；617 有没有调 |
| ioctl 全 ENOTTY | 通道是不是 socket |
| 参数被读成垃圾 | 结构体字段有没有多/少 |
| 命中数暴涨 | 地址是不是每帧函数（静置法验证） |
| 子弹固定偏一边 | 坐标是不是骨骼世界坐标 |
| 骨骼红绿参半 | 有没有 static 跨对象共用 |
| 概率不准 | 是不是按帧掷骰 |
| 断点疯狂重装 | armed 判据 + 冷却 |
| 修好功能后变卡 | 射线/扫描是不是按需计算 |

**排查顺序：编译优化 → 驱动命令表 → 结构体对齐 → 数据新鲜度 → 共享状态 → 最后才是功能逻辑。**
**用户的观察永远优先于你的推断。**

## 七、交付与验证

交付目录：/sdcard/Download/pte_toolkit/

    build_gateway.sh        一键流水线
    ue4_track_tool.py       追踪偏移抓取（特征码+虚表+SDK校验+回填）
    sdk_offset_align.py     偏移 <-> SDK 语义 全量对照
    offset_fix_table.py     错误偏移修正建议
    sdk_verify2.py          指针链/世界链深度验证
    fanpian_1.38.12         已编译产物（3.3MB aarch64 PIE）

验证标准：

    1) 特征码命中数应为 1~2（多于 3 说明特征码太宽）
    2) 虚表槽 index 在多个虚表间应一致（同一基类多子类）
    3) 直接调用数应为 0（不是 0 说明命中的不是纯虚表派发的桩）
    4) SDK 锚点一致数 >= 3（5/5 最佳）
    5) 编译 ok=51 bad=0
    6) 产物 file 输出 aarch64 PIE executable

## 八、跨游戏适配

换游戏时改这几个：
- **特征码**：先反汇编已知桩确认形状（不同编译器/优化等级可能不同）
- **SDK 路径**：换成该游戏的 dump
- **锚点期望值**：REF 字典换成该游戏的已知锚点
- **包名/模块名**：com.tencent.tmgp.pubgmhd / libUE4.so → 目标游戏

方法不变：**特征码扫 → 虚表反查 → SDK 校验 → 导出基线 → 对撞 → 回填 → 编译**。

## 九、机器可读基线 + 跨版本对撞（1.1.0 引入，1.2.0 起随完整插件常驻可用）

v1.0.0 的缺口是「抓完就算完了」——新赛季来了只能重抓再拿眼睛比。
v1.1.0 把结果落成 JSON，对撞交给脚本。

### 已验证基线（PUBGM 1.38.12）

    kTrackShootFn   = 0xA0FB548
    特征码          = a240201e8140201e6040201ec0035fd6   .text 命中 2 处
    虚表槽          = 0x140F1938 / 0x1422E460 / 0x14436A20
    虚表基址        = 0x140EFEE0 / 0x1422CA08 / 0x14434FC8
    槽 index        = 843 / 843 / 843      （三表一致 = 基类虚函数）
    直接调用数      = 0                    （纯虚表间接派发）
    备选桩          = 0xBE33F44（index 191，1 表）
    SDK 锚点        = 5/5 一致
    so 指纹         = 381,387,456 字节 / md5 e33beba15fcc01ae0e589ffea2409ee0
    字段校准        = OK 20 / MOVE 6 / 存疑 2 / 丢失 0

### 已验证基线（IGCE PUBG Mobile 4.7.3 · com.tencent.igce）

    kTrackShootFn   = 0x06235980
    特征码          = c8930490082d42f90005402d020940bdc0035fd6（旧 fmov 特征码已失效）
    指令            = adrp x8,#0xf4ad000 / ldr x8,[x8,#0x458] / ldp s0,s1,[x8] / ldr s2,[x8,#8] / ret
    形状            = 读 GOT 全局坐标对象返回 float3（不再读影子寄存器！）
    坐标对象        = GOT 0xf4ad458 → 运行时 bss 0xF849E00（12 字节 float x/y/z）
    虚表槽          = 84 个；index 843 × 7（继承旧版槽位）
    唯一调用点      = 0x07997CF0（blr [x8,#0x1A58]）
    直接调用数      = 0
    SDK             = 百川 4.7.3（@BCHOOK6），锚点语义与 UE4Dump 不同
    so 指纹         = 258,683,048 字节 / md5 0f7dda2d235b98cdd40d1b93c3746602
    驱动适配        = 挂 810 断点照旧；坐标注入改写全局坐标对象（写 0xF849E00 或改 GOT 0xf4ad458），不再改 s3/s4/s5

**IGCE 4.7.3 三条实战教训（2026-10-18）：**
1. **编译器全面 LDR 化** —— 旧 fmov 纯搬移桩在这版 0 命中，`mov v16b` 向量搬移也全无虚表引用。
2. **追踪桩从"搬影子寄存器"变成"读全局坐标对象"** —— 驱动注入方式必须跟着改，否则断点命中但坐标写不进。
3. **index 843 虚表继承仍在** —— 特征码失效时，先扫「adrp 大全局页 + ldr GOT + ldp/ldr s0,s1,s2 + ret」形状，再用 index 843 兜底确认。

### 两条命令适配新赛季

    # 1) 导出新基线（只读）
    python3 scripts/export_baseline.py libUE4_new.so --sdk-dir <新SDK> --offsets <新Offsets.h> --label "PUBGM 1.40" --out baseline_new.json

    # 2) 与基线对撞
    python3 scripts/diff_baseline.py --base data/baseline_1.38.12.json --new baseline_new.json

对撞输出直接给：so 是否变、kTrackShootFn 新值、**虚表 index 是否重排**、
锚点一致数、逐字段偏移差异（带字节增减）、行动清单。

### 判读规则（对撞结果怎么看）

| 对撞结果 | 含义 | 要做的事 |
|---|---|---|
| so md5 相同 | 没更新 | 什么都不用改 |
| kTrackShootFn 变、index 仍 843 | 只挪了地址，虚表结构没动 | 换一行值即可，风险低 |
| index 不再是 843 或多表不一致 | **基类虚表重排** | 选靶/骨骼链全部复核 |
| 命中数 = 0 | 桩被内联/改写 | 走虚表兜底：找第 843 槽指向的 4 指令小函数 |
| 锚点 < 3/5 | build 差异大 | 重新 dump SDK 再做语义校准 |
| 字段偏移大量变化 | 只换桩不够 | 按差异表逐字段替换 |

### 铁律

- 偏移值**绑定 so 指纹**。换了 so 不重抓，就是把上一个版本的值当新的用。
- 对撞器**只读**，不会替你写 Offsets.h。改完自己跑 build_gateway.sh 验证。
- 别把 .bss 里的锚点读出 0 当 bug —— 那些静态槽是运行时才填的。
---

## 4.6 国际服（com.tencent.ig）已实战定版

全文：`pte_track_doc(section="intl46")` 机器基线：`section="intl46_json"`

| 项目 | 值 |
|---|---|
| 追踪断点 | `0x6FF841C`（STEShootWeaponProjectComponent.cpp，虚函数） |
| 体验服 IGCE | **同构**，写回组同样 `s0/s1/s2`；仅坐标来源改全局对象 |
| 写回组 | **`s0/s1/s2`**（写 `s3/s4/s5` 无效） |
| 骨骼 | Mesh 0x510 / Array 0xA30+0x30 / Count 0xA40 / stride 48 |
| 矩阵 | UE4+0xF5F4370 再 +0x20 再 +0x270 |
| UWorld | UE4+0xF621D90 再 +0x810 再 +0x78，列阵 +0x30 |
| 自身 | +0x38 +0x78 +0x30 +0x28D8 |
| 坐标 | +0x208 +0x1C8 |
| 相机 | +0x4B50 +0x548 +0x520 +0x10 |

**四条最容易翻车的：**

1. 写回组选错，子弹打自己脚下。**先切组，再调参数。**
2. 4.6 没有 fmov s2,s5 / s1,s4 / s0,s3 / ret 桩，别扫了。
3. 驱动 fd 保持 -1（模块全局 hook ioctl），别自己开 socket 传 fd。
4. 选靶半径用独立 300px，别借 NumIo[3]（70px），否则「候选 N / 可选 0」。

