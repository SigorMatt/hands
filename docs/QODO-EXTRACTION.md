# QODO-EXTRACTION — reading a hosted review without losing its findings

Source: the method observed on two pull requests of another repository (2026-10-15), handed to hands by its owner; carried here as evidence for the review protocol's hosted-review step (DESIGN §39). Names, repositories and findings of that project do not appear.

## How Qodo behaves on a PR (what we observed on PR #2 and PR #5)

1. **Three places, one review.** A few minutes after the PR opens, `qodo-code-review[bot]` posts:
   - an **issue comment** "PR Summary by Qodo" — description, diagram, file list, "alternative approaches"; **no findings**;
   - an **issue comment** "Code Review by Qodo" — the header counts (`Bugs (n)`, `Rule violations (n)`, `Skill insights (n)`) and every numbered finding in full (description, code excerpt, evidence, agent prompt);
   - a **pull-request review** (state `COMMENTED`, body empty) carrying one **inline review comment per finding**, anchored to a file and line, with the same title, text and finding ID as the issue comment.
   So every finding appears twice; the "Code Review" issue comment is the canonical list, the inline comments are its anchors.
2. **Re-review on push edits in place.** After you push fixes, Qodo re-runs and **edits the existing "Code Review" comment** — findings get struck through with `✓ Resolved`, the header counts reset, permalinks move to the new head sha, the Dismiss/View links go, and findings may be reordered. **No new comment, no e-mail.** The inline comments are *not* edited; they keep reading as open findings. The GitHub UI shows the edit history ("edited N times"); the API returns only the current body, with `updated_at` moved.
3. **E-mail matches the API.** The notification e-mails (one per comment) carry the same text as the API bodies — verified word for word — so either is a valid source; the API is the one you can diff.

## The procedure

**Phase 1 — first fetch, right after Qodo posts.** Find the PR (`GET /repos/{o}/{r}/pulls?head={o}:{branch}&state=open`), record number and head sha, then fetch all three sources, paginated, filtered to the bot's login:

- `GET /repos/{o}/{r}/issues/{n}/comments`
- `GET /repos/{o}/{r}/pulls/{n}/reviews`
- `GET /repos/{o}/{r}/pulls/{n}/comments` (inline)

Save every body **byte for byte**, one file per comment named by kind and comment id, plus the raw JSON. This copy is the only record of the original findings you will ever have, because the next step overwrites them. Print the numbered findings verbatim, each with its file:line, marking which pairs are duplicates and which comment is the summary. If no bot comments exist yet, say so and retry in a few minutes rather than concluding "clean".

**Phase 2 — after every push, the diff.** Repeat the fetch into a `v2/` (then `v3/` …) directory with the same file names. Compare by comment id against the previous fetch:

- bodies that changed → print `updated_at` and the changed parts verbatim;
- ids present in one fetch and not the other → list them (a new comment means new findings; a vanished one means Qodo deleted something);
- state plainly whether any finding is **open** — i.e., not struck through / not marked resolved in the canonical comment — and if so print it in full.

The verdict comes from the "Code Review" issue comment, never from the inline comments (stale) and never from "nothing new by id" (which is exactly what an in-place edit looks like).

**Disposition and record.** Every finding gets an explicit disposition (fix before merge, or a tracked thread) before the merge; the original bodies are committed to a `reviews/` archive with sha256s, and the registry gets one line per finding with its disposition and commit. Do this extraction in a session with a fresh context, separate from whoever wrote the code and from whoever did your own cold review, so the reading isn't anchored.

## Pitfalls that bit us

- Treating "no new comments" as "no new review" (the in-place edit).
- Archiving only after fixes — by then the original text is gone from the API.
- Reading the inline comments as the current state.
- Waiting for an e-mail as the signal: the first review e-mails, the re-review doesn't.
- Pagination: fetch all pages; the review-comments endpoint in particular grows.
