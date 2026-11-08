#!/usr/bin/env python3
# Волна ×3 · W3-E · Идемпотентность-храповик (предложение repo-doctrine#31).
# canonical_check.py — три команды:
#   scan      — ищет в .github/workflows вызовы мутаторов из mutations.yaml (скрипт + call)
#               без --dry-run и без метки прохода apply (--apply) и краснит прогон (файл:строка);
#   demo      — контрольный демо-мутатор «+1 строка бейджа», идемпотентный по дате:
#               первый дифф +1 строка, повторный — 0 строк;
#   verify    — цепочки dry-run → apply → dry-run-2 в реестре; второй дифф обязан быть пустым.
# stdlib, 3.11+. Поля реестра заполняются один раз — храповик не откатывается назад.
import argparse, os, re, sys
from datetime import date, datetime, timezone

REGISTRY = "mutations.yaml"
BADGE = "demo-badge.md"
NAME = "demo-badge-append"


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def load_registry(path=REGISTRY):
    mutators, cur = [], None
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if s.startswith("  - "):
            cur = {}
            mutators.append(cur)
            k, _, v = s[4:].partition(": ")
            cur[k] = _unquote(v)
        elif s.startswith("    ") and cur is not None and ": " in s:
            k, _, v = s.strip().partition(": ")
            cur[k] = _unquote(v)
    return mutators


def _rewrite(name, field, value, only_empty):
    out, cur, done = [], False, False
    for ln in open(REGISTRY, encoding="utf-8"):
        s = ln.rstrip("\n")
        if s.startswith("  - "):
            cur = s[4:].partition(": ")[2].strip() == name
        m = re.match(r"^(\s+)(\w+): (.*)$", s) if cur else None
        if m and m.group(2) == field and not done:
            if only_empty and m.group(3).strip() not in ('""', "''", ""):
                out.append(ln)
                continue
            out.append("%s%s: %s\n" % (m.group(1), field, value))
            done = True
            continue
        out.append(ln)
    if done:
        with open(REGISTRY, "w", encoding="utf-8") as f:
            f.writelines(out)
    return done


def badge_line():
    return "- [demo-badge-append] W3-E идемпотентность, пломба %s" % date.today().isoformat()


def demo(mode):
    line = badge_line()
    text = open(BADGE, encoding="utf-8").read() if os.path.exists(BADGE) else ""
    present = line in text
    diff = 0 if present else 1
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    applied = any(m.get("name") == NAME and m.get("apply") for m in load_registry())
    if mode == "dry-run":
        print("DRY-RUN %s: дифф: %d строк (%s)" %
              (NAME, diff, "бейдж уже стоит" if present else "будет добавлена 1 строка бейджа"))
        if not present:
            print("+" + line)
        _rewrite(NAME, "dry_run_2" if applied else "dry_run_1",
                 '"%s дифф: %d строк"' % (stamp, diff), only_empty=True)
    else:
        if present:
            print("APPLY %s: бейдж уже стоит — повтор без побочных эффектов." % NAME)
        else:
            with open(BADGE, "a", encoding="utf-8") as f:
                if text and not text.endswith("\n"):
                    f.write("\n")
                f.write(line + "\n")
            print("APPLY %s: добавлена 1 строка бейджа." % NAME)
        _rewrite(NAME, "applied", "true", only_empty=False)
        _rewrite(NAME, "apply", '"%s apply"' % stamp, only_empty=True)


def scan_lines(workdir):
    muts = [m for m in load_registry() if m.get("script") and m.get("call")]
    bad = []
    if not os.path.isdir(workdir):
        return bad
    for wf in sorted(os.listdir(workdir)):
        p = os.path.join(workdir, wf)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                if any(m["script"] in line and m["call"] in line for m in muts):
                    if "--dry-run" not in line and "--apply" not in line:
                        bad.append("%s:%d: мутатор без --dry-run/--apply: %s" % (p, n, s))
    return bad


def cmd_scan(selftest_mode):
    workdir = ".github/workflows"
    tmp = None
    if selftest_mode:
        os.makedirs(workdir, exist_ok=True)
        tmp = os.path.join(workdir, "_selftest-scan.yml")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("name: scan-selftest\njobs:\n  probe:\n    steps:\n"
                    "      - run: python3 scripts/canonical_check.py demo\n")
    try:
        bad = scan_lines(workdir)
        if selftest_mode:
            caught = any(b.startswith(tmp + ":") for b in bad)
            print("SCAN-SELFTEST: %s" % ("нарушение найдено, файл и строка показаны" if caught
                                         else "САМОТЕСТ НЕ ПРОШЁЛ"))
            if not caught:
                sys.exit(1)
            bad = [b for b in bad if not b.startswith(tmp + ":")]
        if bad:
            print("SCAN: мутаторы без --dry-run/--apply:")
            for b in bad:
                print(" -", b)
            sys.exit(1)
        print("SCAN: OK — нарушений нет.")
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def cmd_verify():
    muts = load_registry()
    problems = []
    if not muts:
        problems.append("реестр mutators пуст")
    for m in muts:
        for k in ("name", "script", "target"):
            if not m.get(k):
                problems.append("мутатор без поля %s: %r" % (k, m.get("name")))
    applied = [m for m in muts if m.get("applied") == "true"]
    for m in applied:
        if not m.get("dry_run_1"):
            problems.append("нет dry_run_1: %s" % m.get("name"))
        if not m.get("apply"):
            problems.append("нет apply: %s" % m.get("name"))
        if "0 строк" not in m.get("dry_run_2", ""):
            problems.append("второй дифф не пуст у %s: %s" % (m.get("name"), m.get("dry_run_2") or "нет записи"))
    if os.path.exists(BADGE):
        lines = [l for l in open(BADGE, encoding="utf-8").read().splitlines() if l.strip()]
        if len(lines) != len(set(lines)):
            problems.append("demo-badge.md: дубликаты строк бейджа")
    if problems:
        print("ХРАПОВИК: НАРУШЕНИЯ:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    if applied:
        print("ХРАПОВИК: OK — применённых мутаторов: %d, вторые диффы пусты." % len(applied))
    else:
        print("ХРАПОВИК: OK — применённых мутаторов пока нет, реестр валиден (ждёт первого прогона).")


def main():
    ap = argparse.ArgumentParser(description="Идемпотентность-храповик (repo-doctrine#31)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    g = d.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    s = sub.add_parser("scan")
    s.add_argument("--selftest", action="store_true")
    sub.add_parser("verify")
    a = ap.parse_args()
    if a.cmd == "demo":
        demo("dry-run" if a.dry_run else "apply")
    elif a.cmd == "scan":
        cmd_scan(a.selftest)
    else:
        cmd_verify()


if __name__ == "__main__":
    main()
