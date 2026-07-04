# Obsidian на iPad — подключение к Vault

Как видеть мою работу в Obsidian на iPad. GitHub Desktop на iPad не работает (это Mac/Windows-only приложение) — здесь всё делается внутри самого Obsidian через плагин Git.

---

## Как это работает

Я работаю в облаке, в копии репозитория `begetterai/My-vault` на GitHub. Каждое изменение коммичу и пушу в `main` (`./cli.sh sync`). На iPad плагин **Obsidian Git** клонирует репозиторий прямо в vault и дальше сам синкается по таймеру — никакого отдельного гитхаб-приложения не нужно.

---

## Шаг 1 — Personal Access Token

Нужен как "пароль" для доступа к приватному репозиторию.

1. Safari → **github.com/settings/tokens**
2. **Generate new token** → **Generate new token (classic)**
3. Note: `obsidian-ipad`, Expiration: на свой вкус
4. Galочка **repo** (полный доступ)
5. **Generate token** → скопируй `ghp_...` (покажется один раз)

---

## Шаг 2 — создать vault

1. Установи **Obsidian** из App Store
2. **Create new vault** → имя (например `My-vault`) → Storage: **On My iPad**

---

## Шаг 3 — включить плагины сообщества

1. Настройки ⚙️ → **Сторонние плагины**
2. **Включите плагины сообщества** (Safe mode выключить)
3. **Обзор** → найди **Git** (автор Vinzent03) → **Установить** → **Включить**

---

## Шаг 4 — клонировать репозиторий

1. Открой палитру команд (значок `>_` слева)
2. Введи `Clone an existing remote repo`
3. URL:
   ```
   https://github.com/begetterai/My-vault
   ```
4. Папка — **Vault Root**
5. Если попросит удалить локальный `.obsidian` — соглашайся (vault пустой, ничего не потеряется)
6. Глубина клонирования — оставь пустым, подтверди
7. Username — GitHub username, Password — токен `ghp_...` из Шага 1
8. **"Does your remote repo contain a .obsidian directory at the root?"** → **NO**

После этого появятся все файлы (0-Inbox, 1-Projects, AGENDA и т.д.).

⚠️ Удаление локального `.obsidian` сбрасывает установленные плагины — Git придётся поставить заново тем же путём (Шаг 3) после клонирования.

---

## Шаг 5 — автосинк

Настройки ⚙️ → **Сторонние плагины** → **Git** (шестерёнка рядом) → **Automatic**:
- **Auto pull interval (minutes)** → `5`
- **Auto commit-and-sync interval (minutes)** → `10`

---

## Направление синхронизации

- **Я → GitHub → твой iPad**: автоматически (auto pull)
- **Твой iPad → GitHub → я**: автоматически (auto commit-and-sync), плюс читаю из `main` в начале каждой сессии

---

## Связанные

→ `[[CLAUDE|CLAUDE.md]]`
→ `[[AGENDA]]`
→ `[[3-Resources/guides/obsidian-mac-setup|Obsidian на Mac]]`
