# GenAI

Repo: https://github.com/RyanGinsburg/GenAI

## Git Cheat Sheet

### Check what's going on

```bash
git status        # what's changed, staged, or untracked
git log --oneline # recent commits
```

Run `git status` whenever you're unsure. It's read-only and always safe.

### Push your code (send changes to GitHub)

```bash
git add .                      # stage all changes
git commit -m "what I changed" # save them as a commit
git push                       # upload to GitHub
```

To stage just one file instead of everything: `git add path/to/file`

### Pull code (get changes from GitHub)

```bash
git pull
```

Do this **before** you start working, so you're building on the latest version.

### Typical session

```bash
git pull                    # 1. get up to date
# ...edit files...
git add .                   # 2. stage
git commit -m "add feature" # 3. commit
git push                    # 4. upload
```

## Gotchas

**"nothing to commit"** — Git sees no changed files. Make sure you actually saved
your file (⌘S) and that it lives inside this folder.

**Pull refuses to run** because you have uncommitted changes — either commit them
first, or stash them temporarily:

```bash
git stash    # set changes aside
git pull
git stash pop # bring them back
```

**Push is rejected** because the remote has commits you don't have. Pull, then push:

```bash
git pull
git push
```

**First push on a new branch** needs to set the upstream once:

```bash
git push -u origin main
```

After that, plain `git push` works.

## Setup

This project needs its own Python environment, kept separate from your system
Python, so its dependencies don't collide with anything else on your machine.

### First time

```bash
python3 -m venv .venv                        # create the virtual environment
.venv/bin/pip install -r requirements.txt    # install dependencies into it
cp .env.example .env                         # your local copy of secrets
```

Then open `.env` and fill in:
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from Google Cloud Console
  (only needed once calendar sync is being built)

`.env` is gitignored — it never gets committed, and nothing in this repo should
ever hardcode a real key.

### Every time you come back to work on this

```bash
source .venv/bin/activate
```

(Or skip activating and just call `.venv/bin/python` / `.venv/bin/pip` directly,
like the commands above.)

### Project layout

See [CLAUDE.md](CLAUDE.md) for the full project description, tech stack, and
current build status. Short version:

```
scraper/    scrapes Cornell's club directory -> data/clubs.json
data/       clubs.json, cached embeddings, scrape cache
backend/    FastAPI app: routes/ + services/ (matching, resume parsing,
            club research, calendar sync)
frontend/   React app (not scaffolded yet — needs Node: brew install node)
```
