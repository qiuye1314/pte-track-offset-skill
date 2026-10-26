# PTE 追踪偏移插件 v1.6.1

把「PUBG Mobile 追踪偏移怎么抓」从玄学变成**一条命令可复现 + 可跨版本对撞**的插件。

- 目标：com.tencent.tmgp.pubgmhd（和平精英 / PUBGM），UE4 + libUE4.so
- 产物：追踪断点偏移 kTrackShootFn + 全量字段偏移基线（机器可读 JSON）
- v1.1.0 关键增量：**机器可读基线 + 新赛季自动对撞器**
- v1.2.0 关键增量：**完整插件形态 + 常驻极小（当时 1499 字节，v1.6.1 已增至 2684 字节）+ 全文按需展开，零重启**

---

## 给接手的人 / AI 的指引

**这是一份可直接读的插件包。** 不需要安装、不需要照抄路径，
直接按下面的顺序读就能接手：

| 顺序 | 文件 | 读它解决什么 |
|---|---|---|
| 1 | `SKILL.md` | 方法论主线（第 0 步判定归属 → 抓偏移 → 落地） |
| 2 | `references/source_attribution.md` | **先判这份源码属于哪个游戏/版本**（别跳） |
| 3 | `references/driver_swap_guide.md` | 驱动怎么对接（RT / Paradise / 用户态） |
| 4 | `references/pubg46_intl_port_lessons.md` | 4.6 国际服具体怎么改（含写回组坑） |
| 5 | `references/session_retro_2026_10_26.md` | 上一轮踩过的坑，别重走 |
| 6 | `data/*.json` | 三条已验证基线，直接对撞 |
| 7 | `scripts/` | 判定 / 抓偏移 / 导基线 / 改版本，都能直接跑 |

**最省时间的一句：动手前先跑 `scripts/detect_source_target.py`。**

---

## 零、先记住的结论

**0. 任何源码到手，先判定它属于哪个游戏/版本。**
   `python3 scripts/detect_source_target.py <工程目录>`
   输出包名 / UWorld 指纹 / 追踪偏移 / 形态 → 直接给出该写哪一组寄存器。
   判错版本 = 几小时乱试，判对 = 5 分钟。



**UE4Dump SDK 里找不到追踪偏移。**
SDK 收录的 60020 个函数 100% 是 "exec" 反射桩（UFunction 的 ProcessEvent 跳板），
而追踪桩是**原生 C++ 虚函数**，不进反射表。

| 谁负责什么 | 内容 |
|---|---|
| SDK 负责 | 引擎锚点（GWorld/GNames/Engine）+ 13000+ 类字段偏移 → 直接抄 |
| 二进制负责 | 追踪桩这类原生虚函数 → 特征码扫 + 虚表反查 |
| SDK 的间接价值 | 校验 build 一致性（5 个锚点），决定字段偏移能不能直接用 |

---

## 〇·五、注入形态与开关（v1.2.0 核心设计）

**装得完整，但默认只占一根细线。**

| 注入段 | order | 默认 | 字节 |
|---|---|---|---|
| `pte-track-offset-skill:trigger` | 152 | 永远注入 | **2684** |
| `pte-track-offset-skill:full-index` | 153 | 关（`config.detail=false`） | 12307（开启才计） |

两个工具始终注册，不占提示词：

- **`pte_track_doc`** —— 29 个 section 按需取全文。需要方法论/坑表/基线时调它，**不用重启**。
  首选 `section="index"`（266 行完整作业索引）。
- **`pte_track_status`** —— 回报版本、注入槽位、常驻字节数、基线摘要。
  「装了像没装」时先调它核对第一现场。

开关三档：

```text
① 默认（推荐）  : 常驻 2684B，全文按需     —— 现在就是这个状态
② 全文常驻      : config.detail=true，重启生效，多占 12307B
③ 彻底关掉      : node_modules/pte-track-offset-skill.disabled 放一个空文件
                 （与 ue4-esp-porting-skill / laoda-hermes-dsha 同一禁用机制）
                 或从 profiles/web/package.json 的 bundles 里移除该条目
```

