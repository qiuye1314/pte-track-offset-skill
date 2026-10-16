# 变更记录

## 1.1.0

**新增：机器可读基线 + 跨版本自动对撞。**
v1.0.0 只能「抓一次算一次」，新赛季全靠人肉比对；现在两条命令出差异表。

### 新增文件
- scripts/export_baseline.py —— 抓桩 + 虚表反查 + SDK 锚点 + 工程常量，一次性导出 JSON（schema pte-baseline/1）。默认只读。
- scripts/diff_baseline.py —— 两份基线对撞，输出：so 指纹变化、kTrackShootFn 新旧值、虚表 index 是否重排、锚点一致数、逐字段偏移差异（带字节增减）、行动清单。支持 --json 机器可读输出。
- data/baseline_1.38.12.json —— 1.38.12 实测基线：主桩 0xA0FB548、index 843×3、锚点 5/5、77 项常量全量。
- README.md / plugin.json —— 插件级说明与清单。

### 修复
- diff_baseline.py 初版把第 3 节锚点用的 keys 与第 4 节字段偏移用的 keys 复用同名，
  导致「同一份基线自我对撞」误报 *SDK 锚点有变动*。
  已改为 akeys / atotal 独立变量，并补三组回归自测：
  1) 自撞 → 只剩「什么都不用改」
  2) 伪造新赛季（桩挪位 + 2 个偏移变 + 1 个锚点动）→ 正确报「必改 kTrackShootFn」「锚点 4/5」
  3) --json 输出可被 json.loads 解析

### 实测基线（PUBGM 1.38.12）
- 特征码 a240201e8140201e6040201ec0035fd6 在 3.3 亿字节 .text 命中 **2 处**。
- 主桩 0xA0FB548 被 3 个虚表引用，**index 全部 = 843**；直接调用数 0（纯虚表派发）。
- 备选桩 0xBE33F44，index 191，1 处引用。
- SDK 锚点 5/5 一致 → 同一 build，SDK 字段偏移可直接采用。
- 全量字段校准：OK=20 / MOVE=6 / 存疑=2 / 丢失=0（28 项语义比对）。
- 如实记录 8 项工程历史语义错位，**不做自动修改**。

### 边界声明
- 不含驱动交互代码（615/617、HOOK_STATUS ABI 属驱动侧）。
- 不含已编译产物 fanpian_1.38.12（构建产物，非偏移资产）。
- 除显式 --patch 外全程只读，不写任何工程文件。

## 1.0.0

- 四步抓取法（特征码 → 虚表反查 → 虚表边界重建 → SDK 交叉校验）。
- ue4_track_tool.py / pte_track_find.py 抓取器，可选 --patch 回填。
- sdk_offset_align.py / offset_fix_table.py / sdk_verify2.py 校准三件套。
- build_gateway.sh 一键流水线。
- references/ 5 份拆解文档，含 RT 驱动 15 个坑全表。
