#!/usr/bin/env python3
"""A stand-in for the `gh` CLI, so no test runs the real one (DESIGN §35).

`tests/conftest.py` puts this script on PATH as `gh` for every test. It answers
the two commands `hands doctor` runs, `gh --version` and `gh auth status
--active --hostname github.com` (plain `gh auth status` too), in the shape
`FAKE_GH_MODE` names:

- `ok` (the default): logged in, scopes include `repo`, printed on stdout as
  gh 2.92 does;
- `stderr`: logged in with `repo`, in the older format, printed on stderr;
- `unauth`: not logged in, exit 1;
- `norepo`: logged in, scopes without `repo`;
- `multihost`: a GitHub Enterprise host is listed first, with another login
  and no `repo` scope, then github.com with `repo`; plain `gh auth status`
  exits 1 for a bad account on a third host, as gh does when any account is
  bad, while `--active --hostname github.com` prints github.com alone, exit 0;
- `noversion`: `gh --version` exits 1;
- `hang`: `gh auth status` sleeps far past doctor's probe timeout.

Every logged-in shape prints a `Token:` line carrying FAKE_TOKEN, so a test can
prove doctor never repeats it.
"""

import os
import sys
import time

FAKE_TOKEN = "gho_FAKEtokenFAKEtokenFAKEtoken0000"
LOGIN = "fake-login"
VERSION = "gh version 9.9.9 (fake)\nhttps://github.com/cli/cli/releases/tag/v9.9.9"
GHE_HOST = "ghe.example.invalid"
GHE_LOGIN = "ghe-login"
ACTIVE_GITHUB = ["auth", "status", "--active", "--hostname", "github.com"]


def github_com(scopes: str) -> str:
    return (
        "github.com\n"
        f"  ✓ Logged in to github.com account {LOGIN} (keyring)\n"
        "  - Active account: true\n"
        "  - Git operations protocol: https\n"
        f"  - Token: {FAKE_TOKEN}\n"
        f"  - Token scopes: {scopes}"
    )


def multihost(argv: list[str]) -> int:
    if argv == ACTIVE_GITHUB:
        print(github_com("'gist', 'read:org', 'repo', 'workflow'"))
        return 0
    print(
        f"{GHE_HOST}\n"
        f"  ✓ Logged in to {GHE_HOST} account {GHE_LOGIN} (keyring)\n"
        "  - Active account: true\n"
        "  - Git operations protocol: https\n"
        f"  - Token: {FAKE_TOKEN}\n"
        "  - Token scopes: 'read:org'\n\n"
        + github_com("'gist', 'read:org', 'repo', 'workflow'")
        + "\n\nother.example.invalid\n"
        "  X Failed to log in to other.example.invalid account stale (keyring)\n"
        "  - The token in keyring is invalid."
    )
    return 1


def status(mode: str) -> int:
    if mode == "unauth":
        print(
            "You are not logged into any GitHub hosts. To log in, run: gh auth login",
            file=sys.stderr,
        )
        return 1
    if mode == "stderr":
        print(
            "github.com\n"
            f"  ✓ Logged in to github.com as {LOGIN} (oauth_token)\n"
            "  ✓ Git operations for github.com configured to use https protocol.\n"
            f"  ✓ Token: {FAKE_TOKEN}\n"
            "  ✓ Token scopes: gist, read:org, repo, workflow",
            file=sys.stderr,
        )
        return 0
    scopes = "'gist', 'read:org', 'workflow'" if mode == "norepo" else (
        "'gist', 'read:org', 'repo', 'workflow'"
    )
    print(github_com(scopes))
    return 0


def main(argv: list[str]) -> int:
    mode = os.environ.get("FAKE_GH_MODE", "ok")
    if argv == ["--version"]:
        if mode == "noversion":
            print("fake gh: broken install", file=sys.stderr)
            return 1
        print(VERSION)
        return 0
    if argv in (["auth", "status"], ACTIVE_GITHUB):
        if mode == "hang":
            time.sleep(60)
            return 0
        if mode == "multihost":
            return multihost(argv)
        return status(mode)
    print(f"fake gh: unsupported {argv!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