注册方式见下文「装到别人的机器」。本包不包含任何本机路径。

## 一、当前基线（已实测验证）

    版本      PUBGM 1.38.12  (versionCode 15910)
    模块      libUE4.so  381,387,456 字节
    MD5       e33beba15fcc01ae0e589ffea2409ee0
    .text     0x8FDC960 .. 0x13F128B8

    kTrackShootFn = 0xA0FB548
      机器码      a240201e 8140201e 6040201e c0035fd6
                  fmov s2,s5 / fmov s1,s4 / fmov s0,s3 / ret
      虚表槽      0x140F1938 / 0x1422E460 / 0x14436A20
      虚表基址    0x140EFEE0 / 0x1422CA08 / 0x14434FC8
      槽 index    843 / 843 / 843   （跨 3 个虚表一致 = 基类虚函数）
      直接调用数  0                 （纯虚表间接派发 = 可下断点）
    备选桩      0xBE33F44（index=191，1 处引用）
    SDK 锚点    5/5 一致

### 另两条已定版基线

    【PUBG 4.6 国际服】 com.tencent.ig
      模块   libUE4.so  252,290,584 字节
      MD5    f12aadc1c2132677a3932a27e4736d2f
      kTrackShootFn = 0x6FF841C   （STEShootWeaponProjectComponent.cpp，虚函数）
      写回组         = s0/s1/s2   ← 写 s3/s4/s5 无效，症状是打自己脚下/乱飞
      形态           = 双 float3 参数函数（无 fmov 返回值桩）

    【体验服 IGCE 4.7.3】 com.tencent.igce   —— 与国际服同构
      kTrackShootFn = 0x06235980
      写回组         = s0/s1/s2   （同国际服）
      差异           = 坐标来源改成全局对象（GOT 0xf4ad458 → bss 0xF849E00）

---

## 二、目录

> **改版本号只准用脚本**：`python3 scripts/bump_version.py 1.6.0`
> 它同步 package.json（含 dsh.version）/ plugin.json / skill.json / index.js /
> SKILL.md frontmatter，并插 CHANGELOG。`--check` 只检查不改。
> 手工改必漏——本插件已经漏过 3 次（dsh.version、SKILL.md metadata.version）。


> **第一步永远是判定源码归属**：`python3 scripts/detect_source_target.py <工程目录>`
> 输出包名 / UWorld 指纹 / 追踪偏移 / 形态 → 直接给出**该写哪一组寄存器**。
> 详见 `references/source_attribution.md`。判错版本 = 几小时乱试，判对 = 5 分钟。


