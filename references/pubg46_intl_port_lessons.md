# PUBG MOBILE 4.6 国际服 · PTE 追踪移植实战（坑全记录）

> 来源：2026-10-26 一次完整移植。从「和平精英版 lsrael 漏打陀螺仪」改成
> 「PUBG MOBILE 4.6 国际服 `com.tencent.ig`」，从绘制到追踪全部跑通。
> 本文只记**验证过的事实**和**踩过的坑**，不写推测。

---

## 零、一句话结论（最能省时间的四条）

1. **4.6 国际服写回必须写 `s0/s1/s2`，写 `s3/s4/s5` 完全无效。**
   写错组的症状：子弹往自己脚下打 / 乱飞 / 有时"偏一米能中"。
2. **4.6 国际服没有国服那个 `fmov s2,s5 / s1,s4 / s0,s3 / ret` 返回值桩。**
   全 `.text` 精确扫描命中数 = 0，宽松扫「三条 fmov + ret」也 = 0。别去扫了。
3. **PTE 驱动 `fd` 不要自己开 socket。**
   原版 `kernel.h` 里 `fd` 永远是 `-1`，模块全局 hook `ioctl` 系统调用，不看 fd。
4. **选靶半径别借用 `NumIo[3]`（自瞄圈，默认 70px）。**
   实测 4 个敌人的屏幕距离都在 100px 以上 → "候选 4 人但可选 0 人" → 永远不写回。

---

## 一、4.6 国际服追踪函数

| 项目 | 值 |
|---|---|
| 偏移 | `0x6FF841C` |
| 所在类 | `STEShootWeaponProjectComponent.cpp`（射击武器投射组件） |
| 函数入口 | `stp s0,s1 / stur s2` 与 `stp s3,s4 / stur s5` —— 存两组 float3 |
| 内部 | `0x6FF8494: bl 0x76C0F00`（x1=&s0 组，x2=&s3 组，w3） |
| 调用方式 | 无任何 `BL` 直接调用者 → 虚函数 |
| 断言字符串 | `0x4189635` = `D:\Release4.6.0\AS\Survive\Source\ShadowTrackerExtra\Weapons\STEShootWeaponProjectComponent.cpp` |

**校验地址对错的可靠方法**：在函数体内找 `adrp+add` 拼出的 `__FILE__` 字符串，
反查 UTF-8 内容。比特征码扫描可靠得多。

### 与国服的差异（别混用）

| | 国服 和平精英 | 国际服 4.6 |
|---|---|---|
| 追踪函数 | `0x0A0FB548` | `0x06FF841C` |
| 形态 | `fmov s0,s3 / s1,s4 / s2,s5 / ret` 返回值桩 | 普通函数，存两组 float3 后调 ProcessEvent 封装 |
| 写回组 | `s3/s4/s5` | **`s0/s1/s2`** |

---

## 二、【核心坑】写回寄存器组选错

### 症状谱（按出现顺序）

1. 断点挂上了、命中数随开枪连涨、绘制正常
2. 子弹**打不到人**，落点飘忽
3. 把「左右偏移」调 +3 米 → **变成打自己脚下**
4. 换成另一组寄存器 → **立刻正常**

### 原因

游戏把 `s3/s4/s5` 当**起点**、`s0/s1/s2` 当**终点**（或等价的反向语义）。
我们把敌人坐标写进 `s3/s4/s5`，等于告诉游戏「从敌人身上朝我打」。

### 正确的写回（RT 615/617 通道）

```cpp
// ✅ 4.6 国际服：写 s0/s1/s2
const uint32_t r0 = 0u;
PTE_HookSetRot cfg{};
cfg.stack_rot[0] = r0 + 0; cfg.stack_rot[1] = FloatBits(x); cfg.stack_rot[2] = 1;
cfg.stack_rot[3] = r0 + 1; cfg.stack_rot[4] = FloatBits(y); cfg.stack_rot[5] = 1;
cfg.stack_rot[6] = r0 + 2; cfg.stack_rot[7] = FloatBits(z); cfg.stack_rot[8] = 1;
cfg.stack_count = 9;
cfg.rot[2] = 4;                 // 4 = 写回模式；2 = 捕获模式
ioctl(fd, 617, &cfg);
```

### 排查顺序（照这个走，不要跳）

```
命中数不涨   -> 函数地址错 / 断点没挂 / 驱动通道不对
命中数涨但写回失败 -> 617 失败, 看 errno（25=ENOTTY 表示无此命令）
写回成功但打不中 -> 先切写回组(s0/s1/s2), 再谈偏移
切组仍不中   -> 才轮到弹道下坠/预测/偏移校正
```

