#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Линтер дверей (repo-doctrine#30): schedule без workflow_dispatch = NO-DOOR.

Принцип §2: у каждого schedule-воркфлоу есть ручная дверь. Линтер только
ЧИТАЕТ и докладывает; append-only — при непустом вердикте заводится НОВОЕ
issue в repo-doctrine на каждый проход. Бюджет API: 1 список репо на страницу
+ 1 contents-вызов на репо, тексты YAML по raw-ссылке вне core-квоты.
Парсер on: строковый (stdlib). Контракт нуля ложных срабатываний: формы
`on: [schedule, workflow_dispatch]`, `on: {schedule: …, workflow_dispatch:
{inputs: …}}` и блочная распознаются как «дверь есть» — selftest (--selftest).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = "wave3-door-lint"
KEY_RE = re.compile(r'^(\s*)["\']?on["\']?\s*:\s*(.*?)\s*$')
SCHED_RE = re.compile(r"(?<![A-Za-z0-9_-])schedule(?![A-Za-z0-9_-])")
DOOR_RE = re.compile(r"(?<![A-Za-z0-9_-])workflow_dispatch(?![A-Za-z0-9_-])")
CRON_RE = re.compile(r"cron\s*:\s*['\"]([^'\"]+)['\"]")
CRON_OK = re.compile(r"[\d*/,-]+\s+[\d*/,-]+\s+[\d*/,-]+\s+[\d*/,-]+\s+[\d*/,-]+")

def http(url: str, token: str | None, method: str = "GET", payload: dict | None = None,
         accept: str = "application/vnd.github+json"):
    # кириллические ветки/пути в URL: кодируем путь (ASCII-safe), иначе http.client падает на encode
    url = urllib.parse.quote(url, safe=":/?&=%#[]@!$'()*+,;~-._")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", UA)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if accept.endswith("json") else body)
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError) as e:
        print(f"  сеть: {e}")
        return 0, ""

