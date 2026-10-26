# 驱动对接指南：把一套新驱动接进工程（RT / Paradise / 用户态）

> **换驱动 = 对接驱动。** 本质上是把「一套陌生的驱动接口」接进现有工程，
> 不是改几个常量。本文按**对接流程**组织：拿到 → 认接口 → 接内存 → 接断点 → 验证。

> 来源：2026-10-26 实战。一晚上有一半时间耗在驱动上。
> 本文写清**两种驱动的 ABI 差异、怎么判断装的是哪个、换的时候要改哪几处、验证怎么做**。

---

## 零、先搞清一件事

**「内存读写后端」和「PTE 断点通道」可以是两个不同的驱动。**

| 用途 | 需要什么 |
|---|---|
| 读敌人坐标 / 骨骼 / 矩阵 | 读内存能力（用户态 or 驱动） |
| PTE 追踪写回 | 必须驱动层（PTE shadow） |

**所以换驱动要分两层换，不要混着改。**

---

## 零·五、对接一个新驱动的完整流程（7 步）

> 拿到一份陌生驱动的头文件（比如别人给的 kernel.h），照这个顺序走。

| 步 | 做什么 | 产出/判据 |
|---|---|---|
| 1 | **读头文件，列命令表** | 把所有 OP_CMD_xxx 抄成一张表：编号、含义、结构体 |
| 2 | **找 fd 从哪来** | 文件里有没有 open()/socket()/syscall(142)？没有就是全局 hook，fd 可保持 -1 |
| 3 | **对齐结构体 ABI** | 每个 ioctl 参数的结构体，字段顺序/大小必须一模一样；有 static_assert 就照抄 |
| 4 | **接内存读写** | read/write/get_module_base 三个先通，否则后面全是 0 |
| 5 | **接断点挂点** | 挂点命令 + 摘点命令；挂上后命中数要能涨 |
| 6 | **接写回** | 写回命令 + 寄存器索引；先试夸张值验证是否生效 |
| 7 | **接状态/命中查询** | 命中数、寄存器现场；用于判断链路是否活着 |

**第 4 步不通就别往下走。** 读不到内存 = 后面所有判断都是瞎的。

### 对接时的三个硬约束

1. **不要改结构体字段顺序**：驱动是按字节偏移读的，差一个字节全废。
2. **不要自己发明 fd**：头文件里怎么拿就怎么拿，没写就保持 -1。
3. **先跑探针再跑业务**：用一条最简单的 ioctl（读自身 4 字节）确认通道活，再谈挂断点。

### 对接完成的标志

```
□ 601 读自身成功        □ 603 取模块基址非 0
□ 挂点返回 0           □ 命中数随开枪增长
□ 写回返回 0           □ 写夸张值(抬高50m)子弹飞天
```

---

## 一、两种驱动的 ABI 对照

### RT 风格（`kernel.h⟫ 原版对接例子）

```
601 READ        读内存
602 WRITE       写内存
603 BASE        取模块基址
608 GYRO        陀螺仪注入
615 HOOK_ATTACH     挂 PTE 幽灵页断点
616 HOOK_DETACH     摘点
617 HOOK_SET_ROT    下发寄存器覆盖表
618 HOOK_STATUS     取状态/命中数
619 HOOK_READREG    读指定寄存器当前值
605 HIDE_PROCESS    隐藏进程
```

### Paradise 风格（`paradise_api.h⟫）

```
ptebp_set(points, n)                   挂点        ioctl 0xC1985746
ptebp_get_records(pt, idx, rec, n, &c) 取命中记录   ioctl 0xC0185749
ptebp_set_record(pt, idx, &rec)        改记录       ioctl 0xC360574A
ptebp_remove()                         摘点        ioctl 0xC0045747
hwbp_set / hwbp_remove                 硬件断点
```

**核心区别：**

| | RT | Paradise |
|---|---|---|
| 写回模型 | **整表下发**（告诉驱动"把 s0/s1/s2 改成这些值"） | **改命中记录**（先取记录，改 mask + 值，再写回） |
| 有没有 record 概念 | 没有 | 有（848 字节记录） |
| 断点是否常驻 | 是，换值不重挂 | 是，但记录会被覆盖 |
| 污染风险 | 无 | **高**（见第四节） |

---

## 二、怎么判断手机装的是哪个驱动

### 方法 1：看能力探针（最准）

```cpp
// 601 用真实缓冲区读自身 4 字节
char probe[8] = {0};
PTE_CopyMemory cm{pid, (uintptr_t)probe, probe, 4};
bool canRead = (ioctl(fd, 601, &cm) == 0);

// 615/617/618 用 errno != ENOTTY 判断"有没有这条命令"
errno = 0; ioctl(fd, 615, nullptr); bool can615 = (errno != ENOTTY);
errno = 0; ioctl(fd, 617, nullptr); bool can617 = (errno != ENOTTY);
errno = 0; ioctl(fd, 618, nullptr); bool can618 = (errno != ENOTTY);
```

