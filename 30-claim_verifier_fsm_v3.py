#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLAIM VERIFIER FSM v3 — конечный автомат проверки утверждений (гейт канвы КП).

АВТОРСТВО. Правила протокола сформулированы пользователем диалога 2026-11-20.
Реализация v1 — ассистент (косяки пойманы перебором 128 входов, audit_v1.py).
Реализация v2 — ассистент, закрывает каждый косяк с пломбой прогона.
Реализация v2.1 — фикс Е37: ограниченный квантор («почти всегда») не универсален.
Реализация v3 — ассистент по уроку Хозяина 2026-11-21: «контрпример сам обязан
нести канву (локальный КП нельзя подавать как универсальный)» и «всякий пруф
частный» (ἰδιώτης = частное лицо). Хозяин назначил агента вторым исполнителем
статуса ПОДТВЕРЖДЕНО: сдатчик и приёмщик — один, приёмка = независимые прогоны.

ПЯТЬ ПРАВИЛ ПРОТОКОЛА (канон Хозяина):
  1. МЕТКА ПРОИСХОЖДЕНИЯ: факт / вывод / пересказ / инструкция.
  2. КОНТЕКСТ: утверждение оценивается только в заданной канве.
  3. КОНТРПРИМЕР: один «мал/мел» убивает универсальное «А=Э=Е».
  4. ОТВЕРГАЯ — ПРЕДЛАГАЙ: отказ сопровождается альтернативой.
  5. ПРУФЫ: факт требует источника, вывод — выкладки, инструкция — спецификации.

ЧЕМ v3 ОТЛИЧАЕТСЯ ОТ v2 (каждый пункт = закрытый косяк с пломбой прогона):
  К9  (Е39). ГОЛОЕ ОТРИЦАНИЕ НЕ ПРУФ. В v2 ЛЮБОЙ непустой контрпример убивал
      универсалию — КП мог не говорить, ГДЕ он наблюдён. Локальное «нет» без
      канвы подавалось как универсальный проигрыш. В v3 UNIVERSAL_GATE требует
      от КП ЕГО канву (ce_context): нет канвы → HOLD_NEEDS_CE_CANVAS, КП не
      убивает, автомат ждёт канву наблюдения. В маршрутах (факт/вывод/пересказ)
      голый КП не задерживает проверку: маршрут сам спросит СВОЙ пруф.
  К10 (Е40). КП-УНИВЕРСАЛИЯ — НЕ ПРОБА. В v2 КП «всегда есть иное» убивал
      универсалию — универсалью испытывали универсаль. «Всякий пруф частный»:
      испытание = конкретный наблюдённый случай, а не мини-теория. В v3
      универсальный КП (по тому же детектору кванторов) → FLAG_NEEDS_COUNTEREXAMPLE
      с remedy «приведи пробу».
  К11 (Е41). ИНСТРУКЦИЯ ПЕРЕЖИВАЛА ВАЛИДНЫЙ КП. В v2 kill-гuards стояли в
      EVIDENCE/DERIVATION/SOURCE_TAG, но не в SCOPE: инструкция с валидным КП
      уходила в ACCEPT_SPEC. В v3 SCOPE получил тот же guard — единый инвариант:
      REJECT ⇔ КП-проба с канвой, на всех четырёх маршрутах.
  К12 (Е42). СЧЁТЧИК SCRUB ДОШЁЛ ДО ТРАССЫ. К8 в v2 декларировал «счётчик в
      трассе», а INTAKE его не писал (счёт жил только в Claim). В v3 при
      вычистке невидимых символов в трассе появляется строка INTAKE со счётом.

Инвариант v3 (проверен перебором всех 2048 входов, audit_v3.py):
  REJECT_COUNTEREXAMPLE выдаётся ТОГДА И ТОЛЬКО когда КП — проба:
  несёт свою канву (ce_context) и сам не универсалия. Голое «нет» не убивает.
  Для универсального текста вердикт зависит ТОЛЬКО от рода КП (гейт слеп к метке).

