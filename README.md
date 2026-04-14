# Claude Vault

<p align="center">
  <img src=".github/assets/obsidian-claude-love.png" alt="Obsidian + Claude = Love" width="400">
</p>

An AI-assisted knowledge base for Obsidian. A hybrid system where you have visual access through Obsidian, and your AI assistant has access through Claude Code. Work from your phone, desktop, or terminal — everything stays in sync.

## What You Can Do

- **Keep your notes** — everything in markdown, organized your way
- **Give AI access to your knowledge** — Claude can read, search, and build on your notes
- **Manage tasks and projects** — with an AI executive assistant
- **Store artifacts** — code, files, research outputs — all in project folders
- **Run deep research** — similar to Deep Research, with results saved to your vault
- **Sync across devices** — mobile, desktop, terminal — always up to date

## How It Works

You interact through Obsidian (or any markdown editor). Claude interacts through Claude Code. Both work on the same files.

**Minimal Git knowledge required** — if you can clone a repo, you're set. All changes sync automatically to the main branch. Conflicts are resolved automatically.

## Setup

### 1. Create your repository

Click **"Use this template"** → **"Create a new repository"** to create your own copy.

### 2. Create a GitHub Token

[Create a Personal Access Token](https://github.com/settings/tokens/new) with `repo` scope. Save it — you'll need it in step 4.

### 3. Open Claude Code

Open the Claude app and switch to the **Code** tab:

<img src=".github/assets/setup/step-1.png" width="500">

### 4. Create a Cloud Environment

Click the environment dropdown and select **Add environment**:

<img src=".github/assets/setup/step-3.png" width="400">

Fill in the environment settings:
- **Name**: anything you like
- **Network access**: Full
- **Environment variables**: `GH_TOKEN=your_github_token`

<img src=".github/assets/setup/step-4.png" width="400">

### 5. Start a Session

Click **New session**, select your repository and the environment you created:

<img src=".github/assets/setup/step-2.png" width="300">

Say "Let's set up the knowledge base" — Claude will guide you through onboarding.

<img src=".github/assets/setup/step-5.png" width="600">

### 6. (Optional) Open in Obsidian

To access your vault locally:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

Open the cloned folder in [Obsidian](https://obsidian.md) as a vault.

## Local Sync

Obsidian doesn't sync with Git automatically. After making local changes, run:

```bash
./cli.sh sync
```

Or via Claude CLI:

```bash
claude -p "./cli.sh sync"
```

This commits and pushes everything to main.

## Structure

```
├── CLAUDE.md      # Agent instructions
├── AGENDA.md      # Current context and open threads
├── 0-Inbox/       # Quick capture
├── 1-Projects/    # Active work with artifacts
├── 2-Areas/       # Life areas (health, career, etc.)
├── 3-Resources/   # Reference material
├── 4-Archive/     # Completed items
└── Daily/         # Daily notes
```

## License

MIT
