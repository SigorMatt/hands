# CHECKPOINT

Mission: 29 (meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 with §6, §8, §10,
§13, §27, §31, §32, §35, §36, §39, §43, §44; meta/reviews/REVIEW-28.md;
FINDINGS H-079, H-080; docs/PR-CI-GATE.md).
Branch: `mission-29`, from main f7d61c8; every unit commits and pushes to
it; U7 opens the PR, waits for its `check` check and the hosted review,
fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-079 "decided (DESIGN §45
...), scheduled for U6"; H-080 "decided (DESIGN §45 ...), scheduled for
U4"). Green 3/3 (5137). Pushed; `origin/mission-29` exists.

Done: U1 624aff0 — .github/workflows/check.yml (checkout v7.0.1, setup-uv
v10.3.0 sha-pinned, python 3.11); conftest proxy fixture to 127.0.0.1:9; 12
doctor --live tests pointed at a local ntfy stub; 3 wheel-build tests skip
when uv's cache lacks hatchling (offline); bare run green 3/3 (5140+3 skip),
usual 3/3 (5143). Not proven: the workflow on GitHub's runner, the check's
reported name.

Done: U2 db5c000 — `[repository] main` (direct default, third refused);
src/hands/forge.py (added: owner/repo, rules, required checks, pr checks);
`hands ci-wait` (exit 0/1/2/3, per-check lines, last line; limit/interval/
clock injectable); doctor `main` row (ok, four WARNs, skips);
templates/config.toml; fake_gh rules/checks; green 3/3 (5216). Not proven:
real gh beyond the fake, GitHub's real rules response.

Done: U3 cd0e13f — apply prompt by `[repository] main` (direct + the
refused-push sentence; pull-request §45 word for word, lines joined by single
spaces; branch kit/<stem>-<12 hex>); phone kit, kit apply, kit file pass the
shape and sha256; kit check prints sha256 and the shape's prompt; resumes of
an apply (orphaned, failed, limit) re-send its own prompt via the chain walk;
§32 approved-apply test on the chain's first job; green 3/3 (5237). Not
proven: a real builder following either prompt; handbook §3's pull-request
prompt (U5).

Done: U4 39e7976 — an apply's builder.done not `VERDICT: kit applied` is
the engine's stop before any rule (chain_first), published once over a pause,
never kept; spool.carries_ci + CI hold reason (playbook's wins); kit check
WARN ci:; pull-request journal sentence; handbook §19 two rows + table pins;
H-080 resolved; green 3/3 (5274). Readings: the stop fires with no playbook
file; under a human pause it marks the suppressed stop (blocks resume rules
until `resume`). Not proven: daemon end to end. Left for U5: §19 row's
`hands ci-wait` mention (tests/test_docs.py's command lists).

Done: U5 897ec34 — both review protocols (rules read first, retry,
pull_request branch: Direct blocker, checks wait, review on the branch,
merge wait / not merged, return to main, journal carried over; .github/ and
scripts/check blocker); brief template; architect/CLAUDE.md rules 1, 3;
handbook §3/§9/§10/§12/§18/§19; INTEGRATION, OPERATIONS, PLAYBOOK.md,
CLAUDE.md; tests/test_docs_45.py added; guard already allows git show
origin/<branch>:...; green 3/3 (5353). Not proven: a real aux following it.

Done: U6 7e0914e — `kept_since_rest` flag in pipeline.json set when an end
is kept or replaced after the at-rest mark; check_at_rest republishes the
new list at the next quiet moment; restart publishes only an unpublished
change; §19 row, PLAYBOOK.md, OPERATIONS.md; H-079 resolved. Not proven:
daemon-level republish path, orphan-feed/check order at restart.

Done: U7 9fa853c (report), PR #9; b3f5b91 (tests: zipfile Unicode path per
Python version — the runner's 3.11 failed it, product safe); e375630 (cli:
hosted findings 3, 4); H-081, H-082 (high, blocks the switch to
pull-request), H-083 filed for findings 1, 2, 6; 5 and 7 dismissed; fetch 2:
5 of 7 open; check passed at e375630 (github-actions 15368); (this commit)
the Hosted review and CI sections + archive PR-9/1..2.
Mission 29 — FINISHED after this push and its check; tree returns to main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-29` (never `main`), ./scripts/check green three consecutive
runs before each commit (each a foreground call, 15-minute / 900000 ms
timeout, written `./scripts/check; echo "check-exit=$?"`), explicit paths
only in `git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`; a `refused:`
report is not retried. No write to GitHub beyond pushing `mission-29` (and
U7's PR). Not touched: the ruleset or any repository setting, the harness
seam, review 25's should-fix 2 and 3, a local-model harness, any M9 command,
credential profiles, docs/ARCHITECT-INSTRUCTION.md, docs/PR-CI-GATE.md, this
repository's PLAYBOOK.toml; no host change.