| 路径 | 用途 |
|---|---|
| SKILL.md | 方法论全文（四步法 + 15 个坑 + 排查表） |
| plugin.json | 插件清单（版本 / 文件 / 入口） |
| CHANGELOG.md | 1.0.0 → 1.6.1 变更 |
| scripts/export_baseline.py | ★新增：导出机器可读基线 JSON |
| scripts/diff_baseline.py | ★新增：新赛季 vs 基线 → 差异表 + 行动清单 |
| scripts/ue4_track_tool.py | 追踪偏移抓取（特征码+虚表+SDK校验+可选回填） |
| scripts/pte_track_find.py | 同上，独立版 |
| scripts/sdk_offset_align.py | 工程偏移 ↔ SDK 语义全量对照 |
| scripts/offset_fix_table.py | 错误偏移修正建议 |
| scripts/sdk_verify2.py | 指针链 / 世界链深度验证 |
| scripts/build_gateway.sh | 一键流水线：拉so → 抓偏移 → 回填 → NDK 编译 |
| scripts/scripts-install.sh | 装到 /sdcard/pte_work |
| data/baseline_1.38.12.json | 1.38.12 基线（77 项常量 + 桩指纹 + 锚点） |
| data/PTE_BASELINE_1.38.12.md | 人读版基线报告（和平精英） |
| data/baseline_igce_4.7.3.json | ★体验服 IGCE 4.7.3 基线（已标记 family=intl，写回组 s0/s1/s2） |
| data/PTE_BASELINE_IGCE_4.7.3.md | 体验服人读版基线（顶部标明与国际服同构） |
| data/baseline_pubg46_intl.json | ★新增：PUBG 4.6 国际服基线（偏移全表 + 4 条省时结论） |
| scripts/bump_version.py | ★必用：改版本只准用它，一条命令同步 7 处 + 插 CHANGELOG |
| references/driver_swap_guide.md | ★新增：**驱动对接指南**（RT/Paradise ABI 对照 / 7 步对接流程 / fd 坑 / 验证清单） |
| references/session_retro_2026_10_26.md | ★新增：**完整复盘**（14 轮尝试时间线 / 症状映射表 / 别重走清单） |
| references/source_attribution.md | ★新增：**源码归属判定**（包名表 / 偏移指纹 / 追踪形态） |
| references/pubg46_intl_port_lessons.md | ★新增：4.6 国际服从绘制到追踪的移植实战（11 节，零~十） |
| references/offset_grab_procedure.md | 抓取流程 |
| references/pitfalls.md | 基础坑集 |
| references/rt_pte_pitfalls_full.md | RT 驱动 15 坑全表 |
| references/rt_pte_615_success.md | 615 成功定版记录 |
| references/sdk_usage.md | SDK 用法 |
| scripts/detect_source_target.py | ★新增：一条命令判定源码属于哪个游戏（包名+指纹+形态→写回组） |
| prompts/trigger.md | ★常驻细线（唯一每轮开销，2684 字节） |
| prompts/pte-track-offset-skill.md | 266 行完整作业索引（按需，不常驻） |
| skill.json | 技能清单（触发词 / badge），DSH 发现用 |

---

## 三、用法

### 0. 在对话里（最常用）

说「抓 PTE 追踪偏移」/「新赛季怎么适配」即可 —— 常驻细线已让任何对话一开口就知道有这能力，
需要细节时我会自己调 `pte_track_doc(section="index")` 取全文，你不用做任何开关操作。

### A. 只抓偏移（纯读，不动任何工程文件）

    cd /sdcard/pte_work
    python3 scripts/ue4_track_tool.py libUE4.so --sdk /sdcard

### B. 出基线 JSON

    python3 scripts/export_baseline.py libUE4.so --sdk-dir /sdcard/pte_work/sdk138 --offsets <工程>/jni/include/game/Offsets.h --label "PUBGM 1.38.12" --out baseline_1.38.12.json

### C. 新赛季适配（v1.1.0 的主场景）

    # 1) 更新游戏后拉新 so
    adb-shell "su -c 'cp /data/app/*/com.tencent.tmgp.pubgmhd*/lib/arm64/libUE4.so /sdcard/pte_work/libUE4_new.so'"

    # 2) 导出新基线
    python3 scripts/export_baseline.py libUE4_new.so --sdk-dir <新SDK目录> --offsets <新Offsets.h> --label "PUBGM 1.40" --out baseline_new.json

    # 3) 对撞 → 直接告诉你哪些必改
    python3 scripts/diff_baseline.py --base data/baseline_1.38.12.json --new baseline_new.json

对撞输出包含：so 指纹是否变、kTrackShootFn 新值、虚表 index 是否重排、SDK 锚点一致数、
**逐字段偏移差异（带字节增减）**、以及行动清单。

### D. 全流程含编译

    sh scripts/build_gateway.sh              # 拉so → 抓偏移 → 回填 → NDK 编译
    sh scripts/build_gateway.sh --skip-pull  # 跳过拉 so
    sh scripts/build_gateway.sh --skip-build # 只抓偏移不编译

---

