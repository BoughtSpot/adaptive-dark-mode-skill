#!/usr/bin/env python3
"""Static audit of a web project's theming for Safari Adaptive Dark Mode readiness.

Usage:
    python3 -I audit.py <project-root> [--json] [--fail-on high|medium|low]
                        [--exclude DIR ...] [--max-examples N] [--no-images]

Prints a Markdown report (or JSON with --json). Every finding is a regex
heuristic: open the file and confirm before acting on it.
Standard library only (Python 3.9+); Pillow is used for raster-image checks if installed.

Exit codes: 0 = report produced (and nothing at/above --fail-on), 1 = findings at or
above --fail-on severity, 2 = usage error.

Part of the adaptive-dark-mode Agent Skill:
https://github.com/BoughtSpot/adaptive-dark-mode-skill
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
from collections import Counter, defaultdict

__version__ = "1.0.0"

SKIP_DIRS = {
    "node_modules", ".git", ".hg", ".svn", "dist", "build", ".next", ".nuxt", ".output",
    ".svelte-kit", ".astro", ".vercel", ".netlify", ".turbo", ".cache", ".parcel-cache",
    "coverage", "vendor", "tmp", "log", "logs", "storage", "out", "__pycache__", ".venv",
    "venv", "bower_components", ".idea", ".vscode", "target", "Pods", ".expo",
    "test-results", "playwright-report", ".angular", ".docusaurus",
}
SKIP_SUBPATHS = ("public/assets", "public/packs", "public/build", "static/build", "wp-includes", "wp-admin")

STYLE_EXT = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".postcss"}
SCRIPT_EXT = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx"}
MARKUP_EXT = {
    ".html", ".htm", ".erb", ".haml", ".slim", ".liquid", ".php", ".hbs", ".handlebars",
    ".njk", ".twig", ".jinja", ".j2", ".ejs", ".pug", ".mdx", ".cshtml", ".razor", ".heex", ".eex",
}
SFC_EXT = {".vue", ".svelte", ".astro"}  # markup + style + script
RASTER_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp"}
MAX_FILE_BYTES = 1_500_000

SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def kinds_for(path: str) -> set[str]:
    p = path.lower()
    ext = os.path.splitext(p)[1]
    if p.endswith((".min.css", ".min.js")) or ".bundle." in p or p.endswith(".map"):
        return set()
    if ext in STYLE_EXT:
        return {"style"}
    if ext in SFC_EXT:
        return {"style", "script", "markup"}
    if ext in {".jsx", ".tsx"}:
        return {"script", "markup"}
    if ext in SCRIPT_EXT:
        return {"script"}
    if ext in MARKUP_EXT:
        return {"markup", "style", "script"}  # <style>/<script> blocks, style="" attributes, pre-paint theme scripts
    if ext == ".svg":
        return {"svg"}
    return set()


class Text:
    """File text with fast offset -> line lookups."""

    def __init__(self, path: str, rel: str, text: str):
        self.path, self.rel, self.text = path, rel, text
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self.starts, pos)

    def snippet(self, pos: int, width: int = 140) -> str:
        ln = self.line(pos)
        start = self.starts[ln - 1]
        end = self.starts[ln] - 1 if ln < len(self.starts) else len(self.text)
        s = self.text[start:end].strip()
        return s if len(s) <= width else s[: width - 1] + "…"


class Report:
    def __init__(self, max_examples: int):
        self.max_examples = max_examples
        self.findings: dict[str, dict] = {}
        self.facts: dict = defaultdict(list)
        self.counters: Counter = Counter()
        self.per_file: dict[str, Counter] = defaultdict(Counter)

    def add(self, fid, severity, title, why, fix, t: Text | None = None, pos=None, note=None):
        f = self.findings.setdefault(fid, {
            "id": fid, "severity": severity, "title": title, "why": why, "fix": fix,
            "count": 0, "examples": [],
        })
        f["count"] += 1
        if len(f["examples"]) < self.max_examples:
            if t is not None and pos is not None:
                ex = f"{t.rel}:{t.line(pos)}  `{t.snippet(pos)}`"
            elif t is not None:
                ex = t.rel
            else:
                ex = note or ""
            if note and t is not None:
                ex += f"  ({note})"
            f["examples"].append(ex)


# ---------------------------------------------------------------- regexes
RE_META_CS = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']color-scheme[\"'][^>]*>", re.I | re.S)
RE_CONTENT = re.compile(r"\bcontent\s*=\s*[\"']([^\"']*)[\"']", re.I)
RE_META_THEME = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']theme-color[\"'][^>]*>", re.I | re.S)
RE_CSS_CS = re.compile(r"(?<![-\w])color-scheme\s*:\s*([^;{}\"'\n]+)", re.I)
RE_VIEWPORT_CS = re.compile(r"\bcolorScheme\s*:\s*[\"']([^\"']+)[\"']")
RE_JS_CS = re.compile(r"\.style\.colorScheme\s*=|setProperty\(\s*[\"']color-scheme[\"']|\.colorScheme\s*=(?!=)")
RE_TW_SCHEME = re.compile(r"(?<![\w-])scheme-(light-dark|only-dark|only-light|dark|light|normal)\b")
RE_PREFERS_DARK = re.compile(r"prefers-color-scheme\s*:\s*dark", re.I)
RE_LIGHT_DARK = re.compile(r"\blight-dark\(")
RE_TW_DARKMODE = re.compile(r"darkMode\s*:\s*(\[[^\]]*\]+|[\"'][^\"']+[\"'])", re.S)
RE_TW4_VARIANT = re.compile(r"@custom-variant\s+dark\b([^;{]*)(\{)?")
RE_CLASS_TOGGLE = re.compile(r"classList\.(?:add|toggle|remove|replace)\(\s*[\"'](dark|light|dark-mode|theme-dark)[\"']")
RE_DATA_THEME = re.compile(r"\bdata-(?:bs-)?theme\b|dataset\.theme\b|\[data-(?:bs-)?theme")
RE_DARK_UTIL = re.compile(r"(?<![\w-])dark:[\w\[\]#().%/-]+")
RE_THEME_LIBS = re.compile(
    r"from\s+[\"'](next-themes|mode-watcher|@vueuse/core|@nuxtjs/color-mode|@mui/material/styles|@chakra-ui/react)[\"']|"
    r"\b(useDark|useColorMode|ColorModeScript|InitColorSchemeScript|ModeWatcher|ThemeProvider)\b")
RE_DEFAULT_THEME = re.compile(r"defaultTheme\s*=\s*[\"'{]+\s*[\"']?(light|dark|system)", re.I)

COLOR_PROPS = (r"color|background|background-color|border(?:-(?:top|right|bottom|left|block|inline))?(?:-color)?|"
               r"outline(?:-color)?|fill|stroke|box-shadow|text-shadow|caret-color|text-decoration-color|"
               r"column-rule-color|accent-color")
RE_COLOR_DECL = re.compile(rf"(?<![-\w$@])({COLOR_PROPS})\s*:\s*([^;{{}}\n]+)", re.I)
RE_COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|\b(?:white|black)\b", re.I)
RE_TOKEN_DEF = re.compile(r"(?<![\w-])--[\w-]+\s*:\s*([^;{}]+)")
RE_JS_STYLE_COLOR = re.compile(
    r"\b(color|background|backgroundColor|borderColor|fill|stroke)\s*:\s*[\"'`](#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|white\b|black\b)")
RE_TW_LIGHT_ONLY = re.compile(
    r"(?<![\w:-])(bg-white|bg-(?:gray|slate|zinc|neutral|stone)-(?:50|100)|text-black|"
    r"text-(?:gray|slate|zinc|neutral|stone)-(?:700|800|900|950)|border-(?:gray|slate|zinc|neutral|stone)-(?:100|200|300))\b")

RE_RASTER_REF = re.compile(
    r"(?:src|srcset|href|url\(|image_tag|asset_path|image_path|import\s+\w+\s+from)\s*[=(]?\s*[\"']?"
    r"([^\"'()\s>]*?\.(?:png|jpe?g|gif|webp|bmp|avif))", re.I)
RE_LOGOISH = re.compile(r"logo|brand|wordmark|lockup|mark[-_.]|signature", re.I)
RE_FAVICONISH = re.compile(r"favicon|apple-touch|android-chrome|mstile|og[-_]image|social|opengraph|twitter-card", re.I)
RE_PICTURE_DARK = re.compile(r"<source\b[^>]*prefers-color-scheme\s*:\s*dark", re.I | re.S)

RE_BLOCK = re.compile(r"([^{}]*)\{([^{}]*)\}")
RE_BG_URL = re.compile(r"background(?:-image)?\s*:[^;]*url\(", re.I)
RE_REPEAT_SH = re.compile(r"background\s*:[^;]*url\([^;]*?(?<!no-)\brepeat(?:-x|-y)?\b", re.I)
RE_REPEAT_LONG = re.compile(r"background-repeat\s*:\s*(?:repeat|repeat-x|repeat-y|round|space)\b", re.I)
RE_BG_POS_NEG = re.compile(r"background-position(?:-[xy])?\s*:\s*[^;]*-\d+(?:\.\d+)?px", re.I)
RE_SPRITE_NAME = re.compile(r"url\([^)]*sprite", re.I)

RE_BLEND = re.compile(r"(?<![-\w])(mix-blend-mode|background-blend-mode)\s*:\s*(?!normal\b)([\w-]+)", re.I)
RE_MASK = re.compile(r"(?<![-\w])(-webkit-mask(?:-image|-box-image)?|mask(?:-image)?)\s*:\s*(?!none\b)([^;{}\n]+)", re.I)
RE_INVERT = re.compile(r"(?<![-\w])filter\s*:\s*[^;{}\n]*invert\(", re.I)
RE_TW_BLEND = re.compile(r"(?<![\w-])(mix-blend-(?!normal)[\w-]+|mask-\[|invert(?:-\d+)?)(?![\w-])")

RE_CANVAS = re.compile(r"<canvas\b|getContext\(\s*[\"'](?:2d|webgl2?|bitmaprenderer)[\"']")
RE_IFRAME = re.compile(r"<iframe\b[^>]*>", re.I | re.S)
RE_SRC_ATTR = re.compile(r"\bsrc\s*=\s*[\"'{]?([^\"'\s>}]+)", re.I)
RE_CLASS_ATTR = re.compile(r"\b(?:class|className|class:list)\s*=\s*[\"'`{]([^\"'`}]*)")
RE_JS_COLOR_READ = re.compile(
    r"getComputedStyle\([^)]*\)\s*(?:\.(?:color|backgroundColor|borderColor|fill|stroke)\b|"
    r"\.getPropertyValue\(\s*[\"'](?:--[\w-]*|color|background-color)[\"'])")
RE_SVG_HARD_FILL = re.compile(r"(?:fill|stroke)\s*[=:]\s*[\"']?\s*(#[0-9a-fA-F]{3,8}\b|rgb\(|black\b|white\b)", re.I)
RE_CURRENT_COLOR = re.compile(r"currentColor", re.I)

CANVAS_LIBS = {
    "chart.js": "Chart.js (canvas)", "echarts": "ECharts (canvas by default)", "pixi.js": "PixiJS (canvas/WebGL)",
    "three": "three.js (WebGL)", "@react-three/fiber": "react-three-fiber (WebGL)", "konva": "Konva (canvas)",
    "fabric": "Fabric.js (canvas)", "p5": "p5.js (canvas)", "chartist": "Chartist (SVG)",
    "mapbox-gl": "Mapbox GL (WebGL map)", "maplibre-gl": "MapLibre GL (WebGL map)", "leaflet": "Leaflet (raster tiles)",
    "@googlemaps/js-api-loader": "Google Maps (raster/vector tiles)", "signature_pad": "signature_pad (canvas)",
    "lottie-web": "Lottie (SVG/canvas)", "uplot": "uPlot (canvas)", "@antv/g2": "AntV G2 (canvas)",
}
STACK_DEPS = {
    "next": "Next.js", "react": "React", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte", "@sveltejs/kit": "SvelteKit",
    "astro": "Astro", "@angular/core": "Angular", "solid-js": "Solid", "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap", "@mui/material": "MUI", "@chakra-ui/react": "Chakra UI", "next-themes": "next-themes",
    "mode-watcher": "mode-watcher", "@nuxtjs/color-mode": "@nuxtjs/color-mode", "styled-components": "styled-components",
    "@emotion/react": "Emotion", "@vueuse/core": "VueUse", "daisyui": "daisyUI", "@radix-ui/themes": "Radix Themes",
    "vuetify": "Vuetify", "@mantine/core": "Mantine", "flowbite": "Flowbite", "@headlessui/react": "Headless UI",
}

ROOTISH = re.compile(r"^\s*(?::root|html|body|\*|:host)(\s*,\s*(?::root|html|body|:host))*\s*$", re.I)


def selector_before(text: str, pos: int) -> str:
    brace = text.rfind("{", 0, pos)
    if brace < 0:
        return ""
    close = max(text.rfind("}", 0, brace), text.rfind(";", 0, brace))
    sel = text[close + 1:brace].strip()
    sel = re.sub(r"/\*.*?\*/", "", sel, flags=re.S).strip()
    return sel[-120:]


def strip_comments(text: str, kinds: set[str]) -> str:
    """Blank out CSS/JS block comments and HTML comments, preserving offsets."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    if "markup" in kinds or "svg" in kinds:
        text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    return text