---

## 三、驱动接入：两种 ABI，别混

### A. RT 风格（`kernel.h` 原版对接例子）

```
601 READ  602 WRITE  603 BASE
615 HOOK_ATTACH  616 HOOK_DETACH  617 HOOK_SET_ROT  618 HOOK_STATUS  619 HOOK_READREG
```

**关键：`c_driver() : fd(-1), pid(0) {}`，`initialize()` 只设 pid，从不打开设备。**
模块全局 hook `ioctl` 系统调用，**不看 fd**。

自己 `socket(AF_INET, SOCK_DGRAM)` 然后把 socket fd 传进去，在只认 `-1` 的模块上会被拒。
**照原版：不打开任何设备。**

挂点：
```cpp
PTE_HookAttach ha{}; ha.pid = pid; ha.target_addr = bp;
ioctl(fd, 615, &ha);
```

命中数 / 寄存器现场：
```cpp
struct { uint32_t reg_idx; uint32_t pad; uint64_t value; uint64_t hit_count; } cmd{};
cmd.reg_idx = 3;                       // 0..5 对应 s0..s5
ioctl(fd, 619, &cmd);                  // value = 寄存器当前值, hit_count = 累计命中
```

### B. Paradise 风格（`ptebp_*`）

```
ptebp_set()          挂点
ptebp_get_records()  取命中记录
ptebp_set_record()   改记录的 mask + 寄存器值
ptebp_remove()       摘点
```

**必踩的坑：挂点成功后立刻 `set_record` 塞一条全零记录。**
`set_record` 是整条 848 字节覆盖，之后 `get_records` 读到的全是这条假记录，
**永远看不到游戏真实传的值**，所有诊断都是自己跟影子打架。

正确做法：挂点后**什么都别写**，等游戏自己产生第一条真实记录（`pc != 0`）再读。

---

## 四、选靶半径

```cpp
// ❌ 错：借用自瞄圈
limPx = NumIo[3];              // 默认 70px

// ✅ 对：独立像素半径，对齐 lsrael 的「拾取半径(px)」
limPx = 300.0f;                // 滑条 10~1200
```

**日志证据（4 个敌人，屏幕中心 1520,952）：**

```
#0 头 S=(1162,956)  距中心 358px
#1 头 S=(853,946)   距中心 667px
#2 头 S=(999,956)   距中心 521px
#3 头 S=(1355,947)  距中心 165px    <- 最近的也 165px
半径 70px  =>  全部落在圈外  =>  可选目标=0  =>  永不写回
```

**「候选 N 人 / 可选 0 人」这个现象，先在半径上找原因。**

---

## 五、UI 崩溃坑（加了后端枚举必看）

```cpp
// ❌ 崩溃点
static const char* bkShort[] = { "", "用户态", "Paradise" };   // 3 个
ImGui::TextDisabled("读取:%s", bkShort[g_readBackend]);
// 加了 RT 之后 g_readBackend 可以是 3 -> 越界读野指针 -> %s 解引用 -> SIGSEGV
```

**症状：点「进入主菜单」悬浮窗直接消失（进程死亡）。**

修法：
```cpp
static const char* bkShort[] = { "", "用户态", "Paradise", "RT" };   // 补齐
const int bi = (g_readBackend >= 1 && g_readBackend <= 3) ? g_readBackend : 1;
```

**规则：任何用「后端/模式枚举」当下标的地方，加枚举值时同步扩数组，并夹紧下标。**

---

## 六、PUBG 4.6 国际服全量偏移（可直接当基线）

```cpp
// 世界链
Off_UWorld      = 0xF621D90;   // UE4 + this -> p1
Off_UWorld_B    = 0x810;       // p1 + this  -> p2
Off_UWorld_C    = 0x78;        // p2 + this  -> UWorld
// 列阵 = UWorld + 0x30;  ActorArray = 列阵 + 0xA0;  ActorCount = 列阵 + 0xA8

// 自身链（UWorld 之后）
Off_Self_A = 0x38; Off_Self_B = 0x78; Off_Self_C = 0x30; Off_Self_D = 0x28D8;

// 矩阵
Off_Matrix_46 = 0xF5F4370; Off_Matrix_46_B = 0x20; Off_Matrix_46_C = 0x270;

// GName
Off_GName = 0xF08F820; Off_GName_B = 0x110;

// 坐标
Off_Position = 0x208; Off_Position_B = 0x1C8;

// 相机
Off_PlayerController = 0x4B50; Off_PlayerCameraManager = 0x548;
Off_CameraCache = 0x520; Off_POV = 0x10;                       // rot +0x0C, fov +0x24

// 骨骼
Off_Mesh = 0x510;  Off_Mesh_Human = 0x210;
Off_BoneArray = 0xA30 (+0x30);  Off_BoneCount = 0xA40;  BoneStride = 48;

// 人物字段
Off_Team 0x998 | Off_Name 0x960 | Off_IsBot 0xA59
Off_Health 0xE60 | Off_HealthMax 0xE64 | Off_DeathFlag 0xE7C
Off_Firing 0x1840 | Off_Aiming 0x1134 | Off_Action 0x1058
Off_ItemFilter 0x2B98 | Off_ItemFilter_Old 0x3A64   // 值 479.5f = 真人

// 追踪断点
kTrackShootFn = 0x06FF841C
```

