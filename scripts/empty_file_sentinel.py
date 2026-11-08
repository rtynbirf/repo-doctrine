#!/usr/bin/env python3
# Волна ×6 · 6-D · repo-doctrine#34 — T25 «Сентинел пустых файлов».
# CI-гейт: в репе нет файлов 0 байт. Урок uace-pml: закоммиченный ZIP нулевой
# длины (md5 d41d8cd9…) не видит ни линтер, ни пломба — пломба честно хеширует
# пустоту. Сентинел видит.
# Граница честности: служебные пустые файлы (.gitkeep, .nojekyll) — в белом
# списке; каталог .git не сканируется. stdlib-only, офлайн, 3.10+.
import argparse, os, sys

MANIFEST_REF = "repo-doctrine#34"
DEFAULT_ALLOW = ".gitkeep,.nojekyll"
SKIP_DIRS = (".git",)


def scan(root, allow):
    """Вернуть (отсортированный список пустых файлов относительно root, сколько файлов пройдено)."""
    empty, walked = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            walked += 1
            if name in allow:
                continue
            try:
                size = os.path.getsize(path)
            except OSError as e:
                print("SENTINEL: не удалось прочитать размер %s: %s" % (path, e))
                sys.exit(2)
            if size == 0:
                empty.append(os.path.relpath(path, root).replace(os.sep, "/"))
    return sorted(empty), walked


def main():
    ap = argparse.ArgumentParser(
        description="Сентинел пустых файлов — CI-гейт «в репе нет файлов 0 байт» (%s)" % MANIFEST_REF)
    ap.add_argument("--root", default=".", help="каталог скана (по умолчанию — текущий)")
    ap.add_argument("--allow", default=DEFAULT_ALLOW,
                    help="имена файлов, пустота которых легальна, через запятую")
    a = ap.parse_args()
    allow = tuple(s.strip() for s in a.allow.split(",") if s.strip())
    empty, walked = scan(a.root, allow)
    if empty:
        print("SENTINEL: НАРУШЕНИЕ — пустых файлов: %d (белый список: %s):" % (len(empty), a.allow))
        for p in empty:
            print(" - %s (0 байт)" % p)
        print("Пустой файл — тиходействующий косяк: его не видит ни линтер, ни пломба. Удали или наполни.")
        sys.exit(1)
    print("SENTINEL: OK — пустых файлов нет (пройдено %d, белый список: %s)." % (walked, a.allow))


if __name__ == "__main__":
    main()
