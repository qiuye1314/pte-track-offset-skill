import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// pte-track-offset-skill v1.3.0
//
// 设计：装得完整，常驻极小。
//   - 常驻只注入 prompts/trigger.md（一根细线：能力+触发词+基线+怎么展开）
//   - 完整作业索引 prompts/pte-track-offset-skill.md 默认不进提示词，
//     需要时调 pte_track_doc(section="index") 取，零重启
//   - config.detail = true 时才把完整索引也常驻注入（要重启才生效）
const __dirname = dirname(fileURLToPath(import.meta.url));
const PLUGIN_VERSION = "1.5.4";

// DSH 的提示词插值引擎会把非内置变量的连续花括号当损坏引用抛出
// "malformed prompt variable reference"，这里做无害化转义（与 laoda-hermes-dsha 同一手法）。
const escapePromptVars = (s) => s.replace(/\{\{(?!(?:cwd|model|provider)\}\})/g, "{ {");

// 进系统提示词的文本：转义花括号 + 展开路径占位符
const readAsset = (rel) =>
  escapePromptVars(readFileSync(join(__dirname, rel), "utf8")).replaceAll("__PLUGIN_DIR__", __dirname);

// 工具按需返回的文档：只展开路径占位符，保持原文保真
// （转义是给插值引擎用的，文档进的是消息不是模板，不该改形）
const readDoc = (rel) =>
  readFileSync(join(__dirname, rel), "utf8").replaceAll("__PLUGIN_DIR__", __dirname);

const TRIGGER_TEXT = readAsset("prompts/trigger.md");
const FULL_INDEX_TEXT = readAsset("prompts/pte-track-offset-skill.md");

const BASELINE = JSON.parse(
  readFileSync(join(__dirname, "data/baseline_1.38.12.json"), "utf8")
);

const BASELINE_IGCE = JSON.parse(
  readFileSync(join(__dirname, "data/baseline_igce_4.7.3.json"), "utf8")
);

const BASELINE_INTL46 = JSON.parse(
  readFileSync(join(__dirname, "data/baseline_pubg46_intl.json"), "utf8")
);

const SECTIONS = {
  index: "prompts/pte-track-offset-skill.md",
  skill: "SKILL.md",
  plugin: "prompts/trigger.md",
  sop: "references/offset_grab_procedure.md",
  sdk: "references/sdk_usage.md",
  pitfalls: "references/pitfalls.md",
  rt_pitfalls: "references/rt_pte_pitfalls_full.md",
  rt_success: "references/rt_pte_615_success.md",
  retro: "references/session_retro_2026_10_26.md",
  driver: "references/driver_swap_guide.md",
  attrib: "references/source_attribution.md",
  detect: "scripts/detect_source_target.py",
  intl46: "references/pubg46_intl_port_lessons.md",
  intl46_json: "data/baseline_pubg46_intl.json",
  baseline: "data/PTE_BASELINE_1.38.12.md",
  baseline_json: "data/baseline_1.38.12.json",
  igce_baseline: "data/PTE_BASELINE_IGCE_4.7.3.md",
  igce_baseline_json: "data/baseline_igce_4.7.3.json",
  export: "scripts/export_baseline.py",
  diff: "scripts/diff_baseline.py",
  script: "scripts/pte_track_find.py",
  grabber: "scripts/ue4_track_tool.py",
  align: "scripts/sdk_offset_align.py",
  fixtable: "scripts/offset_fix_table.py",
  verify: "scripts/sdk_verify2.py",
  pipeline: "scripts/build_gateway.sh",
  readme: "README.md",
  changelog: "CHANGELOG.md",
};

const objectOutput = {
  schema: { type: "object", additionalProperties: true },
  render: (_a, v) => [{ type: "text", text: JSON.stringify(v).slice(0, 6000) }],
};

function makeDocTool() {
  return {
    name: "pte_track_doc",
    description:
      "按需读取 PTE 追踪偏移插件全文（不常驻提示词）。section: index(完整作业索引,首选) | skill(主方法论) | baseline(1.38.12基线报告) | baseline_json(机器可读基线) | igce_baseline(IGCE 4.7.3实战报告) | igce_baseline_json(IGCE机器可读基线) | export(基线导出器源码) | diff(新赛季对撞器源码) | rt_pitfalls【必读RT驱动15坑】 | rt_success(615成功定版) | driver【必读·驱动对接/换驱动:ABI对照+7步流程+fd坑】 | retro【必读·这次全错到打通的完整复盘+失败清单】 | attrib【必读·判定源码属于哪个游戏】 | detect(判定脚本) | intl46【4.6国际服移植踩坑·写回组s0s1s2】 | intl46_json(4.6机器可读基线) | sop | sdk | pitfalls | script | grabber | align | fixtable | verify | pipeline | readme | changelog | plugin。",
    parameters: {
      type: "object",
      properties: {
        section: {
          type: "string",
          description: "文档段名",
          enum: Object.keys(SECTIONS),
        },
      },
      required: ["section"],
      additionalProperties: false,
    },
    output: objectOutput,
    execute(args) {
      const key = (args || {}).section || "index";
      const f = SECTIONS[key];
      if (!f) return { ok: false, error: "unknown section: " + key, sections: Object.keys(SECTIONS) };
      try {
        return { ok: true, section: key, file: f, text: readDoc(f) };
      } catch (e) {
        return { ok: false, error: String(e.message), section: key, file: f };
      }
    },
  };
}