ЧЕМ v2 ОТЛИЧАЕТСЯ ОТ v1 (история, каждый пункт = косяк, пойманный перебором):
  К1. гейты по СВОЙСТВУ утверждения, не по метке (лазейка переметки закрыта);
  К2. универсальное без испытания не принимается (FLAG_NEEDS_COUNTEREXAMPLE);
  К3. метка происхождения живёт до выхода (4 раздельных ACCEPT);
  К4. один код HOLD — одна причина (HOLD_NEEDS_CONTEXT / HOLD_NEEDS_SPEC);
  К5. «отвергая — предлагай» исполнен: remedy — функция, строит из КП;
  К6. DONE достижим, таблица валидируется, guard вычислен (2×len(STATES));
  К7. трасса в хэш-цепи, пломба прогона = голова цепи;
  К8. невидимые символы вычищаются на входе (v3: счёт виден в трассе).

Мировые практики (см. protocol_claim_check.md): RAG-grounding, ReAct, Reflexion,
Self-Consistency, Chain-of-Verification, provenance цитат. Своё эмерджентное:
единица проверки = отдельное утверждение, вердикт выносит детерминированная
таблица состояний, а не нейросудья; гейты — по свойствам утверждения и пруфа.

Запуск:  python3 claim_verifier_fsm_v3.py            (демо на утверждениях диалога)
         python3 claim_verifier_fsm_v3.py --selftest (exit 0 — зелёный, 2 — красный)
