#!/usr/bin/env python3
"""
Automatyzacja GitHub dla qwen-agent.
Tworzy branch, commit, push i opis PR (lub prawdziwy PR przez gh/API).

Użycie:
  python3 git_agent.py branch --repo <path> --name "feat/opis"
  python3 git_agent.py commit --repo <path> --message "opis" [--all]
  python3 git_agent.py push   --repo <path> [--remote origin]
  python3 git_agent.py pr     --repo <path> --title "Tytuł" [--body "..."]
  python3 git_agent.py auto   --repo <path> --branch "feat/X" --message "msg" --title "PR title"

Zmienne środowiskowe (opcjonalne, do PR przez API):
  GITHUB_TOKEN  — personal access token
  GITHUB_REPO   — "owner/repo" (np. "jankowalski/moje-repo")
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx
from typing import Optional


# ---------- git helpers ----------

def git(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True,
        check=check,
    )


def current_branch(repo: str) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()


def current_commit(repo: str) -> str:
    return git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()


def get_diff_summary(repo: str, base: str = "HEAD~1") -> str:
    try:
        r = git(["diff", "--stat", base], repo, check=False)
        return r.stdout.strip()
    except Exception:
        return ""


def get_remote_url(repo: str) -> str:
    try:
        return git(["remote", "get-url", "origin"], repo, check=False).stdout.strip()
    except Exception:
        return ""


def parse_github_slug(remote_url: str) -> str:
    """Wyciąga 'owner/repo' z URL git."""
    url = remote_url.rstrip("/").removesuffix(".git")
    if "github.com" in url:
        parts = url.split("github.com")[-1].lstrip("/:")
        return parts
    return ""


# ---------- commands ----------

def cmd_branch(repo: str, name: str) -> dict:
    r = git(["checkout", "-b", name], repo, check=False)
    if r.returncode != 0:
        # branch może już istnieć — tylko przełącz
        git(["checkout", name], repo)
        return {"status": "switched", "branch": name}
    return {"status": "created", "branch": name}


def cmd_commit(repo: str, message: str, add_all: bool = True, files: Optional[list] = None) -> dict:
    if add_all:
        git(["add", "-A"], repo)
    elif files:
        git(["add"] + files, repo)

    # sprawdź czy jest co commitować
    status = git(["status", "--porcelain"], repo).stdout.strip()
    if not status:
        return {"status": "nothing_to_commit"}

    r = git(["commit", "-m", message], repo, check=False)
    if r.returncode != 0:
        return {"status": "error", "detail": r.stderr.strip()}
    sha = current_commit(repo)
    return {"status": "committed", "sha": sha, "message": message}


def cmd_push(repo: str, remote: str = "origin", branch: str = "") -> dict:
    branch = branch or current_branch(repo)
    token = os.environ.get("GITHUB_TOKEN", "")
    remote_url = get_remote_url(repo)

    if not remote_url:
        return {
            "status": "no_remote",
            "instruction": (
                "Brak remote 'origin'. Dodaj go:\n"
                "  git remote add origin https://github.com/OWNER/REPO.git"
            ),
        }

    # Buduj URL z tokenem tylko na czas push — nie zapisuj do .git/config
    push_url = remote_url
    if token and "github.com" in remote_url and "@github.com" not in remote_url:
        push_url = remote_url.replace("https://github.com", f"https://{token}@github.com")

    # Jeśli URL z tokenem, push bezpośrednio do URL (token nie trafia do .git/config)
    if push_url != remote_url:
        r = subprocess.run(
            ["git", "push", "-u", push_url, f"HEAD:{branch}"],
            cwd=repo, capture_output=True, text=True,
        )
        # Po udanym push ustaw upstream tracking
        if r.returncode == 0:
            subprocess.run(
                ["git", "branch", "--set-upstream-to", f"{remote}/{branch}", branch],
                cwd=repo, capture_output=True, text=True,
            )
    else:
        r = subprocess.run(
            ["git", "push", "-u", remote, branch],
            cwd=repo, capture_output=True, text=True,
        )

    if r.returncode != 0:
        err = r.stderr.strip()
        if not token:
            return {
                "status": "auth_required",
                "instruction": (
                    "Push wymaga uwierzytelnienia.\n"
                    "Opcja 1 — token GitHub (zalecane):\n"
                    "  export GITHUB_TOKEN=ghp_TWÓJ_TOKEN\n"
                    "  python3 git_agent.py push --repo .\n\n"
                    "Opcja 2 — gh CLI:\n"
                    "  gh auth login -h github.com\n\n"
                    "Opcja 3 — SSH:\n"
                    "  ssh-keygen -t ed25519 && cat ~/.ssh/id_ed25519.pub  # dodaj do GitHub\n"
                    "  git remote set-url origin git@github.com:OWNER/REPO.git"
                ),
                "error": err,
            }
        return {"status": "push_failed", "error": err}

    return {"status": "pushed", "branch": branch, "remote": remote}


def cmd_pr_description(repo: str, title: str, body: str = "", base: str = "main") -> dict:
    """Generuje opis PR i próbuje otworzyć przez API jeśli dostępny token."""
    branch = current_branch(repo)
    diff_stat = get_diff_summary(repo, base)
    remote_url = get_remote_url(repo)
    slug = parse_github_slug(remote_url)
    token = os.environ.get("GITHUB_TOKEN", "")

    if not body:
        body = (
            f"## Zmiany\n\nBranch: `{branch}`\n\n"
            f"```\n{diff_stat or '(brak diff)'}\n```\n\n"
            f"## Jak testować\n- [ ] Uruchom testy: `pytest`\n"
            f"## Generowane przez\nqwen-agent (~/qwen-agent/github/git_agent.py)"
        )

    pr_url_hint = ""
    api_result = None

    if token and slug:
        try:
            r = httpx.post(
                f"https://api.github.com/repos/{slug}/pulls",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"title": title, "body": body, "head": branch, "base": base},
                timeout=15,
            )
            if r.status_code == 201:
                api_result = r.json()
                pr_url_hint = api_result.get("html_url", "")
        except Exception as e:
            api_result = {"error": str(e)}
    else:
        pr_url_hint = (
            f"https://github.com/{slug}/compare/{base}...{branch}?expand=1"
            if slug else "(ustaw GITHUB_TOKEN + GITHUB_REPO żeby otworzyć PR automatycznie)"
        )

    return {
        "status": "pr_ready" if api_result and "html_url" in api_result else "pr_description_only",
        "title": title,
        "body": body,
        "branch": branch,
        "base": base,
        "pr_url": pr_url_hint,
        "api_result": api_result,
    }


def cmd_auto(repo: str, branch_name: str, message: str, pr_title: str,
             files: Optional[list] = None) -> dict:
    """Pełny pipeline: branch → commit → push → PR."""
    results = {}

    results["branch"] = cmd_branch(repo, branch_name)
    print(f"[branch]  {results['branch']}")

    results["commit"] = cmd_commit(repo, message, add_all=not files, files=files)
    print(f"[commit]  {results['commit']}")

    results["push"] = cmd_push(repo)
    print(f"[push]    {results['push']['status']}")

    results["pr"] = cmd_pr_description(repo, pr_title)
    print(f"[pr]      {results['pr']['status']}")
    if results["pr"].get("pr_url"):
        print(f"          URL: {results['pr']['pr_url']}")

    return results


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="GitHub automation dla qwen-agent")
    parser.add_argument("command", choices=["branch", "commit", "push", "pr", "auto"])
    parser.add_argument("--repo", default=".", help="Ścieżka do repo (domyślnie: .)")
    parser.add_argument("--name", help="Nazwa brancha")
    parser.add_argument("--message", "-m", help="Treść commita")
    parser.add_argument("--title", help="Tytuł PR")
    parser.add_argument("--body", default="", help="Opis PR")
    parser.add_argument("--base", default="main", help="Branch bazowy PR")
    parser.add_argument("--remote", default="origin", help="Remote name")
    parser.add_argument("--all", dest="add_all", action="store_true", help="git add -A")
    parser.add_argument("--files", nargs="*", help="Pliki do dodania")
    parser.add_argument("--branch", help="Branch dla auto pipeline")
    args = parser.parse_args()

    repo = str(Path(args.repo).resolve())

    if args.command == "branch":
        r = cmd_branch(repo, args.name or f"feat/agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    elif args.command == "commit":
        r = cmd_commit(repo, args.message or "agent: automated commit", args.add_all, args.files)
    elif args.command == "push":
        r = cmd_push(repo, args.remote)
    elif args.command == "pr":
        r = cmd_pr_description(repo, args.title or "Agent PR", args.body, args.base)
    elif args.command == "auto":
        r = cmd_auto(
            repo,
            args.branch or args.name or f"feat/agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            args.message or "agent: automated changes",
            args.title or "Agent: automated PR",
            args.files,
        )

    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
