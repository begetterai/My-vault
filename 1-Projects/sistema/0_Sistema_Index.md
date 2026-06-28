# Система — подписки и бюджет

#project/sistema #p2

**Рабочее название.** Цель: заменить старую разрозненную систему учёта (подписки, расходы) на новую — прозрачную, единую, в Vault.

---

## Блоки

| # | Блок | Статус | Файлы |
|---|------|--------|-------|
| 1 | Подписки | 🟡 В работе | [[1-Projects/sistema/подписки|подписки]] |
| 2 | Бюджет | ⬜ Не начат | — |

---

## Архитектура синхронизации

**Принцип:** данные (суммы, даты) живут в Google Drive (Sheets), архитектура (структура, статусы, решения, задачи) — в Obsidian. Между двумя маркерами `<!-- DRIVE-SYNC:START -->` / `<!-- DRIVE-SYNC:END -->` в заметке — автоматически подтягиваемый снимок, остальное правится вручную.

- **Sheet:** [«Система — Подписки»](https://docs.google.com/spreadsheets/d/1tP1xPKU6BO3w9zbhru7dhAsk5nijDl_9Ii9tyF9SAYo) (папка Drive: Private → Трекеры)
- **Скрипт синка:** `scripts/sync_sistema.py` — читает Sheet, обновляет блок в [[1-Projects/sistema/подписки|подписки.md]], коммитит и пушит через `./cli.sh sync`
- **Запуск вручную:** `python3 scripts/sync_sistema.py`

### Автоматический запуск — статус и ограничение

Временно зарегистрирована cron-задача внутри текущей сессии (`CronCreate`, job `00f9cec3`, ежедневно 09:13) с самопродлением. Это стоп-гэп: задача session-only — "dies when Claude exits" даже с флагом `durable: true`. Если эта сессия/контейнер завершится, задача пропадёт — это не настоящая бессрочная автоматизация.

**Настоящий механизм — Routines** (claude.ai/code/routines), отдельный от чата: запускает полноценную облачную сессию по расписанию/событию/API, независимо от того, жив ли текущий разговор. Документация: https://code.claude.com/docs/en/routines

**Как настроить:**
1. claude.ai/code/routines → **New routine**
2. Имя + промпт, например: «В репозитории begetterai/My-vault выполни `python3 scripts/sync_sistema.py`. Скрипт сам обновит снимок в 1-Projects/sistema/подписки.md из Google Sheet и закоммитит+запушит через ./cli.sh sync. Действуй автономно, без вопросов.»
3. Repositories → `begetterai/My-vault`
4. Environment → Default (или свой, см. ниже про сеть)
5. Trigger → **Schedule** → Daily, время по своему часовому поясу (минимум интервала — 1 час)
6. **Permissions → Allow unrestricted branch pushes** — ОБЯЗАТЕЛЬНО включить для этого репо. По умолчанию Routine может пушить только в ветки `claude/*`, а `./cli.sh sync` пушит прямо в `main` (так требует CLAUDE.md этого vault'а)
7. **Environment variables** → добавить `SISTEMA_SA_JSON` = содержимое `scripts/credentials/romashka-drive.json` целиком (этот файл в `.gitignore`, в свежем клоне Routine его не будет — скрипт `sync_sistema.py` уже умеет брать creds из этой переменной, если она задана)
8. Если упадёт по сети — у Default-окружения **Trusted** доступ (стандартные домены), `sheets.googleapis.com`/`www.googleapis.com` туда обычно входят, но если будет 403 — переключить Network access на Custom и добавить эти домены

Пока Routine не настроен (это должен сделать сам Азиз через веб-интерфейс, я не могу) — если снимок данных в подписки.md давно не обновлялся, значит автоматика не работает и нужно либо запустить `python3 scripts/sync_sistema.py` вручную, либо настроить Routine выше.

---

## Связанные

→ `[[2-Areas/Finance/0_Finance_Index|Финансы]]`
→ `[[AGENDA]]`