## 四、验证标准（抓完必须过）

    1) 特征码命中数 1~2         （>3 = 特征码太宽）
    2) 虚表槽 index 多虚表一致   （本例 843 × 3）
    3) 直接调用数 = 0           （否则不是虚函数派发）
    4) SDK 锚点一致 >= 3/5      （5/5 最佳）
    5) 编译 ok=51 bad=0
    6) file 输出 aarch64 PIE executable

---

## 五、换游戏要改的**六处**（v1.5.1 扩写）

> 先跑 `python3 scripts/detect_source_target.py <工程目录>` 拿到判定，再按这张表逐项改。
> **不要跳项**——跳一项的典型症状是「绘制正常但追踪不生效」。

| # | 改什么 | 判据 | 漏改的症状 |
|---|---|---|---|
| 1 | **包名** | `grep com\.tencent src/` | 找进程失败 / 启动不起来 |
| 2 | **UWorld 锚点 + 自身链** | 偏移指纹表 | 坐标恒为 0，绘制空 |
| 3 | **矩阵锚点** | 矩阵指纹表 | 框错位 / 投影全偏 |
| 4 | **坐标链**（`+A +B`） | 数据表 | 坐标跳动或落到地图原点 |
| 5 | **骨骼链**（Mesh / Array / Count / stride） | 数据表 | 骨骼红绿参半或不画 |
| 6 | **写回寄存器组** | 追踪形态表 | **子弹打自己脚下 / 乱飞 / 时中时不中** |

**第 6 项最容易漏，也最难从症状反推。** 4.6 国际服 = `s0/s1/s2`，和平精英 = `s3/s4/s5`。

## 六、已知语义错位（1.38.12 工程历史遗留）

基线如实记录 8 项，**本插件不自动修改**——改了可能把本来能用的版本弄坏：

| 常量 | 工程值 | SDK 实际 | 建议 |
|---|---|---|---|
| kActorHeight | 0x10BC | DefaultSpeedValue（移速） | 0x3E70 StandHalfHeight |
| kActorFeature | 0x3B9C | 本类无此字段 | 0x1D78 InheritFeatureComs |
| kActorAimVector | 0x1164 | VelocitySafety | 需人工确认 |
| kActorThrowableId | 0x0794 | 本类无此字段 | 0x3A90 ThrowGrenadeMode |
| kBoneArray | 0x0848 | 本类无此字段 | 0x838 ComponentSpaceBoneExtraTransform |
| kControllerFov | 0x0688 | 本类无此字段 | 0x5E8 DefaultFOV |
| kCameraWorldPos | 0x0650 | 本类无此字段 | 0x640 CameraCache |
| kActorKillCount | 0x002C | — | 0x844 Kills [AUAEPlayerState] |

另注：kMatchRealPlayerCount 判 OK，但相邻 4 字节处有 TotalPlayerNum，
按「真人玩家数」语义建议手工再确认一次。

---

---

## 七、边界（说清楚不做什么）

- **不含驱动本体与内核模块**（.ko / 驱动二进制不在本仓库，需自行准备）。
  但**驱动怎么接进来有完整指南**：615/617 断点命令、HOOK_STATUS ABI、RT / Paradise 两种 ABI 对照、
  7 步对接流程、ioctl 示例、双后端切换骨架 → `references/driver_swap_guide.md`；
  615/617 成功定版参数约定 → `references/rt_pte_615_success.md`。
- export_baseline.py / diff_baseline.py / 不带 --patch 的 ue4_track_tool.py **全部只读**；只有显式 --patch 才回填 Offsets.h。
- **不含已编译产物** fanpian_1.38.12（3.4MB 二进制，属构建产物，不是偏移资产）。
- 偏移值绑定具体 so 指纹，换了 so 必须重抓 —— 这正是 C 节对撞流程的用途。


---

## 八、作者权衡利弊（Trade-offs & Design Decisions）

这一节把每个「为什么这么选」摊开说，连代价一起列。README 不当宣传页，当决策账本。