def parse_doors(text: str) -> tuple[bool, bool, list[str]]:
    """(есть schedule, есть дверь, кроны) по сырому тексту YAML."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = KEY_RE.match(line)
        if not m:
            continue
        indent, rest = len(m.group(1)), re.sub(r"#.*$", "", m.group(2) or "").strip()
        if rest:  # скалярная/flow-форма: on: [schedule, workflow_dispatch] / {…}
            return (bool(SCHED_RE.search(rest)), bool(DOOR_RE.search(rest)),
                    CRON_RE.findall(rest))
        sched, door, crons = False, False, []  # блочная форма
        for raw in lines[i + 1:]:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if len(raw) - len(raw.lstrip(" ")) <= indent:
                break  # вышли из блока on: (например, в jobs:)
            body = re.sub(r"#.*$", "", raw).strip()
            sched = sched or bool(SCHED_RE.search(body))
            door = door or bool(DOOR_RE.search(body))
            crons += CRON_RE.findall(body)
        return sched, door, crons
    return False, False, []

def fetch_repos(owner: str, token: str | None) -> list[dict]:
    out, page = [], 1
    while True:
        code, data = http(f"{API}/users/{owner}/repos?per_page=100&page={page}", token)
        if code != 200 or not isinstance(data, list):
            break
        out += data
        if len(data) < 100:
            break
        page += 1
    return out

def lint(owner: str, token: str | None) -> tuple[list[dict], dict]:
    rows, stats = [], {"repos": 0, "files": 0, "schedule": 0, "door": 0}
    for repo in fetch_repos(owner, token):
        name, branch = repo.get("name", ""), repo.get("default_branch") or "main"
        stats["repos"] += 1
        code, items = http(f"{API}/repos/{owner}/{name}/contents/.github/workflows?ref={branch}", token)
        if code != 200 or not isinstance(items, list):
            continue
        for item in items:
            path = item.get("path", "")
            if not re.search(r"\.(ya?ml)$", path or ""):
                continue
            stats["files"] += 1
            url = item.get("download_url") or f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{path}"
            code, text = http(url, token, accept="text/plain")
            if code != 200 or not isinstance(text, str):
                continue
            sched, door, crons = parse_doors(text)
            stats["schedule"] += int(sched)
            stats["door"] += int(sched and door)
            if sched and not door:
                rows.append({"repo": name, "file": path, "crons": crons})
    return rows, stats

def fragments(rows: list[dict]) -> str:
    """Слот «генератор патчей»: готовые YAML-фрагменты для ответственной волны."""
    out = ["## Слот «генератор патчей» — готовые фрагменты", ""]
    for r in rows:
        crons = [c for c in r["crons"] if CRON_OK.fullmatch(c)]
        out += [f"### `{r['repo']}` · `{r['file']}`", "", "```yaml",
                "# добавить строку `  workflow_dispatch:` в блок on:",
                "on:", "  schedule:"]
        if crons:
            for c in crons:
                out.append(f"    - cron: '{c}'")
        else:
            out.append("    - cron: '(крон из существующего schedule в файле)'")
        out += ["  workflow_dispatch:", "```", ""]
    return "\n".join(out)

def open_issue(owner: str, token: str | None, rows: list[dict], run_number: str) -> str:
    table = ["| репо | файл | cron |", "|---|---|---|"]
    table += [f"| {r['repo']} | `{r['file']}` | {', '.join(r['crons']) or '—'} |" for r in rows]
    body = "\n".join([
        f"Вердикт **NO-DOOR: {len(rows)}** schedule-воркфлоу без workflow_dispatch (прогон {run_number}).",
        "Число в отчёте = число ручных проверок ±0; после волны исправлений список пуст.", "",
        *table, "", fragments(rows),
        "Применение — отдельным append-коммитом ответственной волны. Линтер только читает и докладывает.",
        "Append-only: новое issue на каждый полный проход, старые не правятся.",
    ])
    code, data = http(f"{API}/repos/{owner}/repo-doctrine/issues", token, "POST",
                      {"title": f"🚪 NO-DOOR: {len(rows)} schedule-воркфлоу без двери · прогон {run_number}",
                       "body": body})
    return (data or {}).get("html_url", "") if code in (200, 201) else f"(issue не создан: HTTP {code})"

def write_summary(path: str | None, rows: list[dict], stats: dict, issue_url: str) -> None:
    lines = ["## 🚪 Линтер дверей workflow_dispatch", "",
             f"Репо: {stats['repos']} · воркфлоу: {stats['files']} · "
             f"с schedule: {stats['schedule']} · с дверью: {stats['door']}", ""]
    if rows:
        lines += [f"Вердикт: NO-DOOR × {len(rows)}." + (f" [Issue]({issue_url})" if issue_url else "")]
    else:
        lines += ["✅ Все двери на месте: ни одного schedule без workflow_dispatch."]
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text, end="")

FIXTURES = [
    ("on: [schedule, workflow_dispatch]\njobs:\n  a:\n    runs-on: ubuntu-latest\n", True, True),
    ("on:\n  schedule:\n    - cron: '7 2 * * *'\n  workflow_dispatch:\n    inputs:\n      go:\n        description: x\n", True, True),
    ("on: {schedule: [{cron: '3 6 * * 1'}], workflow_dispatch: {inputs: {go: {}}}}\n", True, True),
    ("on:\n  schedule:\n    - cron: '17 4 * * *'\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n", True, False),
    ("on: push\njobs: {}\n", False, False),
    ("on:\n  push:\njobs:\n  a:\n    steps:\n      - run: |\n          echo workflow_dispatch\n", False, False),
]

def selftest() -> int:
    ok = True
    for idx, (text, sched, door) in enumerate(FIXTURES, 1):
        got_s, got_d, _ = parse_doors(text)
        good = got_s == sched and got_d == door
        ok = ok and good
        print(f"{'✅' if good else '🔴'} fixture {idx}: schedule={got_s} door={got_d}")
    print(("✅ selftest PASS" if ok else "🔴 selftest FAIL"))
    return 0 if ok else 1

def main() -> int:
    ap = argparse.ArgumentParser(description="Линтер дверей workflow_dispatch (issue #30)")
    ap.add_argument("--owner", default="rtynbirf")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--apply-issue", default="true", help="true = заводить append-issue при NO-DOOR")
    ap.add_argument("--summary", help="файл для markdown-отчёта (GITHUB_STEP_SUMMARY)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    token = os.environ.get("GITHUB_TOKEN") or None
    run_number = os.environ.get("RUN_NUMBER") or "ручной"
    rows, stats = lint(args.owner, token)
    issue_url = ""
    if rows and args.apply_issue.lower() == "true" and token:
        issue_url = open_issue(args.owner, token, rows, run_number)
    write_summary(args.summary, rows, stats, issue_url)
    print(f"NO-DOOR: {len(rows)} · детали: {issue_url or '(issue не заводился)'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