def walk(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")
                       and not any((rel_dir + "/" + d).lstrip("./").startswith(s) for s in SKIP_SUBPATHS)]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def detect_stack(root: str, rep: Report):
    stack = []
    pkg = load_json(os.path.join(root, "package.json"))
    deps = {}
    if isinstance(pkg, dict):
        for k in ("dependencies", "devDependencies", "peerDependencies"):
            if isinstance(pkg.get(k), dict):
                deps.update(pkg[k])
    for dep, name in STACK_DEPS.items():
        if dep in deps:
            stack.append(f"{name} {deps[dep]}")
    for dep, name in CANVAS_LIBS.items():
        if dep in deps:
            rep.facts["canvas_libs"].append(f"{name} [{dep} {deps[dep]}]")
    rep.facts["tailwind_version"] = deps.get("tailwindcss", "")
    gemfile = os.path.join(root, "Gemfile")
    if os.path.exists(gemfile):
        try:
            g = open(gemfile, encoding="utf-8", errors="replace").read()
            if re.search(r"^\s*gem\s+[\"']rails[\"']", g, re.M):
                stack.append("Rails")
            for gem, name in (("tailwindcss-rails", "tailwindcss-rails"), ("turbo-rails", "Turbo"),
                              ("cssbundling-rails", "cssbundling-rails"), ("bootstrap", "Bootstrap gem")):
                if re.search(rf"^\s*gem\s+[\"']{gem}[\"']", g, re.M):
                    stack.append(name)
        except OSError:
            pass
    if os.path.exists(os.path.join(root, "components.json")):
        stack.append("shadcn/ui (components.json)")
    if os.path.isdir(os.path.join(root, "wp-content")) or os.path.exists(os.path.join(root, "theme.json")):
        stack.append("WordPress")
    rep.facts["stack"] = stack
    return deps