| 决定 | 为什么这么选 | 付出的代价 |
|---|---|---|
| 抓偏移走「特征码 + 虚表反查」，不遍历 SDK 反射表 | SDK 的 60020 个函数 100% 是 exec 反射桩；追踪桩是原生 C++ 虚函数，反射表里根本不存在 | 每次大版本更新都要重扫重验，不能靠 dump 一劳永逸 |
| 特征码选「只命中 1~2 次」的稀有形状 | 3.3 亿字节 .text 里命中多 = 特征码太宽会误伤 | 版本一改桩被内联/改写，特征码可能失效，要回退虚表反查兜底 |
| 用 PTE shadow 断点，不用 inline hook | 函数本来就在，只改影子寄存器，游戏读代码段做 CRC 校验时读到的是原版 | 依赖内核驱动（RT 615/617），部署门槛比 inline hook 高，root 环境才玩得转 |
| 常驻只放 2684B 细线，全文按需展开 | 省 token、零重启，首句触发仍然可靠 | 细节展开要多一次 pte_track_doc 工具调用（换掉的是常驻 12307B） |
| 版本号五处统一、不玩小聪明 | package.json / dsh / plugin.json / skill.json / SKILL frontmatter 不一致会让装的人怀疑自己 | 改一行文档也得同步五处，维护动作多 |
| 8 项语义错位只记录、不自动改 | 自动改可能把本来能用的版本弄坏；错位里有「跨类字段」这种假阳性 | 历史错位要人工消化，不能一条命令清零 |
| 不含驱动本体（.ko/驱动二进制）与编译产物，但**给完整驱动对接指南**（ABI 对照 / 7 步流程 / ioctl 示例 / 双后端骨架） | 仓库干净可审计，边界切在「偏移资产 + 对接方法」与「驱动本体」之间 | 仍不能开箱即用，驱动本体需自行准备 |
| 拆 10 个脚本而不是一个大黑盒 | 每步可单独跑、单独验（抓 → 导出 → 对撞 → 回填 → 编译） | 命令数量多，初次上手要读用法 |

### Trade-offs (English)

Every choice below lists what was picked, why, and what it costs — this README is a decision ledger, not a marketing page.

| Decision | Why | What it costs |
|---|---|---|
| Locate offsets by byte-signature + vtable back-trace, not SDK reflection scan | All 60,020 dumped functions are exec reflection stubs; the track stub is a native C++ virtual function that never enters the reflection table | Every major update requires re-scanning; a dump alone is never sufficient |
| Signature tuned to match only 1–2 hits | In a 330 MB .text, more hits means the signature is too loose and misfires | If a patch inlines/rewrites the stub, the signature dies; fall back to vtable back-trace |
| PTE shadow breakpoints instead of inline hooks | The function stays intact; only shadow registers are rewritten, so CRC checks of code pages read original bytes | Requires a kernel driver (RT 615/617); higher deployment bar than inline hooks, root needed |
| Only a 2684-byte resident line; full docs on demand | Saves tokens, zero restart, first-line trigger stays reliable | Detail expansion costs one extra pte_track_doc call (instead of 12307 B always resident) |
| Version pinned identically in five places | Inconsistent versions make users doubt the install | A one-line doc edit means syncing five files |
| 8 semantic mismatches recorded, never auto-patched | Auto-patching may break builds that currently work; some "mismatches" are legit cross-class fields | Legacy mismatches need human triage, not one-command cleanup |
| No driver binary (.ko) and no build artifacts — but ships a full driver-integration guide (ABI comparison / 7-step flow / ioctl samples / dual-backend skeleton) | Keeps the repo clean and auditable; boundary sits between offset assets plus integration know-how and the driver itself | Still not plug-and-play; you supply the driver binary |
| Ten focused scripts instead of one black box | Each step runs and verifies independently (grab → export → diff → patch → build) | More commands to learn on first setup |
