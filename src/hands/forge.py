"""The reading of GitHub through `gh` that `hands ci-wait` and doctor's `main`
row share (DESIGN §45).

Read-only: every call is a GET (`gh api` with no method or field) or a `gh pr`
read. Like `hands hosted-review` (§39) it speaks a transport only through the
`gh` on PATH, argv only, no stdin, no prompt. The repository is named
explicitly, `<owner>/<repo>` read from a github.com `origin` URL in https or
ssh form, never left to gh's own choice of remote.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hands.playbook import GIT_ENV_CLEARED

#: Seconds one `gh` or `git` call may take before it counts as not answering.
GH_TIMEOUT_S = 120.0

_NAME = r"[A-Za-z0-9_.-]+"
#: §45: a github.com URL in https or ssh form (scp-like or `ssh://`).
_ORIGIN_FORMS = (
    re.compile(rf"https?://(?:[^@/\s]+@)?github\.com(?::\d+)?/({_NAME})/({_NAME})/?", re.I),
    re.compile(rf"ssh://(?:[^@/\s]+@)?github\.com(?::\d+)?/({_NAME})/({_NAME})/?", re.I),
    re.compile(rf"(?:[^@/:\s]+@)?github\.com:({_NAME})/({_NAME})/?", re.I),
)


class ForgeError(Exception):
    """A read that did not answer; the message is the reason, with no token in it."""


def owner_repo(url: str) -> str | None:
    """`<owner>/<repo>` of a github.com URL, or None for any other URL."""
    for form in _ORIGIN_FORMS:
        match = form.fullmatch(url.strip())
        if match:
            owner, repo = match.groups()
            repo = repo.removesuffix(".git")
            if owner in (".", "..") or repo in ("", ".", ".."):
                return None
            return f"{owner}/{repo}"
    return None


def origin_url(clone: Path) -> str:
    """`git remote get-url origin` in `clone`; the URL is never put in an error."""
    env = {name: value for name, value in os.environ.items() if name not in GIT_ENV_CLEARED}
    try:
        done = subprocess.run(
            ["git", "-C", str(clone), "remote", "get-url", "origin"],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=GH_TIMEOUT_S, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        raise ForgeError(f"git remote get-url origin did not run: {exc}") from exc
    if done.returncode != 0:
        said = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
        raise ForgeError(f"no origin: {said}")
    return done.stdout.strip()


def origin_repo(clone: Path) -> str:
    """`<owner>/<repo>` of `clone`'s origin, or why there is none."""
    repo = owner_repo(origin_url(clone))
    if repo is None:
        raise ForgeError("origin is not a github.com repository")
    return repo


def gh_path() -> str:
    path = shutil.which("gh")
    if path is None:
        raise ForgeError("no `gh` on PATH")
    return path


def said(text: str) -> str:
    """What `gh` printed, on one line, with every `Token:` line dropped."""
    kept = [line.strip() for line in text.splitlines() if line.strip() and "Token:" not in line]
    return " ".join(kept) or "(nothing printed)"


def run_gh(gh: str, *args: str, timeout: float = GH_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"}
    try:
        return subprocess.run(
            [gh, *args], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=timeout, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        raise ForgeError(f"gh {' '.join(args[:2])} did not run: {exc}") from exc


def signed_in(gh: str, *, timeout: float = GH_TIMEOUT_S) -> None:
    """`gh auth status --active --hostname github.com` (§36): exit 0, or why not."""
    done = run_gh(gh, "auth", "status", "--active", "--hostname", "github.com", timeout=timeout)
    if done.returncode != 0:
        raise ForgeError(
            f"`gh` is not signed in to github.com: {said(done.stderr or done.stdout)}"
        )


def _json(done: subprocess.CompletedProcess[str], what: str) -> Any:
    if done.returncode != 0:
        raise ForgeError(f"{what}: {said(done.stderr or done.stdout)}")
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise ForgeError(f"{what}: not JSON ({exc})") from exc


def branch_rules(
    gh: str, repo: str, branch: str, *, timeout: float = GH_TIMEOUT_S
) -> list[dict[str, Any]]:
    """`gh api repos/<repo>/rules/branches/<branch>`: the branch's effective rules
    (a GET; `[]` for a branch no rule applies to)."""
    done = run_gh(gh, "api", f"repos/{repo}/rules/branches/{branch}", timeout=timeout)
    rules = _json(done, f"{branch}'s rules")
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise ForgeError(f"{branch}'s rules: expected a list of rules")
    return rules


def rule_types(rules: list[dict[str, Any]]) -> list[str]:
    """Each rule type, once, in the order the rules name them."""
    return list(dict.fromkeys(str(rule.get("type")) for rule in rules))


def required_checks(rules: list[dict[str, Any]]) -> list[str]:
    """The `context` of each entry of every `required_status_checks` rule, once each."""
    names: list[str] = []
    for rule in rules:
        if rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters") or {}
        for entry in parameters.get("required_status_checks") or []:
            context = entry.get("context") if isinstance(entry, dict) else None
            if isinstance(context, str) and context and context not in names:
                names.append(context)
    return names


def pr_branches(gh: str, repo: str, pr: int, *, timeout: float = GH_TIMEOUT_S) -> tuple[str, str]:
    """The pull request's base and head branch names."""
    done = run_gh(
        gh, "pr", "view", str(pr), "--repo", repo, "--json", "baseRefName,headRefName",
        timeout=timeout,
    )  # fmt: skip
    data = _json(done, f"pull request #{pr}")
    base = data.get("baseRefName") if isinstance(data, dict) else None
    head = data.get("headRefName") if isinstance(data, dict) else None
    if not isinstance(base, str) or not base or not isinstance(head, str):
        raise ForgeError(f"pull request #{pr}: no base branch in gh's answer")
    return base, head


#: gh's answer before the first check registers (gh 2.89: exit 1, on stderr).
NO_CHECKS = re.compile(r"no checks reported on the '.*' branch")


def pr_checks(
    gh: str, repo: str, pr: int, *, timeout: float = GH_TIMEOUT_S
) -> list[dict[str, str]]:
    """`gh pr checks <pr> --json name,bucket,link`; `[]` while none is reported."""
    done = run_gh(
        gh, "pr", "checks", str(pr), "--repo", repo, "--json", "name,bucket,link",
        timeout=timeout,
    )  # fmt: skip
    if done.returncode != 0 and NO_CHECKS.search(done.stderr or ""):
        return []
    data = _json(done, f"pull request #{pr}'s checks")
    if not isinstance(data, list):
        raise ForgeError(f"pull request #{pr}'s checks: expected a list")
    found = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            found.append(
                {
                    "name": item["name"],
                    "bucket": str(item.get("bucket") or "pending"),
                    "link": str(item.get("link") or ""),
                }
            )
    return found