---

## 七、把「和平精英版工程」改成 4.6 国际服的 9 处对照

以 `lsrael漏打螺贴仪` 结构为例（`绘制.cpp` / `ReadGame.cpp`）：

| 项目 | 和平精英 | 4.6 国际服 |
|---|---|---|
| 包名 | `com.tencent.tmgp.pubgmhd` | `com.tencent.ig` |
| UWorld | `UE4+0x1771CC38` | `UE4+0xF621D90 → +0x810 → +0x78` |
| 列阵 | `read(...+0xb8)` | `UWorld+0x30` |
| 自身 | `+0xc0 +0x88 +0x30 +0x3540` | `+0x38 +0x78 +0x30 +0x28D8` |
| 矩阵 | `0x176E6EE0 +0x20 +0x270` | `0xF5F4370 +0x20 +0x270` |
| 坐标 | `+0x260 +0x200` | `+0x208 +0x1C8` |
| 相机 | `+0x60C8 +0x680 +0x650` | `+0x4B50 +0x548 +0x520 +0x10` |
| 骨骼 | `Mesh+0x658 / 0x848 / 0x1f0` | `Mesh+0x510 / 0xA30 / 0x210`，count `0xA40` |
| 追踪断点 | `0xA0FB548` | `0x6FF841C` |

**骨骼索引表（69/71/73/63/64/38/30/26/27/46/42/76/61…）跨版本通用，不用改。**
它是按 `Bonecount` 自动选表的。

---

## 八、构建坑（Android.mk 丢失时手工编译）

这台机器上 `ndk-build` 的 `Android.mk` 可能丢失，只能手拉命令。踩过的坑：

1. **`#include "./include/My_Utils/xxx.h"` 找不到**
   引号包含先按源文件目录找，再按 `-I`。必须加 `-I<jni 根>`，
   否则 `./` 会解析成 `src/include/...`。

2. **`libembree3.a` 缺失 → `undefined symbol: rtcGetGeometry`**
   工程里只有 embree3 头文件。库要单独找（同项目其它副本里往往有）。
   **embree4 的 `.a` 不能直接配 embree3 的头**。

3. **同名 `.cpp` 互相覆盖**
   `T3/HTTPSession.cpp` 与 `T3/HttpClient.cpp` 同时定义 `HTTPSession::HTTPSession`。
   平铺输出 `.o` 时用 `路径_文件名` 命名，并排除重复那份。

4. **`undefned symbol: sizet`**
   源码里只有 `extern int sizet;` 没有定义（定义在丢失的模块里）。补 `int sizet = 0;`。

5. **`duplicate symbol: PADDING`**
   多个 TU 各定义一份同名全局。加 `-Wl,--allow-multiple-definition`。

6. **`non-constant-expression cannot be narrowed double -> float`**
   `ndk-build` 默认放行，clang 会报错。加 `-Wno-c++11-narrowing`。

---

## 九、最终可用的写回逻辑（照抄即用）

```cpp
// 1) 选中目标骨骼世界坐标 (x,y,z)
// 2) 写 s0/s1/s2 组
PTE_HookSetRot cfg{};
cfg.stack_rot[0] = 0; cfg.stack_rot[1] = FloatBits(x); cfg.stack_rot[2] = 1;
cfg.stack_rot[3] = 1; cfg.stack_rot[4] = FloatBits(y); cfg.stack_rot[5] = 1;
cfg.stack_rot[6] = 2; cfg.stack_rot[7] = FloatBits(z); cfg.stack_rot[8] = 1;
cfg.stack_count = 9;
cfg.rot[2] = 4;
ioctl(fd, 617, &cfg);

// 3) 不锁目标时退回捕获模式，避免上一发残留
PTE_HookSetRot off{};
off.rot[2] = 2;
ioctl(fd, 617, &off);
```

**验证过：4.6 国际服 + RT 615/617，写 s0/s1/s2 = 弹道正常命中。**
