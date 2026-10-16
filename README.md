# PTE 追踪偏移抓取技能（PUBG Mobile · 和平精英 子弹追踪断点）

> **如何让 AI 给你抓追踪偏移？** 一份丢进 DSH 就能用的技能插件：从 `libUE4.so` 里用**特征码 + 虚表反查**定位 PTE shadow 追踪断点，用 dump 出的 SDK 交叉校验 build 一致性并校准全量字段偏移，把「追踪偏移怎么抓」从玄学变成 **10 秒可复现的流程**。
>
> 适用：UE4 手游（`com.tencent.tmgp.pubgmhd` / PUBG Mobile 1.38.12 实测）· root 安卓 · RT 内核驱动（615/617 PTE 幽灵页）

---

## 一、解决什么问题

拿到一份 UE4 手游外挂源码、或者游戏一热更偏移全废，最卡人的从来不是绘制，而是**追踪断点**——它不在 SDK 反射表里，搜遍 dump 也搜不到。本技能把边界画清楚：

| 要查什么 | SDK 能不能查 | 走哪条路 |
|---|---|---|
| GWorld / GNames / GEngine 锚点 | ✅ 能 | `Offsets.hpp` 的 UEPointers |
| 某类某字段偏移（身高/骨骼/FOV…） | ✅ 能 | `AIOHeader.hpp` 搜类名 |
| 类继承关系 / 对象名单 | ✅ 能 | `AIOHeader.hpp` / `Objects.txt` |
| **追踪桩这类原生 C++ 虚函数** | ❌ **不能** | **特征码扫 + 虚表反查** |

**核心口诀：SDK 里找不到追踪偏移。** dump 的 script.json 收录 60020 个函数，100% 是 $$exec 反射桩（UFunction 的 ProcessEvent 跳板）；追踪桩是原生虚函数，不进反射表。SDK 的间接价值是**验证 build 一致性**——锚点 5/5 对上，其余字段偏移才敢直接抄。

## 二、你需要准备什么（唯一前置）

| # | 输入 | 用途 |
|---|---|---|
| 1 | GNames 偏移 | 解类名 |
| 2 | GWorld 偏移 | 取世界指针 |
| 3 | GEngine 偏移 | 引擎锚点 |
| 4 | UObjectArray / ObjObjects 偏移 | 对象遍历 |
| 5 | 任一已知函数/字段偏移 | 参与锚点一致性对撞 |
| 6 | 当前版本 `libUE4.so` | 特征码扫描对象 |
| 7 | 该版本 UE4Dump 出的 SDK（Offsets.hpp / AIOHeader.hpp / Objects.txt） | build 校验 + 字段偏移直抄 |
| 8 | RT 驱动命令表（615/616/617/618/619） | PTE 幽灵页挂断点 |

> 只给 dump 出的 SDK 也能跑：**方法通用，数值零通用**——换游戏只换特征码、SDK 路径、锚点期望值、包名。

## 三、追踪断点的本质（理解了才会抓）

追踪桩是一个 **4 指令 float3 getter**：

```
fmov s2, s5   ; 0x1E2040A2
fmov s1, s4   ; 0x1E204081
fmov s0, s3   ; 0x1E204060
ret           ; 0xD65F03C0
```

机关链条：

```
驱动在函数入口下 PTE 影子断点
      ↓
游戏调用它 → 断点触发
      ↓
驱动把目标坐标写进 v3/v4/v5（只改影子寄存器，物理内存不动）
      ↓
桩函数执行 → 把 v3/v4/v5 当返回值吐回 v0/v1/v2
      ↓
调用者拿去做弹道计算 → 子弹飞向目标
```

**为什么用 PTE shadow 而不是 inline hook**：函数本来就在，只篡改返回寄存器 → 游戏读自己代码段做 CRC 校验时**读到的还是原版**。

## 四、抓取四步法

1. **特征码扫** — `a240201e 8140201e 6040201e c0035fd6`，3.3 亿字节 .text 里只命中 1~2 次，稀有度极高。
2. **虚表反查** — 命中地址没有任何 BL 直接调用 → 扫 `R_AARCH64_RELATIVE` 重定位项，找 `addend == 桩地址`，得到函数指针存放位置（`.data.rel.ro` = 虚表区）。
3. **重建虚表边界** — Itanium ABI 头布局 `[-16] offset_to_top / [-8] typeinfo / [0] 首虚函数`；从槽位往前找**不在重定位表里的连续真零** → 虚表起点，`(槽位-起点)/8` 就是槽 index。
4. **SDK 交叉校验** — Names / World / Engine / UObjectArray / ObjObjects 五个锚点对照，5/5 一致即同一 build。

## 五、偏移校准：SDK 最值钱的用法

把工程里的偏移逐个跟 SDK 对撞，能抓出**语义错位**的偏移（PUBG 1.38.12 实测样本）：

