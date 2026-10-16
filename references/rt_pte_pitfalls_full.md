# RT 驱动 PTE 追踪 · 实战坑集（下一个 AI 必读）

> 来源：2026-10-16 在 PUBGM 1.38.12 + RT hook v1.0 上把 PTE 追踪从零做到能用。
> 记录**所有踩过的坑**，按「症状 → 根因 → 修法 → 教训」组织。
> 按坑的**危害程度**排序，前面的最坑人。

---

## 坑 0（最坑）：编译没加 -O2 —— 抖动/脱框/卡顿的真凶

### 症状
- 转视角时绘制**抖动**（我往上转，它就往上抖）
- 人物**脱框**（方框脱离敌人身体）
- UI 呼出**卡顿**
- 这些症状**跟任何功能开关都无关**，一直存在

### 根因
```
原版: 用 ndk-build 编译 → 默认 -O2
我:   手写 clang 命令忘了写 -O → 默认 -O0（无优化）
→ 性能差 3~5 倍 → 帧率低 → 绘制采样跟不上视角变化 → 抖/脱框/卡
```

### 修法
```bash
# 编译和链接都要加 -O2
clang++ --target=aarch64-linux-android21 --sysroot=$SR -O2 -std=c++17 ... -c x.cpp -o x.o
clang++ --target=aarch64-linux-android21 --sysroot=$SR -O2 -fuse-ld=lld ... -o out <objs>
```

### 验证方法
```bash
# -O2 编出来的体积会明显更小（本例小了 590KB）
stat -c%s 旧版  # 11484664（-O0）
stat -c%s 新版  # 10895544（-O2）
```

### 教训（血泪）
**用户说「没修 PhysX 之前也抖」时，我还在往 PhysX 上猜。**
正确做法：症状与任何开关无关 → 先查**全局因素**（编译优化等级、帧率）。

---

## 坑 1：命令用错 608 vs 615（浪费最多时间）

### 症状
```
[608 HWBP_ADD] ret=0   ✅ 断点装上了
[609 GET_HITS] errno=3 (ESRCH)  ❌ 永远 0 命中
```

### 根因
```
608 = 硬件断点（perf_event / register_user_hw_breakpoint）
      → per-thread！射击线程对不上就永远 0 命中
      → CPU 只有 4-8 个断点槽
615 = HOOK_ATTACH（PTE 幽灵页）
      → 进程级，全线程生效（所有线程共享同一张用户页表）
```

### 修法
```cpp
// RT 驱动正确命令表
#define PTE_RT_HOOK_ATTACH   615   // 挂断点
#define PTE_RT_HOOK_DETACH   616   // 摘除
#define PTE_RT_HOOK_SET_ROT  617   // 设置模式（必须调！）
#define PTE_RT_HOOK_STATUS   618   // 读状态
#define PTE_RT_HOOK_READREG  619   // 读寄存器
```

### 教训
**驱动命令表要先读 kernel.h 确认，不要靠试。**
用户提供的源码里的命令表可能不匹配当前驱动版本。

---

## 坑 2：617 必须调，不调驱动不工作

### 症状
615 挂上了 ret=0，但**命中数永远是 0**。

### 根因
615 只是「挂断点」，驱动默认不做任何事。必须用 617 设置模式：
```
rot[2]=2  捕获模式（只记录命中）
rot[2]=3  内核拷贝模式
rot[2]=4  写回模式（改寄存器）
```

### 修法
```cpp
// 装完断点后必须设模式
HOOK_SET_ROT cfg{};
cfg.rot[2] = 2;            // 捕获
ioctl(fd, 617, &cfg);

// 写回坐标（改 V3/V4/V5 = float3）
HOOK_SET_ROT cfg2{};
cfg2.stack_rot[0]=3; cfg2.stack_rot[1]=float_bits(x); cfg2.stack_rot[2]=1;
cfg2.stack_rot[3]=4; cfg2.stack_rot[4]=float_bits(y); cfg2.stack_rot[5]=1;
cfg2.stack_rot[6]=5; cfg2.stack_rot[7]=float_bits(z); cfg2.stack_rot[8]=1;
cfg2.stack_count = 9;
cfg2.rot[2] = 4;
ioctl(fd, 617, &cfg2);
```

---

## 坑 3：通道必须是 socket，不是 /dev/null

### 症状
```
/dev/null  → 2026/601/810 全部 errno=25 (ENOTTY 不认)
socket     → 认命令
```

### 根因
**RT 驱动只 hook socket 的 ioctl**，不走字符设备。