"""

from __future__ import annotations

import hashlib
import re
import sys

# --- Канон: состояния и вердикты ---------------------------------------------
STATES = (
    "INTAKE",           # приём: чистка невидимых символов, гейт канвы
    "CLASSIFY",         # метка происхождения + детектор универсальности
    "UNIVERSAL_GATE",   # испытание универсальных утверждений (ЛЮБОГО типа)
    "ROUTE",            # маршрутизация по метке происхождения
    "EVIDENCE",         # факт: источник и проверяемость
    "DERIVATION",       # вывод: выкладка
    "SOURCE_TAG",       # пересказ: пометка, чей он
    "SCOPE",            # инструкция: спецификация + КП-гейт (Е41)
    "VERDICT",          # вердикт вынесен
    "HOLD",             # стоп: не хватает данных от автора
    "DONE",             # терминал: вердикт подписан хэшем прогона
)

VERDICTS = (
    "ACCEPT_FACT",              # факт: источник есть и проверяем
    "ACCEPT_INFERRED",          # вывод: выкладка показана
    "ACCEPT_AS_REPORT",         # пересказ: помечен чей он (силой ниже факта)
    "ACCEPT_SPEC",              # инструкция: спецификация дана
    "REJECT_COUNTEREXAMPLE",    # отвергнуто КП-пробой с канвой (+ альтернатива)
    "FLAG_NEEDS_SOURCE",        # нет пруфа по типу (источник/выкладка/пометка)
    "FLAG_NEEDS_DERIVATION",    # вывод без выкладки
    "FLAG_NEEDS_COUNTEREXAMPLE",# универсальное не испытано валидной пробой
    "HOLD_NEEDS_CONTEXT",       # канва утверждения не задана
    "HOLD_NEEDS_CE_CANVAS",     # КП подан без своей канвы — не пруф (Е39)
    "HOLD_NEEDS_SPEC",          # инструкция без спецификации
)

ACCEPTS = frozenset(v for v in VERDICTS if v.startswith("ACCEPT_"))

# Сила вердиктов: пересказ слабее факта и вывода (метка происхождения не теряется)
STRENGTH = {"ACCEPT_FACT": 3, "ACCEPT_INFERRED": 2, "ACCEPT_AS_REPORT": 1, "ACCEPT_SPEC": 3}

# --- Детектор универсальных кванторов (детерминированный, без нейросети) ------
_QUANTIFIER_RE = re.compile(
    r"\b(все|всегда|никогда|любой|любая|любое|каждый|каждая|каждое|всякий|"
    r"всякая|всякое|ни\s+один|ни\s+одна|ни\s+одно|никто|ничто|не\s+бывает|"
    r"нет\s+разниц\w*|одинаково|без\s+исключений)\b", re.IGNORECASE)

# Е37 (пойман прогоном каталога RUVSON): ограничитель перед квантором
# («почти всегда», «почти никогда») инвертирует универсальность —
# ограниченный квантор НЕ универсален.
_LIMITER_RE = re.compile(
    r"\b(почти|практически|вовсе\s+не|далеко\s+не|отнюдь\s+не)\s*$", re.IGNORECASE)


def is_universal(text: str) -> bool:
    """Универсальный квантор БЕЗ ограничителя перед ним (Е37).
    «Мелкое дно всегда проявляется» — универсалия;
    «почти всегда опаздывает» — нет."""
    for m in _QUANTIFIER_RE.finditer(text):
        if _LIMITER_RE.search(text[:m.start()]):
            continue  # ограниченный квантор
        return True
    return False


# Невидимые символы: zero-width, BOM, NBSP, line/para separators
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00a0\u2028\u2029"))


def scrub(text: str) -> tuple[str, int]:
    clean = text.translate(_INVISIBLE).replace("\u00a0", " ")
    return clean, len(text) - len(clean)


def ce_kills(c: "Claim") -> bool:
    """Контрпример убивает ТОЛЬКО как проба: несёт свою канву (где наблюдён)
    и сам не универсалия (Е39+Е40; «всякий пруф частный»).
    Голое отрицание — не пруф: не убивает ни в гейте, ни в маршруте."""
    return (bool(c.counterexample) and bool(c.ce_context)
            and not is_universal(c.counterexample))


class Claim:
    """Утверждение + контекст + пруф-род. Свойства путешествуют вместе
    с утверждением: метка типа НЕ управляет гейтами — только маршрутом пруфа.
    Контрпример — сам мини-утверждение: обязан нести свою канву (ce_context)."""

    _ORIGIN = ("fact", "inference", "report", "instruction")

    def __init__(self, text: str, ctype: str, *,
                 has_source: bool = False, source_checkable: bool = False,
                 derivation_shown: bool = False, counterexample: str | None = None,
                 ce_context: str = "", context: str = "", spec: str | None = None):
        if ctype not in self._ORIGIN:
            raise ValueError(f"неизвестный тип утверждения: {ctype!r}")
        self.text, n1 = scrub(text)
        if counterexample:
            self.counterexample, n2 = scrub(counterexample)
        else:
            self.counterexample, n2 = counterexample, 0
        self.ce_context, n3 = scrub(ce_context)
        self.scrubbed = n1 + n2 + n3        # счёт невидимых — попадёт в трассу (Е42)
        self.ctype = ctype
        self.has_source = has_source
        self.source_checkable = source_checkable
        self.derivation_shown = derivation_shown
        self.context = context
        self.spec = spec


class VerifierFSM:
    """Детерминированный конечный автомат. Таблица переходов — конституция.

    Гейты привязаны к свойствам утверждения И пруфа:
      * контрпример-ПРОБА (с канвой, не универсалия) убивает утверждение
        ЛЮБОГО типа — гейт в UNIVERSAL_GATE и во всех четырёх маршрутах;
      * универсальный квантор ведёт ЛЮБОЙ тип через UNIVERSAL_GATE
        (лазейка переметки закрыта конструкцией, не надзором);
      * голое отрицание и КП-универсалия не убивают (Е39/Е40).
    """

    def __init__(self) -> None:
        self.trace: list[str] = []
        self._prev: str = ""          # предыдущий хэш в цепи трассы
        self.steps: int = 0

    # --- пломба: каждая строка трассы в хэш-цепи ----------------------------
    def _log(self, state: str, msg: str) -> None:
        line = f"{state:<14} | {msg}"
        h = hashlib.sha256((self._prev + line).encode("utf-8")).hexdigest()[:16]
        self._prev = h
        self.trace.append(f"{line}   #{h}")

    # --- таблица переходов: имя охраны -> (предикат, следующее, вердикт) ----
    _T: dict[str, tuple[tuple[str, object, str, str | None], ...]] = {
        "INTAKE": (
            ("канва не задана", lambda c: not c.context, "HOLD", "HOLD_NEEDS_CONTEXT"),
            ("канва принята", lambda c: True, "CLASSIFY", None),
        ),
        "CLASSIFY": (
            ("универсальный квантор — испытание", lambda c: is_universal(c.text),
             "UNIVERSAL_GATE", None),
            ("рядовое — по метке", lambda c: True, "ROUTE", None),
        ),
        # ЛЮБОЙ тип проходит здесь: переметка report/instruction не спасает.
        # Порядок охран = строгость: КП-универсалия → не проба (Е40);
        # КП без канвы → не пруф (Е39); только проба убивает.
        "UNIVERSAL_GATE": (
            ("КП — сам универсалия, не проба", lambda c: bool(c.counterexample)
             and is_universal(c.counterexample), "VERDICT", "FLAG_NEEDS_COUNTEREXAMPLE"),
            ("КП без канвы — не пруф, ждём канву", lambda c: bool(c.counterexample)
             and not c.ce_context, "HOLD", "HOLD_NEEDS_CE_CANVAS"),
            ("КП-проба с канвой убивает", ce_kills, "VERDICT", "REJECT_COUNTEREXAMPLE"),
            ("универсальное не испытано", lambda c: True,
             "VERDICT", "FLAG_NEEDS_COUNTEREXAMPLE"),
        ),
        "ROUTE": (
            ("факт", lambda c: c.ctype == "fact", "EVIDENCE", None),
            ("вывод", lambda c: c.ctype == "inference", "DERIVATION", None),
            ("пересказ", lambda c: c.ctype == "report", "SOURCE_TAG", None),
            ("инструкция", lambda c: c.ctype == "instruction", "SCOPE", None),
        ),
        "EVIDENCE": (
            ("КП-проба с канвой убивает", ce_kills, "VERDICT", "REJECT_COUNTEREXAMPLE"),
            ("источника нет", lambda c: not c.has_source, "VERDICT", "FLAG_NEEDS_SOURCE"),
            ("источник непроверяем", lambda c: not c.source_checkable,
             "VERDICT", "FLAG_NEEDS_SOURCE"),
            ("источник есть и проверяем", lambda c: True, "VERDICT", "ACCEPT_FACT"),
        ),
        "DERIVATION": (
            ("КП-проба с канвой убивает", ce_kills, "VERDICT", "REJECT_COUNTEREXAMPLE"),
            ("выкладки нет", lambda c: not c.derivation_shown,
             "VERDICT", "FLAG_NEEDS_DERIVATION"),
            ("выкладка показана", lambda c: True, "VERDICT", "ACCEPT_INFERRED"),
        ),
        "SOURCE_TAG": (
            ("КП-проба с канвой убивает", ce_kills, "VERDICT", "REJECT_COUNTEREXAMPLE"),
            ("чей он не помечен", lambda c: not c.has_source,
             "VERDICT", "FLAG_NEEDS_SOURCE"),
            ("помечен", lambda c: True, "VERDICT", "ACCEPT_AS_REPORT"),
        ),
        # Е41: guard КП добавлен — инструкция больше не переживает валидную пробу.
        "SCOPE": (
            ("КП-проба с канвой убивает", ce_kills, "VERDICT", "REJECT_COUNTEREXAMPLE"),
            ("спецификации нет — не работать", lambda c: not c.spec,
             "HOLD", "HOLD_NEEDS_SPEC"),
            ("спецификация есть", lambda c: True, "VERDICT", "ACCEPT_SPEC"),
        ),
        "HOLD": (
            ("стоп — ждём данных автора", lambda c: True, "VERDICT", None),
        ),
        "VERDICT": (
            ("вердикт вынесен — подпись прогона", lambda c: True, "DONE", None),
        ),
    }

    def _step(self, state: str, c: Claim) -> tuple[str, str | None]:
        if state not in self._T:
            raise RuntimeError(f"состояние вне канона: {state}")
        for name, guard, nxt, verdict in self._T[state]:
            if guard(c):
                self._log(state, f"{name} -> {nxt}" + (f" [{verdict}]" if verdict else ""))
                return nxt, verdict
        raise RuntimeError(f"тупик таблицы в {state}: ни одна охрана не сработала")

    def run(self, claim: Claim) -> tuple[str | None, list[str], str]:
        """Прогнать утверждение. Вернуть (вердикт, трасса-с-цепью, пломба)."""
        self.trace, self._prev, self.steps = [], "", 0
        if claim.scrubbed:               # Е42: счётчик чистки виден в трассе
            self._log("INTAKE", f"невидимых символов вычищено: {claim.scrubbed}")
        state, verdict = "INTAKE", None
        guard_max = 2 * len(STATES)          # вычислен, не магия
        while state != "DONE":
            self.steps += 1
            if self.steps > guard_max:
                raise RuntimeError("автомат зациклился — ошибка таблицы переходов")
            nxt, v = self._step(state, claim)
            if v is not None:                # вердикт фиксируется при первом назначении
                verdict = v                  # и дальше НЕ перезаписывается (К4)
            state = nxt
        run_hash = self._prev
        return verdict, self.trace, run_hash

    def revise(self, claim: Claim, **changes) -> tuple[str | None, list[str], str]:
        """Петля доводки: remedy подсказал изменение — повторный прогон тем же
        автоматом (детерминированный аналог Reflexion, без нейросети)."""
        fields = {k: getattr(claim, k) for k in
                  ("text", "ctype", "has_source", "source_checkable",
                   "derivation_shown", "counterexample", "ce_context", "context", "spec")}
        unknown = set(changes) - set(fields)
        if unknown:
            raise ValueError(f"неизвестные поля утверждения: {sorted(unknown)}")
        fields.update(changes)
        return self.run(Claim(**fields))


# --- «Отвергая — предлагай»: альтернатива строится ИЗ утверждения --------------
def remedy(verdict: str | None, c: Claim) -> str:
    """Функция, не строка: remedy содержит конкретику этого утверждения."""
    if verdict in ACCEPTS:
        mark = {"fact": "факт (источник проверяем)", "inference": "вывод (выкладка показана)",
                "report": "пересказ чужого — силой ниже факта", "instruction": "инструкция (спека дана)"}
        return f"— принято как {mark[c.ctype]}"
    if verdict == "REJECT_COUNTEREXAMPLE":
        narrowed = f"«{c.text} — кроме случаев: {c.counterexample}»"
        return (f"контрпример «{c.counterexample}» (канва КП: {c.ce_context}) убил "
                f"утверждение; альтернатива: сузить область до {narrowed}")
    if verdict == "FLAG_NEEDS_DERIVATION":
        return (f"вывод «{c.text}» без выкладки; альтернатива: показать шаги "
                f"или перевести в гипотезу (канва: {c.context})")
    if verdict == "FLAG_NEEDS_COUNTEREXAMPLE":
        if c.counterexample:  # КП подан, но не проба: сам универсалия (Е40)
            return (f"поданный «контрпример» — сам универсалия: всякий пруф частный, "
                    f"универсаль испытывает только конкретная проба; приведи "
                    f"наблюдённый случай (канва утверждения: {c.context})")
        return (f"утверждение «{c.text}» универсально, а испытания не было: "
                f"приведи контрпример-пробу или сузь область (канва: {c.context})")
    if verdict == "HOLD_NEEDS_CE_CANVAS":
        return (f"контрпример «{c.counterexample}» подан без канвы — это отрицание, "
                f"не пруф: КП обязан нести канву (где наблюдён, в какой системе); "
                f"доводка: revise(ce_context=<канва наблюдения>)")
    if verdict == "FLAG_NEEDS_SOURCE":
        proof = {"fact": "проверяемый источник", "inference": "показанные шаги выкладки",
                 "report": "пометку, чей это пересказ", "instruction": "спецификацию (что, куда, в каком виде)"}
        alt = ("пометить как вывод и показать выкладку" if c.ctype in ("fact", "report")
               else "дать пруф по типу утверждения")
        return f"пруфа по типу нет; альтернатива: приложить {proof[c.ctype]} или {alt}"
    if verdict == "HOLD_NEEDS_CONTEXT":
        return "дать канву: область, рамка, границы применимости — без неё не рассматриваем"
    if verdict == "HOLD_NEEDS_SPEC":
        return f"инструкция «{c.text}» без спецификации не исполняется: что, куда, в каком виде, чем проверить"
    return "—"


# --- Валидация конституции: STATES и VERDICTS несущие, не декорация -----------
def validate_constitution() -> None:
    unknown_states = set(VerifierFSM._T) - set(STATES)
    if unknown_states:
        raise RuntimeError(f"в таблице состояния вне канона: {sorted(unknown_states)}")
    missing = set(STATES) - set(VerifierFSM._T) - {"VERDICT", "HOLD", "DONE"}
    if missing:
        raise RuntimeError(f"состояния канона без переходов: {sorted(missing)}")
    table_verdicts = {v for row in VerifierFSM._T.values() for (_, _, _, v) in row if v}
    unknown_v = table_verdicts - set(VERDICTS)
    if unknown_v:
        raise RuntimeError(f"в таблице вердикты вне канона: {sorted(unknown_v)}")
    unreachable_v = set(VERDICTS) - table_verdicts
    if unreachable_v:
        raise RuntimeError(f"вердикты недостижимы таблицей: {sorted(unreachable_v)}")
    # достижимость состояний: обход из INTAKE
    seen, todo = {"INTAKE"}, ["INTAKE"]
    while todo:
        s = todo.pop()
        for (_, _, nxt, _) in VerifierFSM._T.get(s, ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    dead = set(STATES) - seen
    if dead:
        raise RuntimeError(f"состояния недостижимы из INTAKE: {sorted(dead)}")


# --- Демо: утверждения диалога -------------------------------------------------
def demo() -> None:
    claims = [
        Claim("Суворов родился в 1730 году в Москве", "fact", context="биография"),
        Claim("Суворов родился в Москве (год спорный: 1729/1730)", "fact",
              has_source=True, source_checkable=True, context="биография, RuWiki"),
        Claim("А=Э=Е — нет разницы в смысле", "fact",
              counterexample="мал/мол/мел/мил/мул",
              ce_context="фонология русского: живая речь, минимальные пары",
              context="фонология"),
        Claim("пед- = дитя (греч. παῖς): педагог, педиатр, энциклопедия", "report",
              has_source=True, context="этимология, словари"),
        Claim("смысл слова = его употребление", "inference",
              derivation_shown=True, context="языкознание"),
        Claim("интегрируй всё у нас", "instruction", context="безрепозиторная среда"),
        Claim("собрать FSM-протокол в файл и прогнать тесты", "instruction",
              spec="Python 3, stdlib, демо на 7 утверждениях", context="песочница"),
        # лазейка v1: переметка универсального в пересказ и инструкцию
        Claim("А=Э=Е — нет разницы в смысле", "report", has_source=True,
              context="фонология (переметка)"),
        Claim("А=Э=Е — нет разницы в смысле", "instruction", spec="считать истинным",
              context="фонология (переметка)"),
        # v3/Е39: КП без канвы — голое отрицание не пруф
        Claim("А=Э=Е — нет разницы в смысле", "fact", counterexample="мел",
              context="фонология"),
        # v3/Е40: КП-универсалия — не проба («всякий пруф частный»)
        Claim("графемы M и T всегда различимы на письме", "fact",
              counterexample="всякое правило где-то нарушается",
              context="графематика рукописи"),
    ]
    fsm = VerifierFSM()
    for i, c in enumerate(claims, 1):
        v, trace, seal = fsm.run(c)
        print(f"--- УТВЕРЖДЕНИЕ {i}: {c.text}")
        for line in trace:
            print("   ", line)
        print(f"    ВЕРДИКТ: {v}  (сила: {STRENGTH.get(v, 0)}/3)")
        print(f"    ОТВЕРГАЯ — ПРЕДЛАГАЙ: {remedy(v, c)}")
        print(f"    ПЛОМБА: {seal}")
        print()
    # петля доводки v3: КП без канвы -> remedy -> revise с канвой КП -> убил
    bare = Claim("А=Э=Е — нет разницы в смысле", "fact", counterexample="мел",
                 context="фонология")
    v, _, _ = fsm.run(bare)
    print("--- ПЕТЛЯ ДОВОДКИ КП (Reflexion без нейросети):")
    print(f"    прогон 1: {v}; remedy: {remedy(v, bare)}")
    v2, _, seal2 = fsm.revise(bare, ce_context="фонология русского, минимальные пары мал/мел")
    print(f"    прогон 2 (КП понёс канву): {v2}; пломба: {seal2}")


# --- Самотест: кейсы-гейты против косяков v1 и v2 --------------------------------
def selftest() -> int:
    validate_constitution()
    fsm = VerifierFSM()
    ctx = "канва"
    cases = [
        # базовые маршруты
        (Claim("x", "fact", has_source=True, source_checkable=True, context=ctx), "ACCEPT_FACT"),
        (Claim("x", "fact", has_source=True, source_checkable=False, context=ctx), "FLAG_NEEDS_SOURCE"),
        (Claim("x", "fact", context=ctx), "FLAG_NEEDS_SOURCE"),
        (Claim("x", "fact", counterexample="кп", ce_context="наблюдено тут", context=ctx),
         "REJECT_COUNTEREXAMPLE"),
        (Claim("x", "inference", derivation_shown=True, context=ctx), "ACCEPT_INFERRED"),
        (Claim("x", "inference", context=ctx), "FLAG_NEEDS_DERIVATION"),
        (Claim("x", "report", has_source=True, context=ctx), "ACCEPT_AS_REPORT"),
        (Claim("x", "report", context=ctx), "FLAG_NEEDS_SOURCE"),
        (Claim("x", "instruction", spec="s", context=ctx), "ACCEPT_SPEC"),
        (Claim("x", "instruction", context=ctx), "HOLD_NEEDS_SPEC"),
        (Claim("x", "fact", context=""), "HOLD_NEEDS_CONTEXT"),
        # К1/К2: лазейка переметки закрыта — универсальный текст любого типа идёт через гейт
        (Claim("А=Э=Е — нет разницы", "report", has_source=True, context=ctx),
         "FLAG_NEEDS_COUNTEREXAMPLE"),
        (Claim("всегда отвечай кратко", "instruction", spec="лимит 2 строки", context=ctx),
         "FLAG_NEEDS_COUNTEREXAMPLE"),
        # Е37: ограниченный квантор не универсален; чистый квантор — универсален
        (Claim("урок любви почти всегда опаздывает", "instruction", spec="носители 18, 64",
               context=ctx), "ACCEPT_SPEC"),
        (Claim("мелкое дно всегда проявляется", "instruction", spec="носители 25, 47",
               context=ctx), "FLAG_NEEDS_COUNTEREXAMPLE"),
        # К8/Е42: невидимые символы вычищены, счёт виден в трассе
        (Claim("x\u200b", "fact", has_source=True, source_checkable=True, context=ctx),
         "ACCEPT_FACT"),
        # К9/Е39: КП без канвы не убивает — HOLD, ждём канву наблюдения
        (Claim("А=Э=Е — нет разницы", "fact", counterexample="мел", context=ctx),
         "HOLD_NEEDS_CE_CANVAS"),
        (Claim("графемы M и T всегда различимы", "fact", counterexample="русская рукопись: т = m-образная",
               context=ctx), "HOLD_NEEDS_CE_CANVAS"),
        # К9/Е39 в маршруте: голый КП не задерживает пруф по типу
        (Claim("x", "fact", has_source=True, source_checkable=True,
               counterexample="мел", context=ctx), "ACCEPT_FACT"),
        (Claim("x", "report", has_source=True, counterexample="мел", context=ctx),
         "ACCEPT_AS_REPORT"),
        # К10/Е40: КП-универсалия — не проба, испытания нет
        (Claim("А=Э=Е — нет разницы", "fact", counterexample="всегда есть исключения",
               ce_context="где-то видел", context=ctx), "FLAG_NEEDS_COUNTEREXAMPLE"),
        # К11/Е41: инструкция не переживает валидную пробу
        (Claim("x", "instruction", spec="s", counterexample="кп", ce_context="тут", context=ctx),
         "REJECT_COUNTEREXAMPLE"),
        # К9: валидная проба с канвой убивает универсалию
        (Claim("А=Э=Е — нет разницы", "fact", counterexample="мел",
               ce_context="фонология русского, минимальные пары", context=ctx),
         "REJECT_COUNTEREXAMPLE"),
        # приём: revise возвращает доведённое утверждение в приём
        ("REVISE", "ACCEPT_FACT"),
        # приём v3: revise КП — канва КП доставлена, проба убила
        ("REVISE_CE", "REJECT_COUNTEREXAMPLE"),
    ]
    bad = 0
    for c, expected in cases:
        if c == "REVISE":
            v, _, _ = fsm.revise(Claim("x", "fact", context=ctx),
                                 has_source=True, source_checkable=True)
            label = "revise"
        elif c == "REVISE_CE":
            v, _, _ = fsm.revise(Claim("А=Э=Е — нет разницы", "fact",
                                       counterexample="мел", context=ctx),
                                 ce_context="фонология русского")
            label = "revise-КП"
        else:
            v, _, _ = fsm.run(c)
            label = c.ctype
        ok = v == expected
        bad += 0 if ok else 1
        print(f"[{'OK ' if ok else 'FAIL'}] {label:<11} -> {v} (ожидалось {expected})")
    # каждый вердикт канона достижим хотя бы одним кейсом
    reached = {fsm.run(c)[0] for c, _ in cases
               if c not in ("REVISE", "REVISE_CE")}
    reached.add(fsm.revise(Claim("x", "fact", context=ctx),
                           has_source=True, source_checkable=True)[0])
    reached.add(fsm.revise(Claim("А=Э=Е — нет разницы", "fact", counterexample="мел",
                                 context=ctx), ce_context="фонология")[0])
    missing_v = set(VERDICTS) - reached
    ok = not missing_v
    bad += 0 if ok else 1
    print(f"[{'OK ' if ok else 'FAIL'}] покрытие   -> все {len(VERDICTS)} вердиктов достижимы"
          + ("" if ok else f", не хватает: {sorted(missing_v)}"))
    print(f"\nselftest: {len(cases) + 1 - bad}/{len(cases) + 1} прошло")
    return 2 if bad else 0


if __name__ == "__main__":
    validate_constitution()
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    demo()
