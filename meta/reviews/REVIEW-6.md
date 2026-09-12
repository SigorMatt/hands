# REVIEW-6 — cold review of mission 6 (close review 5, retire the driver wait)

Aux session, no mission context. Base `44e42ba` → `origin/main` `dca0820`.
Protocol: `meta/REVIEW-PROTOCOL.md`.

    VERDICT: review mission 6 blockers=2 should-fix=6

Read: `DESIGN.md` §22 (with §4, §5, §7, §11, §12, §21),
`meta/BUILDER-6-PROMPT.md`, `meta/FINAL-REPORT-6.md`,
`meta/findings/FINDINGS.md` (H-012, H-013), `meta/reviews/REVIEW-5.md`,
`git log --oneline 44e42ba..origin/main`.

**Scope, stated first.** The prompt's base is `44e42ba`, which is itself a unit
commit of this mission (U5's first). So the range holds three unit commits —
`3809fcf` (U5's second), `56bef53` and `3dd3403` (U6) — and four `meta:`
commits. One sub-agent per unit commit, each in its own detached worktree; the
`meta:` commits skipped. Mission 6's other five unit commits (`81e4cd2` U1,
`0042433` U2, `5ffbe33` U3, `fba759b` U4, `44e42ba` U5a) are **outside the base
and were not reviewed per-commit**. To keep the mission-level verdict honest I
re-drove the mission's five acceptance criteria by hand at the tip instead
(§Notes 1); that exercises U1–U3's shipped behaviour but is not a substitute
for the test-first and design-conformance checks the protocol asks per commit.
A future review of U1–U4 would start at `b950956`.

## Blockers

1. **The tip's `README.md` still tells a reader the retired procedure exists,
   and that the question §11 answers is open.** `README.md:116-118` at
   `dca0820`:

       Whether a finished background task wakes an idle interactive Claude
       Code session (DESIGN §11, §16) is still an open question — `hands
       doctor` prints the procedure that answers it.

   DESIGN §11's decision paragraph — the half U6 correctly chose to follow —
   says the opposite in as many words ("The wake-path question is answered: it
   works, and it is not worth its price on Claude Code 2.1.x"), and after
   `56bef53` `hands doctor` prints a **notification** check (ntfy, `pause`, a
   gated send), not a wake procedure, which the same `README.md` says 35 lines
   earlier at `:78-80`. So the file contradicts the design section the unit
   implements, the code at the tip, and itself. This is not a spelling U6 could
   not have reached: `3dd3403` exists precisely to sweep "the sentences outside
   the grep that still said the driver waits", it edited `README.md` for that
   reason (`:77` and `:92`, the "three commands" comment and the `wait` line),
   and `README.md` is in the phrase test's file list — the phrase list simply
   does not contain this sentence's words, so nothing fails. Found
   independently by both U6 sub-agents, confirmed by me at the tip.
   `FINAL-REPORT-6.md` §3 item 9 concedes the class in general ("a stale
   claim spelled a new way is not caught"); it does not name this instance, and
   §1 U6 reports the same open question as *replaced* — true of
   `docs/INTEGRATION.md`, not of `README.md`.

2. **`FINAL-REPORT-6.md` §1 U5 item 7 makes a totality claim `hands notify
   --test` contradicts, in review 5 should-fix 7's own shape.** The report:
   "`_utf8_bytes(text, where)` is the one place a string a human handed the
   client is refused for not being UTF-8." Driven at the tip against a real
   config, `PYTHONUTF8=1`, the same bytes on the same argv:

       $ hands --project revprobe send --role builder --context clear $'hi\xff'
       hands: a prompt argument: not UTF-8 text ('utf-8' codec can't encode
       character '\udcff' in position 2: surrogates not allowed)      # exit 2
       $ hands --project revprobe notify --test $'hi\xff'
       hands: http://127.0.0.1:1/rev-probe-topic did not take the message:
       UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' …
                                                                     # exit 1

   `notify --test` is a client-side command (`cli._notify` →
   `notify.send_test`), so it never reaches `call()` and the request-wide check
   cannot see it: a string a human handed the client dies at the encode, with a
   codec message, exit **1**, and a line that blames the ntfy URL for a
   client-side encoding fault. That is the exact shape review 5 should-fix 7
   objected to, one command over. Review 5's item was scoped to the prompt
   routes and those do now agree, so the *table* entry is defensible — the
   defect is the report sentence, which the builder brief forbids by name
   ("never a totality claim … unless a test enumerates the whole space") and
   which the disk falsifies. Either narrow it to "every string a **request**
   carries" (what the commit title says and what the tests cover) or route
   `notify --test`'s message through `_utf8_bytes` too.

## Should-fix

1. **U6's sweep is not exhaustive even for its own phrases, and the gate cannot
   see the offender.** `tests/test_playbook.py:689-691` at the tip still reads
   "a driver blocked on `hands wait --for stop,held` is not woken by a pause";
   `driver blocked on` is a literal entry in `tests/test_docs.py:217`'s
   `DRIVER_WAITS`, but `test_playbook.py` is not in the scanned file list, so
   the pinned phrase survives in a file the pin does not read. "Nineteen
   sentences in eight files" was therefore the count of what the list looked
   at, not of what said it.
2. **Both U6 regression tests are partly circular, and the count is of pairs,
   not sentences.** The phrase lists were derived from the very hits they pin,
   so they prove those sentences do not return and nothing about a new one; the
   19 offenders are 19 (file, phrase) pairs over ~17 sentences
   (`docs/PLAYBOOK.md:81` and `src/hands/playbook.py:974` each match two
   phrases). And `test_the_docs_say_the_humans_check_is_the_drivers_wake`'s
   `"check" in text.lower()` half was already true at `56bef53^` for all three
   documents — that half pins nothing. §3 item 9 says these are source-text
   assertions; it does not say one half of one of them is vacuous.
3. **A unit commit shipped U7's unfinished deliverable, placeholders and all.**
   `3dd3403` adds `meta/FINAL-REPORT-6.md` (+444) — swept in by a `git add -A`
   — and the version it carries has seven unfilled placeholders, including the
   mission's gate claim: "green on the pushed tip `TIP_SHA` … `TIP_COUNT
   passed` (TIP_TIMES)". The commit body's file list never mentions the file.
   The tip's copy is clean and the report's front matter discloses the accident
   honestly (and correctly does not rewrite history, DESIGN §20); what is left
   is a pushed sha whose body does not describe its own diff. Worth a line in
   the builder brief: `git add -A` in a tree that holds a draft of the report.
4. **The UTF-8 check and the size measurement walk different trees.**
   `cli._labelled_strings` (`:995`) iterates top-level `str` and list-of-`str`
   values only, while `cli._strings` (`:967`) recurses and `json.dumps` encodes
   dict keys as well. Driven in-process by the U5 sub-agent, `_checked_request`
   with `{"files": {"a": bad}}`, `{"files": {bad: "v"}}` or `{"file": [[bad]]}`
   raises a bare `UnicodeEncodeError` — the exit-1 shape — instead of §4's
   refusal. Latent: no command builds such params today. Not named in NOT
   PROVEN, and it is the seam that made blocker 1 of review 5 silent.
5. **Positionals are refused under flag names the human never typed.**
   `_utf8_bytes`'s docstring says the label is "the name the human knows the
   string by", but `hands result $'job-\xff'` (also `show`, `open`) answers
   `hands: --job: not UTF-8 text …` and `put`/`get`/`ls` on a bad path answer
   `hands: --path: …`. Right refusal, right exit code, invented name.
6. **DESIGN §11's self-contradiction is recorded in the report, not in
   `FINDINGS.md`.** §11 still opens by instructing the driver to run `hands
   wait --for stop,held` as a background Bash task and still closes with the
   background-completion fallback, around the decision paragraph that retires
   both. U6 was right to follow the decision paragraph and §22, and
   `FINAL-REPORT-6.md` §3 item 13 and §6 item 1 say so plainly — but
   `CLAUDE.md` and the builder brief both say a needed design change goes to
   `meta/findings/FINDINGS.md`, and no H-number covers this. A report is a
   snapshot; `FINDINGS.md` is the list that survives the mission.

## Notes

1. **Acceptance, re-driven by me at the tip `dca0820`** (the five criteria of
   `BUILDER-6-PROMPT.md`, since five of this mission's unit commits are outside
   the base): `./scripts/check` green — ruff clean, `1112 passed in 61.48s`,
   `check: green`, exit 0 (one run here; the `3dd3403` sub-agent ran two more,
   1112 both times, and the builder claims three). The blocker-1 reproduction
   refuses on the client: at-cap `--prompt-file` plus twelve `--file` values of
   131 000 backslashes → exit 2, `the request is 13630014 bytes on the wire,
   over the daemon's 13107200 byte line room; the largest part is the prompt at
   10485760 bytes`, no socket opened. `tail -n 0` / `-n -3` → exit 2, `tail -n
   takes 1 or more, not 0; the answer is capped at 1000 entries (§4)`. All six
   should-fix-1 guard probes blocked at the tip (`--upload-pack=`, `-C ./src
   fetch --upload-pack=`, `fetch --exec=`, `ls-remote --exec=`, `branch
   --edit-description`, `-C --exec-path=`), `bash_guard --selftest` 100/100 and
   `no_background --selftest` 65/65, both exit 0. `driver/CLAUDE.md` rule 8
   equals DESIGN §12 rule 8 (hand-compared by the `56bef53` sub-agent).
   `meta/FINAL-REPORT-5.md` §3 carries three dated corrections (`:272`, `:295`,
   `:317`), each after an untouched original.
2. **Forbidden files, checked over the whole mission** (`bb9d8fb^..dca0820`,
   not just the base): no unit commit touches `DESIGN.md`, `meta/plan.md` or
   `meta/CHECKPOINT.md`. Four unit commits touch `meta/findings/FINDINGS.md`,
   which the brief asks for. The one meta/ exception is should-fix 3.
3. **NOT PROVEN read against the sub-agents.** §3 is unusually honest and
   mostly holds up: items 1 (the guard's allow list still permits `git branch
   <name>`, `git remote prune`, `git fetch origin main:main` — I confirmed all
   three allowed at the tip), 9 (source-text assertions; ntfy unwitnessed) and
   13 (DESIGN §11) each predicted what a reviewer would find. Blocker 1 is the
   case where item 9's general concession hides a specific live contradiction,
   and blocker 2 is a §1 sentence §3 does not qualify. Item 5's "nothing checks
   strings a request carries outside `params`" is true and narrower than §1's
   claim — the two sentences disagree with each other.
4. **What the range let me confirm about U5a and U1–U3 only indirectly.**
   `44e42ba` was not reviewed, so should-fix 3, 4, 5(a) and 6 of review 5 are
   closed on this review's word only as far as the tip's suite being green goes
   (`Runner.retained`, `ops.monitor_cmd` resolution, the config section scan,
   the audit-by-type rewrite). The report's own statement that 5(b) and 5(c)
   are **not closed and unscheduled** matches the disk (`playbook.py`'s
   `last_rule_sha256` comparison, `config.py`'s `_str_list` over
   `gates.patterns`), and neither is in `meta/BACKLOG.md`.
5. **`put --from FILE` sends the path, not the bytes** (`cli.py:353`), so a
   file of invalid UTF-8 is copied by the daemon without passing the client's
   check. Correct for a byte copy, but it is a third answer to "what does the
   client refuse" alongside blocker 2 and should-fix 4, and no test covers it.
6. Verified also: the test renamed by `3dd3403`
   (`test_the_driver_kit_spelling_resolves_to_real_event_kinds`) is gone from
   disk, so earlier mission reports cite a name that no longer exists — the
   report says so itself. `tests/test_wake.py:128,130` keep a stop reason
   "arrived while the driver was reporting", which is the retired model in a
   fixture string rather than a claim.

## Per-commit verdicts

sha 3809fcf — U5 of mission 6 (second commit), DESIGN §4 (+H-012), REVIEW-5 should-fix 7
1 claim check: claims match the disk. `_utf8_bytes` is the single refusal site; `_checked_prompt`, `_prompt_of` and `_checked_request` all call it, and `_checked_request` runs for every `call()`, so the breadth is real. The title's totality ("every string a request carries") is enumerated by no test — only `--gate` has one; `--file`/`--content` and all other params (`--job`, `--path`, `--reason`, `--quote`, `--grep`, `--origin`, `--since`, `--for`, `--role`) are unasserted, and the body admits the first two. `_utf8_bytes`'s docstring "the name the human knows the string by" overstates: positionals are refused as `--job` / `--path`, flags the human never typed.
2 test-first: PASS. With `git checkout 3809fcf^ -- src/hands/cli.py docs/INTEGRATION.md`, `uv run pytest tests/test_daemon.py tests/test_docs.py -q` → 2 failed: `…refuses_the_same_not_utf8_bytes_the_same_way` ("a prompt argument: hands: 'utf-8' codec can't encode characters in position 8-9: surrogates not allowed / assert 1 == 2") and `…a_gate_reason_that_is_not_utf8…` ("hands: 'utf-8' codec can't encode character '\udcff' in position 3 / assert 1 == 2"). test_docs stayed green — the INTEGRATION.md paragraph is pinned by nothing. Restored; `git status --porcelain` empty.
3 ./scripts/check: green — `== ruff ==` / `All checks passed!` · `== pytest ==` / `1109 passed in 73.06s (0:01:13)` · `== cli smoke ==` / `check: green`, exit 0 (one run; matches the body's 1109).
4 forbidden: none. `git show --stat` = docs/INTEGRATION.md, src/hands/cli.py, tests/test_daemon.py only. No DESIGN.md, no meta/plan.md, no meta/CHECKPOINT.md. One commit, `<area>: <one line>`, body names unit + §4, co-author trailer present.
5 NOT proven: (a) **`notify --test` is the same bug one command over.** Real subprocess, `PYTHONUTF8=1`, `hands --project probe2 notify --test $'hi\xff'` → exit **1**, `hands: http://127.0.0.1:1/probe-topic did not take the message: UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff'…` — a string argv carries, dying at the encode with a codec message and exit 1, i.e. exactly should-fix 7's shape; it never reaches `call()`, so "the one place" is one place per *request*, not per handed string. (b) **Positional labels are wrong names**: `result $'job-\xff'`/`show`/`open` → `hands: --job: not UTF-8 text…`, `put`/`get`/`ls $'drop/\xff'` → `hands: --path: …` (exit 2, right refusal, invented flag name). (c) **`_labelled_strings` walks only top-level str and list-of-str while `_wire_size`'s `_strings` recurses and `json.dumps` encodes dict keys**: in-process, `_checked_request` with `{"files": {"a": bad}}`, `{"files": {bad: "v"}}` and `{"file": [[bad]]}` each raised bare `UnicodeEncodeError` (exit-1 shape) instead of PromptError — latent only, no command builds such params today, and the body's last NOT PROVEN line does not name it. (d) `--project $'probe\xff'` → exit 1 "cannot read config …"; `--socket $'/tmp/s\xff'` → exit 1 "no daemon on …" (path semantics, arguably out of scope but not exit 2). (e) `put --from <file containing \xff>` is not checked at all — only the path travels, so the client connects and the daemon reads the bytes; untested either side. (f) I did close the body's first NOT PROVEN myself: all 19 params probed through a real `uv run hands` subprocess under `PYTHONUTF8=1` refuse with exit 2 and one message shape, and the argv/stdin routes behave identically under `LC_ALL=C` too.

sha 56bef53 — U6 first commit (driver kit + doctor text), DESIGN §11 decision paragraph, §12 rule 8, §22 bullet 1; not a REVIEW-5 item
1 claims true, and it picked the right half of the self-contradictory §11. driver/CLAUDE.md:50-53 == DESIGN.md §12 rule 8 verbatim (hand-compared, whitespace-normalized only; the exit-2 sentence really did move to driver/CLAUDE.md:102). doctor.wake_procedure() prints no arming step: ntfy doorbell, `check` as the driver's wake, `hands pause`/`--gate` send plus the clear-up, §11 cited; driver/README.md:47-54 and docs/INTEGRATION.md:158-162,344-346 say the same. §22 is the v3.5 changelog and §12 rule 8 already carries the new rule, so following the decision paragraph over §11's surviving v3.4 prose is correct — but no finding was filed for that contradiction (CLAUDE.md says file one), so DESIGN §11's "runs `hands wait --for stop,held` as a Claude Code *background* Bash task" and its dangling re-arm fallback stay invisible.
2 test-first: PASS. After `git checkout 56bef53^ -- docs/INTEGRATION.md driver/CLAUDE.md driver/README.md src/hands/doctor.py`: 5 failed / 39 passed. Red: test_driver_rule_8_is_the_design_section_12_rule_8 ("assert 'Never arm a ...not an event.' == 'Never arm a ... an approval.'"); test_no_shipped_document_tells_anyone_to_arm_a_background_wait; test_the_docs_say_the_humans_check_is_the_drivers_wake ("driver/README.md never names the doorbell (§11)"); test_the_wake_check_is_a_notification_test_not_an_armed_wait and test_the_notification_check_is_in_the_json_too (both "AssertionError: hands wait --for stop,held"). Restored; `git status --porcelain` empty.
3 ./scripts/check: green, exit 0 — "1112 passed in 78.89s (0:01:18)" / "== cli smoke ==" / "check: green".
4 forbidden: PASS. Stat is docs/INTEGRATION.md, driver/CLAUDE.md, driver/README.md, src/hands/doctor.py, tests/test_docs.py, tests/test_doctor.py only — no DESIGN.md, no meta/plan.md, no meta/CHECKPOINT.md, nothing under meta/.
5 NOT proven: (a) unit gate `grep -rn background driver/ docs/ src/hands/doctor.py` returns 11 hits, none an instruction to arm one (driver/CLAUDE.md:50 is rule 8's prohibition; doctor.py:21,404 are docstrings about the retirement; docs/INTEGRATION.md:7,273-302 are the no_background hook) — gate honestly met. (b) 3dd3403's "19 in 8 files" is the real count at this commit: I ran its own test against this tree and got exactly 19 offenders in README.md, docs/PLAYBOOK.md, api.py, cli.py, daemon.py, playbook.py, spool.py, tests/test_wake.py — but they are 19 (file,phrase) pairs over ~17 sentences (docs/PLAYBOOK.md:81 and src/hands/playbook.py:974 each match two phrases in one sentence), and the phrase list was derived from those same hits, so the gate is circular. Located: README.md:77,92; docs/PLAYBOOK.md:81; api.py:206,209; cli.py:47,720,721; daemon.py:502; playbook.py:951,974,976; spool.py:129; tests/test_wake.py:56,66,69,91. (c) One stale sentence neither commit's list reaches and which survives to the tip dca0820: README.md:114-116 "Whether a finished background task wakes an idle interactive Claude Code session (DESIGN §11, §16) is still an open question — `hands doctor` prints the procedure that answers it" — §11 declares that question answered and doctor no longer prints that procedure, so at 56bef53 the honest count is 18 distinct stale sentences. (d) The doctor tests do invoke the real CLI (`main([... "doctor"])`, JSON parsed) but assert only string presence/absence in the printed text — no behaviour, and nobody has run the printed procedure (ntfy delivery still unwitnessed, as the body says). (e) `test_the_docs_say_the_humans_check_is_the_drivers_wake`'s three-document loop is near-vacuous: `"check" in text.lower()` was already true at 56bef53^ for all three (the parent failed only on the ntfy assertion), so that half pins nothing. (f) `wake_check` JSON key genuinely unchanged (single site, src/hands/doctor.py:500) and §11 still cited (10 → 11 occurrences).

sha 3dd3403 — U6 second commit ("driver wait retired"), DESIGN §11, §12 rule 8, §22 bullet 1
1 Claim holds. api/cli/daemon/playbook/spool: AST identical to 3dd3403^ after stripping docstrings (checked mechanically); test_wake.py identical after stripping docstrings and normalizing the one rename; its assert lines byte-identical. Only executable change is tests/test_docs.py (new DRIVER_WAITS + WAKE_PATH_TEXT tuples, same assertion widened, test renamed) — no exit code, no resolve_kinds, no playbook semantics, no weakened assertion.
2 test-first: red. Reverting the 7 non-test files → test_docs.py:267 AssertionError "a shipped sentence still arms the retired wait (§11, §22)" listing 15 offenders in 7 files; also reverting tests/test_wake.py gives exactly 19 offenders in 8 files, matching the body. git status --porcelain clean after restore. The red proves only that the 26 pinned phrases are absent, not that the replacement prose is true.
3 ./scripts/check: green twice at 3dd3403 — run 1 "1112 passed in 72.97s (0:01:12)" then "check: green" (real 1m14s); run 2 "1112 passed in 61.95s (0:01:01)" then "check: green" (real 1m03s); ruff clean and cli smoke in both. I ran 2 of the claimed 3 runs; count matches the report's 1112.
4 forbidden: no DESIGN.md, no meta/plan.md, no meta/CHECKPOINT.md. The commit body contains NO "No DESIGN.md, no meta/" line — grep of `git log -1 --format=%B` for design/meta returns only "U6 follow-up ... — DESIGN §11, §12 rule 8, §22's". Disk shows the commit adds meta/FINAL-REPORT-6.md (+444), U7's deliverable, which the body's file list never mentions, and the version committed here is a placeholder-bearing draft: line 9 "Tip `TIP_SHA` — ruff clean, **TIP_COUNT passed** (TIP_TIMES), cli smoke," ; line 158 "`U6B_SHA` `U6B_SUBJECT`" ; 178 "- U6B_BULLET" ; 188 "TIP_COUNT" ; 370 "`56bef53` and `U6B_SHA`" ; 376-377 "pushed tip `TIP_SHA` ... `TIP_COUNT passed` (TIP_TIMES)". So a mission-tip gate claim ships unfilled.
5 NOT proven: (a) tests/test_playbook.py:689-691 still says "Without the event, a driver blocked on `hands wait --for stop,held` is not woken by a pause and §11's wake check has no one-command event behind it" — it carries the very phrase "driver blocked on" the new list pins, but test_playbook.py is not in WAKE_PATH_TEXT, so the gate cannot see it; the sweep of 19 sentences is therefore incomplete. (b) README.md:115-118 "Whether a finished background task wakes an idle interactive Claude Code session (DESIGN §11, §16) is still an open question — `hands doctor` prints the procedure that answers it" contradicts both §11 ("the wake-path question is answered") and the same commit's README.md:78-80 plus doctor.py:400-418, which print the notification check, not a wake procedure. (c) tests/test_wake.py:128,130 keep the stop reason "arrived while the driver was reporting". (d) Both U6 regression tests are source-text phrase lists over fixed file lists (test_docs.py ARMED_WAIT+DRIVER_WAITS over 11 paths; test_doctor.py:377 RETIRED = ("hands wait --for stop,held","background","Background")), so a stale claim spelled a new way, or in any file outside those lists, passes — as (a) demonstrates today. (e) The renamed test name is gone from disk: `grep -rn test_the_driver_kit_spelling_resolves_to_real_event_kinds .` → no hits (and no hits for the old test_docs name either). (f) Unchanged and unreviewable here: DESIGN §11's own first paragraph still describes the driver arming the background wait, so shipped text now disagrees with §11's opening while agreeing with its decision paragraph and §22; no finding covers that.
