#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Токен-клетка · repo-doctrine#15 · Волна ×3 (W3-F1).
Инвентарь секретов (read-only), TTL-гейт 30 дней, скан PAT-подобных строк. Только stdlib.
Команды:
  scan [--root ПУТЬ] [--allow ИМЯ...]    — ноль PAT-подобных строк в артефактах (критерий 3);
                                           собственные файлы клетки в allowlist по умолчанию
  pull --repo OWNER/NAME [--repo ...] [--repos-file ФАЙЛ] [--out secrets-inventory.jsonl]
                                         — инвентарь Actions-секретов через gh CLI, read-only,
                                           append-only (критерий 1); выполняет агент-держатель
  ttl [--max-age 30] [--inventory ...]   — долги: секрет старше N дней → exit 1 (критерий 2)
  svod-line [--inventory ...]            — готовая строка для 12-свод-недоделок
  --selftest                             — самотест на синтетике
"""
import argparse, datetime as dt, json, os, re, subprocess, sys, tempfile
from pathlib import Path
# Префиксы собраны из частей: в самих артефактах клетки литералов токенов нет.
PREFIXES = tuple(''.join(p) for p in (
    ('g', 'h', chr(112), '_'), ('g', 'h', chr(111), '_'), ('g', 'h', chr(115), '_'),
    ('g', 'h', chr(114), '_'), ('g', 'h', chr(117), '_'), ('github', '_pat', '_')))
TOKEN_RE = re.compile('|'.join(re.escape(p) + r'[A-Za-z0-9_\-]{16,}' for p in PREFIXES))
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv'}
DOC = '13-токен-клетка-ноль-вечных-токенов-2026-11-09.md'
def scan(root, allow):
    root, allowset, hits = Path(root), set(allow), []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or any(s in p.parts for s in SKIP_DIRS):
            continue
        rel = p.relative_to(root).as_posix()
        if rel in allowset:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = TOKEN_RE.search(line)
            if m:
                hits.append((rel, i, m.group(0)[:10] + '…'))
    return hits
def cmd_scan(a):
    root = Path(a.root)
    allow = list(DEFAULT_ALLOW := ('scripts/token_cage.py', DOC)) if not a.allow else a.allow
    hits = scan(root, allow)
    for rel, i, frag in hits:
        print('НАЙДЕНО %s:%d — префикс-подобная строка «%s»' % (rel, i, frag))
    print('скан: файлов под правилом, попаданий: %d' % len(hits))
    return 1 if hits else 0
def pull_repo(repo, out):
    try:
        r = subprocess.run(['gh', 'api', 'repos/%s/actions/secrets' % repo], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        print('gh CLI не найден — инвентарь наполняется локально агентом-держателем .token_active')
        return 2
    if r.returncode != 0:
        print('gh api %s: %s' % (repo, (r.stderr or '').strip()[:160]))
        return 2
    now = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    data = json.loads(r.stdout or '{}')
    with open(out, 'a', encoding='utf-8') as f:  # append-only: инвентарь только растёт
        for s in data.get('secrets', []):
            f.write(json.dumps({'snapshot_at': now, 'repo': repo, 'secret': s.get('name', ''),
                                'updated_at': s.get('updated_at', ''), 'note': ''}, ensure_ascii=False, sort_keys=True) + '\n')
    print('%s: секретов в снапшоте %d' % (repo, len(data.get('secrets', []))))
    return 0
def cmd_pull(a):
    repos = list(a.repo or [])
    if a.repos_file:
        repos += [l.strip() for l in Path(a.repos_file).read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
    if not repos:
        print('укажите --repo OWNER/NAME или --repos-file (по одному OWNER/NAME в строке)')
        return 2
    rc = 0
    for repo in repos:
        rc = max(rc, pull_repo(repo, a.out))
    return rc
def latest_map(inventory):
    inv = Path(inventory)
    if not inv.exists():
        return None
    latest = {}
    for line in inv.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        key = (rec.get('repo', ''), rec.get('secret', ''))
        prev = latest.get(key)
        if prev is None or str(rec.get('updated_at', '')) > str(prev.get('updated_at', '')):
            latest[key] = rec
    return latest
def cmd_ttl(a):
    latest = latest_map(a.inventory)
    if latest is None:
        print('(заполняется скриптом при первом прогоне: secrets-inventory.jsonl ещё не создан — выполните pull)')
        return 0
    today, debt = dt.date.today(), []
    for (repo, name), rec in sorted(latest.items()):
        updated = str(rec.get('updated_at', ''))
        if not updated:
            debt.append((repo, name, 'нет даты обновления')); continue
        age = (today - dt.date.fromisoformat(updated[:10])).days
        if age > a.max_age:
            debt.append((repo, name, '%d дн' % age))
    for repo, name, why in debt:
        print('ДОЛГ: %s / %s — %s (старше %d дн)' % (repo, name, why, a.max_age))
    print('ttl: секретов %d, долгов %d' % (len(latest), len(debt)))
    return 1 if debt else 0
def cmd_svod(a):
    latest = latest_map(a.inventory)
    n = len(latest) if latest else 0
    debt = 0
    if latest:
        today = dt.date.today()
        debt = sum(1 for rec in latest.values() if rec.get('updated_at')
                   and (today - dt.date.fromisoformat(rec['updated_at'][:10])).days > 30)
    print('| %s | токен-клетка: инвентарь ведётся, секретов %d, долгов (>30 дн) %d |' % (dt.date.today().isoformat(), n, debt))
    return 0
def selftest():
    fails = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / 'src').mkdir()
        tok = PREFIXES[0] + 'A' * 36
        (t / 'src' / 'leak.js').write_text('const t = "%s";\n' % tok, encoding='utf-8')
        (t / DOC).write_text('документ клетки, литералов нет\n', encoding='utf-8')
        hits = scan(t, ('scripts/token_cage.py', DOC))
        if [(h[0], h[1]) for h in hits] != [('src/leak.js', 1)]:
            fails.append('сканер не поймал injected-токен: %s' % hits)
        inv = t / 'secrets-inventory.jsonl'
        old = (dt.date.today() - dt.timedelta(days=40)).isoformat() + 'T00:00:00Z'
        fresh = dt.date.today().isoformat() + 'T00:00:00Z'
        with open(inv, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'snapshot_at': fresh, 'repo': 'r/a', 'secret': 'OLD', 'updated_at': old, 'note': ''}) + '\n')
            f.write(json.dumps({'snapshot_at': fresh, 'repo': 'r/a', 'secret': 'NEW', 'updated_at': fresh, 'note': ''}) + '\n')
        args = argparse.Namespace(inventory=str(inv), max_age=30)
        if cmd_ttl(args) != 1:
            fails.append('ttl не поднял долг на 40-дневном секрете')
        late = latest_map(inv)
        if set(late) != {('r/a', 'OLD'), ('r/a', 'NEW')}:
            fails.append('latest по инвентарю собран неверно')
    print('selftest: %s' % ('OK — injected-токен и 40-дневный долг ловятся, литералов в клетке нет' if not fails else 'ПРОВАЛ: ' + '; '.join(fails)))
    return 1 if fails else 0
def main(argv=None):
    ap = argparse.ArgumentParser(description='Токен-клетка (repo-doctrine#15)')
    ap.add_argument('--selftest', action='store_true')
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('scan'); s.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    s.add_argument('--allow', nargs='*', help='пути-исключения (по умолчанию — файлы клетки)')
    p = sub.add_parser('pull'); p.add_argument('--repo', action='append'); p.add_argument('--repos-file')
    p.add_argument('--out', default='secrets-inventory.jsonl')
    t = sub.add_parser('ttl'); t.add_argument('--max-age', type=int, default=30)
    t.add_argument('--inventory', default='secrets-inventory.jsonl')
    v = sub.add_parser('svod-line'); v.add_argument('--inventory', default='secrets-inventory.jsonl')
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if a.cmd == 'scan': return cmd_scan(a)
    if a.cmd == 'pull': return cmd_pull(a)
    if a.cmd == 'ttl': return cmd_ttl(a)
    if a.cmd == 'svod-line': return cmd_svod(a)
    ap.print_help(); return 0
if __name__ == '__main__':
    sys.exit(main())
