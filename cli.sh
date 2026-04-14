#!/bin/bash
# cli.sh - Bootstrap script for obsidian-cli + custom commands
# Downloads the appropriate binary on first run

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLI_DIR="$SCRIPT_DIR/.cli"
VERSION="0.2.0"
GITHUB_RELEASE="https://github.com/Yakitrak/obsidian-cli/releases/download/v${VERSION}"

detect_platform() {
  case "$(uname -s)" in
    Darwin*)
      echo "darwin_all"
      ;;
    Linux*)
      case "$(uname -m)" in
        x86_64)  echo "linux_amd64" ;;
        aarch64|arm64) echo "linux_arm64" ;;
        *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
      esac
      ;;
    *)
      echo "Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac
}

ensure_binary() {
  local platform=$(detect_platform)
  local binary="$CLI_DIR/obsidian-cli"
  local tarball="obsidian-cli_${VERSION}_${platform}.tar.gz"
  local url="$GITHUB_RELEASE/$tarball"

  if [ ! -x "$binary" ]; then
    echo "Downloading obsidian-cli v${VERSION} for ${platform}..." >&2
    mkdir -p "$CLI_DIR"

    if command -v curl &> /dev/null; then
      curl -fsSL "$url" | tar -xz -C "$CLI_DIR"
    elif command -v wget &> /dev/null; then
      wget -qO- "$url" | tar -xz -C "$CLI_DIR"
    else
      echo "Error: curl or wget required" >&2
      exit 1
    fi

    chmod +x "$binary"
    echo "Installed to $CLI_DIR" >&2
  fi
}

# === Git Remote Handling ===

# Extract GitHub repo from current remote (handles various URL formats)
get_github_repo() {
  local remote=$(git remote get-url origin 2>/dev/null || echo "")
  local repo=""

  # Extract owner/repo from various formats:
  # - https://github.com/owner/repo.git
  # - git@github.com:owner/repo.git
  # - http://proxy@127.0.0.1:PORT/git/owner/repo

  if echo "$remote" | grep -q "github.com"; then
    repo=$(echo "$remote" | sed -E 's|.*github\.com[:/]||' | sed 's|\.git$||')
  elif echo "$remote" | grep -q "/git/"; then
    repo=$(echo "$remote" | sed -E 's|.*/git/||')
  fi

  echo "$repo"
}

# Ensure remote origin points directly to GitHub (not through proxy)
ensure_remote() {
  local current_remote=$(git remote get-url origin 2>/dev/null || echo "")
  local repo=$(get_github_repo)

  if [ -z "$repo" ]; then
    echo "ERROR: Could not determine GitHub repo from remote" >&2
    echo "Current remote: $current_remote" >&2
    exit 1
  fi

  # Check if remote is already correct (github.com, not proxy)
  if echo "$current_remote" | grep -q "github.com"; then
    return 0
  fi

  # Need to fix remote - check for GH_TOKEN
  if [ -z "$GH_TOKEN" ]; then
    echo "ERROR: Remote needs fixing but GH_TOKEN is not set" >&2
    echo "Current remote: $current_remote" >&2
    echo "" >&2
    echo "To fix: set GH_TOKEN environment variable with your GitHub token" >&2
    exit 1
  fi

  local auth_remote="https://x-access-token:${GH_TOKEN}@github.com/${repo}.git"

  echo "Fixing remote origin..."
  echo "  Was: $current_remote"
  echo "  Now: https://***@github.com/${repo}.git"

  git remote set-url origin "$auth_remote"
}

# Ensure main branch exists locally
ensure_main_branch() {
  # Check if main exists locally
  if git show-ref --verify --quiet refs/heads/main; then
    return 0
  fi

  echo "Branch 'main' not found locally. Fetching..."

  # Try to fetch main from origin
  if git fetch origin main:main 2>/dev/null; then
    echo "Fetched 'main' from origin."
  else
    # Maybe we need to create it from current HEAD
    echo "Creating 'main' branch from current HEAD..."
    git branch main
  fi
}