def scan_text(t: Text, kinds: set[str], rep: Report, tailwind: bool):
    text = strip_comments(t.text, kinds)
    rel = t.rel

    # ---- declarations
    if "markup" in kinds or "script" in kinds:
        for m in RE_META_CS.finditer(text):
            c = RE_CONTENT.search(m.group(0))
            val = (c.group(1) if c else "?").strip()
            rep.facts["meta_color_scheme"].append({"where": f"{rel}:{t.line(m.start())}", "value": val})
        for m in RE_META_THEME.finditer(text):
            rep.facts["meta_theme_color"].append({"where": f"{rel}:{t.line(m.start())}",
                                                  "has_media": "media" in m.group(0).lower()})
    if "style" in kinds or "markup" in kinds:
        for m in RE_CSS_CS.finditer(text):
            val = m.group(1).strip()
            sel = selector_before(text, m.start())
            inline = bool(re.search(r"style\s*=\s*[\"'][^\"']*$", text[max(0, m.start() - 200):m.start()]))
            rep.facts["css_color_scheme"].append({"where": f"{rel}:{t.line(m.start())}", "value": val,
                                                  "selector": "(inline style)" if inline else sel,
                                                  "root": inline and "<html" in t.snippet(m.start()).lower()
                                                  or bool(ROOTISH.match(sel))})
    if "script" in kinds:
        if re.search(r"export\s+(?:const\s+viewport|(?:async\s+)?function\s+generateViewport)", text):
            for m in RE_VIEWPORT_CS.finditer(text):
                rep.facts["next_viewport_color_scheme"].append({"where": f"{rel}:{t.line(m.start())}",
                                                                "value": m.group(1)})
        for m in RE_JS_CS.finditer(text):
            rep.facts["js_color_scheme"].append(f"{rel}:{t.line(m.start())}")
        for m in RE_THEME_LIBS.finditer(text):
            rep.facts["theme_libs"].append(f"{rel}:{t.line(m.start())} {m.group(1) or m.group(2)}")
        for m in RE_DEFAULT_THEME.finditer(text):
            rep.facts["default_theme"].append({"where": f"{rel}:{t.line(m.start())}", "value": m.group(1).lower()})
        for m in RE_CLASS_TOGGLE.finditer(text):
            rep.facts["class_toggles"].append(f"{rel}:{t.line(m.start())}")
    if "markup" in kinds:
        for m in RE_TW_SCHEME.finditer(text):
            snip = t.snippet(m.start()).lower()
            rep.facts["tw_scheme_utils"].append({"where": f"{rel}:{t.line(m.start())}", "value": m.group(1),
                                                 "root": "<html" in snip})

    # ---- dark-mode mechanisms
    for m in RE_PREFERS_DARK.finditer(text):
        rep.counters["prefers_dark"] += 1
        if len(rep.facts["prefers_dark_where"]) < rep.max_examples:
            rep.facts["prefers_dark_where"].append(f"{rel}:{t.line(m.start())}")
    n_ld = len(RE_LIGHT_DARK.findall(text))
    rep.counters["light_dark_fn"] += n_ld
    if n_ld:
        rep.per_file[rel]["light-dark()"] += n_ld
    if "style" in kinds:
        for m in RE_TW4_VARIANT.finditer(text):
            rep.facts["tw4_dark_variant"].append({"where": f"{rel}:{t.line(m.start())}",
                                                  "decl": (m.group(1) or "").strip() or "{block}",
                                                  "media_aware": "prefers-color-scheme" in text[m.start():m.start() + 400]})
        for m in re.finditer(r"(?:^|[\s,}])(\.dark|\[data-(?:bs-)?theme=[\"']?dark[\"']?\]|\.theme-dark|\.dark-mode)\b[^{]*\{",
                             text):
            rep.counters["dark_selectors"] += 1
            if len(rep.facts["dark_selector_where"]) < rep.max_examples:
                rep.facts["dark_selector_where"].append(f"{rel}:{t.line(m.start())}")
    if RE_DATA_THEME.search(text):
        rep.counters["data_theme_files"] += 1
    if "markup" in kinds:
        n_dark = len(RE_DARK_UTIL.findall(text))
        rep.counters["dark_utils"] += n_dark

    # ---- color tokenization
    if "style" in kinds:
        for line in text.split("\n"):
            for tm in RE_TOKEN_DEF.finditer(line):
                if RE_COLOR_LITERAL.search(tm.group(1)) or "light-dark(" in tm.group(1):
                    rep.counters["color_tokens"] += 1
            line = RE_TOKEN_DEF.sub("", line)
            for m in RE_COLOR_DECL.finditer(line):
                val = m.group(2)
                if "light-dark(" in val:
                    rep.counters["themed_decls"] += 1
                elif "var(--" in val and not RE_COLOR_LITERAL.search(re.sub(r"var\([^)]*\)", "", val)):
                    rep.counters["token_decls"] += 1
                elif RE_COLOR_LITERAL.search(re.sub(r"url\([^)]*\)", "", val)):
                    rep.counters["hardcoded_decls"] += 1
                    rep.per_file[rel]["hardcoded"] += 1
    if "script" in kinds or "markup" in kinds:
        for m in RE_JS_STYLE_COLOR.finditer(text):
            rep.counters["hardcoded_js_styles"] += 1
            rep.per_file[rel]["hardcoded-js"] += 1
    if tailwind and "markup" in kinds:
        for line in text.split("\n"):
            hits = RE_TW_LIGHT_ONLY.findall(line)
            if hits and "dark:" not in line:
                rep.counters["tw_light_only_lines"] += 1
                rep.per_file[rel]["tw-light-only"] += 1

    # ---- raster logos and images
    if "markup" in kinds or "style" in kinds or "script" in kinds:
        has_dark_picture = bool(RE_PICTURE_DARK.search(text))
        for m in RE_RASTER_REF.finditer(text):
            ref = m.group(1)
            line_txt = t.snippet(m.start(), 400)
            if RE_FAVICONISH.search(ref) or re.search(r"rel\s*=\s*[\"'](?:shortcut\s+)?(?:icon|apple-touch-icon|mask-icon|manifest)", line_txt, re.I) \
                    or re.search(r"og:image|twitter:image|itemprop=[\"']image", line_txt, re.I):
                continue
            rep.counters["raster_refs"] += 1
            if RE_LOGOISH.search(ref) or re.search(r"\balt\s*=\s*[\"'][^\"']*(?:logo|brand|wordmark)", line_txt, re.I):
                rep.add("RASTER_LOGO", "medium", "Raster logo or brand mark",
                        "Bitmaps aren't converted (only simple black-and-white logos may be inverted). A dark or colorful "
                        "logo on a transparent background can vanish on dark, and one on white becomes a white box.",
                        "fix-patterns §5: SVG with currentColor, a <picture> dark source, or a framed light tile.",
                        t, m.start(), note="has <picture> dark source in file" if has_dark_picture else None)

    # ---- tiled backgrounds and sprites (rule blocks)
    if "style" in kinds:
        for b in RE_BLOCK.finditer(text):
            body = b.group(2)
            if not RE_BG_URL.search(body):
                continue
            pos = b.start(2)
            if RE_REPEAT_SH.search(body) or RE_REPEAT_LONG.search(body):
                rep.add("TILED_BG", "medium", "Tiled background image",
                        "Bitmap backgrounds aren't converted, so a light texture stays light behind darkened content. "
                        "WebKit explicitly recommends CSS colors or gradients instead.",
                        "fix-patterns §5: CSS gradient/pattern built from tokens.", t, pos)
            elif RE_BG_POS_NEG.search(body) or RE_SPRITE_NAME.search(body):
                rep.add("SPRITE", "medium", "Image sprite",
                        "Sprite bitmaps aren't converted, and their baked-in colors and backgrounds won't match a dark page.",
                        "fix-patterns §5: individual SVG icons with currentColor, CSS for states, corners and shadows.", t, pos)

    # ---- effects that may be disabled
    if "style" in kinds or "markup" in kinds:
        for rx, label in ((RE_BLEND, "blend mode"), (RE_MASK, "mask")):
            for m in rx.finditer(text):
                rep.add("BLEND_MASK", "medium", "mix-blend-mode / mask in use",
                        "Safari may disable masks and blend modes on elements it transforms. Masked icons can become solid "
                        "boxes, and multiply-to-remove-white tricks bring the white back.",
                        "fix-patterns §7: inline SVG instead of mask icons, transparent assets instead of multiply.",
                        t, m.start(), note=label)
        for m in RE_INVERT.finditer(text):
            rep.add("INVERT_HACK", "medium", "filter: invert() (likely a home-made dark mode)",
                    "Stacks with Safari's conversion or double-inverts images and brand colors.",
                    "fix-patterns §7: remove it and use real tokens.", t, m.start())
    if "markup" in kinds and tailwind:
        for ca in RE_CLASS_ATTR.finditer(text):
            for u in RE_TW_BLEND.finditer(ca.group(1)):
                rep.add("BLEND_MASK", "medium", "mix-blend-mode / mask in use",
                        "Safari may disable masks and blend modes on elements it transforms.",
                        "fix-patterns §7.", t, ca.start(), note=f"Tailwind `{u.group(1)}`")

    # ---- canvas, iframes, JS color reads
    if "markup" in kinds or "script" in kinds:
        for m in RE_CANVAS.finditer(text):
            rep.add("CANVAS", "medium", "<canvas> rendering",
                    "Canvas content is never converted. Dark ink on a transparent canvas becomes dark-on-dark, and "
                    "an opaque white canvas becomes a glaring box.",
                    "fix-patterns §6: theme the drawing yourself (path A) or make it a self-contained opaque island (path B).",
                    t, m.start())
        for m in RE_JS_COLOR_READ.finditer(text):
            rep.add("JS_COLOR_READ", "low", "JavaScript reads computed colors",
                    "Under Adaptive Dark Mode, getComputedStyle returns the authored light values, so derived colors "
                    "(chart palettes, auto text color) are computed for light while the page is shown dark.",
                    "Fine on path A. On path B, keep anything drawn from these colors on an opaque light surface.",
                    t, m.start())
    if "markup" in kinds:
        for m in RE_IFRAME.finditer(text):
            rep.add("IFRAME", "low", "iframe embed",
                    "How Adaptive Dark Mode treats iframes is undocumented. Third-party embeds keep their own theme.",
                    "fix-patterns §6: pass a theme parameter if the embed supports one, declare color-scheme in your own "
                    "iframe documents, and list it for a Safari check.", t, m.start(),
                    note=(lambda s: s.group(1)[:80] if s else None)(RE_SRC_ATTR.search(m.group(0))))
        if "<svg" in text:
            svg_hard = len(RE_SVG_HARD_FILL.findall(" ".join(re.findall(r"<svg\b.*?</svg>", text, re.S))))
            if svg_hard:
                rep.counters["inline_svg_hard_paint"] += svg_hard
                rep.per_file[rel]["svg-hard-paint"] += svg_hard


