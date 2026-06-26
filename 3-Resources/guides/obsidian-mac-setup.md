# Obsidian на MacBook — подключение к Vault

Как видеть мою работу в Obsidian на Mac. Один раз настроил — дальше всё само.

---

## Как это работает

Я работаю в облаке, в копии репозитория `begetterai/My-vault` на GitHub. Каждое изменение коммичу и пушу в `main` (`./cli.sh sync`). Чтобы видеть это у себя — нужна локальная копия на Mac, подключённая к Obsidian, с автосинком.

---

## Шаг 1 — GitHub Desktop (самый простой способ авторизации)

1. Скачай: [desktop.github.com](https://desktop.github.com)
2. Установи, войди в свой GitHub аккаунт через браузер (кнопка **Sign in**)
3. **File → Clone Repository** → вкладка URL → вставь:
   ```
   https://github.com/begetterai/My-vault
   ```
4. Local path: оставь по умолчанию (например `~/Documents/GitHub/My-vault`) или выбери свою папку
5. **Clone**

---

## Шаг 2 — Открыть в Obsidian

1. Скачай: [obsidian.md](https://obsidian.md) (если не установлен)
2. **Open folder as vault** → выбери папку, куда склонировал (`My-vault`)
3. Готово — видишь все файлы, заметки, AGENDA.md, проекты

---

## Шаг 3 — Автосинк (плагин Obsidian Git)

Чтобы не открывать терминал каждый раз:

1. В Obsidian: **Settings → Community plugins → Browse**
2. Найди **Obsidian Git** (автор Vinzent03) → **Install** → **Enable**
3. **Settings → Obsidian Git**:
   - **Auto pull interval** → `5` (минут) — подтягивает мои изменения автоматически
   - **Auto backup interval** (commit + push) → `10` (минут) — если сам что-то правишь в Obsidian, это уйдёт обратно в GitHub
4. Вручную в любой момент: `Cmd+P` → **Obsidian Git: Commit and Sync**

---

## Шаг 4 — Плагины для удобного восприятия (рекомендую)

В том же **Community plugins → Browse**:

- **Dataview** — живые дашборды, например список всех `#p1` задач по всему vault одним запросом
- **Tasks** — общий список открытых задач с фильтрами по тегам/срокам
- Встроённые **Graph view** и **Backlinks** (уже включены) — визуальная карта связей между заметками/проектами/областями

---

## Направление синхронизации

- **Я → GitHub → твой Mac**: автоматически через Obsidian Git (auto pull)
- **Твой Mac → GitHub → я**: автоматически при следующей моей сессии (читаю из `main`), плюс твой auto backup пушит сразу

Конфликтов почти не бывает — мы редко правим один файл одновременно. Если возникнет — Obsidian Git подскажет, либо просто напиши мне, разберу.

---

## Связанные

→ `[[CLAUDE|CLAUDE.md]]`
→ `[[AGENDA]]`
