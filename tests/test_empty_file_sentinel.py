#!/usr/bin/env python3
# Волна ×6 · 6-D · тесты T25 «Сентинел пустых файлов» (repo-doctrine#34).
# Храповик: тесты только добавляются. stdlib-only, офлайн.
import os, subprocess, sys, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "empty_file_sentinel.py")


def run(root, extra=()):
    p = subprocess.run([sys.executable, SCRIPT, "--root", root, *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def touch(path, bytes_count=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * bytes_count)


class EmptyFileSentinelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t25-")

    def test_green_no_empty_files(self):
        touch(os.path.join(self.tmp, "a.md"), 10)
        touch(os.path.join(self.tmp, "sub", "b.txt"), 1)
        rc, out = run(self.tmp)
        self.assertEqual(rc, 0, out)
        self.assertIn("SENTINEL: OK", out)

    def test_red_empty_file_listed(self):
        bad = os.path.join(self.tmp, "broken.zip")
        touch(bad)  # 0 байт
        rc, out = run(self.tmp)
        self.assertEqual(rc, 1, out)
        self.assertIn("НАРУШЕНИЕ", out)
        self.assertIn("broken.zip", out)

    def test_gitkeep_and_nojekyll_are_legal(self):
        touch(os.path.join(self.tmp, ".gitkeep"))
        touch(os.path.join(self.tmp, "docs", ".nojekyll"))
        rc, out = run(self.tmp)
        self.assertEqual(rc, 0, out)
        self.assertIn("SENTINEL: OK", out)

    def test_git_dir_not_scanned(self):
        os.makedirs(os.path.join(self.tmp, ".git", "objects"))
        touch(os.path.join(self.tmp, ".git", "objects", "empty"))
        rc, out = run(self.tmp)
        self.assertEqual(rc, 0, out)

    def test_custom_allowlist(self):
        touch(os.path.join(self.tmp, "stub"))
        rc, out = run(self.tmp, ["--allow", "stub"])
        self.assertEqual(rc, 0, out)
        # а без белого списка тот же файл — красный
        rc2, out2 = run(self.tmp)
        self.assertEqual(rc2, 1, out2)
        self.assertIn("stub", out2)


if __name__ == "__main__":
    unittest.main()
