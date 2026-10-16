import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_TEXT = readFileSync(join(__dirname, "prompts/pte-track-offset-skill.md"), "utf8")
  .replaceAll("__PLUGIN_DIR__", __dirname);

const docTool = {
  name: "pte_track_doc",
  description:
    "读取 PTE 追踪偏移抓取 skill 的全文文档。section: skill(主方法论) | sop(抓取作业程序) | sdk(SDK用法与边界) | pitfalls(踩坑记录) | script(抓取脚本源码) | plugin(本插件安装说明) | rt_pitfalls(【必读】RT驱动实战15坑) | rt_success(RT 615成功定版)。",
  parameters: {
    type: "object",
    properties: {
      section: {
        type: "string",
        description: "文档段名",
        enum: ["skill", "sop", "sdk", "pitfalls", "script", "plugin", "rt_pitfalls", "rt_success"],
      },
    },
    required: ["section"],
    additionalProperties: false,
  },
  output: {
    schema: { type: "object", additionalProperties: true },
    render: (_a, v) => [{ type: "text", text: JSON.stringify(v).slice(0, 6000) }],
  },
  execute(args) {
    const map = {
      skill: "SKILL.md",
      plugin: "prompts/pte-track-offset-skill.md",
      sop: "references/offset_grab_procedure.md",
      sdk: "references/sdk_usage.md",
      pitfalls: "references/pitfalls.md",
      script: "scripts/pte_track_find.py",
      rt_pitfalls: "references/rt_pte_pitfalls_full.md",   // 【新增】RT 实战 15 坑
      rt_success: "references/rt_pte_615_success.md",       // 【新增】615 成功定版
    };
    const f = map[(args || {}).section || "skill"];
    try {
      return { ok: true, text: readFileSync(join(__dirname, f), "utf8") };
    } catch (e) {
      return { ok: false, error: String(e.message) };
    }
  },
};

export const name = "pte-track-offset-skill";
export const inject = ["systemPrompt", "tools"];

export function apply(ctx, config = { enabled: true }) {
  ctx.effect(() => {
    ctx.systemPrompt.section({ name: "pte-track-offset-skill:doc-index", order: 152, text: SKILL_TEXT });
  });
  ctx.effect(() => { ctx.tools.register(docTool); });
}