### 修法
```cpp
int fd = socket(AF_INET, SOCK_DGRAM, 0);   // 唯一正确通道
```

### 坑中坑：盲扫命令会让手机重启
```c
// 千万别这么干！RT 驱动对未知命令不做参数校验，盲扫会内核 oops
for (int cmd = 605; cmd <= 630; cmd++) { ioctl(fd, cmd, &bad_args); }  // ❌ 手机会重启
```
只测**已知命令**，且参数必须合法。

---

## 坑 4：结构体多一个字段就全错

### 症状
ioctl 返回失败，或参数被驱动读成垃圾。

### 根因
PTE 源码版的 `ShadowSetArgs` 多了 `is_write_regs` 字段，导致 `reg_count` 从 @16 错位到 @20，**整个结构体参数全错**。

### 修法（正确布局，352 字节）
```c
struct pte_bp_shadow_set_args {
    pid_t    pid;              // @0
    uintptr_t addr;            // @8
    int      reg_count;        // @16  ← 没有前置字段！
    int      reg_index[16];    // @20
    uint64_t reg_value[16];    // @88
    int      fp_reg_count;     // @216
    int      fp_reg_index[16]; // @220
    float    fp_reg_value[16]; // @284
};  // 352 字节
```

HOOK_STATUS 精确 **72 字节**（别手动加 padding）：
```c
struct HOOK_STATUS {
    uint8_t  active;   // @0
    uint8_t  armed;    // @1
    pid_t    pid;      // @4  (自然对齐)
    unsigned long vaddr;       // @8
    unsigned long target_addr; // @16
    uint32_t rot[3], stack_rot[3];
    uint32_t stack_count, stack_offset;
    uint64_t hit_count;        // @56
    uint64_t captured_x0;      // @64
};  // 72 字节
```

### 验证方法
```cpp
static_assert(sizeof(PTE_HookAttach) == 16, "HookAttach ABI");
static_assert(sizeof(PTE_HookSetRot) == 68, "HookSetRot ABI");
static_assert(sizeof(PTE_HookStatus) == 72, "HookStatus ABI");
```
**用 static_assert 在编译期卡住**，别等运行时才发现。

---

## 坑 5：PTE 是页级断点，不是指令级

### 症状
静置（不开枪）时命中数也疯狂增长（39次/秒 ≈ 帧率）。

### 根因
```
PTE 幽灵页 = 把 4KB 页的 UXN 位置 1
1 页 = 21 个函数（实测 0xA0FB000 页）
整页所有函数都被拦 → 写回会影响整页所有函数
```

### 判定地址对不对的方法（区分每帧函数 vs 射击函数）
```
1. 615 挂断点 + 617 捕获模式
2. 静置 10 秒 → 记命中数
3. 开枪 10 秒 → 记命中增量

静置 ≈ 0 且 开枪 > 0  → 真射击函数 ✅
静置 > 100          → 每帧函数，地址错 ❌
```

### 教训
**训练场里有别人开枪**，但别人的射击是服务器算的，不会触发你本地的射击逻辑。
所以「静置 vs 开枪」对比法仍然有效，但必须真的停火。

---

## 坑 6：坐标必须用骨骼世界坐标，不能自己算偏移

### 症状
追踪能生效，但子弹**固定偏一边**（比如永远偏右）。

### 根因
```cpp
// ❌ 错：世界坐标 + 估算偏移（像素值）
z = 坐标.Z + (205.0f - 部位高度 * 2.0f);

// ❌ 也错：世界坐标 + 身高偏移（还是偏）
z = 坐标.Z + 身高 * 0.70f;
```

### 修法
```cpp
// ✅ 对：直接用骨骼世界坐标（精确部位点）
部位坐标 = 对象信息.敌人信息.骨骼坐标[部位索引];
//   骨骼坐标[0] = 头   骨骼坐标[1] = 胸   骨骼坐标[2] = 臀
//   由 骨骼->更新骨骼数据() 每帧填充，已是精确世界坐标
```

骨骼索引映射（`骨骼.hpp` 的 `boneIndices` 数组）：
```cpp
boneIndices = {5, 4, 0, ...}
// 头, 胸, 盆骨, 左肩, 右肩, 左肘, 右肘, 左腕, 右腕,
// 左大腿, 右大腿, 左膝, 右膝, 左脚踝, 右脚踝
骨骼坐标[0].Z += 7;   // 脖子长度修正
```

---

## 坑 7：static 变量被所有敌人共用（隐蔽 bug）

