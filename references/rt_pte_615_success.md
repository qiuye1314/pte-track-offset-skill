# RT驱动 PTE幽灵页追踪 · 实战定版（615/617）

> 2026-10-16 真机验证通过：PUBGM 1.38.12 + RT_hook v1.0 + 内核 6.6.118
> 用户反馈原话：对上了，而且没有失效

## 一、命令表：RT 用 615/617，不是 608

错误路径（浪费大量时间）：
    608 = 硬件断点（perf_event / register_user_hw_breakpoint）
        per-thread，射击线程对不上就永远 0 命中
        CPU 只有 4-8 个断点槽

正确路径：
    615 = HOOK_ATTACH   挂 PTE 幽灵页断点（进程级，全线程生效）
    616 = HOOK_DETACH   摘除
    617 = HOOK_SET_ROT  设置模式（必须调，不调驱动不工作）
    618 = HOOK_STATUS   读状态（active/armed/hit_count/vaddr）
    619 = HOOK_READREG  读命中时寄存器

## 二、617 的模式（rot[2]）

| rot[2] | 含义 | stack_rot 用法 |
|---|---|---|
| 2 | 捕获模式（只记录） | 空 |
| 3 | 内核拷贝模式 | [0]=extra_offset, [1]=skip_bytes |
| 4 | 写回模式（改寄存器） | 见下 |

写回 V3/V4/V5 = float3 坐标：
    cfg.stack_rot[0]=3; cfg.stack_rot[1]=float_bits(x); cfg.stack_rot[2]=1;
    cfg.stack_rot[3]=4; cfg.stack_rot[4]=float_bits(y); cfg.stack_rot[5]=1;
    cfg.stack_rot[6]=5; cfg.stack_rot[7]=float_bits(z); cfg.stack_rot[8]=1;
    cfg.stack_count = 9;
    cfg.rot[2] = 4;
    ioctl(fd, 617, &cfg);

## 三、三个致命坑

### 坑1：通道必须是 socket，不是 /dev/null
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
RT 只 hook socket 的 ioctl；用 /dev/null 会全部 ENOTTY(25)。

### 坑2：结构体多一个字段就全错
PTE 源码版的 ShadowSetArgs 多了 is_write_regs，
导致 reg_count 从 @16 错位到 @20，整个结构体参数全错。

正确布局（无 is_write_regs，352 字节）：
    pid @0      addr @8     reg_count @16
    reg_index[16] @20       reg_value[16] @88
    fp_reg_count @216       fp_reg_index[16] @220
    fp_reg_value[16] @284

HOOK_STATUS 精确 72 字节（别手动加 padding）：
    active @0  armed @1  pid @4  vaddr @8  target_addr @16
    rot[3] stack_rot[3] stack_count stack_offset
    hit_count @56  captured_x0 @64

### 坑3：PTE 是页级断点，不是指令级
    1 页 = 21 个函数（实测 0xA0FB000 页）
整页 UXN 置 1，整页所有函数都被拦。
写回会影响该页所有函数。

判定地址对不对的方法（区分每帧函数与射击函数）：
    1. 615 挂 + 617 捕获模式
    2. 静置 10 秒记命中
    3. 开枪 10 秒记增量
    静置接近 0 且开枪大于 0  -> 真射击函数
    静置大于 100            -> 每帧函数，地址错

注意：训练场里有别人开枪，别人开枪不影响你客户端本地的射击逻辑，
      但页内每帧函数会让静置计数也暴涨，必须用静置作基准。

## 四、坐标必须用骨骼世界坐标

错误做法：世界坐标加估算偏移（子弹固定偏一边）
    z = 坐标.Z + (205.0f - 部位高度 * 2.0f);   // 像素值，错
    z = 坐标.Z + 身高 * 0.70f;                 // 仍偏

正确做法：直接用骨骼世界坐标
    部位坐标 = 对象信息.敌人信息.骨骼坐标[部位索引];
    骨骼坐标[0] = 头    [1] = 胸    [2] = 臀
