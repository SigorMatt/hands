# FINAL-REPORT-26 — mission 26: the project separation

VERDICT: mission 26 finished pr=6

Source: meta/BUILDER-26-PROMPT.md, DESIGN v3.25 §42 (with §27, §31, §33,
§36, §38), meta/reviews/REVIEW-25.md. Branch `mission-26`, from main
9877b57. Gate: `./scripts/check` green three consecutive runs before every
commit (4823 tests at U4's tip).

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch and findings | 5c1c9c3 | `plan:` — plan, checkpoint; H-070 and H-071 filed (decided, mission 27), H-072 filed (decided, closed by U4) |
| U1 `consult` from the phone and the laptop | b956e2a | phone `consult <secret> <text>` (+ an optional `.md` attachment) and `hands consult [--file] [<text>]` ask the engine to start one architect consultation of origin `playbook`; the prompt builder takes a job or the human's reason; `consult.sent`/`consult.done` fields; refusals titled `consult`; architect/CLAUDE.md's new rule and rule 13's routes 4 and 5; handbook §16 |
| U2 `digest` | d222109 | `src/hands/digest.py` (added): `hands digest` (and `--json`) and phone `digest <secret>`, one line per project, redacted before any cut; docs/OPERATIONS.md `digest` row |
| U3 The decisions kit and the owner file on a resume | 592fc6e | `hands kit check` passes a decisions kit 6 of 6 with the plan-only apply prompt; `hands kit apply` and the phone's `kit` path file its apply; `kit_file` refuses one; the brief template's §R carries the owner-file sentence; handbook §3, §4, §11 |
| U4 The handbook, the instruction and the runbooks | 79eb270 | handbook §10's builder-question row, §13, §14, §18 and the new §19 (the operator table, the `digest` row, the HF report's form); docs/ARCHITECT-INSTRUCTION.md's opening, rules 3, 9, 12, 14 and rule 15; docs/OPERATIONS.md `consult` row; docs/INTEGRATION.md H-072; H-072 resolved-by-doc |
| U5 Final report | (this commit) | this file; the `## Hosted review` table and archive follow the pull request |

## 2. What the tests prove

- A phone `consult` and a `hands consult` in role mode each start one
  architect job of origin `playbook`, never `phone`; its prompt's first line
  is `hands consult: consult on job none (role human)` and it holds the
  reason under `The human's reason for this consultation` and no review
  section; an attached `.md` lands in `kit_dir` under its name (or the
  first free `<stem>-<n>.md`) and its text follows the reason.
- Each refusal §42 lists starts nothing, and on the phone is published
  titled `consult`; the budget counts the consultation and refuses at the
  limit; a stopped pipeline is un-paused before `consult.sent`; the
  consultation's `next kit` kit is filed and applied as any.
- `consult.sent` carries every field §42 lists and never the reason;
  `consult.done` and the journal line read `consult by the human`, never
  `job none`; a review's consultation prompt is byte-identical to main's.
- Neither guarded role's guard admits `hands consult` or `hands digest`;
  the architect guard with `HANDS_CONSULT_ROLE=human` still refuses every
  send and admits its read set.
- `hands digest` prints one line per project in name order with §42's
  fields, `down` for a missing, dead or silent socket; a config that does
  not load is named by its file only (its secret-shaped value is absent);
  a secret straddling the 100-character cut is absent in full; the phone
  publishes the same lines titled `digest` on `ntfy_topic`.
- A decisions kit passes `hands kit check` 6 of 6 (plain zip, `zip -r`
  directory entries, a directory, two owner files); 14 variants that are
  not decisions kits fail `brief` exactly as on main; `hands kit apply` and
  the phone's `kit` path file the held apply; `hands kit file` refuses one;
  the template §R sentence is pinned; a kit from the templates still
  passes 6 of 6.
- Every `stop` and `notify` message of both template playbooks appears in
  handbook §19's table; the table's four columns, the HF report's form, the
  instruction's opening paragraph, the four reworded rules and rule 15 are
  pinned word for word against DESIGN §42; a `hands project add` with fakes
  prints the instruction with rule 15; the no-phone `consult` and `digest`
  rows and the H-072 sentence are pinned.

## 3. NOT PROVEN

- No real phone sent `consult` or `digest`; no real ntfy attachment was
  fetched, and a real ntfy server's size limit on a long digest is untried.
- No real decisions kit was applied, and no builder has yet followed the
  §R owner-file sentence on a real resume.
- No project chat has yet answered a notification from the operator table;
  no test lists every stop reason in the code, so §19 may miss one written
  outside the templates.
- `consult`'s refusal while an architect job is queued (only running and
  held are tested); a daemon restart during a human-started consultation;
  the no-`[roles.architect]` refusal is tested at the engine only (the
  daemon will not start without the table in role mode).
- `digest`'s `spool unreadable` branch.
- The CLI ceiling on `BASH_MAX_TIMEOUT_MS` (none) was read from Claude Code
  2.1.302's bundled files only.

## 4. Deviations

- U1 also changed `src/hands/kit.py` (the fetch's extension) and
  docs/INTEGRATION.md (its command list); U2 also changed
  docs/INTEGRATION.md and docs/OPERATIONS.md (the `digest` row the runbook
  test requires); U4 edited meta/findings/FINDINGS.md (H-072's status).
  Each is listed in its commit's body.
- Where §42 is silent: "the playbook in force" for `consult` is the
  committed playbook reloaded at the request; a refused attachment stays in
  `kit_dir` as a refused kit does; `digest` reads `driver <used>/<default>`
  when no playbook loads, the newest builder job's verdict even while it
  runs, and the newest `stop` event even after a resume; a decisions kit's
  `<date>` is any run of non-space characters; `hands kit file`'s client
  prints its PASS lines before the daemon's refusal; §19 writes the route
  in the "Who answers" cell.
- U1's gate saw one unrelated failure
  (`test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot`)
  that did not recur in eight further runs; three consecutive green runs
  followed. U0's three gate runs ran in one foreground call.

## Review items

| REVIEW-25 item | Disposition |
|---|---|
| Should-fix 1 — the correction line under FINAL-REPORT-25 §3's NOT PROVEN line on the U4 warning test | carried to mission 27 by DESIGN §42 |
| Should-fix 2 — the capture script after a failed `find` | carried to mission 29 by DESIGN §42 |
| Should-fix 3 — docs/HARNESS-PROBE.md's approval flag form and stray line break | carried to mission 27 by DESIGN §42 |

## Hosted review

(written after the pull request's hosted review)
