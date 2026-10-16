# 追踪偏移抓取作业程序（SOP）

## 0. 前置检查

```bash
# 确认工具链
python3 --version                                    # 需要 3.8+
ls /opt/ndk/android-ndk-aide/toolchains/llvm/prebuilt/linux-arm/bin/clang++
which adb-shell                                      # 拉 so 用
```

## 1. 拿到 libUE4.so

容器 PID 命名空间与手机隔离，**容器里看不到手机进程**，必须走设备 shell：

```bash
# 找游戏安装路径（设备 shell）
adb-shell ls -d /data/app/*/com.tencent.tmgp.pubgmhd-*/lib/arm64/

# 拷贝到 sdcard（设备 shell）
adb-shell cp <上面路径>/libUE4.so /sdcard/pte_work/libUE4.so
```

拉完检查：
```bash
ls -la /sdcard/pte_work/libUE4.so    # 约 380MB 是对的
readelf -h /sdcard/pte_work/libUE4.so | grep -E 'Class|Machine'
# 期望: ELF64 / AArch64
```

## 2. 特征码扫描

```bash
python3 ue4_track_tool.py libUE4.so
```

**期望输出**：
```
[1] 特征码扫描  a240201e8140201e6040201ec0035fd6
     0x0A0FB548  [.text]
     0x0BE33F44  [.text]
```

判定：
- 命中 1~2 处 → 正常
- 命中 0 处 → 大版本更新，桩被改写，走 §5 兜底
- 命中 3+ 处 → 特征码太宽，需要加长

## 3. 虚表反查确认

同一脚本自动做：
```
[2] 虚表反查（R_AARCH64_RELATIVE, addend = 桩地址）
     桩 0x0A0FB548 -> 3 处引用
        槽 0x140F1938  虚表 0x140EFEE0  槽index=843
        槽 0x1422E460  虚表 0x1422CA08  槽index=843
        槽 0x14436A20  虚表 0x14434FC8  槽index=843
```

判定：
- 多虚表**同槽 index** → 同一基类多子类，正常
- 槽 index 差异大 → 可能是不同功能的同类桩，人工确认

## 4. SDK 交叉校验

```bash
python3 ue4_track_tool.py libUE4.so --sdk "sdk138/和平SDK"
```

```
[3] SDK 交叉校验
     与已知锚点一致: 5/5  ['Engine','Names','ObjObjects','UObjectArray','World']
     => 同一 build，SDK 其余偏移可直接采用
```

判定：
- >= 3/5 → SDK 可用，字段偏移可直接抄
- < 3/5 → build 不同，需重新 dump SDK

## 5. 特征码失效兜底（虚表反查法）

如果特征码 0 命中：

1. 反汇编已知桩附近，看新形状（可能是 `fmov s0,s3/s1,s4/s2,s5` 顺序变了，或加了 `paciasp`）
2. 或直接扫虚表：在 `.data.rel.ro` 找**第 843 槽附近**指向小函数（4~8 指令 + ret）的虚表
3. 用 `readelf -r` 导出全部重定位，找 addend 落在 `.text` 且目标函数极短的项

## 6. 回填与编译

```bash
python3 ue4_track_tool.py libUE4.so --sdk "sdk138/和平SDK" \
    --patch "ex/.../jni/include/game/Offsets.h"
```

或一键流水线：
```bash
sh build_gateway.sh              # 全流程
sh build_gateway.sh --skip-pull  # 跳过拉 so
sh build_gateway.sh --skip-build # 只抓偏移
```

## 7. 验收清单

```
[ ] 特征码命中 1~2 处
[ ] 虚表槽 index 一致（多虚表时）
[ ] SDK 锚点一致 >= 3/5
[ ] Offsets.h 的 kTrackShootFn 已更新
[ ] 编译 ok=51 bad=0
[ ] file 输出 aarch64 PIE executable
[ ] 产物大小约 3.3~3.5MB
```
