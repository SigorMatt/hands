# CHECKPOINT

Mission: 25 (meta/BUILDER-25-PROMPT.md, DESIGN v3.24 §41 with §39, §40;
meta/reviews/REVIEW-24.md; docs/HARNESS-PROBE.md).
Branch: `mission-24` (PR #5, open), main 20aac9f merged in at cc2a9e5;
every unit commits and pushes to it; U6 opens no PR, reads the hosted
review again, fixes, and returns the tree to main.

Done: U0 (`plan:`) — main merged at cc2a9e5, H-062 note; green 3/3 (4636).

Done: U1 11cd19c — find and the record read through `failed`; cut inside the redactor after redaction; 5 tests (hanging find/python3, straddle 4000, URL-encoded, by-value ntfy.password), -k 5 pinned; green 3/3 (4641).

Done: U2 2f9e219 — staged_path/read_staged O_NOFOLLOW|O_NONBLOCK + fstat; remove_staged in api finally; 8 socket-client cases ('..', symlink, FIFO guarded, dir, missing, .part removed x3); green 3/3 (4649).

Done: U3 f53ec39 — tests only (code already right): two sessions same task id, 1025th evicts oldest, backslash ambiguous prefix, cap counts journal sentence dirty/clean; each mutation red; green 3/3 (4654).

Done: U4 f0eb0d0 — kit.py unchanged (warning already unconditional), pinned (no-kickoff case red under the mutation); stale defined in both protocols and handbook §7; opening remove --force and closing prune pinned by paragraph; green 3/3 (4659).

Done: U5 4f46bda — Codex VERDICT partial + footnote; opening qualified; OpenCode/dsh re-checked, stay unavailable; on-request approval row left a gap (no approval event, bwrap fails, file absent); grep -c redacted = 3; green 3/3 (4659).

Done: U6 (this commit) — meta/FINAL-REPORT-25.md (NOT PROVEN, Review items, Hosted review); archive PR-5/4..5; bot at 4f46bda: 1 of 9 open (sub-agents/protected metadata, dismissed again); no fix needed.
Mission 25 — FINISHED after this push; PR #5 open for review 25; tree returns to main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-24`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the backend
seam, the credential profiles, the polish round, any M9 command (missions 26
and 27), no host change (AppArmor is the human's).
