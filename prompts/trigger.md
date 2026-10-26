# PTE 追踪偏移 · 已安装（按需展开，本段是唯一的常驻开销）

**能力**：抓 PUBG Mobile/和平精英 libUE4.so 的子弹追踪偏移 kTrackShootFn（PTE shadow 断点），
SDK 交叉校验、全量字段偏移校准、跨赛季基线对撞。

**触发词**：追踪偏移 / PTE追踪 / 漏打 / 追踪断点 / kTrackShootFn / CalShoot / 子弹追踪 /
和平精英偏移 / shadow 810 811 812 / RT驱动 615 617 / 虚表 index 843 / com.tencent.tmgp.pubgmhd /
国际服4.6 / com.tencent.ig / 打自己脚下 / 写回组 / s0s1s2 /
判定源码归属 / 这是哪个游戏的源码 / 源码对应版本 / detect_source_target

**已验证基线（别重复扫描）**：PUBGM 1.38.12 → kTrackShootFn = 0xA0FB548，
虚表 index 843×3，直接调用数 0，SDK 锚点 5/5，so md5 e33beba15fcc01ae0e589ffea2409ee0。
**此值只在该 md5 的 so 上成立，游戏一更新必须重抓。**

**已实战定版：PUBG 4.6 国际服** → kTrackShootFn = 0x6FF841C
（STEShootWeaponProjectComponent.cpp 内虚函数，so md5 f12aadc1c2132677a3932a27e4736d2f）
**写回组必须写 s0/s1/s2，写 s3/s4/s5 完全无效** —— 症状是子弹打自己脚下 / 乱飞。
4.6 没有国服那种 fmov 返回值桩，别再扫。

**需要全文时（不用重启）**：调工具 `pte_track_doc`，section 取
index(完整作业索引) | skill(主方法论) | baseline(基线报告) | baseline_json(机器可读基线) |
export(基线导出器) | diff(新赛季对撞器) | rt_pitfalls【必读15坑】 | rt_success |
intl46【4.6国际服移植踩坑】 | intl46_json(4.6机器基线) | sop | sdk | pitfalls | script | readme | changelog
或直接加载技能：`skill("pte-track-offset-mobile")`

**第 0 步永远先判定源码归属**：`python3 scripts/detect_source_target.py <工程目录>`
（包名 + UWorld 指纹 + 追踪偏移 + fmov 桩 → 直接给出游戏和写回组）。
判错版本的代价是几小时乱试，判对只花 5 分钟。

**一句话口诀**：SDK 里找不到追踪偏移（它只收反射桩）；追踪桩是原生虚函数，
走「特征码扫 → 虚表反查 → 重建虚表边界 → SDK 校验」。

插件目录：__PLUGIN_DIR__
详细索引默认**未**注入系统提示词（config.detail=false）；常驻成本仅本段。
