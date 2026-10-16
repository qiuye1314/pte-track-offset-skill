# PTE 追踪偏移 · 已安装（按需展开，本段是唯一的常驻开销）

**能力**：抓 PUBG Mobile/和平精英 libUE4.so 的子弹追踪偏移 kTrackShootFn（PTE shadow 断点），
SDK 交叉校验、全量字段偏移校准、跨赛季基线对撞。

**触发词**：追踪偏移 / PTE追踪 / 漏打 / 追踪断点 / kTrackShootFn / CalShoot / 子弹追踪 /
和平精英偏移 / shadow 810 811 812 / RT驱动 615 617 / 虚表 index 843 / com.tencent.tmgp.pubgmhd

**已验证基线（别重复扫描）**：PUBGM 1.38.12 → kTrackShootFn = 0xA0FB548，
虚表 index 843×3，直接调用数 0，SDK 锚点 5/5，so md5 e33beba15fcc01ae0e589ffea2409ee0。
**此值只在该 md5 的 so 上成立，游戏一更新必须重抓。**

**需要全文时（不用重启）**：调工具 `pte_track_doc`，section 取
index(完整作业索引) | skill(主方法论) | baseline(基线报告) | baseline_json(机器可读基线) |
export(基线导出器) | diff(新赛季对撞器) | rt_pitfalls【必读15坑】 | rt_success | sop | sdk | pitfalls | script | readme | changelog
或直接加载技能：`skill("pte-track-offset-mobile")`

**一句话口诀**：SDK 里找不到追踪偏移（它只收反射桩）；追踪桩是原生虚函数，
走「特征码扫 → 虚表反查 → 重建虚表边界 → SDK 校验」。

插件目录：__PLUGIN_DIR__
详细索引默认**未**注入系统提示词（config.detail=false）；常驻成本仅本段。