### 症状
① 骨骼颜色**一半红一半绿**
② 追踪**失效**（选靶读到脏数据）

### 根因
```cpp
// ❌ 错：static 轮转变量被所有敌人抢着改
static int 轮转 = 0;
for (int k = 0; k < 2; k++) {
    const int b = 轮转;
    轮转 = (轮转 + 1) % 15;
    isVisible[b] = CustomLineTrace(...);
}
// 敌人A只更新 isVisible[0][1]，敌人B只更新 [2][3]...
// → 大部分骨骼保持初始值 → 红绿参半 + 选靶读到旧值
```

### 修法
```cpp
// ✅ 对：每个敌人算完整 15 根
for (int i = 0; i < 15; i++)
    isVisible[i] = CustomLineTrace(locVec, 骨骼坐标[i]);
```

### 教训
**「分帧轮转省性能」这类优化，在「每个对象共享 static 变量」的循环里会出致命 bug。**
要省性能就按**距离**或**对象属性**过滤，不要用跨对象共享的状态变量。

---

## 坑 8：选靶位置必须在骨骼更新之后

### 症状
选「胸部」「臀部」没效果，只有「头部」看着还行。

### 根因
```
选靶代码在 1848 行，骨骼更新在 2342 行
→ 选靶读的是【上一个敌人】的旧骨骼数据
→ 头（索引0）碰巧看着还行，胸/臀完全错位
```

### 修法
**选靶块必须放在【骨骼更新】和【isVisible 射线计算】之后。**
```cpp
骨骼->更新骨骼数据(...);              // ① 先算骨骼
isVisible[i] = CustomLineTrace(...);  // ② 再算射线
// ③ 然后才是选靶
if (漏打开关) { ...选靶逻辑... }
```

---

## 坑 9：概率要按「发」算，不能按「帧」算

### 症状
设 50% 概率，打 30 发只中 5 发（期望 15 发）。

### 根因
```cpp
// ❌ 错：每帧掷一次骰子
if (rand() % 100 < 概率) 写回();
// 全自动 60fps，一发子弹跨多帧 → 掷骰次数 ≠ 发数
```

### 修法
```cpp
// ✅ 对：只在「新的一发」掷骰，整发期间结果保持
static bool 当前这发要吸 = false;
static int  距上次掷骰帧 = 999;

距上次掷骰帧++;
if (g_PTE目标.有效 && 距上次掷骰帧 >= 发间隔帧) {
    距上次掷骰帧 = 0;
    当前这发要吸 = (概率 >= 100) || (rand()*100.0f/RAND_MAX < 概率);
}
if (!g_PTE目标.有效) { 距上次掷骰帧 = 999; 当前这发要吸 = false; }
本帧写回 = g_PTE目标.有效 && 当前这发要吸;
```

**发间隔帧**要按武器射速调（60fps 下）：
```
M416(约11发/s) → 5.5 帧/发
AKM(约10发/s)  → 6 帧/发
UZI(约21发/s)  → 2.8 帧/发
M249(约13发/s) → 4.6 帧/发
```
**做成面板可调**，让用户自己校准。

---

## 坑 10：健康检查判据（armed 的陷阱）

### 症状 A：断点掉了检测不到
```cpp
// ❌ 只检查自己的标记
if (基址变了 || !pst.installed) 重挂;   // 驱动真挂了，installed 还是 true
```

### 症状 B：疯狂重装（每帧都重挂）
```cpp
// ❌ 用 armed 当失效判据
if (基址变了 || !pst.installed || !pst.armed) 重挂;
// 写回模式(rot[2]=4)下驱动【本来就报 armed=0】→ 每帧重装 → 卡顿
```

### 正确做法
```cpp
// ✅ 判据：基址变了 / 未安装 / 未武装（但加冷却）
static int 重挂冷却帧 = 0;
if (重挂冷却帧 > 0) 重挂冷却帧--;
const bool 需要重挂 = 基址变了 || !pst.installed || !pst.armed;
if (需要重挂 && 重挂冷却帧 == 0) {
    PTE追踪_卸载();
    if (PTE追踪_安装(基址)) 重挂冷却帧 = 30;   // 冷却 30 帧
}
```

**关键**：游戏重载关卡会还原页表 UXN 位，驱动 armed 会变 0 → 必须能检测到。
但 armed=0 在写回模式下是正常的 → 必须加冷却避免刷爆。

---

## 坑 11：PhysX 偏移错误反而「让程序流畅」

### 症状
修好 PhysX 后，程序变卡（帧率下降）。

