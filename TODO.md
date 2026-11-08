# TODO · repo-doctrine · живой трекер

> Живой трекер-мемо Волны ×5 (2026-11-09). Полный реестр аккаунта: github-runbook → РЕЕСТР-НЕДОДЕЛАННОГО-2026-11-09.md · мастер-индекс: github-runbook#10.

## 1. Открытые issues (26 штук — T01–T25, Э-2.4, T24, T25)

Волна ×5-B в них НЕ комментировала (закон тишины: 26 комментов = шум). Полный список строками-ссылками:

- [#3 · T01 · СВОД как SBOM аккаунта](https://github.com/rtynbirf/repo-doctrine/issues/3)
- [#4 · T02 · Числа, которые сами себя пишут](https://github.com/rtynbirf/repo-doctrine/issues/4)
- [#5 · T03 · Карта как код + drift-детектор доктрины](https://github.com/rtynbirf/repo-doctrine/issues/5)
- [#6 · T04 · Каталог как данные, а не как список](https://github.com/rtynbirf/repo-doctrine/issues/6)
- [#7 · T05 · Геном как сервис-реестр](https://github.com/rtynbirf/repo-doctrine/issues/7)
- [#8 · T06 · Метрики как .prom, журнал с печатью, договор с подписью](https://github.com/rtynbirf/repo-doctrine/issues/8)
- [#9 · T07 · ConsentGrant как ReBAC роя](https://github.com/rtynbirf/repo-doctrine/issues/9)
- [#10 · T08 · Рецепт = аттестация вход-выход](https://github.com/rtynbirf/repo-doctrine/issues/10)
- [#11 · T09 · Пломбы по SLSA: subject+digest без инфраструктуры](https://github.com/rtynbirf/repo-doctrine/issues/11)
- [#12 · T10 · Реновация как канал, а не как разовая волна](https://github.com/rtynbirf/repo-doctrine/issues/12)
- [#13 · T11 · Двухименная ветка и защитная пломба](https://github.com/rtynbirf/repo-doctrine/issues/13)
- [#14 · T12 · 3-2-1-1-0 для роя: учение восстановления раз в квартал](https://github.com/rtynbirf/repo-doctrine/issues/14)
- [#18 · Э-2.4 · Агентный workflow «доктрина сама следит за собой»: пилот Markdown→Actions (пункт карты: T03/П-03)](https://github.com/rtynbirf/repo-doctrine/issues/18)
- [#19 · T16 · Исключение с маркером — не воевать с генератором](https://github.com/rtynbirf/repo-doctrine/issues/19)
- [#20 · T15 · Живой пин с TTL-пломбой](https://github.com/rtynbirf/repo-doctrine/issues/20)
- [#21 · T14 · Факт без тела — артефактная дисциплина и квота-дозиметр](https://github.com/rtynbirf/repo-doctrine/issues/21)
- [#22 · T18 · Pin-freshness — геном догоняет тело сам](https://github.com/rtynbirf/repo-doctrine/issues/22)
- [#23 · T13 · Re-run guard — реанимация по закону, не по памяти](https://github.com/rtynbirf/repo-doctrine/issues/23)
- [#24 · T17 · Манифест свежести — генерится, а не пишется](https://github.com/rtynbirf/repo-doctrine/issues/24)
- [#25 · T22 · Метаболизм agryp — CI с нулём доверия](https://github.com/rtynbirf/repo-doctrine/issues/25)
- [#26 · T19 · Иммунитет ×4 — включить и замкнуть цепь](https://github.com/rtynbirf/repo-doctrine/issues/26)
- [#27 · T20 · Волновой генератор dependabot.yml](https://github.com/rtynbirf/repo-doctrine/issues/27)
- [#28 · T23 · First green — веха, а не прогон](https://github.com/rtynbirf/repo-doctrine/issues/28)
- [#29 · T21 · Мембрана как код — membrane-check и template-sync](https://github.com/rtynbirf/repo-doctrine/issues/29)
- [#33 · T24 · ПРЕДЛОЖЕНИЕ · Пин-дозор аккаунта: еженедельная живая сверка всех uses-SHA](https://github.com/rtynbirf/repo-doctrine/issues/33)
- [#34 · T25 · ПРЕДЛОЖЕНИЕ · Сентинел пустых файлов: CI-гейт «в репе нет файлов 0 байт»](https://github.com/rtynbirf/repo-doctrine/issues/34)

## 2. Честные хвосты ⬜

- ⬜ Красные прогоны sentry 42515192021 (19:28, deb2055) и 42515826530 (19:35, 27cb653 — startup-failure без джоб: мусор конфликта в yml) в истории не перекрашиваются; ×4 докрутил в 4fad75c («GITHUB_EVENT_PATH вместо пустого github.event_path + вычищен мусор конфликта») — зелёный с 19:36 (42515886207 🟢), push 4c9da08 🟢, ec7d8bd 🟢 (20:40); диспатч волны ×5 42527784267 🟢 на ec7d8bd.
- ⬜ 26 T-issues не тронуты — они требуют содержательных решений (карта/геном/ДПР), не клавишных добивок; сгруппированы выше для следующей волны.
- ⬜ Э-2.4 (агентный пилот «доктрина сама следит за собой») не реализован.

## 3. Что делать следующей волне

- wave3-immunity-sentry: STRICT через репо-переменную WAVE3_SENTRY_STRICT (по умолчанию false = observe); белый список авторов — allow-сет в скрипте + WAVE3_ALLOW_DIRECT. Прямые пуши Хозяина (rtynbirf) уже в белом списке.
- T-issues добивать по одному закону «сингулярного хода»: issue → коммит → пломба-коммент; не валить пачкой.
- Мембрана (ec7d8bd): дефолт код-владельца аккаунта (П36, .github#2) — при template-sync не потерять якорь.
- Диспатч-двери: у wave3-immunity-sentry есть workflow_dispatch — для проверки конфигурации без пушей.
