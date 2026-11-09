#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Волна ×8 · repo-doctrine#18 (Э-2.4): пилот «Markdown → Actions».
# Компилятор: agentic/ЗАДАЧА-*.md → bash-скрипты → исполнение с fail-closed.
# Естественный язык = контекст задачи; блоки ```sh = машинная часть.
#
# Режимы:
#   (по умолчанию) — компиляция + исполнение всех задач папки
#   --list         — только перечень задач и их блоков
#   --dry          — компиляция без исполнения (печать скриптов)
#
# Закон: первый не-ноль = красный прогон. Никаких || true.
import os
import re
import subprocess
import sys
from pathlib import Path

FENCE_OPEN = re.compile(r'^```sh\s*$')
FENCE_CLOSE = re.compile(r'^```\s*$')


def parse_task(md_path: Path):
    """Возвращает (заголовок, [блоки sh]). Блок — список строк."""
    lines = md_path.read_text(encoding='utf-8').splitlines()
    title = next((ln.lstrip('# ').strip() for ln in lines if ln.startswith('# ')), md_path.name)
    blocks, cur = [], None
    for ln in lines:
        if cur is None:
            if FENCE_OPEN.match(ln):
                cur = []
        elif FENCE_CLOSE.match(ln):
            blocks.append(cur)
            cur = None
        else:
            cur.append(ln)
    return title, blocks


def compile_script(title, blocks):
    out = ['#!/usr/bin/env bash', f'# скомпилировано md2actions из задачи: {title}',
           'set -euo pipefail', '', f'echo "== ЗАДАЧА: {title}"', '']
    for i, block in enumerate(blocks, 1):
        out.append(f'echo "--- блок {i}/{len(blocks)} ---"')
        out.extend(block)
        out.append('')
    return '\n'.join(out)


def main():
    args = sys.argv[1:]
    mode = 'run'
    if '--list' in args:
        mode = 'list'
        args.remove('--list')
    if '--dry' in args:
        mode = 'dry'
        args.remove('--dry')
    root = Path(args[0]) if args else Path('agentic')

    tasks = sorted(root.glob('ЗАДАЧА-*.md'))
    if not tasks:
        print(f'FAIL: в {root} нет задач ЗАДАЧА-*.md')
        return 1

    compiled = []
    for t in tasks:
        title, blocks = parse_task(t)
        if not blocks:
            print(f'FAIL: {t.name} без блоков ```sh — задача без машинной части')
            return 1
        compiled.append((t.name, title, compile_script(title, blocks)))

    if mode == 'list':
        for name, title, script in compiled:
            n = script.count('--- блок')
            print(f'{name} · {title} · блоков: {n}')
        print(f'итого задач: {len(compiled)}')
        return 0

    if mode == 'dry':
        for name, title, script in compiled:
            print(f'===== {name} =====')
            print(script)
        return 0

    summary = []
    failed = []
    for name, title, script in compiled:
        r = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
        tail = '\n'.join((r.stdout + r.stderr).strip().splitlines()[-12:])
        if r.returncode == 0:
            summary.append(f'✅ {name} — {title}')
            print(tail)
        else:
            summary.append(f'❌ {name} — {title} (код {r.returncode})')
            failed.append(name)
            print(tail)

    print('\n## Итог пилота Markdown→Actions')
    print('\n'.join(summary))
    s = os.environ.get('GITHUB_STEP_SUMMARY')
    if s:
        with open(s, 'a', encoding='utf-8') as f:
            f.write('\n'.join(['## agentic-пилот'] + summary) + '\n')

    if failed:
        print(f'FAIL: задачи с красным: {", ".join(failed)}')
        return 1
    print(f'OK: {len(compiled)}/{len(compiled)} задач зелёные')
    return 0


if __name__ == '__main__':
    sys.exit(main())
