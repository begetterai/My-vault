#!/usr/bin/env bash
# Agent Reach — доступ агента к интернету (YouTube, RSS, веб, поиск).
# Контейнер сессии одноразовый: всё, что поставлено, исчезает вместе с ним.
# Поэтому установка вынесена сюда — запускается в начале новой сессии.
#
#   bash scripts/setup_agent_reach.sh
#
# Ставится в ~/.agent-reach-venv, рабочую папку не трогает.
set -euo pipefail

VENV="$HOME/.agent-reach-venv"
SRC="$HOME/.agent-reach/tools/agent-reach"
REPO="https://github.com/Panniantong/agent-reach"

echo "== Agent Reach: установка =="

# ВАЖНО: ставим ТОЛЬКО из репозитория Panniantong.
# В PyPI есть пакет с тем же именем agent-reach от другого автора — это не он.
mkdir -p "$(dirname "$SRC")"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" pull --ff-only --quiet || true
else
  rm -rf "$SRC"
  git clone --depth 1 --quiet "$REPO" "$SRC"
fi

[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
"$VENV/bin/pip" install -q "$SRC"
"$VENV/bin/pip" install -q -U "yt-dlp[default]"

# yt-dlp: без JS-рантайма YouTube не отдаёт субтитры
mkdir -p "$HOME/.config/yt-dlp"
grep -qxF -- '--js-runtimes node' "$HOME/.config/yt-dlp/config" 2>/dev/null \
  || printf '%s\n' '--js-runtimes node' >> "$HOME/.config/yt-dlp/config"

# Семантический поиск по вебу (Exa через MCP, ключ не нужен)
if ! command -v mcporter >/dev/null 2>&1; then
  npm install -g mcporter >/dev/null 2>&1 || echo "  !! mcporter не поставился — поиск Exa будет недоступен"
fi
if command -v mcporter >/dev/null 2>&1; then
  mcporter config add exa https://mcp.exa.ai/mcp --scope home >/dev/null 2>&1 || true
fi

# Инструменты должны быть на PATH — иначе doctor их «не видит»
for t in agent-reach yt-dlp; do
  ln -sf "$VENV/bin/$t" "/usr/local/bin/$t" 2>/dev/null || true
done
export PATH="$VENV/bin:$PATH"

echo
echo "== Проверка =="
agent-reach doctor 2>&1 | tail -20
echo
echo "Готово. Инструменты: $VENV/bin/agent-reach, $VENV/bin/yt-dlp, mcporter"
echo "Поиск по вебу:  mcporter call exa.web_search_exa query=\"...\" numResults=3"
echo "Чтение страницы: curl -s https://r.jina.ai/<URL>"
