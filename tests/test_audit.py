"""Regression tests for skills/adaptive-dark-mode/scripts/audit.py.

Run from the repository root:
    python3 -I -m unittest discover -s tests -v

Standard library only. Image checks are skipped when Pillow isn't installed,
mirroring how audit.py itself degrades.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "skills", "adaptive-dark-mode", "scripts", "audit.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


def run(target, *args):
    return subprocess.run([sys.executable, "-I", AUDIT, target, *args],
                          capture_output=True, text=True, timeout=120)


def audit(target, *args):
    proc = run(target, "--json", *args)
    if proc.returncode != 0:
        raise AssertionError(f"audit failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def ids(report, severity=None):
    return {f["id"] for f in report["findings"] if severity is None or f["severity"] == severity}


class VerdictTests(unittest.TestCase):
    """Each fixture must land on the verdict that SKILL.md's decision table depends on."""

    def check(self, fixture, state, must_have=(), must_not_have=()):
        r = audit(os.path.join(FIXTURES, fixture))
        self.assertEqual(r["verdict"]["state"], state, fixture)
        found = ids(r)
        for fid in must_have:
            self.assertIn(fid, found, f"{fixture}: expected {fid}, got {sorted(found)}")
        for fid in must_not_have:
            self.assertNotIn(fid, found, f"{fixture}: unexpected {fid}")
        return r

    def test_good_site_is_clean(self):
        r = self.check("good", "skipped (declared)")
        self.assertEqual(r["findings"], [], "a correctly themed site must produce zero findings")
        self.assertTrue(r["verdict"]["static_dark_declaration"])

    def test_declared_without_dark_styles(self):
        self.check("declared-incomplete", "declared but no dark styles found",
                   must_have=["DECLARED_NO_DARK", "CANVAS", "RASTER_LOGO"],
                   must_not_have=["DARK_UNDECLARED"])

    def test_declared_with_class_only_dark_styles(self):
        self.check("declared-class-only", "skipped (declared)",
                   must_have=["CLASS_MISMATCH"], must_not_have=["DECLARED_NO_DARK", "DARK_UNDECLARED"])

    def test_media_query_dark_theme_without_declaration(self):
        self.check("media-undeclared", "probably skipped as already dark (undeclared)",
                   must_have=["DARK_UNDECLARED", "RASTER_LOGO"])

    def test_light_dark_function_without_declaration(self):
        r = self.check("ld-undeclared", "converted (light-dark() used without a declaration)",
                       must_have=["DARK_UNDECLARED"])
        self.assertGreaterEqual(r["counters"]["light_dark_fn"], 2)

    def test_js_only_declaration(self):
        self.check("js-only-declaration", "probably skipped as already dark (undeclared)",
                   must_have=["JS_ONLY_DECL", "DARK_UNDECLARED"])

    def test_tailwind_next_class_strategy(self):
        r = self.check("tw-next-undeclared", "converted (dark theme exists but is undeclared)",
                       must_have=["DARK_UNDECLARED", "DEFAULT_LIGHT", "BLEND_MASK", "TILED_BG", "SPRITE",
                                  "CANVAS", "CANVAS_LIB", "RASTER_LOGO", "JS_COLOR_READ", "IFRAME"])
        self.assertTrue(r["verdict"]["class_based_dark"])
        self.assertTrue(any("Tailwind CSS" in s for s in r["facts"]["stack"]))
        self.assertTrue(any("next-themes" in s for s in r["facts"]["stack"]))

    def test_commented_out_declarations_are_ignored(self):
        # tw-next-undeclared/app/globals.css contains `/* .commented { color-scheme: light dark; } */`
        r = audit(os.path.join(FIXTURES, "tw-next-undeclared"))
        self.assertEqual(r["facts"]["css_color_scheme"], [])


@unittest.skipUnless(HAVE_PIL, "Pillow not installed; raster checks are optional")
class RasterTests(unittest.TestCase):
    def test_dark_on_transparent_and_baked_white(self):
        r = audit(os.path.join(FIXTURES, "tw-next-undeclared"))
        found = ids(r)
        self.assertIn("RASTER_DARK_ON_TRANSPARENT", found)
        self.assertIn("RASTER_WHITE_BG", found)

    def test_no_images_flag_skips_pixels(self):
        r = audit(os.path.join(FIXTURES, "tw-next-undeclared"), "--no-images")
        self.assertNotIn("RASTER_DARK_ON_TRANSPARENT", ids(r))
        self.assertEqual(r["counters"].get("raster_files_checked", 0), 0)


class WalkTests(unittest.TestCase):
    def test_vendored_and_excluded_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, "site")
            shutil.copytree(os.path.join(FIXTURES, "ld-undeclared"), site)
            for d in ("node_modules/pkg", "dist", "generated"):
                os.makedirs(os.path.join(site, d))
                with open(os.path.join(site, d, "x.css"), "w") as fh:
                    fh.write(":root { color-scheme: light dark; }\n")
            r = audit(site, "--exclude", "generated")
            self.assertEqual(r["facts"]["css_color_scheme"], [],
                             "declarations inside node_modules/, dist/ or --exclude dirs must not count")
            self.assertFalse(r["verdict"]["static_dark_declaration"])


class CliTests(unittest.TestCase):
    def test_markdown_report_has_core_sections(self):
        out = run(os.path.join(FIXTURES, "declared-incomplete")).stdout
        for heading in ("## Verdict", "## Declarations", "## Dark-mode mechanisms", "## Color tokenization", "## Findings"):
            self.assertIn(heading, out)

    def test_fail_on_exit_codes(self):
        self.assertEqual(run(os.path.join(FIXTURES, "good"), "--fail-on", "low").returncode, 0)
        self.assertEqual(run(os.path.join(FIXTURES, "declared-incomplete"), "--fail-on", "high").returncode, 1)
        self.assertEqual(run(os.path.join(FIXTURES, "declared-incomplete")).returncode, 0,
                         "without --fail-on the audit is informational and exits 0")

    def test_bad_path_is_usage_error(self):
        self.assertEqual(run(os.path.join(FIXTURES, "does-not-exist")).returncode, 2)

    def test_version_and_json_metadata(self):
        v = subprocess.run([sys.executable, "-I", AUDIT, "--version"], capture_output=True, text=True).stdout.strip()
        r = audit(os.path.join(FIXTURES, "good"))
        self.assertTrue(v.endswith(r["version"]))
        self.assertEqual(r["tool"], "adaptive-dark-mode/audit.py")


if __name__ == "__main__":
    unittest.main()
