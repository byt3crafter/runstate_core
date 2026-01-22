# Git Commit and Push Guide for Runstate

## Repository Location

The main repository to commit and push from:
```
/home/d0v1k/Projects/erpnext-v15/runstate/runstate_core
```

**NOT** from the docker frappe-bench apps folder.

## Remote Configuration

```
origin: git@github-personal:byt3crafter/runstate_core.git
```

Uses SSH config at `~/.ssh/config` with host alias `github-personal`.

## Git User Config

```bash
git config user.email "ludovic.micinthe@gmail.com"
git config user.name "Ludovic Micinthe"
```

## Commit and Push Workflow

### 1. Navigate to the repo
```bash
cd /home/d0v1k/Projects/erpnext-v15/runstate/runstate_core
```

### 2. Check status
```bash
git status
```

### 3. Stage files
```bash
# Stage specific files
git add path/to/file1 path/to/file2

# Or stage all changes (be careful)
git add -A
```

### 4. Commit with message
```bash
git commit -m "fix: Short description of the fix"
```

Or for multi-line commit messages:
```bash
git commit -m "$(cat <<'EOF'
fix: Short description

- Detail 1
- Detail 2

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### 5. Push to GitHub
```bash
git push origin version-15
```

## Commit Message Style

Follow the convention:
- `fix:` - Bug fixes
- `feat:` - New features
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

## Notes

- The impex app in docker (`/frappe_docker/development/frappe-bench/apps/impex`) syncs with `runstate_core`
- Always commit from `runstate_core`, not the docker apps folder
- The docker folder remote points to a container path that won't work from host