| 常量 | 工程值 | SDK 里实际是什么 | 结论 |
|---|---|---|---|
| kActorHeight | 0x10BC | DefaultSpeedValue（默认移速） | 注释写「身高」，其实是移速 → 改 0x3E70 StandHalfHeight |
| kActorFeature | 0x3B9C | HighWalkSpeed | 注释写「特征值」，其实是移速 → 改 0x1D78 InheritFeatureComs |
| kActorAimVector | 0x1164 | VelocitySafety | 不是朝向向量 |

判定规则：偏移精确命中 + 字段名语义吻合 → 直接用；命中但名不吻合 → 存疑，查正确字段；命中的是派生类字段 → 正常。

## 六、RT 驱动实战 · 最要命的 5 个坑（v1.1.0 新增，必读）

- **坑 A（最坑）**：编译忘加 `-O2` → 默认 -O0，性能差 3~5 倍，症状是「转视角抖动 / 人物脱框 / UI 卡顿」，跟任何功能开关都无关。**症状与开关无关时先查全局因素。**
- **坑 B**：命令用 608（硬件断点，per-thread，CPU 只有 4-8 个槽）而不是 **615（PTE 幽灵页，进程级全线程）** → 射击线程对不上就永远 0 命中。
- **坑 C**：615 只负责挂断点，**必须再调 617 设模式**（`rot[2]=2` 捕获 / `rot[2]=4` 写回 V3/V4/V5），不调驱动啥都不干。
- **坑 D**：`HOOK_STATUS` 结构体多一个字段就全错 → 用 `static_assert(sizeof(HOOK_STATUS)==72)` 在编译期卡住 ABI。
- **坑 E**：坐标必须用**骨骼世界坐标**（`骨骼坐标[0]头 [1]胸 [2]臀`），拿像素值当高度偏移会让子弹固定偏一边。

外加 10 个次要坑（容器 PID 命名空间、zstd 静态链接、虚表「真零」判定、socket 通道、PTE 页级断点、static 跨对象共用、选靶时序、按「发」算概率、armed 冷却、按需算射线）全在 `references/rt_pte_pitfalls_full.md`。

**排查顺序：编译优化 → 驱动命令表 → 结构体对齐 → 数据新鲜度 → 共享状态 → 最后才怀疑功能逻辑。用户的观察永远优先于你的推断。**

## 七、装进 DSH

```bash
# 方式 1：整包丢进技能目录
cp -r pte-track-offset-skill /root/.dsh/skills/pte-track-offset-mobile

# 方式 2：作为插件（systemPrompt 注入 + pte_track_doc 工具）
#   index.js 注册 inject = ["systemPrompt","tools"]
#   只注入索引段，全文按需读取，不整段灌提示词
```

装完直接对 AI 说一句就能触发：

```
帮我抓 pte 追踪偏移
这版和平精英的 kTrackShootFn 在哪
用 SDK 能不能找到追踪断点
```

## 八、手动跑抓取脚本

```bash
python3 scripts/pte_track_find.py /sdcard/pte_work/libUE4.so \\
    [--sdk /sdcard/pte_work/SDKDir] [--patch /path/to/Offsets.h]
```

拉 so（容器里看不到手机进程，必须走设备通道）：

```bash
adb-shell cp /data/app/*/com.tencent.tmgp.pubgmhd-*/lib/arm64/libUE4.so /sdcard/pte_work/libUE4.so
```

## 九、目录结构

```
pte-track-offset-skill/
├── SKILL.md                              主方法论（四步法 / SDK 边界 / 校准 / 15 坑 / 跨游戏适配）
├── references/
│   ├── offset_grab_procedure.md          抓取作业程序（SOP）
│   ├── sdk_usage.md                      SDK 能查什么、不能查什么
│   ├── pitfalls.md                       基础踩坑
│   ├── rt_pte_pitfalls_full.md           【必读】RT 驱动实战 15 坑全量
│   └── rt_pte_615_success.md             RT 615/617 成功定版（命令表 + 写回参数 + ABI）
├── scripts/
│   └── pte_track_find.py                 特征码扫描 + 虚表反查 + SDK 校验 + 偏移回填
├── prompts/pte-track-offset-skill.md     插件注入用索引段
├── index.js                              DSH 插件入口（注入 + pte_track_doc 工具）
├── package.json                          插件元数据
├── cordis.patch.yml                      bundle 注册补丁
├── scripts-install.sh                    工具链落地脚本
├── LICENSE                               GPL-3.0
└── README.md
```

## 十、验证标准

1. 特征码命中数 1~2（>3 说明特征码太宽）
2. 同一基类的多个子类，虚表槽 index 应一致
3. SDK 锚点一致数 >= 3（5/5 最佳）
4. `--patch` 回填后 `kTrackShootFn` 与虚表反查结果一致

## 十一、许可

**GPL-3.0** —— 用了、改了，**二改必须同样开源回馈**。文档与代码同源，全部随本仓库公开。

TG 频道：**@FJNB99**