**判据：`errno == 25 (ENOTTY)⟫ 表示驱动没这条命令。**

### 方法 2：看模块有没有加载

```bash
su -c 'lsmod | head -20'
su -c 'cat /proc/modules | head'
```

### 方法 3：试握手

```cpp
// Paradise 用 reboot magic 拿 fd
syscall(142, 0xDEADBEEF, 0xF00DCAFE, 0, &fd);   // fd >= 0 = 成功
// 失败常见 errno = 22 (EINVAL) = 这组 magic 驱动不认
```

---

## 三、换驱动要改的四处（缺一处就"半通不通"）

| # | 改什么 | RT | Paradise | 漏改症状 |
|---|---|---|---|---|
| 1 | **内存读写后端** | `g_rt->read/write/get_module_base⟫ | `g_paradise->read/write/get_module_base⟫ | 坐标恒 0，绘制空 |
| 2 | **fd 获取方式** | `socket(AF_INET, SOCK_DGRAM)⟫ 或直接 `-1⟫ | `syscall(142, magic1, magic2, 0, &fd)⟫ | 驱动"未连接" |
| 3 | **PTE 挂点命令** | 615 | `ptebp_set()⟫ | 断点挂不上 |
| 4 | **写回方式** | 617 整表 | 取记录→改→`set_record⟫ | 命中数涨但打不中 |

**再加一处 UI/配置的后端枚举（见第六节），漏了会崩。**

---

## 四、Paradise 的必踩坑：挂点后立刻写假记录

```cpp
// ❌ 这样写会毁掉一切
installed = g_paradise->ptebp_set(&pt, 1);
if (installed) {
    ClearWriteBack();      // 内部调 ptebp_set_record 塞全零记录
}
```

`set_record⟫ 是**整条 848 字节覆盖**。断点刚挂、游戏还没命中过，
这条假记录就成了驱动里的"唯一记录"。

**后果：之后 `get_records⟫ 读到的永远是这条假记录。
你以为在看"游戏原始值"，其实在看自己写进去的值，所有诊断全废。**

**正确做法：挂点后什么都别写，等游戏自己产生第一条真实记录。**

```cpp
// 判断记录是不是真的
if (rec[0].pc == 0) {
    // 还没有真实命中，这条不能当数据看
    return false;
}
```

---

## 五、RT 的必踩坑：fd 不要自己造

`kernel.h⟫ 原版里：

```cpp
c_driver() : fd(-1), pid(0) {}
void initialize(pid_t target_pid) { pid = target_pid; }   // 只设 pid，不碰 fd
```

**`fd⟫ 恒为 `-1⟫，它照样能工作。**

原因：RT 模块**全局 hook 了 ioctl 系统调用**，不看 fd 指向什么。

### 两种错法

```cpp
// ❌ 错法1: 自己开 socket 然后把 socket fd 传进去
fd = socket(AF_INET, SOCK_DGRAM, 0);
ioctl(fd, 615, &ha);        // 只认 -1 的模块会拒