由 骨骼->更新骨骼数据() 每帧填充，已是精确世界坐标。

索引映射（骨骼.hpp 的 boneIndices 数组）：
    boneIndices = {5, 4, 0, ...}   // 头, 胸, 盆骨, 左肩, 右肩...
    骨骼坐标[0].Z += 7;            // 脖子长度修正

## 五、选靶必须准心命中式

用户原话：跟不知道我要打哪个人似的，应该是按我的瞄准准心来打。

错误做法：选离框中心最近的（会锁错人）
正确做法：用骨骼世界坐标自行投影，判准心是否落在目标身上

    auto 投影 = [&](const D3DVector& wpt, float& sx, float& sy) -> bool {
        const float* m = 自身数据.矩阵;
        const float depth = m[3]*X + m[7]*Y + m[11]*Z + m[15];
        if (!(depth >= 1.0f) || !(depth < 1e9f)) return false;
        const float inv = 1.0f / depth;
        sx = PX + (m[0]*X + m[4]*Y + m[8]*Z + m[12]) * inv * PX;
        sy = PY - (m[1]*X + m[5]*Y + m[9]*Z + m[13]) * inv * PY;
        return std::isfinite(sx) && std::isfinite(sy);
    };
    命中距离2 = min(准心到头, 准心到胸);
    命中阈值 = min(PX, PY) * 0.18f;   // 约屏高 18%
    命中距离2 < 命中阈值平方  -> 锁定

## 六、防失效：armed 健康检查 + 自动重挂

现象：开启追踪之后过一会儿又没效果。
原因：游戏重载关卡，页表重建，UXN 被还原，驱动 armed 变 0。
      只检查自己的 installed 标记发现不了。

    if (基址变了 || !pst.installed || !pst.armed) {
        PTE追踪_卸载();
        PTE追踪_安装(地址.libue4);   // 自动重挂
    }

## 七、概率必须按发算，不是按帧

用户原话：调到 50% 那么 10 发里面就有 5 发能中，调到 9 那就 10 发 1 发左右。

错误做法：每帧 rolls 一次随机（全自动 60fps 会严重偏离预期）。
正确做法：只在开火沿或连发间隔判定新的一发，每发只掷一次骰子。

    static int 上次开火状态 = 0;
    static bool 当前这发要吸 = false;
    static long long 上次掷骰us = 0;
    clock_gettime(CLOCK_MONOTONIC, &ts);   // 真实时钟，不是 CPU 时钟
    新的一发 = 开火 != 0 且 (上次开火 == 0 或 间隔 > 55000us);
    if (新的一发) 当前这发要吸 = 概率 >= 100 或 rand()*100 < 概率;
    本帧写回 = 目标有效 且 开火 != 0 且 当前这发要吸;

55ms 对应约 1200rpm 射速上限，全自动每发刚好一次。

## 八、成功参数速查

    驱动:   RT_hook v1.0（含 615-619）
    内核:   6.6.118-android15-8
    通道:   socket(AF_INET, SOCK_DGRAM)
    命令:   615 挂 / 617 设模式 / 618 读状态 / 616 摘
    模式:   rot[2]=2 捕获   rot[2]=4 写回 V3/V4/V5
    追踪桩: 0xA0FB548（相对 libUE4.so 偏移）
    坐标源: 骨骼坐标[0/1/2] = 头/胸/臀（世界坐标）
    选靶:   准心命中（屏幕距离 < min(PX,PY)*0.18）
    概率:   按发，55ms 间隔判定新一发
    健康:   !installed 或 !armed 就重挂

## 九、实测日志样本

    [615 HOOK_ATTACH] ret=0
    [617 写回 V3/V4/V5] ret=0
    [618] active=1 armed=1 hits=N
    命中增长: 231 -> 622 -> 1078 -> 1647
    vaddr=0x6c38107000   （4K 页对齐，证明是 PTE 机制）
