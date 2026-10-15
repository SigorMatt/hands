# Owner decisions — <project>, <date>

File: `meta/decisions/<date>-owner.md`. Committed as `plan: decisions <date>
(owner)`, the one commit the review protocol reads for what it says it does
and does not review as a unit.

Precedence: this file is the owner's word. It wins over `DESIGN.md` and over
every earlier decisions file wherever they disagree, until a later owner file
says otherwise. A builder that finds the design contradicting a decision below
follows the decision and files a finding naming both.

Numbering: `O-<n>` continued from the last owner file on the branch (the
highest `O-` number in `meta/decisions/*-owner.md`, plus one); numbers are
never reused.

Findings closed: <the finding or question ids this file answers, e.g. H-012,
OQ-3; "none">

## O-<n> <one-line title of the ruling>

Asked: <the question as the builder or the review put it, verbatim, with
where it was asked (the `VERDICT: question` reply, the review, the finding)>.

Decided: <the ruling, in full sentences: what is done, what is not, and the
reason when the reason constrains later work>.

## O-<n+1> <one-line title>

Asked: <…>.

Decided: <…>.

## For the builder

This is the only section the builder reads. Exact steps, in order, each one
checkable:

1. <the first step: a file to commit by path, a unit to redo, a branch to
   continue>
2. <…>
3. Continue the mission from `meta/CHECKPOINT.md` and end the reply with one
   of the brief's `VERDICT:` lines.
