# Настройка Claude Code + Vault (Windows)

Пошаговый гайд для нового пользователя. Время установки: ~30 минут.

---

## Шаг 1 — GitHub аккаунт

1. Зайди на [github.com](https://github.com) → **Sign up**
2. Придумай username (например `aziz-vault`), email, пароль
3. Подтверди email

---

## Шаг 2 — Git для Windows

1. Скачай: [git-scm.com/download/win](https://git-scm.com/download/win)
2. Установи с настройками по умолчанию
3. При вопросе "Default editor" → выбери **Notepad** или **VS Code**
4. При вопросе "line endings" → **Checkout as-is, commit as-is**

Проверь установку — открой **Git Bash** и введи:
```bash
git --version
```

---

## Шаг 3 — Node.js

Нужен для Claude Code.

1. Скачай: [nodejs.org](https://nodejs.org) → LTS версия
2. Установи с настройками по умолчанию
3. Проверь в Git Bash:
```bash
node --version
npm --version
```

---

## Шаг 4 — Claude Code

В **Git Bash** (или PowerShell):
```bash
npm install -g @anthropic-ai/claude-code
```

Проверь:
```bash
claude --version
```

Авторизация:
```bash
claude
```
Откроется браузер → войди через аккаунт Anthropic → введи код.

---

## Шаг 5 — Создать Vault

В Git Bash:
```bash
mkdir ~/My-vault
cd ~/My-vault
```

Создай базовую структуру:
```bash
mkdir -p 0-Inbox 1-Projects 2-Areas 3-Resources 4-Archive Daily Templates
mkdir -p 2-Areas/Health 2-Areas/Finance 2-Areas/Learning 2-Areas/Career
```

---

## Шаг 6 — Подключить GitHub

### Создай репо на GitHub:
1. Зайди на [github.com/new](https://github.com/new)
2. Repository name: `My-vault`
3. **Private** ✓
4. **НЕ** ставь галочки на README/gitignore
5. Нажми **Create repository**

### Подключи локально:
```bash
cd ~/My-vault
git init
git branch -M main

# Настрой себя (замени на свои данные)
git config --global user.name "Твоё Имя"
git config --global user.email "твой@email.com"

# Подключи GitHub (замени USERNAME на твой GitHub username)
git remote add origin https://github.com/USERNAME/My-vault.git
```

### Настрой авторизацию GitHub:
```bash
git config --global credential.helper manager
```
При первом push браузер попросит войти в GitHub — сделай это.

---

## Шаг 7 — CLAUDE.md

Создай файл `~/My-vault/CLAUDE.md`:

```bash
cat > ~/My-vault/CLAUDE.md << 'EOF'
# Личная база знаний

Ты мой интеллектуальный ассистент. Этот репозиторий — моя личная операционная система.

## Agenda

`AGENDA.md` — текущий контекст сессии: что делаем, что открыто, что важно.
Читай его в начале каждой сессии. Обновляй в конце.

## Структура (PARA)

```
0-Inbox/      — Захват идей, обработка позже
1-Projects/   — Активные проекты с конечной целью
2-Areas/      — Жизненные сферы (без дедлайна)
3-Resources/  — Справочные материалы
4-Archive/    — Завершённое и неактивное
Daily/        — Ежедневные заметки
Templates/    — Шаблоны
```

## Правила

- Все заметки на русском
- Используй Obsidian wiki-links: [[filename]]
- Никогда не создавай README.md — используй 0_Name_Index.md
- Никогда не добавляй раздел "Related Notes" вручную
- Sync через `./cli.sh sync`

## Git

- Всегда `./cli.sh sync` — пушит в main
- Никаких feature branch
- Никаких PR

## Пользователь

- **Язык:** Русский
- **Стиль:** коротко, по делу, без воды
EOF
```

---

## Шаг 8 — cli.sh (утилита синка)

```bash
cat > ~/My-vault/cli.sh << 'EOF'
#!/bin/bash
CMD=$1
shift

case "$CMD" in
  sync)
    cd ~/My-vault
    git add -A
    git commit -m "sync: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || echo "Нечего коммитить"
    git pull --rebase origin main 2>/dev/null
    git push origin main
    echo "✅ Синк завершён"
    ;;
  status)
    cd ~/My-vault && git status --short
    ;;
  tasks)
    grep -r "- \[ \]" ~/My-vault --include="*.md" | grep -v ".git" | sed 's/.*- \[ \] //'
    ;;
  daily)
    DATE=$(date '+%Y-%m-%d')
    FILE=~/My-vault/Daily/$DATE.md
    if [ ! -f "$FILE" ]; then
      echo "# $DATE" > "$FILE"
      echo "" >> "$FILE"
      echo "## Задачи" >> "$FILE"
      echo "" >> "$FILE"
      echo "## Заметки" >> "$FILE"
    fi
    echo "Открой файл: $FILE"
    ;;
  *)
    echo "Использование: ./cli.sh sync|status|tasks|daily"
    ;;
esac
EOF
chmod +x ~/My-vault/cli.sh
```

---

## Шаг 9 — AGENDA.md

```bash
cat > ~/My-vault/AGENDA.md << 'EOF'
# Agenda

## Статус: Настройка завершена ✅

Vault создан. Claude Code подключён. Начинаем работать.

---

## Текущий фокус

(заполни сам — что сейчас важно)

---

## Открытые треды

(пусто — начни с чистого листа)
EOF
```

---

## Шаг 10 — Первый коммит и пуш

```bash
cd ~/My-vault

# Создай .gitignore
cat > .gitignore << 'EOF'
.obsidian/workspace*
.obsidian/cache
*.tmp
.DS_Store
Thumbs.db
EOF

git add -A
git commit -m "init: vault structure + CLAUDE.md"
git push -u origin main
```

---

## Шаг 11 — Стоп-хук Claude Code

Хук будет проверять незакоммиченные изменения после каждой сессии.

Создай файл `C:\Users\ИМЯ\.claude\stop-hook-git-check.sh`:

В Git Bash:
```bash
cat > ~/.claude/stop-hook-git-check.sh << 'EOF'
#!/bin/bash
VAULT=~/My-vault
cd "$VAULT" 2>/dev/null || exit 0

UNTRACKED=$(git status --porcelain 2>/dev/null)
if [ -n "$UNTRACKED" ]; then
  echo '{"systemMessage": "⚠️ Есть незакоммиченные изменения. Запусти: ./cli.sh sync"}'
fi
EOF
chmod +x ~/.claude/stop-hook-git-check.sh
```

Добавь хук в настройки Claude Code — создай файл `~/.claude/settings.json`:
```bash
cat > ~/.claude/settings.json << 'EOF'
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/stop-hook-git-check.sh"
          }
        ]
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(./cli.sh *)"
    ]
  }
}
EOF
```

---

## Шаг 12 — Obsidian (опционально)

1. Скачай: [obsidian.md](https://obsidian.md)
2. Установи
3. **Open folder as vault** → выбери `C:\Users\ИМЯ\My-vault`
4. Включи плагин **Backlinks** в настройках

---

## Шаг 13 — Запуск Claude Code

Открой Git Bash в папке vault:
```bash
cd ~/My-vault
claude
```

Готово. Claude прочитает CLAUDE.md и начнёт работать.

---

## Частые команды

```bash
./cli.sh sync          # Сохранить всё и запушить на GitHub
./cli.sh status        # Что изменилось
./cli.sh tasks         # Все открытые задачи
./cli.sh daily         # Создать заметку на сегодня
```

---

## Если что-то пошло не так

**Git просит логин/пароль при push:**
```bash
git config --global credential.helper manager
```
Затем сделай push снова — браузер попросит войти в GitHub.

**Claude Code не запускается:**
```bash
npm install -g @anthropic-ai/claude-code
```

**Хук не работает:**
В Git Bash проверь:
```bash
bash ~/.claude/stop-hook-git-check.sh
```
