#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T24 · Пин-дозор аккаунта — еженедельная живая сверка всех uses-SHA (repo-doctrine#33).

Урок волны FIX-2 (2026-11-08): dependabot-волна пронесла фальшивый пин
actions/github-script@3a2844b7 (SHA есть, тега v9.0.0 не соответствует) и
codeql-action@33d7b85 (вообще 404). Находка сделана РУЧНЫМ сканом 35 пар
(action, ref) по 96 workflow 41 репы. Дозор делает то же — машиной, еженедельно.

Три класса вердикта по каждому uses:
  канон        — 40-hex SHA существует в апстриме;
  ЛЕВЫЙ ПИН    — 40-hex, но GET commits/{sha} = 404 (SHA не существует);
  НЕСООТВЕТСТВИЕ — SHA с теговым комментарием #vX.Y.Z, но тег в апстриме
                   указывает на другой коммит (правда комментария != байты пина);
  НЕ-КАНОН     — рефс не 40-hex (@v4, @main) — политика аккаунта: полный SHA.

Итог: одна сводка «пины: N каноничны, M левых/несоответствий, K не-канон»
с пофайловым списком; при M>0 или K>0 — красный маяк и (по флагу) append-only
issue в repo-doctrine. Ритм без шума: 0 проблем = коммита/issue нет.

Токен: секрет W3_PAT (охват 41 репо) или github.token — тогда видны только
публичные репы (приватные выпадут из сверки — дозор честно напишет об этом).

Офлайн-проверка парсера без API:
  python3 scripts/pin_drift_watch.py --selftest
"""
import argparse
import base64
import datetime
import json
import os
import re
import sys
import urllib.request

API = "https://api.github.com"
USES_RE = re.compile(r'^\s*(?:[-]?\s*)uses:\s*([^\s#]+)\s*(?:#\s*(\S+))?', re.M)
HEX40_RE = re.compile(r'^[0-9a-f]{40}$')


def api_get(path, token):
    """GET api.github.com → (dict|None, status). 404/410 → None."""
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        if e.code in (403, 404, 410):
            return None, e.code
        raise


def raw_get(owner, repo, branch, path, token):
    """Файл через raw.githubusercontent.com — не тратит квоту api.github.com."""
    url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, path)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer %s" % token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError:
        return None


def parse_uses(text):
    """Извлечь все uses: owner/repo@ref (+ теговый комментарий). Локальные ./ и docker:// — мимо."""
    out = []
    for m in USES_RE.finditer(text):
        target, tag = m.group(1), m.group(2)
        if target.startswith(("./", "docker://")):
            continue
        if "@" not in target:
            out.append((target, "", tag))
            continue
        repo, ref = target.rsplit("@", 1)
        out.append((repo, ref, tag))
    return out


def list_repos(owner, token):
    """Список неархивных реп владельца. PAT → приватные+публичные, иначе только публичные."""
    data, code = api_get("/user/repos?per_page=100&sort=pushed&type=owner", token)
    if not data:  # нет скоупа/пусто → публичные (дозор честно пометит охват)
        data, code = api_get("/users/%s/repos?per_page=100&sort=pushed" % owner, token)
        if data is None:
            return [], "нет доступа (проверь токен: код %s)" % code
        return [r for r in data if not r.get("archived")], "только ПУБЛИЧНЫЕ репы (github.token не видит приватные — используй W3_PAT)"
    return [r for r in data if not r.get("archived")], ""


def check_ref(repo_full, ref, tag, token, cache):
    """Вердикт по паре (repo, ref): канон / левый / несоответствие / не-канон."""
    key = (repo_full, ref, tag or "")
    if key in cache:
        return cache[key]
    if not HEX40_RE.match(ref):
        cache[key] = "не-канон"
        return cache[key]
    data, code = api_get("/repos/%s/commits/%s" % (repo_full, ref), token)
    if data is None:
        cache[key] = "левый (HTTP %s)" % code
        return cache[key]
    if tag and tag.startswith("v"):
        tdata, _ = api_get("/repos/%s/git/ref/tags/%s" % (repo_full, tag), token)
        if tdata is None:
            cache[key] = "канон (тега %s в апстриме нет)" % tag
            return cache[key]
        obj = tdata["object"]
        sha = obj["sha"]
        if obj["type"] == "tag":
            td, tc = api_get("/repos/%s/git/tags/%s" % (repo_full, sha), token)
            sha = td["object"]["sha"] if td else sha
        if sha != ref:
            cache[key] = "НЕСООТВЕТСТВИЕ (%s -> %s, пин %s)" % (tag, sha[:12], ref[:12])
            return cache[key]
    cache[key] = "канон"
    return cache[key]