cmd_sync() {
  cd "$SCRIPT_DIR"

  # Ensure remote is configured correctly
  ensure_remote

  # Ensure main branch exists
  ensure_main_branch

  # Check current branch
  current_branch=$(git branch --show-current)

  # Switch to main if needed
  if [ "$current_branch" != "main" ]; then
    echo "Switching from '$current_branch' to 'main'..."
    git checkout main
  fi

  # Check for uncommitted changes
  if git diff --quiet && git diff --staged --quiet; then
    # Check for untracked files
    if [ -z "$(git ls-files --others --exclude-standard)" ]; then
      echo "Nothing to sync."
      exit 0
    fi
  fi

  # Stage all changes
  git add -A

  # Commit with timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M')
  git commit -m "sync: $timestamp"

  echo "Committed. Pushing to main..."

  # Try to push
  if git push origin main 2>&1; then
    echo "Synced successfully."
  else
    echo ""
    echo "=== PUSH FAILED ==="
    echo "Conflict detected. Pulling with rebase..."
    echo ""

    # Try to pull and rebase
    if git pull --rebase origin main 2>&1; then
      echo "Rebase successful. Pushing again..."
      if git push origin main 2>&1; then
        echo "Synced successfully after rebase."
      else
        echo ""
        echo "=== CRITICAL: Push still failing ==="
        echo "Manual intervention required. Current status:"
        git status
        exit 1
      fi
    else
      echo ""
      echo "=== CRITICAL: Rebase conflict ==="
      echo "Manual intervention required."
      echo ""
      echo "Conflicting files:"
      git diff --name-only --diff-filter=U
      echo ""
      echo "To resolve:"
      echo "1. Edit conflicting files"
      echo "2. git add <resolved files>"
      echo "3. git rebase --continue"
      echo "4. ./cli.sh sync"
      exit 1
    fi
  fi
}

cmd_read() {
  cd "$SCRIPT_DIR"
  local query="$1"

  if [ -z "$query" ]; then
    echo "Usage: ./cli.sh read <note-name or path>" >&2
    exit 1
  fi

  # Find the file
  local file=""

  # If it's a direct path that exists
  if [ -f "$query" ]; then
    file="$query"
  elif [ -f "$query.md" ]; then
    file="$query.md"
  else
    # Search for Obsidian-style note name
    file=$(find . -name "*.md" -type f | grep -i "$query" | head -1)
  fi

  if [ -z "$file" ] || [ ! -f "$file" ]; then
    echo "Note not found: $query" >&2
    exit 1
  fi

  # Get the basename for backlink search
  local basename=$(basename "$file" .md)

  # Print file content with line numbers (same format as Claude Read tool)
  local abs_path="$(cd "$(dirname "$file")" && pwd)/$(basename "$file")"
  echo "=== $abs_path ==="
  echo ""
  awk '{printf "%6d→%s\n", NR, $0}' "$file"

  # Find and print backlinks
  echo ""
  echo "=== Backlinks ==="

  local backlinks=$(grep -rn "\[\[$basename" --include="*.md" . 2>/dev/null | grep -v "^$file:" || true)

  if [ -n "$backlinks" ]; then
    echo "$backlinks"
  else
    echo "(no backlinks)"
  fi
}

