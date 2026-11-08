# KNOWN ISSUES · repo-doctrine

## Волна ×5 · 2026-11-09

| Воркфлоу | Run id (sha) | Диагноз | Статус после патча |
|---|---|---|---|
| wave3-immunity-sentry | 42515192021 (deb2055, 19:28) | скрипт стража не видел event-payload: пустой github.event_path → FileNotFoundError | 🟢 ×4 (4fad75c): GITHUB_EVENT_PATH вместо expression-контекста; 42515886207 🟢 (19:36), 42515886450 🟢, 42516507486 🟢 (19:44), 42521313175 🟢 (20:40) |
| wave3-immunity-sentry | 42515826530 (27cb653, 19:35) | startup-failure, 0 джоб: мусор конфликта в yml (двойной on-блок) | 🟢 ×4 вычистил в 4fad75c; диспатч ×5 42527784267 🟢 на ec7d8bd |

### Квирки

- У sentry события push: слияния ДПР распознаются по «Merge pull request…»/«Merge branch…» в head_commit.message; экстренные пуши вне списка — красный маяк по задумке (strict по переменной WAVE3_SENTRY_STRICT).
- guardian-tripwire.yml и self-audit.yml — существующие контуры (×3/×4), волной ×5 не тронуты.
- Репо приватное: rulesets-слой 1 (публичные) не применим — страж-маяк слой 2 остаётся единственным автоматом.