// ❌ 错法2: 拿 /dev/null 当驱动
fd = open("/dev/null", O_RDWR);
ioctl(fd, 615, &ha);        // 同上
```

### 正确做法

```cpp
// ✅ 照原版: 不打开任何设备, fd 保持 -1
c_driver* drv = new c_driver();
drv->initialize(pid);                    // 只绑 pid
drv->PteAttach(bp);                      // 内部 ioctl(-1, 615, ...)
```

**不确定模块认哪种，就都试一遍，看哪个 errno 不是 ENOTTY。**

---

## 六、UI / 配置里的后端枚举（最容易崩的地方）

```cpp
// ❌ 加了 RT 之后崩溃
static const char* bkShort[] = { "", "用户态", "Paradise" };   // 只有 3 个
ImGui::TextDisabled("读取:%s", bkShort[g_readBackend]);
// g_readBackend 可以是 3 -> 越界读野指针 -> %s 解引用 -> SIGSEGV
```

**症状：点「进入主菜单」悬浮窗直接消失（进程死亡）。**

```cpp
// ✅ 修法: 扩数组 + 夹紧下标
static const char* bkShort[] = { "", "用户态", "Paradise", "RT" };
const int bi = (g_readBackend >= 1 && g_readBackend <= 3) ? g_readBackend : 1;
```

**规则：任何用「后端/模式枚举」当下标的数组，加枚举值时同步扩数组。**

---

## 七、配置方式（示例工程的写法）

```
文件: /sdcard/Android/data/<包名>/files/fj_config.txt
第一行: 1 = 用户态   2 = Paradise   3 = RT
第二行: (可选) 设备路径
```

```cpp
int mode = 1;
if (v >= 1 && v <= 3) mode = v;
SetReadBackend(mode);
KernelBackend_Init();     // 内部把两套实例都建好，谁在用谁
```

**建议：两个实例都建好，按选择分派，不要"只建一个"。**

---

## 八、换完驱动的验证清单（按顺序过）

```
□ 1. 内存读探针     601 读自身 4 字节，返回成功
□ 2. 模块基址       603 取 libUE4.so 基址，非 0
□ 3. 挂点           615 返回 0（或 ptebp_set 返回 true）
□ 4. 命中数         开一枪，618/619 的 hit_count 增长
□ 5. 写回           617 返回 0
□ 6. 写回生效       写一个离谱值（如抬高 50m），子弹应该飞天
□ 7. 写回组         飞天说明写回生效；打不中人再换组（s3/s4/s5 ↔ s0/s1/s2）
```

**第 6 步是判断"写回到底进没进游戏"最快的方法：把落点抬高 50 米，飞天就是通了。**

---

## 九、症状 → 驱动问题 映射表

| 症状 | 驱动层原因 | 修法 |
|---|---|---|
| 驱动"未连接" | fd 获取方式错 | RT 用 socket/-1；Paradise 用 reboot magic |
| 所有 ioctl 都 ENOTTY | 通道不对（模块没 hook 这个 fd） | 换 fd 来源，或确认模块加载 |
| 601 能读，615 全 ENOTTY | 该驱动只做读写，没 PTE 能力 | 换驱动 |
| 断点挂了但命中数不动 | 地址错，或该函数不常驻 | 换地址 / 静置法验证 |
| 命中数涨但永不打中 | 写回组错 | 换组 |
| 命中数暴涨 | 挂在了每帧函数上 | 换地址 |
| 读到的寄存器值永远是自己写的 | Paradise 记录被污染 | 重挂断点，别再写假记录 |
| 进主菜单崩溃 | UI 数组越界 | 扩数组 |
| 换驱动后整个程序卡死 | 某路 ioctl 超时 | 加冷却，别每帧重试 |

---

## 十、切换代码骨架（双后端共存）

```cpp
// ---- 实例 ----
inline c_driver*        g_rt       = nullptr;   // RT
inline paradise_driver* g_paradise = nullptr;   // Paradise
inline std::atomic<int> g_driverSel{0};         // 0=RT 1=Paradise

// ---- 初始化：两个都建 ----
inline void DriverInit(pid_t pid) {
    if (!g_rt) g_rt = new c_driver();
    g_rt->initialize(pid);

    if (!g_paradise) g_paradise = new paradise_driver();
    g_paradise->initialize(pid);
}

// ---- 挂点 ----
inline bool DriverAttach(uintptr_t bp) {
    if (g_driverSel.load() == 0) return g_rt->PteAttach(bp);
    paradise_ptebp_point_config pt{};
    pt.address = bp; pt.type = PARADISE_HWBP_EXECUTE;
    pt.length = 4;  pt.scope = PARADISE_HWBP_ALL_THREADS;
    return g_paradise->ptebp_set(&pt, 1);
}

// ---- 写回 ----
inline bool DriverWrite3(float x, float y, float z) {
    if (g_driverSel.load() == 0) return g_rt->PteUpdateFloat3(x, y, z);
    // Paradise: 取记录 -> 改 -> 写回
    paradise_ptebp_record rec[2]; uint32_t n = 0;
    if (!g_paradise->ptebp_get_records(0, 0, rec, 2, &n) || n == 0) return false;
    if (rec[0].pc == 0) return false;               // 真实记录还没来
    paradise_ptebp_record& r = rec[0];
    memset(r.mask, 0, sizeof(r.mask));
    r.q0 = (__uint128_t)FBits(x);
    r.q1 = (__uint128_t)FBits(y);
    r.q2 = (__uint128_t)FBits(z);                   // 4.6 国际服写 s0/s1/s2
    PARADISE_BP_SET_MASK(&r, PARADISE_REG_Q0, PARADISE_BP_OP_WRITE);
    PARADISE_BP_SET_MASK(&r, PARADISE_REG_Q1, PARADISE_BP_OP_WRITE);
    PARADISE_BP_SET_MASK(&r, PARADISE_REG_Q2, PARADISE_BP_OP_WRITE);
    return g_paradise->ptebp_set_record(0, 0, &r);
}

// ---- 摘点 ----
inline void DriverDetach() {
    if (g_driverSel.load() == 0) g_rt->PteDetach();
    else { g_paradise->ptebp_remove(); g_paradise->hwbp_remove(); }
}
```

---

## 十一、一句话口诀

> **换驱动 = 换 fd 来源 + 换挂点命令 + 换写回模型，四处一起换。**
> **RT 靠全局 ioctl hook（fd 可保持 -1），Paradise 靠 reboot magic 拿 fd。**
> **Paradise 挂点后千万别写假记录，否则后面全是假数据。**
