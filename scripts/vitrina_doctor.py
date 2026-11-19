#!/usr/bin/env python3
# ВИТРИННЫЙ ДОКТОР ДОМА · конечный автомат SCAN → DIFF → APPLY → VERIFY → REPORT (+ LLMS-GEN)
# Роль: витрина роя живёт в метаданных GitHub (description/topics) и в агентной двери
# (llms.txt на Pages). Доктор держит оба в каноне: не выдумывает, доклеивает, идемпотентен.
# Токен: только env GH_TOKEN (протокол дома). Архивные тела — законное состояние:Doctor
# их не разархивирует; их место — раздел «Архив» llms-карты.
# Запуск: GH_TOKEN=... python3 vitrina_doctor.py [--dry-run] [--llms OUT.md]
import os, sys, json, time, base64, urllib.request, urllib.error

API = "https://api.github.com"
OWNER = "rtynbirf"
TOK = os.environ["GH_TOKEN"]

# ── КАНОН РОЛЕЙ (эмерджентная карта дома: жанр клетки → ролевые топики) ──
# Доклеиваются к существующим (merge), дом-словарь (pid1, doctrine, python, audit,
# documentation, ssot, automation, github, constitution) приоритетен.
CANON_TOPICS = {
    "assembly-protocol": ["pid1", "verification", "protocol", "python", "build-automation"],
    "dogovor": ["pid1", "doctrine", "governance", "agent-governance", "ssot"],
    "lfs-core": ["pid1", "testing", "audit", "agent-infrastructure", "python"],
    "repo-seed": ["pid1", "template", "boilerplate", "github", "automation"],
}
CANON_DESC_IF_EMPTY = {  # описания уже стоят у всех 77 — правило работает только на пустоту
}

def api(url, method="GET", body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {TOK}", "User-Agent": "free-man-vitrina-doctor",
                "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(r, timeout=40) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(3 * (i + 1)); continue
            return e.code, {"message": f"HTTP {e.code}"}
        except Exception as e:
            time.sleep(2 * (i + 1))
    return 0, {"message": "no connection"}

# ── SCAN ──
def scan():
    repos, page = [], 1
    while True:
        s, chunk = api(f"{API}/user/repos?per_page=100&page={page}&sort=full_name")
        if s != 200 or not isinstance(chunk, list) or not chunk:
            raise RuntimeError(f"SCAN fail: GET /user/repos page {page} → {s}")
        repos += chunk
        if len(chunk) < 100: break
        page += 1
    return repos

# ── DIFF: что канон требует, чего витрина не несёт ──
def diff(repos):
    acts = []
    for r in repos:
        n = r["name"]
        if r["archived"]:
            continue  # законное состояние — не трогаем
        cur = sorted(r.get("topics") or [])
        want = sorted(set(cur) | set(CANON_TOPICS.get(n, [])))
        if want != cur:
            acts.append({"repo": n, "kind": "topics", "from": cur, "to": want})
        d = r.get("description")
        if not d and n in CANON_DESC_IF_EMPTY:
            acts.append({"repo": n, "kind": "description", "from": None, "to": CANON_DESC_IF_EMPTY[n]})
    return acts

# ── APPLY ──
def apply(acts, dry=False):
    done, failed = [], []
    for a in acts:
        if a["kind"] == "topics":
            s, _ = api(f"{API}/repos/{OWNER}/{a['repo']}/topics", "PUT", {"names": a["to"]})
        else:
            s, _ = api(f"{API}/repos/{OWNER}/{a['repo']}", "PATCH", {"description": a["to"]})
        (done if s in (200, 202, 204) else failed).append({**a, "http": s})
        time.sleep(0.4)
    return done, failed

# ── VERIFY: перечитывание ──
def verify(done):
    ok, bad = [], []
    for a in done:
        s, r = api(f"{API}/repos/{OWNER}/{a['repo']}")
        got = sorted((r or {}).get("topics") or []) if a["kind"] == "topics" else (r or {}).get("description")
        want = a["to"]
        (ok if (s == 200 and got == want) else bad).append({"repo": a["repo"], "want": want, "got": got, "http": s})
        time.sleep(0.3)
    return ok, bad

# ── LLMS-GEN: аккаунтная карта роя для AI-агентов (конвенция llmstxt.org) ──
def llms_map(repos):
    alive = sorted([r for r in repos if not r["archived"]], key=lambda r: r["name"])
    arch = sorted([r for r in repos if r["archived"]], key=lambda r: r["name"])
    L = ["# Дом rtynbirf · карта роя для AI-агентов",
         "> Человек=Аккаунт=PID1 · ПОЛИМАТ=Мультиагент · живая кузня: рой агентов, офлайн-вселенная, ни одного стороннего виджета.",
         "",
         f"Автоген витринным доктором дома · источник: живой GitHub API · {len(repos)} тел: {len(alive)} живых + {len(arch)} архивных (законное состояние дома).",
         "",
         "## Живые клетки"]
    for r in alive:
        d = (r.get("description") or "клетка роя").strip()
        t = ", ".join((r.get("topics") or [])[:8])
        lang = f" · язык {r['language']}" if r.get("language") else ""
        L.append(f"- [{r['name']}](https://github.com/{OWNER}/{r['name']}): {d} ({t}{lang})")
    L += ["", "## Архив (законное состояние, история роя)"]
    for r in arch:
        d = (r.get("description") or "клетка роя").strip()
        L.append(f"- [{r['name']}](https://github.com/{OWNER}/{r['name']}) (архив): {d}")
    L += ["", "## Двери",
          "- [Лицо профиля](https://github.com/rtynbirf): канон пинов, геном роя, летопись",
          f"- [Карта (этот файл)](https://rtynbirf.github.io/llms.txt)",
          f"- [Плеер-мембрана](https://rtynbirf.github.io/): MEGA-PLAYER SINGULYAR",
          f"- raw llms.txt](https://raw.githubusercontent.com/{OWNER}/rtynbirf.github.io/main/llms.txt)"]
    return "\n".join(L) + "\n"

# ── REPORT ──
def main():
    dry = "--dry-run" in sys.argv
    out_llms = None
    if "--llms" in sys.argv:
        out_llms = sys.argv[sys.argv.index("--llms") + 1]
    repos = scan()
    acts = diff(repos)
    print(f"SCAN: {len(repos)} тел | DIFF: {len(acts)} действий")
    for a in acts: print(f"  {a['repo']}: {a['kind']} {a['from']} → {a['to']}")
    if out_llms:
        body = llms_map(repos)
        open(out_llms, "w").write(body)
        print(f"LLMS-GEN: {out_llms} ({len(body)} б, {len(repos)} тел в карте)")
    if not acts:
        print("VERIFY-канон: диф пуст, витрина в каноне — идемпотентный ноль.")
        return
    if dry:
        print("DRY-RUN: применений нет."); return
    done, failed = apply(acts)
    ok, bad = verify(done)
    rep = {"scanned": len(repos), "diff": len(acts), "applied": len(done),
           "apply_failed": failed, "verify_ok": len(ok), "verify_bad": bad}
    json.dump(rep, open("/home/z/my-project/scripts/vitrina_state.json", "w"), ensure_ascii=False, indent=1)
    print(f"APPLY: {len(done)} ok, {len(failed)} fail | VERIFY: {len(ok)} ok, {len(bad)} bad")
    if bad: print(json.dumps(bad, ensure_ascii=False, indent=1))
    sys.exit(1 if (failed or bad) else 0)

if __name__ == "__main__":
    main()
