# PTE 追踪偏移抓取技能（插件版索引）

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
