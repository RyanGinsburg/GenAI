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
