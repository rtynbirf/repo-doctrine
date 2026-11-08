#!/usr/bin/env python3
# Волна ×6 · 6-D · тесты T17 «Манифест свежести» (repo-doctrine#24).
# Приёмка issue: красный без пересборки, зелёный после make manifest,
# страж GENERATED на ручную правку. Храповик: тесты только добавляются.
import os, shutil, subprocess, sys, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "manifest_check.py")
MANIFEST = "MANIFEST_SHA256.txt"


def run(root, *args):
    p = subprocess.run([sys.executable, SCRIPT, *args, "--root", root],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def build(root):
    return run(root, "build")


class ManifestFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t17-")

    def w(self, rel, data):
        """Записать файл в тестовом дереве (создав каталоги), без утечек дескрипторов."""
        full = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(data)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_green_after_build(self):
        self.w("README.md", "доктрина\n")
        self.w("scripts/tool.py", "print('x')\n")
        build(self.tmp)
        rc, out = run(self.tmp, "check")
        self.assertEqual(rc, 0, out)
        self.assertIn("ЗЕЛЁНЫЙ", out)

    def test_red_when_stale(self):
        self.w("README.md", "строка v1\n")
        build(self.tmp)
        self.w("README.md", "строка v2 — README изменился\n")
        rc, out = run(self.tmp, "check")
        self.assertEqual(rc, 1, out)
        self.assertIn("устарел", out)
        self.assertIn("README.md", out)

    def test_red_when_file_added(self):
        self.w("a.md", "a\n")
        build(self.tmp)
        self.w("b.md", "новый файл без пересборки\n")
        rc, out = run(self.tmp, "check")
        self.assertEqual(rc, 1, out)
        self.assertIn("+ ", out)  # приговор показывает, что именно появилось

    def test_red_on_manual_edit_header_stripped(self):
        self.w("a.md", "a\n")
        build(self.tmp)
        with open(os.path.join(self.tmp, MANIFEST), encoding="utf-8") as f:
            body = [l for l in f.read().splitlines() if not l.startswith("#")]
        with open(os.path.join(self.tmp, MANIFEST), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        rc, out = run(self.tmp, "check")
        self.assertEqual(rc, 1, out)
        self.assertIn("ручная правка", out)

    def test_manifest_excludes_itself_and_living_files(self):
        self.w("README.md", "r\n")
        self.w("PULSE.md", "живой журнал\n")
        self.w("mutations.yaml", "registry: true\n")
        build(self.tmp)
        rc, out = run(self.tmp, "check")
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.tmp, MANIFEST), encoding="utf-8") as f:
            text = f.read()
        for living in ("PULSE.md", "mutations.yaml", "demo-badge.md"):
            self.assertNotIn("  %s\n" % living, text, "живой файл %s попал в заморозку" % living)
        self.assertNotIn("  %s\n" % MANIFEST, text)

    def test_deterministic(self):
        self.w("a.md", "a\n")
        self.w("sub/b.py", "b\n")
        build(self.tmp)
        with open(os.path.join(self.tmp, MANIFEST), encoding="utf-8") as f:
            first = f.read()
        build(self.tmp)
        with open(os.path.join(self.tmp, MANIFEST), encoding="utf-8") as f:
            self.assertEqual(first, f.read())
        self.assertIn("  sub/b.py", first)  # вложенные пути с сортировкой


if __name__ == "__main__":
    unittest.main()
