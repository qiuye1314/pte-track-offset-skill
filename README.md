# PTE 追踪偏移插件 v1.2.0

把「PUBG Mobile 追踪偏移怎么抓」从玄学变成**一条命令可复现 + 可跨版本对撞**的插件。

- 目标：com.tencent.tmgp.pubgmhd（和平精英 / PUBGM），UE4 + libUE4.so
- 产物：追踪断点偏移 kTrackShootFn + 全量字段偏移基线（机器可读 JSON）
- v1.1.0 关键增量：**机器可读基线 + 新赛季自动对撞器**
- v1.2.0 关键增量：**完整插件形态 + 常驻极小（1499 字节）+ 全文按需展开，零重启**

---

## 零、先记住的结论

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
| `pte-track-offset-skill:trigger` | 152 | 永远注入 | **1499** |
| `pte-track-offset-skill:full-index` | 153 | 关（`config.detail=false`） | 7778（开启才计） |

两个工具始终注册，不占提示词：

- **`pte_track_doc`** —— 20 个 section 按需取全文。需要方法论/坑表/基线时调它，**不用重启**。
  首选 `section="index"`（158 行完整作业索引）。
- **`pte_track_status`** —— 回报版本、注入槽位、常驻字节数、基线摘要。
  「装了像没装」时先调它核对第一现场。

开关三档：

```text
① 默认（推荐）  : 常驻 1499B，全文按需     —— 现在就是这个状态
② 全文常驻      : config.detail=true，重启生效，多占 7778B
③ 彻底关掉      : node_modules/pte-track-offset-skill.disabled 放一个空文件
                 （与 ue4-esp-porting-skill / laoda-hermes-dsha 同一禁用机制）
                 或从 profiles/web/package.json 的 bundles 里移除该条目
```

注册现状：已在 `/root/.dsh/profiles/web/package.json` 的 dependencies + bundles（第 15 个），
`node_modules` 软链已建，`skill.json` 已提供（badge: PTE追踪偏移 v1.2.0）。

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

---

## 二、目录

| 路径 | 用途 |
|---|---|
| SKILL.md | 方法论全文（四步法 + 15 个坑 + 排查表） |
| plugin.json | 插件清单（版本 / 文件 / 入口） |
| CHANGELOG.md | 1.0.0 → 1.1.0 变更 |
| scripts/export_baseline.py | ★新增：导出机器可读基线 JSON |
| scripts/diff_baseline.py | ★新增：新赛季 vs 基线 → 差异表 + 行动清单 |
| scripts/ue4_track_tool.py | 追踪偏移抓取（特征码+虚表+SDK校验+可选回填） |
| scripts/pte_track_find.py | 同上，独立版 |
| scripts/sdk_offset_align.py | 工程偏移 ↔ SDK 语义全量对照 |
| scripts/offset_fix_table.py | 错误偏移修正建议 |
| scripts/sdk_verify2.py | 指针链 / 世界链深度验证 |
| scripts/build_gateway.sh | 一键流水线：拉so → 抓偏移 → 回填 → NDK 编译 |
| scripts/scripts-install.sh | 装到 /sdcard/pte_work |
| data/baseline_1.38.12.json | ★新增：1.38.12 基线（77 项常量 + 桩指纹 + 锚点） |
| data/PTE_BASELINE_1.38.12.md | 人读版基线报告 |
| references/ | 5 份拆解文档（抓取流程 / 坑集 / 615 成功记录 / SDK 用法 / 坑全表） |
| prompts/trigger.md | ★v1.2.0 常驻细线（唯一每轮开销，1499 字节） |
| prompts/pte-track-offset-skill.md | 158 行完整作业索引（按需，不常驻） |
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

## 五、换游戏要改的四处

    - 特征码      先反汇编已知桩确认形状（编译器 / 优化等级不同会变）
    - SDK 路径    换成该游戏的 dump
    - 锚点期望值  export_baseline.py 的 EXPECT_KEY + sdk_offset_align.py 的 REF 字典
    - 包名模块名  com.tencent.tmgp.pubgmhd / libUE4.so → 目标游戏

方法不变：**特征码扫 → 虚表反查 → SDK 校验 → 导出基线 → 对撞**。

---

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

## 七、边界（说清楚不做什么）

- **不内置任何驱动交互代码**：断点命令（615/617）、HOOK_STATUS ABI 由使用者的 RT 驱动侧负责，参数约定见 references/rt_pte_615_success.md。
- export_baseline.py / diff_baseline.py / 不带 --patch 的 ue4_track_tool.py **全部只读**；只有显式 --patch 才回填 Offsets.h。
- **不含已编译产物** fanpian_1.38.12（3.4MB 二进制，属构建产物，不是偏移资产）。
- 偏移值绑定具体 so 指纹，换了 so 必须重抓 —— 这正是 C 节对撞流程的用途。
