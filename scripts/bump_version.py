#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bump_version.py - sync every version field in this plugin with one command

Why:
    The version number lives in 7 places. Manual edits always miss some.
    This plugin already shipped 3 inconsistent versions
    (dsh.version / SKILL.md metadata.version were forgotten twice).
    From now on: never hand-edit a version, always run this script.

Usage:
    python3 scripts/bump_version.py 1.6.0
    python3 scripts/bump_version.py 1.6.0 --title "new feature" --note "details"
    python3 scripts/bump_version.py --check

Covers 7 places:
    package.json -> version
    package.json -> dsh.version                    (most often forgotten)
    plugin.json  -> version
    skill.json   -> version
    skill.json   -> badge
    index.js     -> const PLUGIN_VERSION
    SKILL.md     -> frontmatter metadata.version   (most often forgotten)
Plus: CHANGELOG.md gets a new section inserted.
"""
import argparse
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = [
    ("package.json", "version"),
    ("package.json", "dsh.version"),
    ("plugin.json", "version"),
    ("skill.json", "version"),
    ("index.js", "PLUGIN_VERSION"),
    ("SKILL.md", "metadata.version"),
]


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(os.path.join(ROOT, p), "w", encoding="utf-8") as f:
        f.write(s)


def get_json_version(fn, dotted):
    d = json.loads(read(fn))
    cur = d
    for k in dotted.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def set_json_version(fn, dotted, ver):
    path = os.path.join(ROOT, fn)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    cur = d
    keys = dotted.split(".")
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = ver
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def get_index_version():
    m = re.search(r"PLUGIN_VERSION\s*=\s*.([0-9][^\x22\x27]*)", read("index.js"))
    return m.group(1).strip().strip("\x22\x27") if m else None


def set_index_version(ver):
    s = read("index.js")
    s2 = re.sub(r"(PLUGIN_VERSION\s*=\s*)([\x22\x27])([0-9][^\x22\x27]*)([\x22\x27])",
                lambda m: m.group(1) + m.group(2) + ver + m.group(4), s, count=1)
    if s2 == s:
        raise SystemExit("index.js: PLUGIN_VERSION not found")
    write("index.js", s2)


def get_skill_md_version():
    s = read("SKILL.md")
    m = re.search(r"^\s*version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", s, re.M)
    return m.group(1) if m else None


def set_skill_md_version(ver):
    s = read("SKILL.md")
    s2 = re.sub(r"^(\s*version:\s*)([0-9]+\.[0-9]+\.[0-9]+)\s*$",
                lambda m: m.group(1) + ver, s, count=1, flags=re.M)
    if s2 == s:
        raise SystemExit("SKILL.md: metadata.version not found")
    write("SKILL.md", s2)


def get_badge():
    return json.loads(read("skill.json")).get("badge")


def set_badge(ver):
    path = os.path.join(ROOT, "skill.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d["badge"] = "PTE追踪偏移 v" + ver
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def insert_changelog(ver, title, note):
    s = read("CHANGELOG.md")
    if ("## v" + ver) in s:
        print("CHANGELOG: v" + ver + " already present, skip")
        return
    block = "## v" + ver + " - " + date.today().isoformat()
    if title:
        block += " " + title
    block += chr(10) + chr(10)
    if note:
        block += note.strip() + chr(10) + chr(10)
    write("CHANGELOG.md", block + s)
    print("CHANGELOG: inserted v" + ver)


def refresh_manifest():
    """同步 plugin.json 里的 injection 字节数与 section 计数

    这几项是历史高频漂移点: prompt 一改长度就变, 手工维护必错。
    bump_version 时顺手刷一遍。
    """
    import re as _re
    src = read("index.js")
    m = _re.search(r"const SECTIONS = \{(.*?)\n\};", src, _re.S)
    if not m:
        print("WARN: SECTIONS not found, skip manifest refresh")
        return
    nsec = len(_re.findall(r"^\s+\w+:\s*\"[^\"]+\",$", m.group(1), _re.M))
    rb = len(read("prompts/trigger.md").encode("utf-8"))
    ob = len(read("prompts/pte-track-offset-skill.md").encode("utf-8"))
    path = os.path.join(ROOT, "plugin.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    inj = d.setdefault("injection", {})
    inj.setdefault("resident", {})["bytes"] = rb
    inj.setdefault("optional", {})["bytes"] = ob
    inj["tools"] = [
        "pte_track_doc (%d sections, 按需取全文)" % nsec,
        "pte_track_status (版本/注入)",
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("manifest refreshed: resident=%d optional=%d sections=%d" % (rb, ob, nsec))


def collect():
    vals = {}
    for fn, dotted in CHECKS:
        if fn == "index.js":
            v = get_index_version()
        elif fn == "SKILL.md":
            v = get_skill_md_version()
        else:
            v = get_json_version(fn, dotted)
        vals[fn + " -> " + dotted] = v
    return vals


def report():
    vals = collect()
    print("%-36s %s" % ("location", "value"))
    print("-" * 60)
    for k, v in vals.items():
        print("%-36s %s" % (k, v))
    print("%-36s %s" % ("skill.json -> badge", get_badge()))
    print()
    uniq = set(v for v in vals.values() if v)
    if len(uniq) == 1:
        print("OK all versions match: " + uniq.pop())
        return 0
    print("FAIL version mismatch: " + str(sorted(uniq)))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", nargs="?", help="new version, e.g. 1.6.0")
    ap.add_argument("--title", default="", help="CHANGELOG section title")
    ap.add_argument("--note", default="", help="CHANGELOG section body")
    ap.add_argument("--check", action="store_true", help="check only")
    a = ap.parse_args()
    if a.check or not a.version:
        sys.exit(report())
    ver = a.version.lstrip("v")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", ver):
        raise SystemExit("bad version: " + a.version)
    set_json_version("package.json", "version", ver)
    set_json_version("package.json", "dsh.version", ver)
    set_json_version("plugin.json", "version", ver)
    set_json_version("skill.json", "version", ver)
    set_index_version(ver)
    set_skill_md_version(ver)
    set_badge(ver)
    insert_changelog(ver, a.title, a.note)
    refresh_manifest()
    print()
    print("synced to " + ver + ":")
    for fn, dotted in CHECKS:
        print("  + " + fn + " -> " + dotted)
    print("  + skill.json -> badge")
    print()
    sys.exit(report())


if __name__ == "__main__":
    main()
