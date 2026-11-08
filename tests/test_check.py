# SPDX-License-Identifier: MIT
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.check import check, main


class RepositoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.put("README.md", "# Workbook\n\n[Drill](labs/core.md#cs01-network-isolation)\n")
        self.put("labs/core.md", "# Core\n\n## CS01 Network isolation\n")
        self.put("preparation/STUDY-PATH.md", "# Study path\n\n| CS01 | Networking |\n")

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_links_anchors_and_json(self):
        self.put("solutions/two words.md", "# Answer & `Pod`\n\n## Check\n\n## Check\n")
        self.put("README.md", """# Workbook
[Solution](solutions/two%20words.md#answer--pod)
[Duplicate heading](<solutions/two words.md#check-1>)
[This heading](#workbook)
[Web](https://example.invalid/missing)
[Secure web](http://example.invalid/missing)
[Contact](mailto:example@example.invalid)
""")
        self.put("labs/fixtures/profile.json", '{"defaultAction": "SCMP_ACT_ALLOW"}\n')
        self.put("labs/fixtures/events.jsonl", '{"status": 200}\n{"status": 403}\n')
        self.assertEqual(check(self.root), [])

    def test_missing_local_target(self):
        self.put("README.md", "[Missing](labs/missing.md)\n")
        self.assertTrue(any("missing target" in error for error in check(self.root)))

    def test_infrastructure_guides_are_checked(self):
        self.put("infrastructure/local/README.md", "[Missing](missing.md)\n")
        self.assertTrue(any("infrastructure/local/README.md" in error for error in check(self.root)))

    def test_missing_anchor(self):
        self.put("README.md", "[Missing](labs/core.md#not-a-heading)\n")
        self.assertTrue(any("missing anchor" in error for error in check(self.root)))

    def test_absolute_outside_and_private_targets_are_rejected(self):
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        self.put("work/private.md", "# Private\n")
        self.put("README.md", f"[Absolute]({outside})\n[Escape](../outside.md)\n[Private](work/private.md)\n")
        errors = check(self.root)
        self.assertEqual(len(errors), 3, errors)
        self.assertTrue(any("absolute" in error for error in errors))
        self.assertTrue(any("outside" in error for error in errors))
        self.assertTrue(any("private" in error for error in errors))

    def test_symlink_cannot_escape_repository(self):
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        (self.root / "outside.md").symlink_to(outside)
        self.put("README.md", "[Escape](outside.md)\n")
        self.assertTrue(any("outside" in error for error in check(self.root)))

    def test_hidden_directory_is_not_a_public_target(self):
        self.put("labs/.private/note.md", "# Private\n")
        self.put("README.md", "[Private](labs/.private/note.md#private)\n")
        self.assertTrue(any("private" in error for error in check(self.root)))

    def test_hidden_directory_targets_preserve_public_dot_paths(self):
        self.put(".cache/note.md", "# Private\n")
        self.put("labs/.private/note.md", "# Private\n")
        self.put(".github/workflows/check.yml", "name: Checks\n")
        self.put(".gitignore", "/work/\n")
        self.put("README.md", "[Private](.cache/)\n[Nested](labs/.private/)\n[Workflows](.github/)\n[Ignore](.gitignore)\n")
        errors = check(self.root)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all("private local link" in error for error in errors))

    def test_fenced_and_inline_code_are_ignored(self):
        self.put("README.md", """# Workbook
```markdown
[Not a link](missing.md)
## CS99 Not a drill
```
~~~~text
[Not a link](missing.md)
~~~
~~~~
Use `[Not a link](missing.md)` as an example.
""")
        self.assertEqual(check(self.root), [])

    def test_unclosed_fence_fails(self):
        self.put("README.md", "# Workbook\n\n```sh\ntrue\n")
        self.assertTrue(any("unclosed fence" in error for error in check(self.root)))

    def test_duplicate_drill_ids_fail(self):
        self.put("labs/duplicate.md", "## CS01 Another exercise\n")
        self.assertTrue(any("duplicate drill CS01" in error for error in check(self.root)))

    def test_study_path_must_cover_new_drill(self):
        self.put("labs/extra.md", "## SH05 Host firewall\n")
        self.assertTrue(any("SH05 missing from study path" in error for error in check(self.root)))

    def test_study_path_cannot_invent_a_drill(self):
        self.put("preparation/STUDY-PATH.md", "CS01\nSC99\n")
        self.assertTrue(any("unknown drill SC99" in error for error in check(self.root)))

    def test_compatibility_map_cannot_omit_or_invent_drills(self):
        self.put("preparation/COMPATIBILITY.md", "# Compatibility\n\n| SC99 | Local |\n")
        errors = check(self.root)
        self.assertTrue(any("CS01 missing from compatibility map" in error for error in errors))
        self.assertTrue(any("unknown drill SC99" in error for error in errors))
        self.put("preparation/COMPATIBILITY.md", "# Compatibility\n\n| CS01 | Local |\n")
        self.assertEqual(check(self.root), [])

    def test_malformed_json_and_jsonl_fail_with_locations(self):
        self.put("labs/fixtures/profile.json", '{"broken": }')
        self.put("labs/fixtures/events.jsonl", '{"valid": true}\nnot json\n')
        errors = check(self.root)
        self.assertTrue(any("profile.json" in error for error in errors))
        self.assertTrue(any("events.jsonl:2" in error for error in errors))

    def test_non_json_constants_and_blank_jsonl_lines_fail(self):
        self.put("labs/fixtures/profile.json", '{"value": NaN}')
        self.put("labs/fixtures/events.jsonl", '{}\n\n')
        self.assertEqual(len(check(self.root)), 2)

    def test_local_and_hidden_work_is_not_scanned(self):
        for prefix in ["work", ".git", ".cache", "labs/.private"]:
            self.put(f"{prefix}/broken.md", "[Broken](missing.md)\n```\n")
            self.put(f"{prefix}/broken.json", "not json")
        self.assertEqual(check(self.root), [])

    def test_main_reports_failure_and_scope(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(self.root), 0)
        self.assertIn("YAML", output.getvalue())
        self.assertIn("runtime", output.getvalue())
        self.put("README.md", "[Broken](missing.md)\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.root), 1)

    def test_cli_uses_script_root_and_failure_exit_status(self):
        script = self.root / "scripts/check.py"
        script.parent.mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts/check.py", script)
        result = subprocess.run([sys.executable, str(script)], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.put("README.md", "[Broken](missing.md)\n")
        result = subprocess.run([sys.executable, str(script)], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