cmd_tasks() {
  cd "$SCRIPT_DIR"

  local path_filter=""
  local tag_filter=""
  local show_all=false

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --p1|--p2|--p3)
        tag_filter="${1#--}"
        shift
        ;;
      --next|--waiting|--someday)
        tag_filter="${1#--}"
        shift
        ;;
      --all)
        show_all=true
        shift
        ;;
      -*)
        echo "Unknown option: $1" >&2
        echo "Usage: ./cli.sh tasks [path] [--p1|--p2|--p3|--next|--waiting|--someday] [--all]" >&2
        exit 1
        ;;
      *)
        path_filter="$1"
        shift
        ;;
    esac
  done

  # Build search path
  local search_path="."
  if [ -n "$path_filter" ]; then
    # Find directories matching the filter
    search_path=$(find . -type d -iname "*$path_filter*" 2>/dev/null | head -1)
    if [ -z "$search_path" ]; then
      # Try as a direct path
      if [ -d "$path_filter" ]; then
        search_path="$path_filter"
      else
        echo "No directory matching: $path_filter" >&2
        exit 1
      fi
    fi
  fi

  echo "=== Tasks in $search_path ==="
  echo ""

  # Find all unchecked tasks
  local tasks
  tasks=$(grep -rn "\- \[ \]" --include="*.md" "$search_path" 2>/dev/null || true)

  if [ -z "$tasks" ]; then
    echo "No open tasks found."
    return 0
  fi

  # Filter by tag if specified
  if [ -n "$tag_filter" ]; then
    tasks=$(echo "$tasks" | grep -i "#$tag_filter" || true)
    if [ -z "$tasks" ]; then
      echo "No tasks with #$tag_filter"
      return 0
    fi
    echo "Filtered by: #$tag_filter"
    echo ""
  fi

  # Group and display
  local current_file=""
  local count=0

  echo "$tasks" | while IFS= read -r line; do
    # Extract file path and line number
    local file=$(echo "$line" | cut -d: -f1)
    local linenum=$(echo "$line" | cut -d: -f2)
    local content=$(echo "$line" | cut -d: -f3-)

    # Clean up content - remove leading spaces and the checkbox
    content=$(echo "$content" | sed 's/^[[:space:]]*- \[ \] //')

    # Print file header if new file
    if [ "$file" != "$current_file" ]; then
      if [ -n "$current_file" ]; then
        echo ""
      fi
      echo "$file"
      current_file="$file"
    fi

    # Highlight priority tags
    if echo "$content" | grep -q "#p1"; then
      echo "  [!] $content"
    elif echo "$content" | grep -q "#p2"; then
      echo "  [*] $content"
    elif echo "$content" | grep -q "#p3"; then
      echo "  [-] $content"
    elif echo "$content" | grep -q "#next"; then
      echo "  [>] $content"
    elif echo "$content" | grep -q "#waiting"; then
      echo "  [?] $content"
    elif echo "$content" | grep -q "#someday"; then
      echo "  [~] $content"
    else
      echo "  [ ] $content"
    fi

    count=$((count + 1))
  done

  echo ""
  echo "---"
  local total=$(echo "$tasks" | wc -l | tr -d ' ')
  echo "Total: $total tasks"
}

cmd_status() {
  cd "$SCRIPT_DIR"

  echo "=== Git Status ==="

  # Branch
  branch=$(git branch --show-current)
  echo "Branch: $branch"

  # Uncommitted changes
  changes=$(git status --porcelain | wc -l | tr -d ' ')
  if [ "$changes" -gt 0 ]; then
    echo "Uncommitted changes: $changes files"
    git status --short
  else
    echo "Working tree clean."
  fi

  # Ahead/behind
  git fetch origin main --quiet 2>/dev/null || true
  ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
  behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")

  if [ "$ahead" -gt 0 ] || [ "$behind" -gt 0 ]; then
    echo "Ahead: $ahead, Behind: $behind"
  fi
}

# === Main ===

case "${1:-}" in
  sync)
    cmd_sync
    ;;
  status)
    cmd_status
    ;;
  read)
    cmd_read "$2"
    ;;
  tasks)
    shift
    cmd_tasks "$@"
    ;;
  help|--help|-h)
    echo "Usage: ./cli.sh <command>"
    echo ""
    echo "Custom commands:"
    echo "  sync              Commit all changes and push to main"
    echo "  status            Show git status summary"
    echo "  read <note>       Read note with backlinks"
    echo "  tasks [path]      List open tasks"
    echo "        --p1/p2/p3  Filter by priority"
    echo "        --next      Filter by #next tag"
    echo ""
    echo "Obsidian commands:"
    ensure_binary
    "$CLI_DIR/obsidian-cli" --help
    ;;
  *)
    ensure_binary
    exec "$CLI_DIR/obsidian-cli" "$@"
    ;;
esac
