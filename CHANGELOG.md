# 变更记录

## 1.2.0

**装得完整，常驻极小。** 插件形态补齐（注册进 profile + skill.json + node_modules link），
但默认只向系统提示词注入一根细线（1499 字节），158 行完整作业索引改为按需读取，不用重启。

### 注入形态重设计
- 新增 `prompts/trigger.md`：常驻段，含能力/触发词/已验证基线/怎么展开/一句话口诀 —— **1499 字节**。
- `index.js` 重写为三段式：
  - order 152 `pte-track-offset-skill:trigger` —— 永远注入
  - order 153 `pte-track-offset-skill:full-index` —— **仅 `config.detail=true` 时注入**（7778 字节）
  - `pte_track_doc` / `pte_track_status` 两个工具始终注册
- `pte_track_doc` 从 8 个 section 扩到 **20 个**，新增 `index`（完整作业索引）/ `baseline` /
  `baseline_json` / `export` / `diff` / `grabber` / `align` / `fixtable` / `verify` / `pipeline` / `readme` / `changelog`。
- 新增 `pte_track_status` 工具：回报版本、注入槽位、**常驻字节数**、基线摘要。
  装了像没装 / 怀疑降智时先调它核对第一现场（对齐 laoda_profile 的约定）。

### 完整插件形态
- 注册进 `/root/.dsh/profiles/web/package.json`：dependencies 加 link，bundles 追加
  `pte-track-offset-skill`（现为第 15 个 bundle）。
- 建 `node_modules/pte-track-offset-skill` 软链（其余 14 个 bundle 都有，缺它会在加载时成为变数）。
- 新增 `skill.json`（id / name / version / trigger / persona_file / badge），照 laoda 约定。
- `package.json` 的 files 数组补 `skill.json` / `README.md` / `CHANGELOG.md` / `data`。

### 新增内容资产
- `data/baseline_1.38.12.json`：1.38.12 机器可读基线（主桩 0xA0FB548、index 843×3、锚点 5/5、77 项常量）。
- `data/PTE_BASELINE_1.38.12.md`：人读基线报告。
- `scripts/export_baseline.py` / `scripts/diff_baseline.py`：基线导出 + 跨赛季对撞。
- `scripts/ue4_track_tool.py` / `sdk_offset_align.py` / `offset_fix_table.py` / `sdk_verify2.py` /
  `build_gateway.sh` 一并入插件（此前只有 pte_track_find.py）。
- `SKILL.md` 加第九节（基线数据 + 对撞用法 + 判读规则表 + 铁律），240 → 288 行。

### 修复
- **diff_baseline.py 变量遮蔽**：第 3 节锚点与第 4 节字段偏移复用同名 `keys`，
  导致"同一份基线自我对撞"误报 *SDK 锚点有变动*。改为 `akeys` / `atotal`，
  并补三组回归自测（自撞 / 伪造新赛季 / `--json` 可解析），全绿。
- **版本自相矛盾**：插件 `package.json=1.1.0` 而 `SKILL.md frontmatter=1.0.0` → 统一到 1.2.0
  （package.json / dsh.version / SKILL.md 三处一致）。
- **两处 pitfalls.md 长期不同步**（插件 3498 字节 vs skill 6319 字节）→ 拉齐。
- `index.js` 补 `escapePromptVars`：DSH 插值引擎会把非内置 `{{` 当损坏引用抛出
  "malformed prompt variable reference"，照 laoda 同一手法做无害化转义。
  实测：全插件仅本文件描述该转义处含 `{{`，两个被注入文件各 0 处，注入字节流裸 `{{` = 0（属预防）。
- **转义只作用于进提示词的文本**：`readAsset`（注入用）转义 + 展开 `__PLUGIN_DIR__`；
  `readDoc`（`pte_track_doc` 取文档用）只展开路径、保持原文保真 —— 否则文档里的 `{{` 会被改成 `{ {` 而失真。

### 实测基线（PUBGM 1.38.12）
- 特征码 `a240201e8140201e6040201ec0035fd6` 在 3.3 亿字节 .text 命中 **2 处**。
- 主桩 `0xA0FB548`：3 个虚表引用，**index 全部 = 843**；直接调用数 0（纯虚表派发）。
- 备选桩 `0xBE33F44`（index 191，1 处引用）。SDK 锚点 5/5 一致。
- 字段校准：OK 20 / MOVE 6 / 存疑 2 / 丢失 0（28 项语义比对）。
- 8 项工程历史语义错位**照实记录，不自动修改**。

### 验证方式
- `node --check index.js` 通过；**假 ctx 实跑 `apply()`** 通过（注入段/字节数/两个工具/
  未知 section 报错分支/detail=true 分支全部覆盖）；经 node_modules 软链路径加载通过。
- 提示词引用 15 条 + docTool 映射 20 条路径存在性校验：**MISS = 0**。

### 边界声明
- 不含驱动交互代码（615/617、`HOOK_STATUS` ABI 属驱动侧）。
- 不含已编译产物 `fanpian_1.38.12`（构建产物，非偏移资产）。
- `export` / `diff` 及不带 `--patch` 的抓取全程**只读**，不写任何工程文件。

## 1.1.0

**新增：机器可读基线 + 跨版本自动对撞。**
v1.0.0 只能「抓一次算一次」，新赛季全靠人肉比对；现在两条命令出差异表。

### 新增文件
- scripts/export_baseline.py —— 抓桩 + 虚表反查 + SDK 锚点 + 工程常量，一次性导出 JSON（schema pte-baseline/1）。默认只读。
- scripts/diff_baseline.py —— 两份基线对撞，输出：so 指纹变化、kTrackShootFn 新旧值、虚表 index 是否重排、锚点一致数、逐字段偏移差异（带字节增减）、行动清单。支持 --json 机器可读输出。
- data/baseline_1.38.12.json —— 1.38.12 实测基线。
- README.md / plugin.json —— 插件级说明与清单。

### 实测基线（PUBGM 1.38.12）
- 特征码 a240201e8140201e6040201ec0035fd6 在 3.3 亿字节 .text 命中 **2 处**。
- 主桩 0xA0FB548 被 3 个虚表引用，**index 全部 = 843**；直接调用数 0。
- SDK 锚点 5/5 一致 → 同一 build。

### 修复
- diff_baseline.py 初版 keys 变量复用，导致自撞误报「SDK 锚点有变动」。改为 akeys/atotal。

### 边界声明
- 不含驱动交互代码；不含已编译产物；除显式 --patch 外全程只读。

## 1.0.0

- 四步抓取法（特征码 → 虚表反查 → 虚表边界重建 → SDK 交叉校验）。
- ue4_track_tool.py / pte_track_find.py 抓取器，可选 --patch 回填。
- sdk_offset_align.py / offset_fix_table.py / sdk_verify2.py 校准三件套。
- build_gateway.sh 一键流水线。
- references/ 5 份拆解文档，含 RT 驱动 15 个坑全表。
