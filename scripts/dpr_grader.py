#!/usr/bin/env python3
"""ДПР-грейдер (repo-doctrine#16): трёхкоридорный конвейер Dependabot.

Коридоры (сингулярный ход issue #16): A — patch/minor + CI 🟢 → автопилот
(approve + auto-merge); A-hold — ждёт CI; B — major/нестандартный заголовок →
сводка рисков в ДПР; C — геномные/конституционные → конверт крови, грейдер
сам не мержит никогда. Режимы: --selftest (без сети), --plan --input prs.json,
--run --repo owner/name (мутации только при --apply true). stdlib, Python 3.11.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = "wave3-dpr-grader"
RE_BUMP = re.compile(r"Bump\s+(?P<pkg>\S+)\s+from\s+(?P<frm>\S+)\s+to\s+(?P<to>\S+)")
RE_GENOME = re.compile(r"cell-swarm|doctrine|геном|конституц|канон|blood", re.IGNORECASE)

def bump_level(frm: str, to: str) -> str:
    """major/minor/patch/unknown по числовым компонентам версий."""
    def core(v: str) -> list[int] | None:
        out = []
        for part in re.split(r"[.+-]", v.lstrip("vV"))[:3]:
            m = re.match(r"\d+", part)
            if not m:
                return None
            out.append(int(m.group(0)))
        return (out + [0, 0, 0])[:3]

    a, b = core(frm), core(to)
    if a is None or b is None:
        return "unknown"
    if a[0] != b[0]:
        return "major"
    if a[1] != b[1]:
        return "minor"
    if a[2] != b[2]:
        return "patch"
    return "unknown"

def classify(pr: dict) -> dict:
    """pr: {number,title,labels,head_ref,ci_green} → вердикт коридора."""
    title = pr.get("title") or ""
    hay = " ".join([title, pr.get("head_ref") or "", " ".join(pr.get("labels") or [])])
    if RE_GENOME.search(hay):
        return {**pr, "package": title[:60] or "-", "bump": "genome", "corridor": "C",
                "action": "конверт крови: коммент в ДПР, сам не мержит"}
    m = RE_BUMP.search(title)
    if not m:
        return {**pr, "package": title[:60] or "-", "bump": "unknown", "corridor": "B",
                "action": "сводка рисков (нестандартный заголовок)"}
    level = bump_level(m.group("frm"), m.group("to"))
    verdict = {**pr, "package": m.group("pkg"), "bump": level,
               "from": m.group("frm"), "to": m.group("to")}
    if level in ("major", "unknown"):
        verdict["corridor"], verdict["action"] = "B", "сводка рисков в ДПР"
    elif pr.get("ci_green") is True:
        verdict["corridor"], verdict["action"] = "A", "approve + auto-merge (squash)"
    else:
        verdict["corridor"], verdict["action"] = "A-hold", "ждёт CI 🟢, потом автопилот"
    return verdict

def risk_summary(pr: dict, files: list[str] | None = None) -> str:
    """Сводка рисков коридора B: что ломается, где используется."""
    v = classify(pr)
    files_cell = (", ".join(f"`{f}`" for f in (files or []))
                  or "(список files API — при живом прогоне)")
    return "\n".join([
        "## 🛢 Сводка рисков (коридор B)", "",
        "| поле | значение |", "|---|---|",
        f"| пакет | `{v['package']}` |",
        f"| версии | {pr.get('from', '?')} → {pr.get('to', '?')} |",
        f"| уровень | {v['bump']} |",
        "| что ломается | (заполняется роям при разборе changelog/breaking-notes) |",
        "| где используется | (по геному репо — заполняется скриптом при первом прогоне) |",
        f"| файлы ДПР | {files_cell} |", "",
        "Решение — осознанное: рой читает сводку и отвечает merge/закрытием.",
        "Грейдер сам major не мержит — только раскладывает факты.",
    ])

def blood_envelope(pr: dict) -> str:
    """Конверт крови коридора C: факт без решения."""
    return "\n".join([
        "## 🩸 Конверт крови (коридор C)", "",
        f"ДПР #{pr.get('number')} распознан как геномный/конституционный.",
        "Грейдер сам не мержит — никогда. Факт передаётся рою:",
        "решение по правилу дополнения (append, не перезапись).",
    ])

def http(url: str, token: str | None, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": UA,
               **({"Content-Type": "application/json"} if data else {}),
               **({"Authorization": f"Bearer {token}"} if token else {})}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")

def collect_verdicts(repo: str, token: str | None) -> list[dict]:
    _, prs = http(f"{API}/repos/{repo}/pulls?state=open&per_page=100", token)
    out = []
    for pr in prs or []:
        sha, green = (pr.get("head") or {}).get("sha"), None
        if sha:
            code, st = http(f"{API}/repos/{repo}/commits/{sha}/status", token)
            if code == 200:
                green = {"success": True, "failure": False, "error": False}.get(st.get("state"))
        out.append(classify({"number": pr.get("number"), "title": pr.get("title") or "",
                             "labels": [l.get("name") for l in pr.get("labels") or []],
                             "head_ref": (pr.get("head") or {}).get("ref") or "",
                             "ci_green": green}))
    return out

def run(repo: str, apply: bool, summary: str | None) -> int:
    token = os.environ.get("GITHUB_TOKEN") or None
    verdicts = collect_verdicts(repo, token)
    lines = ["## 🌊 ДПР-грейдер · коридоры A/B/C", "",
             f"Репо: `{repo}` · режим: {'ПРИМЕНЕНИЕ' if apply else 'сухой прогон'}", ""]
    for v in verdicts:
        n = v["number"]
        lines.append(f"- ДПР #{n} `{v['package']}` → коридор **{v['corridor']}**: {v['action']}")
        if v["corridor"] == "A" and apply:
            http(f"{API}/repos/{repo}/pulls/{n}/reviews", token, "POST", {"event": "APPROVE"})
            code, _ = http(f"{API}/repos/{repo}/pulls/{n}/auto-merge", token, "PUT",
                           {"merge_method": "squash"})
            if code >= 300:
                lines.append(f"  - ⚠ auto-merge не включён (HTTP {code}); approve отправлен")
        elif v["corridor"] == "B":
            code, fl = http(f"{API}/repos/{repo}/pulls/{n}/files?per_page=15", token)
            files = [f.get("filename", "") for f in (fl or [])] if code == 200 else []
            if apply:
                http(f"{API}/repos/{repo}/issues/{n}/comments", token, "POST",
                     {"body": risk_summary(v, files)})
            lines.append("  - сводка рисков построена (постится при --apply true)")
        elif v["corridor"] == "C" and apply:
            http(f"{API}/repos/{repo}/issues/{n}/comments", token, "POST",
                 {"body": blood_envelope(v)})
    if not verdicts:
        lines.append("- открытых ДПР нет — конвейер простаивает 🟢")
    report = "\n".join(lines) + "\n"
    (open(summary, "a", encoding="utf-8") if summary else sys.stdout).write(report)
    return 0

FIXTURES = [
    ({"number": 1, "title": "Bump requests from 2.31.0 to 2.32.3 in /api", "labels": ["dependencies"], "head_ref": "dependabot/pip/api/requests", "ci_green": True}, "A"),
    ({"number": 2, "title": "Bump numpy from 1.24.0 to 2.1.0", "labels": ["dependencies"], "head_ref": "d/numpy", "ci_green": True}, "B"),
    ({"number": 3, "title": "Bump cell-swarm genome manifest to v3", "labels": ["dependencies"], "head_ref": "genome/blood", "ci_green": True}, "C"),
    ({"number": 4, "title": "Bump flask from 3.0.0 to 3.0.9", "labels": ["dependencies"], "head_ref": "d/flask", "ci_green": None}, "A-hold"),
    ({"number": 5, "title": "Update doctrine канон", "labels": [], "head_ref": "canon/main", "ci_green": True}, "C"),
    ({"number": 6, "title": "Bump black from 24.1.0 to 24.2.0", "labels": ["dependencies"], "head_ref": "d/black", "ci_green": False}, "A-hold"),
]

def selftest() -> int:
    ok = True
    for pr, expected in FIXTURES:
        got = classify(pr)["corridor"]
        ok = ok and got == expected
        print(f"{'✅' if got == expected else '🔴'} fixture #{pr['number']}: {got} (ожидалось {expected})")
    txt = risk_summary(FIXTURES[1][0])
    ok = ok and "(заполняется роям" in txt and "не мержит" in txt
    ok = ok and "не мержит" in blood_envelope(FIXTURES[2][0])
    print("✅ selftest PASS" if ok else "🔴 selftest FAIL")
    return 0 if ok else 1

def main() -> int:
    ap = argparse.ArgumentParser(description="ДПР-грейдер: коридоры A/B/C")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--plan", action="store_true", help="грейд JSON-массива ДПР из --input")
    ap.add_argument("--run", action="store_true", help="живой обход открытых ДПР")
    ap.add_argument("--input", help="файл с JSON-массивом ДПР (для --plan)")
    ap.add_argument("--repo", help="owner/name (для --run)")
    ap.add_argument("--apply", default="false", help="true = применять действия коридоров")
    ap.add_argument("--summary", help="файл для markdown-отчёта (GITHUB_STEP_SUMMARY)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.plan:
        prs = json.load(open(args.input, encoding="utf-8")) if args.input else json.load(sys.stdin)
        if isinstance(prs, dict):
            prs = [prs]
        print(json.dumps({"verdicts": [classify(p) for p in prs]}, ensure_ascii=False, indent=1))
        return 0
    if args.run:
        if not args.repo:
            ap.error("--run требует --repo owner/name")
        return run(args.repo, args.apply.lower() == "true", args.summary)
    ap.error("укажите режим: --selftest | --plan | --run")
    return 2

if __name__ == "__main__":
    sys.exit(main())
