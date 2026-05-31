# GitHub Automation — konfiguracja tokena

## Wymagania do push/PR

### Opcja 1: Personal Access Token (najszybciej)

1. Wejdź na: https://github.com/settings/tokens/new
2. Zaznacz scope: `repo` (pełny dostęp do repo)
3. Skopiuj token (widoczny tylko raz, zaczyna się od `ghp_`)
4. Ustaw zmienną środowiskową:

```bash
export GITHUB_TOKEN=ghp_WSTAW_SWÓJ_TOKEN
export GITHUB_REPO=OWNER/REPO   # np. jankowalski/moje-repo
```

5. Uruchom push:
```bash
python3 ~/qwen-agent/github/git_agent.py push --repo /ścieżka/do/repo
```

Żeby token był trwały, dodaj do `~/.zshrc`:
```bash
echo 'export GITHUB_TOKEN=ghp_TWÓJ_TOKEN' >> ~/.zshrc
```

### Opcja 2: gh CLI (rekomendowana)

```bash
brew install gh
gh auth login        # logowanie przez przeglądarkę
gh auth status       # weryfikacja
```

Po zalogowaniu `gh` obsługuje autoryzację automatycznie.
Możesz też zintegrować z git_agent.py: `gh pr create --title "..." --body "..."`

### Opcja 3: SSH

```bash
ssh-keygen -t ed25519 -C "twój@email.com"
cat ~/.ssh/id_ed25519.pub   # skopiuj i dodaj na https://github.com/settings/ssh/new
git remote set-url origin git@github.com:OWNER/REPO.git
```

## Użycie po konfiguracji

```bash
# Pełny pipeline (branch → commit → push → PR)
python3 ~/qwen-agent/github/git_agent.py auto \
  --repo /ścieżka/do/repo \
  --branch "feat/nowa-funkcja" \
  --message "feat: dodaj nową funkcję" \
  --title "Nowa funkcja X"

# Tylko push
python3 ~/qwen-agent/github/git_agent.py push --repo .

# Tylko PR (po push)
python3 ~/qwen-agent/github/git_agent.py pr --repo . --title "Tytuł PR"
```
