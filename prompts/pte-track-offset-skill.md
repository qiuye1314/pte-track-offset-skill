# PTE 追踪偏移 · 完整作业索引

## ★ 第 0 步（每次都先做）：判定源码属于哪个游戏

```bash
python3 scripts/detect_source_target.py <工程目录> [--so libUE4.so]
```

输出：包名候选 / UWorld+矩阵指纹 / 追踪函数归属 / 版本串 / fmov 桩 / 建议写回组。

**判错一次浪费几小时，判对只花 5 分钟。**

| 包名 | 游戏 | UWorld 锚点 | 追踪偏移 | 写回组 |
|---|---|---|---|---|
| com.tencent.tmgp.pubgmhd | 和平精英 | 0x1771CC38 | 0xA0FB548 | s3/s4/s5 |
| com.tencent.ig | PUBG 4.6 国际服 | 0xF621D90 | 0x6FF841C | **s0/s1/s2** |
| com.tencent.igce | 国际服 IGCE 4.7.3 | — | 0x06235980 | 不写寄存器 |

全文：`pte_track_doc(section="attrib")`

**铁律：参数调不通时，先回头确认游戏/版本判对了吗，别继续调参数。**

---

当用户提到「追踪偏移 / PTE追踪 / 漏打追踪 / 追踪断点 / kTrackShootFn / CalShoot / 子弹追踪怎么实现 /
和平精英1.38偏移 / 用SDK找偏移 / 阴影断点 / shadow 810 811 812 / RT驱动 / 615 / 617」，
或游戏包名为 com.tencent.tmgp.pubgmhd 时，**按本索引取全文执行，不要凭简写动手**：

- 主方法论: __PLUGIN_DIR__/SKILL.md
- 抓取SOP: __PLUGIN_DIR__/references/offset_grab_procedure.md
- SDK用法与边界: __PLUGIN_DIR__/references/sdk_usage.md
- 踩坑记录(基础): __PLUGIN_DIR__/references/pitfalls.md
- **RT驱动实战15坑【必读】**: __PLUGIN_DIR__/references/rt_pte_pitfalls_full.md
- **RT 615 成功定版**: __PLUGIN_DIR__/references/rt_pte_615_success.md
- 抓取脚本: __PLUGIN_DIR__/scripts/pte_track_find.py
- 抓取脚本(带回填): __PLUGIN_DIR__/scripts/ue4_track_tool.py
- **基线报告(1.38.12实测)**: __PLUGIN_DIR__/data/PTE_BASELINE_1.38.12.md
- **机器可读基线**: __PLUGIN_DIR__/data/baseline_1.38.12.json
- **基线报告(IGCE 4.7.3实战)**: __PLUGIN_DIR__/data/PTE_BASELINE_IGCE_4.7.3.md
- **机器可读基线(IGCE 4.7.3)**: __PLUGIN_DIR__/data/baseline_igce_4.7.3.json
- **基线导出器**: __PLUGIN_DIR__/scripts/export_baseline.py
- **新赛季对撞器**: __PLUGIN_DIR__/scripts/diff_baseline.py
- 偏移校准: __PLUGIN_DIR__/scripts/sdk_offset_align.py · offset_fix_table.py · sdk_verify2.py
- 插件说明/变更: __PLUGIN_DIR__/README.md · __PLUGIN_DIR__/CHANGELOG.md

## 核心口诀（先记这个，避免走弯路）

**SDK 里找不到追踪偏移**——script.json 收录的 60020 个函数 100% 是反射桩（exec 跳板），
追踪桩是原生 C++ 虚函数，不注册进反射表。所以：

- SDK 管**引擎锚点 + 类字段偏移**（直接抄）
- 二进制管**原生虚函数**（特征码扫 + 虚表反查）
- SDK 的间接价值是**验证 build 一致性**

## 四步流程（模式A：抓偏移）

1. **特征码扫**：a240201e8140201e6040201ec0035fd6（fmov s2,s5|s1,s4|s0,s3|ret）
2. **虚表反查**：扫 R_AARCH64_RELATIVE 找 addend==桩地址 → 虚表槽位
3. **重建虚表**：往前找「真零」（排除重定位项）→ 槽 index
4. **SDK 校验**：锚点对照 5/5 → 同一 build

一键命令：
```bash
sh /sdcard/pte_work/build_gateway.sh              # 全流程
python3 /sdcard/pte_work/pte_track_find.py libUE4.so --sdk <SDK> --patch Offsets.h
```

## 已验证基线（PUBGM 1.38.12 · 别重复扫描）

```
kTrackShootFn = 0xA0FB548
  虚表槽 0x140F1938 / 0x1422E460 / 0x14436A20   槽 index = 843 × 3（一致）
  直接调用数 = 0（纯虚表间接派发）
  机器码 a240201e 8140201e 6040201e c0035fd6
备选桩 = 0xBE33F44（index 191，1 处引用）
so 指纹 = 381,387,456 字节 / md5 e33beba15fcc01ae0e589ffea2409ee0
SDK 锚点 = 5/5 一致（Names 0x16CA0898 / World 0x1771CC38 / Engine 0x17719B78
           / UObjectArray 0x173EE2B8 / ObjObjects 0x173EE2C8）
字段校准 = OK 20 / MOVE 6 / 存疑 2 / 丢失 0
```