### 根因
```
原版 OffsetPhysxInstancePtr = 0x16B08F10  ← 旧版 fallback，读到 0x1 垃圾值
→ PhysX 场景是空的 → LineTraceSingle 第一行 if(scene==nullptr) return false
→ 秒返回，零开销 → 反而流畅

修成 0x16bae798 → 场景真有 1900+ actor
→ 射线真开始算 → 15根 × N个敌人 → 帧率暴跌
```

### 修法
```cpp
// 射线只在【开启掩体漏打】时才算
if (按钮.PTE掩体漏打) {
    for(int i = 0; i < 15; i++) isVisible[i] = CustomLineTrace(...);
} else {
    for (int i = 0; i < 15; i++) isVisible[i] = true;   // 全可见，零开销
}
```

### 教训
**修好一个「坏掉的功能」可能让程序变慢** —— 因为坏掉时它什么都不做。
优化时要考虑「功能开启/关闭」的分支开销。

---

## 坑 12：PhysX 绘制「画什么」容易搞错

### 三种做法（我前两种都做错了）
```cpp
// ❌ 简约版：只画命中点附近 3m 内、最多 150 个三角形 → 残缺
if (距离 > kHitRadius) continue;
if (已画 >= kMaxTri) break;

// ❌ 全场景版：画附近 80m 内所有 mesh → 满屏绿
auto meshes = Scene->GetNearMesh(POV.Location, kRadiusSq);
for (auto* m : meshes) 画一个mesh(m);

// ✅ 正确：准心射线命中【哪一个物体】→ 把那个物体的【全部三角形】画出来
TriangleMeshData* mesh_ptr = LineTrace::getNextHint(POV.Rotation, POV.Location);
if (mesh_ptr == nullptr) return;
for (size_t i = 0; i + 2 < mesh.Indices.size(); i += 3) {
    // 把这个 mesh 的全部三角形画完
}
```

### 教训
**先问清用户要哪种效果**，别自己猜。用户说的是「准心命中哪个就画哪个的完整模型」。

---

## 坑 13：不要把原版能用的代码改坏

### 症状
用户说「原来的源码没这个情况」。

### 根因
我在原版基础上加了很多「优化」，把干净的结构搞乱了：
```
原版绘制.cpp:  110357 字节
我改的:       124118 字节   ← 多塞了 13KB
```

### 修法
```bash
# 每次改动前先 diff 原版，确认只改必要的地方
diff 原版/绘制.cpp 当前/绘制.cpp | grep '^<' | grep -v '^< *$'
# 输出的「原版独有行」应该只有你【故意】删掉的
```

### 教训
**用户的直觉通常是对的。** 他说「原来的没问题」，就先 diff 找出差异，而不是继续加功能。
**改之前先备份**，出问题能回退。

---

## 坑 14：UI 挪位置时不要动逻辑

### 教训
用户说「移动过去，但本身的效果还是不要变身，就是换一个地方而已」。

**正确做法**：
```
1. 原样摘出代码块（一行不改）
2. 在新位置粘贴
3. 只调整索引/缩进等结构性东西
4. 编译验证功能不变
```

---

## 快速排查表

| 症状 | 优先排查 |
|---|---|
| 抖动/脱框/卡顿 | **编译有没有 -O2** |
| 断点装了不命中 | 命令是不是 615（不是 608）；617 有没有调 |
| ioctl 全 ENOTTY | 通道是不是 socket |
| 参数被读成垃圾 | 结构体字段有没有多/少 |
| 命中数暴涨 | 地址是不是每帧函数（用静置法验证） |
| 子弹固定偏一边 | 坐标是不是用了骨骼世界坐标 |
| 骨骼红绿参半 | 有没有 static 变量跨对象共用 |
| 概率不准 | 是不是按帧掷骰（应该按发） |
| 断点疯狂重装 | armed 判据 + 有没有冷却 |
| 修好功能后变卡 | 射线/扫描是不是按需计算 |

---

## 一句话总结给下一个 AI

**做这类活，90% 的时间会浪费在「看起来像功能 bug 其实是性能/配置问题」上。**

排查顺序应该是：
1. **编译优化等级**（-O2）
2. **驱动命令表**（读 kernel.h，别猜）
3. **结构体对齐**（static_assert 卡住）
4. **数据新鲜度**（选靶在骨骼更新之后）
5. **共享状态**（static 变量）
6. 最后才是功能逻辑

**用户的观察永远优先于你的推断。** 他说「没修之前也抖」，就别往那个功能上查。