def run(owner, token, apply_issue):
    repos, note = list_repos(owner, token)
    cache = {}
    rows, canon = [], 0
    for repo in sorted(repos, key=lambda r: r["name"]):
        full = repo["full_name"]
        branch = repo["default_branch"]
        tree, code = api_get("/repos/%s/git/trees/%s" % (full, branch), token)
        if tree is None:
            rows.append((full, "-", "-", "дерево недоступно (HTTP %s)" % code))
            continue
        wf = [t["path"] for t in tree.get("tree", [])
              if t["path"].startswith(".github/workflows/") and t["path"].endswith((".yml", ".yaml"))]
        for path in sorted(wf):
            text = raw_get(owner, repo["name"], branch, path, token)
            if text is None:
                rows.append((full, path, "-", "файл не прочитан"))
                continue
            for action_repo, ref, tag in parse_uses(text):
                if not ref:
                    rows.append((full, path, action_repo, "без рефса"))
                    continue
                verdict = check_ref(action_repo, ref, tag, token, cache)
                if verdict == "канон":
                    canon += 1
                else:
                    rows.append((full, path, "%s@%s" % (action_repo, ref[:12]), verdict))
    bad = len(rows)
    summary = "пины: %d каноничны, %d проблемных, реп в сверке %d" % (canon, bad, len(repos))
    if note:
        summary += " · %s" % note
    print(summary)
    for r in rows:
        print("  [%s] %s :: %s :: %s" % r)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("## T24 · Пин-дозор\n\n**%s**\n\n" % summary)
            for r in rows:
                fh.write("- `%s` :: %s :: %s :: %s\n" % r)
    if bad and apply_issue:
        body = "**T24 · пин-дозор: найдены проблемные пины**\n\n%s\n\n| репа | файл | пин | вердикт |\n|---|---|---|---|\n" % summary
        for r in rows:
            body += "| `%s` | `%s` | `%s` | %s |\n" % r
        body += "\n*(append-only сводка по repo-doctrine#33; чинится перепином на канон SHA, не молчаливым удалением)*\n"
        req = urllib.request.Request(API + "/repos/%s/repo-doctrine/issues" % owner,
                                     json.dumps({
                                         "title": "T24 · пин-дозор: %d проблемных пинов (%s)" % (bad, datetime.date.today().isoformat()),
                                         "body": body,
                                         "labels": [],
                                     }).encode("utf-8"), method="POST")
        req.add_header("Authorization", "Bearer %s" % token)
        req.add_header("Accept", "application/vnd.github+json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print("issue создан: #%s" % json.loads(resp.read())["number"])
        except Exception as e:  # noqa: BLE001 — дозор не падает на недоступных issues
            print("issue не создан (%s) — сводка в логе/summary" % e)
    return 1 if bad else 0


def selftest():
    """Офлайн-проверка парсера: эталонные случаи, ноль API."""
    cases = {
        "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n":
            [("actions/checkout", "3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1")],
        "  uses: amannn/action-semantic-pull-request@2252a14e810aa9b85c2d560bd7070c802206ecf6 # v6.1.2\n":
            [("amannn/action-semantic-pull-request", "2252a14e810aa9b85c2d560bd7070c802206ecf6", "v6.1.2")],
        "  - uses: ./local/action\n  - uses: docker://alpine:3\n  uses: foo/bar@v4\n":
            [("foo/bar", "v4", None)],
        "  uses: owner/repo\n":
            [("owner/repo", "", None)],
    }
    for text, expected in cases.items():
        got = parse_uses(text)
        assert got == expected, "%r -> %r (ожидалось %r)" % (text, got, expected)
    print("selftest: парсер uses — %d случая, OK" % len(cases))
    return 0


def main():
    ap = argparse.ArgumentParser(description="T24 · пин-дозор аккаунта (repo-doctrine#33)")
    ap.add_argument("--owner", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "rtynbirf"))
    ap.add_argument("--apply-issue", default=os.environ.get("APPLY_ISSUE", "true"),
                    help="true = заводить append-only issue при проблемах")
    ap.add_argument("--selftest", action="store_true", help="офлайн-самопроверка парсера")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("нет GITHUB_TOKEN — дозор невозможен")
        sys.exit(2)
    sys.exit(run(args.owner, token, str(args.apply_issue).lower() == "true"))


if __name__ == "__main__":
    main()