**这条值只在上面那个 md5 的 so 上成立。** 游戏一更新就必须重抓——重抓不是失败，是常态。

## 已验证基线（IGCE PUBG Mobile 4.7.3 · com.tencent.igce · 别重复扫描）

```
kTrackShootFn = 0x06235980
  形状 = adrp x8,#0xf4ad000 / ldr x8,[x8,#0x458] / ldp s0,s1,[x8] / ldr s2,[x8,#8] / ret
  语义 = 读 GOT 全局坐标对象返回 float3（不再读影子寄存器！）
  坐标对象 = GOT 0xf4ad458 → 运行时 bss 0xF849E00（12 字节 float x/y/z）
  虚表槽 = 84 个；index 843 × 7（继承旧版槽位）
  唯一调用点 = 0x07997CF0（blr [x8,#0x1A58]）；直接调用数 = 0
  机器码 c8930490 082d42f9 0005402d 020940bd c0035fd6
  SDK = 百川 4.7.3（@BCHOOK6）
  so 指纹 = 258,683,048 字节 / md5 0f7dda2d235b98cdd40d1b93c3746602
  驱动适配 = 挂 810 断点照旧；坐标注入改写全局坐标对象（写 0xF849E00 或改 GOT 0xf4ad458），不再改 s3/s4/s5
```

**IGCE 4.7.3 教训**：编译器全面 LDR 化，旧 fmov 特征码 0 命中、纯搬移桩不存在；
追踪桩变成「读全局坐标对象」，驱动注入必须同步改；index 843 虚表继承仍在。

## 模式C：跨赛季对撞（v1.2.0 · 新赛季适配就走这条）

不要凭眼睛比两个版本的偏移，让脚本比：

```bash
# 1) 更新后拉新 so
adb-shell "su -c 'cp /data/app/*/com.tencent.tmgp.pubgmhd*/lib/arm64/libUE4.so /sdcard/pte_work/libUE4_new.so'"

# 2) 导出新基线（只读）
python3 __PLUGIN_DIR__/scripts/export_baseline.py /sdcard/pte_work/libUE4_new.so \
  --sdk-dir <新SDK目录> --offsets <新Offsets.h> --label "PUBGM 新版" --out /sdcard/pte_work/baseline_new.json

# 3) 与基线对撞 → 直接给「哪些必改」
python3 __PLUGIN_DIR__/scripts/diff_baseline.py \
  --base __PLUGIN_DIR__/data/baseline_1.38.12.json --new /sdcard/pte_work/baseline_new.json
```

对撞结果怎么读：

| 结果 | 含义 | 动作 |
|---|---|---|
| so md5 相同 | 没更新 | 什么都不改 |
| kTrackShootFn 变、index 仍 843 | 只挪地址，虚表没动 | 换一行值，风险低 |
| index 不是 843 或多表不一致 | **基类虚表重排** | 选靶/骨骼链全部复核 |
| 命中数 0 | 桩被内联/改写 | 虚表兜底：找第 843 槽指向的 4 指令小函数 |
| 锚点 < 3/5 | build 差异大 | 重新 dump SDK 再语义校准 |

**export/diff 全程只读，绝不写 Offsets.h；只有 ue4_track_tool.py 显式带 --patch 才回填。**

---

## 模式B：RT 驱动接入（把追踪真正跑起来）—— 这一步最坑

如果目标是把追踪**真正跑起来**（不只是抓偏移），**必须先读**
`__PLUGIN_DIR__/references/rt_pte_pitfalls_full.md`（15 个坑，按危害排序）。

### 最要命的 5 个（不看会浪费大量时间）

**坑 0 · 编译没加 -O2**（症状：抖动/脱框/卡顿，跟任何开关无关）
```
根因：手写 clang 命令忘了 -O → 默认 -O0 → 性能差 3~5 倍 → 帧率低
修法：编译和链接都加 -O2
验证：-O2 编出来体积明显更小（本例小 590KB）
教训：症状与开关无关 → 先查全局因素，别往功能上猜
```

**坑 1 · 命令用 608 而不是 615**
```
608 = 硬件断点 → per-thread → 射击线程对不上就永远 0 命中
615 = HOOK_ATTACH → 进程级全线程 → 正确
```

**坑 2 · 617 必须调，不调驱动不工作**
```
615 只是「挂断点」。必须用 617 设模式：
  rot[2]=2 捕获模式（只记录）
  rot[2]=4 写回模式（改 V3/V4/V5 = float3 坐标）
```

