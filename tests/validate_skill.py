#!/usr/bin/env python3
"""Validate the skill against the Agent Skills spec and this repo's own invariants.

Run from the repository root:
    python3 -I tests/validate_skill.py

Spec rules (https://agentskills.io/specification):
  - name: 1-64 chars, [a-z0-9-], no leading/trailing/double hyphen, equals the directory name
  - description: 1-1024 chars; compatibility: <=500 chars; metadata: string -> string
  - SKILL.md body under 500 lines; file references are relative and one level deep
Repo invariants:
  - every references/ and scripts/ file is mentioned in SKILL.md, and every mention exists
  - every "fix-patterns §N" cited anywhere has a matching "## §N" heading
  - versions agree: SKILL.md metadata, audit.py __version__, plugin.json, marketplace.json, package.json,
    CITATION.cff, CHANGELOG.md
  - no machine-specific paths or agent-product-specific tool names leak into the skill
Standard library only. Exits 1 with a list of problems.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "adaptive-dark-mode")
problems = []


def fail(msg):
    problems.append(msg)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fail("SKILL.md: missing YAML frontmatter")
        return {}, text
    data, current = {}, None
    for line in m.group(1).split("\n"):
        if not line.strip():
            continue
        if line.startswith((" ", "\t")):
            if current is None:
                fail(f"SKILL.md frontmatter: unexpected indented line {line!r}")
                continue
            k, _, v = line.strip().partition(":")
            data[current][k.strip()] = v.strip().strip('"').strip("'")
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v == "":
            data[k], current = {}, k
        else:
            data[k], current = v.strip('"').strip("'"), None
    return data, text[m.end():]


def main():
    skill_md = os.path.join(SKILL_DIR, "SKILL.md")
    text = read(skill_md)
    fm, body = parse_frontmatter(text)

    # --- spec: name
    name = fm.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        fail(f"name {name!r} violates the spec (1-64 chars, a-z0-9 and single hyphens)")
    if name != os.path.basename(SKILL_DIR):
        fail(f"name {name!r} must equal its directory name {os.path.basename(SKILL_DIR)!r}")
    # --- spec: description, compatibility, metadata
    desc = fm.get("description", "")
    if not 1 <= len(desc) <= 1024:
        fail(f"description is {len(desc)} chars (spec: 1-1024)")
    if "compatibility" in fm and not 1 <= len(fm["compatibility"]) <= 500:
        fail(f"compatibility is {len(fm['compatibility'])} chars (spec: 1-500)")
    if not isinstance(fm.get("metadata", {}), dict):
        fail("metadata must be a mapping of string keys to string values")
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    for k in fm:
        if k not in allowed:
            fail(f"unknown frontmatter field {k!r} (spec allows {sorted(allowed)})")
    # --- spec: size
    n_lines = body.count("\n")
    if n_lines >= 500:
        fail(f"SKILL.md body is {n_lines} lines (spec recommends < 500)")

    # --- references: mentioned <-> exists
    mentioned = set(re.findall(r"(?<![\w/.-])((?:references|scripts)/[\w./-]+\.(?:md|py|js|mjs))", text))
    for rel in sorted(mentioned):
        if not os.path.isfile(os.path.join(SKILL_DIR, rel)):
            fail(f"SKILL.md mentions {rel}, which does not exist")
    for sub in ("references", "scripts"):
        for fn in sorted(os.listdir(os.path.join(SKILL_DIR, sub))):
            if fn.startswith(".") or fn == "__pycache__":
                continue
            if f"{sub}/{fn}" not in mentioned:
                fail(f"{sub}/{fn} is never mentioned in SKILL.md, so agents won't know it exists")

    # --- fix-patterns section citations
    fp = read(os.path.join(SKILL_DIR, "references", "fix-patterns.md"))
    headings = set(re.findall(r"^## (§\d+)\b", fp, re.M))
    for path in [skill_md] + [os.path.join(SKILL_DIR, "references", f) for f in os.listdir(os.path.join(SKILL_DIR, "references"))] \
            + [os.path.join(SKILL_DIR, "scripts", "audit.py")]:
        for sec in re.findall(r"§(\d+)", read(path)):
            if f"§{sec}" not in headings:
                fail(f"{os.path.relpath(path, ROOT)} cites §{sec}, but fix-patterns.md has no '## §{sec}' heading")

    # --- version agreement
    versions = {"SKILL.md metadata.version": fm.get("metadata", {}).get("version")}
    m = re.search(r'^__version__ = "([^"]+)"', read(os.path.join(SKILL_DIR, "scripts", "audit.py")), re.M)
    versions["audit.py __version__"] = m.group(1) if m else None
    plugin = os.path.join(ROOT, ".claude-plugin", "plugin.json")
    market = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    if os.path.exists(plugin):
        versions["plugin.json version"] = json.loads(read(plugin)).get("version")
    if os.path.exists(market):
        entries = [p for p in json.loads(read(market)).get("plugins", []) if p.get("name") == name]
        if not entries:
            fail(f"marketplace.json has no plugin entry named {name!r}")
        elif "version" in entries[0]:
            versions["marketplace.json plugin version"] = entries[0]["version"]
    pkg = os.path.join(ROOT, "package.json")
    if os.path.exists(pkg):
        versions["package.json version"] = json.loads(read(pkg)).get("version")
    cff = os.path.join(ROOT, "CITATION.cff")
    if os.path.exists(cff):
        m = re.search(r"^version:\s*([\d.]+)", read(cff), re.M)
        versions["CITATION.cff version"] = m.group(1) if m else None
    changelog = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.exists(changelog):
        m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", read(changelog), re.M)
        versions["CHANGELOG.md latest release"] = m.group(1) if m else None
    if len(set(versions.values())) != 1:
        fail("version mismatch: " + ", ".join(f"{k}={v}" for k, v in versions.items()))

    # --- leaks: machine paths and product-specific tool names don't belong in a portable skill
    leak = re.compile(r"/Users/|/home/[a-z]|C:\\\\Users|mcp__|resize_window|javascript_tool|scratch-workspaces")
    for dirpath, _, files in os.walk(SKILL_DIR):
        for fn in files:
            if fn.endswith((".md", ".py", ".js", ".mjs")):
                p = os.path.join(dirpath, fn)
                for i, line in enumerate(read(p).split("\n"), 1):
                    if leak.search(line):
                        fail(f"{os.path.relpath(p, ROOT)}:{i} leaks a local path or tool name: {line.strip()[:80]}")

    if problems:
        print("Skill validation FAILED:")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"Skill validation passed: {name} v{versions['SKILL.md metadata.version']}, "
          f"description {len(desc)}/1024 chars, SKILL.md body {n_lines} lines, {len(mentioned)} file references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