def scan_svg_file(t: Text, rep: Report):
    hard = RE_SVG_HARD_FILL.findall(t.text)
    if not hard:
        return
    rep.counters["svg_files_hard_paint"] += 1
    if not RE_CURRENT_COLOR.search(t.text) and "prefers-color-scheme" not in t.text and RE_LOGOISH.search(t.rel):
        rep.add("SVG_LOGO_FIXED", "low", "SVG logo with fixed colors",
                "Safari recolors SVG when needed on path B, but in your own dark theme fixed dark fills stay dark.",
                "fix-patterns §5: currentColor, CSS variables, or an internal prefers-color-scheme style.", t)


def scan_raster(path: str, rel: str, rep: Report, budget: list[int]):
    if budget[0] <= 0:
        return
    try:
        from PIL import Image  # type: ignore
    except Exception:
        rep.facts["pillow"] = False
        return
    rep.facts["pillow"] = True
    budget[0] -= 1
    try:
        with Image.open(path) as im:
            im.thumbnail((64, 64))
            im = im.convert("RGBA")
            w, h = im.size
            if w < 8 or h < 8:
                return
            px = im.load()
            border = [px[x, y] for x in range(w) for y in (0, h - 1)] + [px[x, y] for y in range(h) for x in (0, w - 1)]
            near_white = sum(1 for r, g, b, a in border if a > 245 and r > 238 and g > 238 and b > 238) / len(border)
            transparent_border = sum(1 for *_, a in border if a < 16) / len(border)
            opaque = [(r, g, b) for x in range(w) for y in range(h) for (r, g, b, a) in [px[x, y]] if a > 200]
    except Exception:
        return
    rep.counters["raster_files_checked"] += 1
    logoish = bool(RE_LOGOISH.search(rel))
    if near_white > 0.85:
        rep.counters["raster_baked_white"] += 1
        rep.add("RASTER_WHITE_BG", "medium" if logoish else "low", "Raster image with a baked-in white background",
                "Images aren't converted, so it shows as a white rectangle on the darkened page.",
                "fix-patterns §5: transparent cutout, or present it on an intentional light tile with padding.",
                note=f"{rel}  (border {near_white:.0%} white{', logo-like' if logoish else ''})")
    elif transparent_border > 0.6 and opaque:
        lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in opaque) / len(opaque) / 255
        if lum < 0.3:
            colorful = len({(r // 32, g // 32, b // 32) for r, g, b in opaque}) > 6
            rep.add("RASTER_DARK_ON_TRANSPARENT", "high" if logoish else "medium",
                    "Dark artwork on a transparent background",
                    "On a dark page it nearly disappears. Safari may invert it only if it's a simple black-and-white logo"
                    + (", and this one looks colorful." if colorful else "."),
                    "fix-patterns §5: SVG with currentColor, a dark variant, or a light tile.",
                    note=f"{rel}  (mean lightness {lum:.0%}{', colorful' if colorful else ', mostly monochrome'})")


def build_verdict(rep: Report) -> dict:
    f = rep.facts
    decl_vals = [d["value"] for d in f["meta_color_scheme"]] + \
                [d["value"] for d in f["css_color_scheme"] if d["root"]] + \
                [d["value"] for d in f["next_viewport_color_scheme"]] + \
                [d["value"].replace("-", " ") for d in f["tw_scheme_utils"] if d["root"]]
    norm = [v.lower() for v in decl_vals]
    static_dark = any(("dark" in v) and not re.search(r"\blight\s+only\b|\bonly\s+light\b|only-light", v) for v in norm)
    opt_out = any(re.search(r"\blight\s+only\b|\bonly\s+light\b|only-light", v) for v in norm + [d["value"].lower() for d in f["css_color_scheme"]])
    dark_only_root = any(v.strip() in ("dark", "only dark", "dark only") for v in norm)
    c = rep.counters
    mechanisms = []
    if c["prefers_dark"]:
        mechanisms.append(f"prefers-color-scheme: dark ×{c['prefers_dark']}")
    if c["light_dark_fn"]:
        mechanisms.append(f"light-dark() ×{c['light_dark_fn']}")
    if c["dark_selectors"]:
        mechanisms.append(f".dark / [data-theme=dark] rule blocks ×{c['dark_selectors']}")
    if c["dark_utils"]:
        mechanisms.append(f"Tailwind dark: utilities ×{c['dark_utils']}")
    if f["tw4_dark_variant"]:
        mechanisms.append("Tailwind v4 @custom-variant dark")
    if f["class_toggles"]:
        mechanisms.append(f"JS class toggles ×{len(f['class_toggles'])}")
    has_dark = bool(c["prefers_dark"] or c["light_dark_fn"] or c["dark_selectors"] or c["dark_utils"] > 5)
    class_based = bool(c["dark_selectors"] or f["class_toggles"] or c["tw_class_config"]
                       or any(not d["media_aware"] for d in f["tw4_dark_variant"]))

    if static_dark and has_dark:
        state = "skipped (declared)"
        summary = ("Declares dark support statically, so Safari leaves the site alone. Users see your own dark theme, which "
                   "now has to be complete (path A verification).")
    elif static_dark and not has_dark:
        state = "declared but no dark styles found"
        summary = ("Declares `dark` but no dark styles were found. UA surfaces (canvas, controls, default text) go dark while "
                   "your hard-coded colors stay light. Either build the dark theme or remove the declaration (path B).")
    elif has_dark and c["light_dark_fn"] and not c["prefers_dark"] and not class_based:
        state = "converted (light-dark() used without a declaration)"
        summary = ("Colors use light-dark(), but nothing declares `color-scheme: light dark`, so every light-dark() value "
                   "resolves to its light side and the dark theme never activates. Safari converts the light render. "
                   "Add the declaration (path A). It's the whole fix.")
    elif has_dark and c["prefers_dark"] and not class_based:
        state = "probably skipped as already dark (undeclared)"
        summary = ("Dark styles follow prefers-color-scheme, so for users with a dark system the page should render dark, "
                   "and Safari's 'already dark' check should leave it alone. That's a heuristic, not the documented "
                   "contract, and without the declaration UA form controls and scrollbars stay light on your dark page. "
                   "Add the declaration (path A).")
    elif has_dark:
        state = "converted (dark theme exists but is undeclared)"
        summary = ("A dark theme exists but there's no static declaration. Whenever the site's default render is light, "
                   "Safari converts the light theme and your real dark theme never shows. Form controls and scrollbars "
                   "also won't match. Adding the declaration (path A) is the highest-value fix.")
    else:
        state = "converted (undeclared light site)"
        summary = ("No dark theme and no declaration. Safari will convert this site when the user opts in. Choose path A "
                   "(build a dark theme) or path B (clean up assets and effects so conversion works well).")
    if opt_out:
        summary += " Opt-out (`light only`) declarations exist, but `only` is not supported in Safari 27.3 beta 1."
    return {"state": state, "summary": summary, "static_dark_declaration": static_dark, "has_dark_styles": has_dark,
            "class_based_dark": class_based, "opt_out_present": opt_out, "dark_only_root": dark_only_root,
            "mechanisms": mechanisms, "declarations": decl_vals}


def derive_findings(rep: Report, v: dict):
    f, c = rep.facts, rep.counters
    if v["static_dark_declaration"] and not v["has_dark_styles"]:
        rep.add("DECLARED_NO_DARK", "high", "Declares dark support without dark styles",
                "The declaration switches off Safari's conversion and turns UA surfaces dark, while your colors stay light. "
                "The result is light panels on a dark canvas and dark default text.",
                "SKILL.md cardinal rule: build the dark theme (fix-patterns §3) or remove the declaration.",
                note="; ".join(v["declarations"])[:200])
    if v["has_dark_styles"] and not v["static_dark_declaration"]:
        rep.add("DARK_UNDECLARED", "high", "Dark theme exists but no static color-scheme declaration",
                "Safari only reliably skips sites that declare `light dark`. Without it, a light-by-default render gets "
                "converted, and UA controls and scrollbars stay light even when your dark CSS is active.",
                "fix-patterns §1: <meta name=\"color-scheme\" content=\"light dark\"> early in <head> plus "
                ":root { color-scheme: light dark; }.",
                note=", ".join(v["mechanisms"])[:200])
    if f["js_color_scheme"] and not v["static_dark_declaration"]:
        rep.add("JS_ONLY_DECL", "high", "color-scheme is only set from JavaScript",
                "WebKit asks for the declaration in HTML or CSS, not injected by script. Safari may analyze or convert "
                "the page before the script runs.",
                "fix-patterns §1: add the static declaration and keep JS only for narrowing.",
                note=", ".join(f["js_color_scheme"][:rep.max_examples]))
    for d in f["default_theme"]:
        if d["value"] == "light":
            rep.add("DEFAULT_LIGHT", "medium", "Theme defaults to light instead of system",
                    "First-time visitors with a dark system get the light theme, which Safari then converts, so your "
                    "dark theme is never shown to them.",
                    "fix-patterns §2: default to system.", note=d["where"])
    if v["static_dark_declaration"] and v["class_based_dark"] and not any(d["media_aware"] for d in f["tw4_dark_variant"]) \
            and c["prefers_dark"] == 0 and c["light_dark_fn"] == 0:
        rep.add("CLASS_MISMATCH", "high", "Class-only dark styles behind a `light dark` declaration",
                "With a dark system and no class applied yet (first visit, JS slow or disabled), `light dark` resolves dark "
                "for UA surfaces while the `.dark` styles are inactive, giving a mixed light/dark page.",
                "fix-patterns §2: make the dark selector also match prefers-color-scheme unless `.light` is set, or "
                "resolve the class before first paint. See frameworks.md for Tailwind syntax.")
    if v["dark_only_root"] and (c["prefers_dark"] or c["dark_selectors"]):
        rep.add("DARK_ONLY_ROOT", "medium", "Root declares `color-scheme: dark` alone",
                "If the site also has a light theme, light-mode users get dark form controls and scrollbars.",
                "fix-patterns §1/§2: `light dark` at the root, narrowed per theme.")
    if f["meta_theme_color"] and not any(d["has_media"] for d in f["meta_theme_color"]) and v["has_dark_styles"]:
        rep.add("THEME_COLOR_SINGLE", "low", "Single theme-color for both schemes",
                "The browser UI tint stays light in dark mode.", "fix-patterns §4: two theme-color metas with media.",
                note=f["meta_theme_color"][0]["where"])
    if v["static_dark_declaration"] and not f["meta_color_scheme"] and not f["next_viewport_color_scheme"]:
        rep.add("NO_META", "low", "Declared in CSS only (no meta tag)",
                "The meta tag is seen before CSS loads, which avoids a white canvas flash on slow connections.",
                "fix-patterns §1: add <meta name=\"color-scheme\" content=\"light dark\"> before stylesheets.")
    total_color = c["hardcoded_decls"] + c["token_decls"] + c["themed_decls"]
    if total_color:
        share = c["hardcoded_decls"] / total_color
        if share > 0.35 and c["hardcoded_decls"] > 15:
            top = sorted(((n["hardcoded"], fn) for fn, n in rep.per_file.items() if n["hardcoded"]), reverse=True)[:rep.max_examples]
            rep.add("HARDCODED_COLORS", "medium" if v["has_dark_styles"] or v["static_dark_declaration"] else "low",
                    f"{c['hardcoded_decls']} of {total_color} color declarations use literals ({share:.0%})",
                    "Literal colors don't change with the scheme. On path A every one needs a dark value, and on path B "
                    "they're fine but make a later move to A expensive.",
                    "fix-patterns §3: route through tokens, biggest visual area first.",
                    note="top files: " + ", ".join(f"{fn} ({n})" for n, fn in top))
    if c["tw_light_only_lines"] > 5 and (v["has_dark_styles"] or v["static_dark_declaration"]):
        top = sorted(((n["tw-light-only"], fn) for fn, n in rep.per_file.items() if n["tw-light-only"]), reverse=True)[:rep.max_examples]
        rep.add("TW_LIGHT_ONLY", "medium", f"{c['tw_light_only_lines']} lines use light-only Tailwind colors without dark:",
                "In a dark theme, these elements stay white or near-black.",
                "Use semantic theme colors (bg-surface, text-ink) or add dark: partners.",
                note="top files: " + ", ".join(f"{fn} ({n})" for n, fn in top))
    if f["canvas_libs"]:
        rep.add("CANVAS_LIB", "medium", "Canvas/WebGL/tile-based visualization library",
                "Canvas and raster map tiles are never converted.", "fix-patterns §6.",
                note=", ".join(f["canvas_libs"]))
    if c["inline_svg_hard_paint"] > 10 and v["has_dark_styles"]:
        top = sorted(((n["svg-hard-paint"], fn) for fn, n in rep.per_file.items() if n["svg-hard-paint"]), reverse=True)[:rep.max_examples]
        rep.add("SVG_HARD_PAINT", "low", f"{c['inline_svg_hard_paint']} hard-coded fills/strokes in inline SVG",
                "Fixed dark fills stay dark in your own dark theme.", "fix-patterns §5: currentColor.",
                note="top files: " + ", ".join(f"{fn} ({n})" for n, fn in top))


def render_md(root, rep: Report, v: dict) -> str:
    f, c = rep.facts, rep.counters
    out = [f"# Adaptive Dark Mode static audit: `{os.path.basename(os.path.abspath(root))}`", ""]
    out += ["> Heuristic scan. Confirm each finding in the file before acting. It can't see CSS-in-JS theme objects, "
            "CMS or database content, or remote stylesheets. Run the runtime probe for rendered results.", ""]
    out += ["## Verdict", f"- **Under Adaptive Dark Mode today:** {v['state']}", f"- {v['summary']}", ""]
    out += ["## Stack", "- " + (", ".join(f["stack"]) if f["stack"] else "not detected (no package.json/Gemfile hints)"), ""]
    out += ["## Declarations"]
    if not (f["meta_color_scheme"] or f["css_color_scheme"] or f["next_viewport_color_scheme"] or f["tw_scheme_utils"]):
        out.append("- none found")
    for d in f["meta_color_scheme"]:
        out.append(f"- meta `{d['value']}`: {d['where']}")
    for d in f["next_viewport_color_scheme"]:
        out.append(f"- Next.js viewport.colorScheme `{d['value']}`: {d['where']}")
    for d in f["css_color_scheme"][:20]:
        tag = "root" if d["root"] else "scoped"
        out.append(f"- CSS `color-scheme: {d['value']}` on `{d['selector'] or '?'}` ({tag}): {d['where']}")
    if len(f["css_color_scheme"]) > 20:
        out.append(f"- … {len(f['css_color_scheme']) - 20} more CSS declarations")
    for d in f["tw_scheme_utils"][:10]:
        out.append(f"- Tailwind `scheme-{d['value']}`{' on <html>' if d['root'] else ''}: {d['where']}")
    if f["js_color_scheme"]:
        out.append(f"- set from JavaScript: {', '.join(f['js_color_scheme'][:rep.max_examples])}")
    for d in f["meta_theme_color"][:4]:
        out.append(f"- theme-color meta{' (with media)' if d['has_media'] else ''}: {d['where']}")
    out.append("")
    out += ["## Dark-mode mechanisms", "- " + ("; ".join(v["mechanisms"]) if v["mechanisms"] else "none found")]
    for d in f["tw_darkmode"]:
        out.append(f"- tailwind.config darkMode: {d}")
    for label, key in (("prefers-color-scheme", "prefers_dark_where"), ("dark selectors", "dark_selector_where")):
        if f[key]:
            out.append(f"- {label} at: {', '.join(f[key])}")
    for d in f["tw4_dark_variant"]:
        out.append(f"- Tailwind v4 dark variant `{d['decl']}` (media-aware: {d['media_aware']}): {d['where']}")
    if f["theme_libs"]:
        out.append(f"- theme libraries/providers: {', '.join(sorted(set(x.split(' ', 1)[1] for x in f['theme_libs'])))}")
    for d in f["default_theme"]:
        out.append(f"- defaultTheme `{d['value']}`: {d['where']}")
    out.append("")
    total = c["hardcoded_decls"] + c["token_decls"] + c["themed_decls"]
    out += ["## Color tokenization",
            f"- color declarations: {total} (literals {c['hardcoded_decls']}, var() {c['token_decls']}, light-dark() {c['themed_decls']})",
            f"- color custom properties defined: {c['color_tokens']}",
            f"- inline JS/JSX style colors: {c['hardcoded_js_styles']}"]
    if c["tw_light_only_lines"]:
        out.append(f"- Tailwind light-only color lines without dark:: {c['tw_light_only_lines']}")
    out.append(f"- raster image references: {c['raster_refs']}; raster files pixel-checked: {c['raster_files_checked']}"
               + ("" if f.get("pillow", True) else " (Pillow not installed, so the pixel checks were skipped)"))
    out.append("")
    out += ["## Findings"]
    items = sorted(rep.findings.values(), key=lambda x: (SEV_ORDER[x["severity"]], -x["count"]))
    if not items:
        out.append("- none")
    for it in items:
        out.append(f"### [{it['severity'].upper()}] {it['title']} ({it['count']})")
        out.append(f"- **Why:** {it['why']}")
        out.append(f"- **Fix:** {it['fix']}")
        for ex in it["examples"]:
            out.append(f"  - {ex}")
        if it["count"] > len(it["examples"]):
            out.append(f"  - … {it['count'] - len(it['examples'])} more")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-examples", type=int, default=8)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--max-images", type=int, default=400)
    ap.add_argument("--fail-on", choices=["high", "medium", "low", "never"], default="never",
                    help="exit 1 if any finding is at or above this severity (for CI)")
    ap.add_argument("--exclude", action="append", default=[], metavar="DIR",
                    help="extra directory name to skip (repeatable)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args()
    root = a.root
    if not os.path.isdir(root):
        ap.error(f"not a directory: {root}")
    SKIP_DIRS.update(a.exclude)
    rep = Report(a.max_examples)
    deps = detect_stack(root, rep)
    tailwind = "tailwindcss" in deps or any("tailwind" in s.lower() for s in rep.facts["stack"])
    budget = [0 if a.no_images else a.max_images]
    n_files = 0
    for path in walk(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        ext = os.path.splitext(path)[1].lower()
        base = os.path.basename(path)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if ext in RASTER_EXT:
            scan_raster(path, rel, rep, budget)
            continue
        if re.match(r"tailwind\.config\.(?:js|cjs|mjs|ts)$", base):
            try:
                txt = open(path, encoding="utf-8", errors="replace").read()
                m = RE_TW_DARKMODE.search(txt)
                rep.facts["tw_darkmode"].append(f"{rel}: {m.group(1).strip() if m else '(unset: media)'}")
                if m and re.search(r"class|selector|variant", m.group(1)) and "prefers-color-scheme" not in m.group(1):
                    rep.counters["tw_class_config"] += 1
            except OSError:
                pass
        k = kinds_for(path)
        if not k or size > MAX_FILE_BYTES:
            continue
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        n_files += 1
        t = Text(path, rel, txt)
        if k == {"svg"}:
            scan_svg_file(t, rep)
        else:
            scan_text(t, k, rep, tailwind)
    rep.facts["files_scanned"] = n_files
    v = build_verdict(rep)
    derive_findings(rep, v)
    if a.json:
        print(json.dumps({"tool": "adaptive-dark-mode/audit.py", "version": __version__,
                          "verdict": v, "facts": rep.facts, "counters": rep.counters,
                          "findings": sorted(rep.findings.values(), key=lambda x: (SEV_ORDER[x["severity"]], -x["count"]))},
                         indent=2, default=list))
    else:
        print(render_md(root, rep, v))
        print(f"\n_{n_files} files scanned by audit.py {__version__}._")
    if a.fail_on != "never":
        limit = SEV_ORDER[a.fail_on]
        if any(SEV_ORDER[f["severity"]] <= limit for f in rep.findings.values()):
            sys.exit(1)


if __name__ == "__main__":
    main()