**坑 4 · 结构体多一个字段就全错**
```c
// 正确：无 is_write_regs，reg_count @16，总 352 字节
static_assert(sizeof(HOOK_STATUS) == 72, "HookStatus ABI");  // 用 static_assert 卡住
```

**坑 6 · 坐标必须用骨骼世界坐标**
```cpp
// 错：z = 坐标.Z + (205.0f - 部位高度*2.0f);   // 像素值，子弹固定偏一边
// 对：部位坐标 = 对象信息.敌人信息.骨骼坐标[部位索引];  // [0]头 [1]胸 [2]臀
```

### 快速排查表（照这个顺序查）

| 症状 | 优先排查 |
|---|---|
| 抖动/脱框/卡顿 | **编译有没有 -O2** |
| 断点装了不命中 | 命令是不是 615；617 有没有调 |
| ioctl 全 ENOTTY | 通道是不是 socket（不是 /dev/null） |
| 参数被读成垃圾 | 结构体字段有没有多/少 |
| 命中数暴涨 | 地址是不是每帧函数（静置法验证） |
| 子弹固定偏一边 | 坐标是不是骨骼世界坐标 |
| 骨骼红绿参半 | 有没有 static 跨对象共用 |
| 概率不准 | 是不是按帧掷骰（应该按发） |
| 断点疯狂重装 | armed 判据 + 冷却 |
| 修好功能后变卡 | 射线/扫描是不是按需计算 |

**排查顺序：编译优化 → 驱动命令表 → 结构体对齐 → 数据新鲜度 → 共享状态 → 最后才是功能逻辑。**

**用户的观察永远优先于你的推断。** 他说「没修之前也抖」→ 就别往那个功能上查。

---

## 关键坑（基础版，详见 references/pitfalls.md）

1. 容器 PID namespace 隔离 → 拉 so 走 adb-shell
2. 静态链接被 ELFCOMPRESS_ZSTD 卡 → 改动态链接
3. PIE 里重定位项本身就是 0 → 找虚表起点必须排除重定位表
4. 特征码失效 → 虚表第 843 槽兜底
5. **别盲扫 ioctl 命令** → RT 驱动不校验参数，会让手机内核 oops 重启

---

## ★ 4.6 国际服移植（2026-10-26 实战定版）

**全文：`pte_track_doc(section="intl46")`　机器基线：`section="intl46_json"`**

四条最能省时间的结论：

1. **4.6 国际服写回必须写 `s0/s1/s2`。** 写 `s3/s4/s5` 完全无效。
   写错组的症状：**子弹往自己脚下打 / 乱飞 / "偏一米能中"**。
   排查时先切组，再谈偏移，别一上来调参数。
2. **4.6 没有国服那个 `fmov s2,s5 / s1,s4 / s0,s3 / ret` 桩。**
   精确扫 + 宽松扫（三条 fmov + ret）命中数都是 0。别再扫了，换虚表/字符串反查。
3. **驱动 `fd` 不要自己 socket。** `kernel.h` 原版 `fd` 恒为 `-1`，
   模块全局 hook `ioctl`，不看 fd。自己开 socket 再传 fd 会被拒。
4. **选靶半径别借用 `NumIo[3]`（70px）。** 用独立 300px。
   「候选 N 人 / 可选 0 人」基本就是这个原因。

### 4.6 追踪函数

```
偏移   0x6FF841C   (libUE4 +)
类     STEShootWeaponProjectComponent.cpp
入口   stp s0,s1 / stur s2 ; stp s3,s4 / stur s5
调用   无直接 BL -> 虚函数
```

**地址校验法**：在函数体内找 `adrp+add` 拼出的 `__FILE__` 字符串，反查 UTF-8。
比特征码可靠。

### 写回（RT 615/617）

```cpp
PTE_HookSetRot cfg{};
cfg.stack_rot[0] = 0; cfg.stack_rot[1] = FloatBits(x); cfg.stack_rot[2] = 1;
cfg.stack_rot[3] = 1; cfg.stack_rot[4] = FloatBits(y); cfg.stack_rot[5] = 1;
cfg.stack_rot[6] = 2; cfg.stack_rot[7] = FloatBits(z); cfg.stack_rot[8] = 1;
cfg.stack_count = 9; cfg.rot[2] = 4;
ioctl(fd, 617, &cfg);
```

### 一排坑（详见 intl46）

| 坑 | 症状 | 修法 |
|---|---|---|
| 写回组错 | 打自己脚下 / 打不中 | 写 s0/s1/s2 |
| 驱动 fd 自开 socket | 驱动连不上 | fd 保持 -1，靠全局 ioctl hook |
| 选靶半径 70px | 候选 N / 可选 0 | 独立 300px |
| Paradise 挂点后 set_record | 读到的永远是自己写的 | 等真实记录 pc!=0 |
| 后端枚举当下标 | 进主菜单悬浮窗消失(SIGSEGV) | 扩数组 + 夹紧下标 |
| Android.mk 丢失 | 编不过 | 手拉命令，见 intl46 第八节 |