function makeStatusTool(cfg) {
  return {
    name: "pte_track_status",
    description:
      "返回 PTE 追踪偏移插件的版本、注入槽位与常驻字节数、已验证基线摘要。装了像没装/怀疑降智时先调这个核对第一现场。",
    parameters: { type: "object", properties: {}, additionalProperties: false },
    output: objectOutput,
    execute() {
      return {
        ok: true,
        plugin: "pte-track-offset-skill",
        pluginVersion: PLUGIN_VERSION,
        displayName: "PTE追踪偏移抓取",
        dir: __dirname,
        config: { enabled: cfg.enabled !== false, detail: cfg.detail === true },
        injection: [
          { section: "pte-track-offset-skill:trigger", order: 152, enabled: true, bytes: Buffer.byteLength(TRIGGER_TEXT, "utf8") },
          { section: "pte-track-offset-skill:full-index", order: 153, enabled: cfg.detail === true, bytes: cfg.detail === true ? Buffer.byteLength(FULL_INDEX_TEXT, "utf8") : 0 },
        ],
        residentBytes:
          Buffer.byteLength(TRIGGER_TEXT, "utf8") +
          (cfg.detail === true ? Buffer.byteLength(FULL_INDEX_TEXT, "utf8") : 0),
        onDemandBytes: Buffer.byteLength(FULL_INDEX_TEXT, "utf8"),
        baselines: [
          {
            label: BASELINE.label,
            kTrackShootFn: BASELINE.primary && BASELINE.primary.addr_hex,
            vtableIndexes: BASELINE.primary && BASELINE.primary.indexes,
            soMd5: BASELINE.target && BASELINE.target.md5,
            soSize: BASELINE.target && BASELINE.target.size,
          },
          {
            label: BASELINE_IGCE.label,
            kTrackShootFn: BASELINE_IGCE.primary && BASELINE_IGCE.primary.addr_hex,
            vtableIndexes: BASELINE_IGCE.primary && BASELINE_IGCE.primary.indexes,
            soMd5: BASELINE_IGCE.target && BASELINE_IGCE.target.md5,
            soSize: BASELINE_IGCE.target && BASELINE_IGCE.target.size,
            family: BASELINE_IGCE.family || "intl",
            writeGroup: (BASELINE_IGCE.write_group_names || ["s0","s1","s2"]).join("/"),
          },
          {
            label: BASELINE_INTL46.game + " " + BASELINE_INTL46.version + " 国际服",
            package: BASELINE_INTL46.package,
            kTrackShootFn: BASELINE_INTL46.track && BASELINE_INTL46.track.offset,
            writeGroup: (BASELINE_INTL46.track && BASELINE_INTL46.track.write_group_names || []).join("/"),
            soMd5: BASELINE_INTL46.so && BASELINE_INTL46.so.md5,
            soSize: BASELINE_INTL46.so && BASELINE_INTL46.so.size,
          },
        ],
        baseline: {
          label: BASELINE.label,
          kTrackShootFn: BASELINE.primary && BASELINE.primary.addr_hex,
          vtableIndexes: BASELINE.primary && BASELINE.primary.indexes,
          soMd5: BASELINE.target && BASELINE.target.md5,
          soSize: BASELINE.target && BASELINE.target.size,
          sdkAnchors: Object.keys(BASELINE.sdk_anchors || {}).length,
          exportedConstants: Object.keys(BASELINE.game_offsets || {}).length,
        },
        tools: ["pte_track_doc", "pte_track_status"],
        expandHint: '要全文就调 pte_track_doc(section="index")，不用重启；要把完整索引常驻就设 config.detail=true 后重启 Harness',
      };
    },
  };
}

export const name = "pte-track-offset-skill";
export const version = PLUGIN_VERSION;
export const inject = ["systemPrompt", "tools"];

export function apply(ctx, config = { enabled: true, detail: false }) {
  const cfg = config || {};
  ctx.effect(() => {
    ctx.systemPrompt.section({
      name: "pte-track-offset-skill:trigger",
      order: 152,
      text: TRIGGER_TEXT,
    });
  });
  if (cfg.detail === true) {
    ctx.effect(() => {
      ctx.systemPrompt.section({
        name: "pte-track-offset-skill:full-index",
        order: 153,
        text: FULL_INDEX_TEXT,
      });
    });
  }
  ctx.effect(() => { ctx.tools.register(makeDocTool()); });
  ctx.effect(() => { ctx.tools.register(makeStatusTool(cfg)); });
}
