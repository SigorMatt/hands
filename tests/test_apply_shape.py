"""Mission 29 U3: the apply by the setting, and its resume (DESIGN §45 "The apply
(§27), by the setting"; §6, §10, §27, §32, §43).

The `direct` prompt gains one sentence; the `pull-request` prompt is §45's, word
for word, its wrapped lines joined with single spaces. `hands kit check` prints
the kit's sha256 and the prompt of the configured shape, saying which. A resume
of an apply — §10's `resume` rule on `builder.orphaned` or `builder.failed`, and
§6's limit resume — re-sends the apply's own prompt, never `resume_line`, and a
resumed apply the engine approved that lands is followed by the engine's kickoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import shlex
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands import kit as kit_mod
from hands.gates import decide
from hands.limits import LimitManager
from hands.spool import Job, Spool, new_kit_id
from harness import config_body, kit_zip, passing_kit
from test_kit import write_tree
from test_playbook import AUTONOMOUS, engine_for, filed_kit

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"

#: The `direct` prompt as it was before §45, for a kit `m-11.zip`.
OLD_DIRECT = (
    "Apply ~/Downloads/m-11.zip to this repository: unzip -o into the repo root "
    "(it replaces DESIGN.md and adds KIT.md), then one plan-only sub-agent makes a "
    "single commit 'plan: kit m-11' listing those files in its body, and pushes. "
    "Change nothing else. Reply with one line: VERDICT: kit applied <sha>."
)
#: §45: the one sentence the `direct` prompt gains, before "Change nothing else.".
ADDED = (
    "If the push is refused, undo that commit (git reset --keep HEAD~1) and reply "
    "instead with one line: VERDICT: kit not applied pr=none <why, in one line>."
)
APPLY_PROMPT = "Apply ~/Downloads/k.zip to this repository: the apply's own prompt."


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)  # type: ignore[arg-type]


def design_template() -> str:
    """§45's `pull-request` prompt: the indented block, its lines joined with
    single spaces (it is one paragraph, wrapped in DESIGN.md)."""
    lines = DESIGN.read_text(encoding="utf-8").splitlines()
    start = lines.index(
        "    Apply {location} to this repository, whose `main` takes pull requests"
    )
    block = []
    for line in lines[start:]:
        if not line.startswith("    "):
            break
        block.append(line.strip())
    return " ".join(block)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ the prompts


def test_the_direct_prompt_gains_exactly_the_one_sentence() -> None:
    """§45: under `direct` the prompt is today's with one sentence added before
    "Change nothing else.", and otherwise byte for byte as it was."""
    head, tail = OLD_DIRECT.split("Change nothing else.")
    expected = head + ADDED + " Change nothing else." + tail
    for shape in ({}, {"shape": "direct"}):
        prompt = kit_mod.apply_prompt(
            "~/Downloads/m-11.zip", ["DESIGN.md"], ["KIT.md"], "plan: kit m-11",
            sha256=sha(b"x"), **shape,
        )
        assert prompt == expected, shape
    assert expected.replace(ADDED + " ", "") == OLD_DIRECT


def test_the_pull_request_prompt_is_section_45s_word_for_word() -> None:
    """§45, for a kit named `a b.c.zip`: `{branch}` is `kit/a-b-c-<12 hex>`, the
    title the message shell-quoted, the body and the subject §45's, shell-quoted."""
    digest = sha(b"the kit's bytes")
    prompt = kit_mod.apply_prompt(
        "~/Downloads/a b.c.zip", ["DESIGN.md"], ["KIT.md"], "plan: kit a b.c",
        shape="pull-request", sha256=digest,
    )
    branch = f"kit/a-b-c-{digest[:12]}"
    touched = "replaces DESIGN.md and adds KIT.md"
    body = f"Kit a b.c.zip (sha256 {digest}), applied by hands (DESIGN §45): it {touched}."
    expected = (
        design_template()
        .replace("{location}", "~/Downloads/'a b.c.zip'")
        .replace("{touched}", touched)
        .replace("{message}", "'plan: kit a b.c'")
        .replace("{branch}", branch)
        .replace("{title}", "'plan: kit a b.c'")
        .replace("{body}", shlex.quote(body))
        .replace("{subject}", "'merge: kit a-b-c (PR #<pr>)'")
    )
    assert prompt == expected
    assert "{" not in strip_paths(prompt) and "}" not in strip_paths(prompt)
    assert prompt.startswith(
        "Apply ~/Downloads/'a b.c.zip' to this repository, whose `main` takes pull requests "
        "only (DESIGN §45). First, where the working tree is. (a) On `" + branch + "`, "
    )
    assert "--subject 'merge: kit a-b-c (PR #<pr>)'`" in strip_paths(prompt)
    assert f"--title 'plan: kit a b.c' --body '{body}'`" in strip_paths(prompt)
    assert prompt.endswith("<its error, in one line>. Change nothing else.")


def test_a_stem_over_40_characters_is_cut_in_the_branch_and_the_subject() -> None:
    name = "mission-29.decisions for the builder and the reviewer"
    assert len(name) > 40
    digest = sha(b"long")
    prompt = kit_mod.apply_prompt(
        f"~/Downloads/{name}.zip", [], ["KIT.md"], "plan: x", shape="pull-request",
        sha256=digest,
    )
    stem = "mission-29-decisions-for-the-builder-and-the-reviewer"[:40]
    assert stem == "mission-29-decisions-for-the-builder-and"
    assert kit_mod.kit_branch(f"{name}.zip", digest) == f"kit/{stem}-{digest[:12]}"
    assert f"`gh pr list --head kit/{stem}-{digest[:12]} --state all" in strip_paths(prompt)
    assert f"--subject 'merge: kit {stem} (PR #<pr>)'" in strip_paths(prompt)


def test_the_same_name_with_other_bytes_gets_another_branch() -> None:
    one, two = sha(b"first bytes"), sha(b"other bytes")
    branches = {kit_mod.kit_branch("a b.c.zip", digest) for digest in (one, two)}
    assert branches == {f"kit/a-b-c-{one[:12]}", f"kit/a-b-c-{two[:12]}"}
    prompts = {
        kit_mod.apply_prompt(
            "~/Downloads/a b.c.zip", [], ["KIT.md"], "m", shape="pull-request", sha256=digest
        )
        for digest in (one, two)
    }
    assert len(prompts) == 2


def test_apply_from_zip_names_the_branch_by_the_zips_own_sha256(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = tmp_path / "m29.zip"
    path.write_bytes(kit_zip(passing_kit()))
    digest = sha(path.read_bytes())
    plan = kit_mod.apply_from_zip(path, repo, "~/Downloads/m29.zip", shape="pull-request")
    assert f"`kit/m29-{digest[:12]}`" in strip_paths(plan.prompt)
    assert f"(sha256 {digest})" in strip_paths(plan.prompt)
    direct = kit_mod.apply_from_zip(path, repo, "~/Downloads/m29.zip")
    assert ADDED in strip_paths(direct.prompt) and "kit/m29" not in strip_paths(direct.prompt)


# ------------------------------------------------------------------ kit check


def check_out(kit: Path, repo: Path, project: str | None = None) -> str:
    out = io.StringIO()
    code = kit_mod.run(str(kit), str(repo), out=out, as_json=False, project=project)
    assert code == 0, out.getvalue()
    return out.getvalue()


def prompt_of(out: str) -> str:
    lines = out.splitlines()
    return lines[lines.index("apply prompt:") + 1].removeprefix("    ")


def test_kit_check_without_a_configuration_prints_the_sha256_and_the_direct_prompt(
    tmp_home: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    kit = tmp_path / "m29.zip"
    kit.write_bytes(kit_zip(passing_kit()))
    out = check_out(kit, repo)
    assert f"sha256: {sha(kit.read_bytes())} (of the zip)\n" in strip_paths(out), out
    said = "apply shape: direct (no project configuration is known here)\n"
    assert said in strip_paths(out), out
    assert ADDED in strip_paths(prompt_of(out))
    assert "pull requests only" not in strip_paths(out)


@pytest.mark.parametrize("shape", ["pull-request", "direct"])
def test_kit_check_with_a_configuration_prints_its_shapes_prompt_naming_it(
    tmp_home: Path, tmp_path: Path, workdir: Path, shape: str
) -> None:
    config = tmp_home / ".hands" / "demo.toml"
    config.write_text(
        config_body(tmp_home, workdir, extra=f'\n[repository]\nmain = "{shape}"\n')
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    kit = tmp_path / "m29.zip"
    kit.write_bytes(kit_zip(passing_kit()))
    out = check_out(kit, repo, project="demo")
    digest = sha(kit.read_bytes())
    assert f"sha256: {digest} (of the zip)\n" in strip_paths(out), out
    said = strip_paths(f'apply shape: {shape} ([repository] main = "{shape}" in {config})\n')
    assert said.endswith("demo.toml)\n") and said in strip_paths(out), out
    prompt = prompt_of(out)
    if shape == "pull-request":
        assert prompt.startswith(
            "Apply ~/Downloads/m29.zip to this repository, whose `main` takes pull requests"
        )
        assert f"`kit/m29-{digest[:12]}`" in strip_paths(prompt)
    else:
        assert ADDED in strip_paths(prompt) and "kit/" not in strip_paths(prompt)


def test_kit_check_of_a_directory_prints_the_sha256_hands_kit_file_files(
    tmp_home: Path, tmp_path: Path, workdir: Path
) -> None:
    """§45: for a directory kit, the sha256 of the zip `hands kit file` builds from
    it (`build_zip`), and the pull-request prompt's branch names that hash."""
    (tmp_home / ".hands" / "demo.toml").write_text(
        config_body(tmp_home, workdir, extra='\n[repository]\nmain = "pull-request"\n')
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    kit = write_tree(tmp_path / "kits" / "m29", passing_kit())
    digest = sha(kit_mod.build_zip(kit))
    out = check_out(kit, repo, project="demo")
    said = f"sha256: {digest} (of the zip `hands kit file` builds from this directory)\n"
    assert said in strip_paths(out), out
    assert f"`kit/m29-{digest[:12]}`" in strip_paths(prompt_of(out))


# ------------------------------------------------------- the resume of an apply

RESUME_BOOK = '''version = 1
[limits]
max_resumes = 3

[[rule]]
on = "builder.orphaned"
then = "resume"

[[rule]]
on = "builder.failed"
then = "resume"
'''


def an_apply(spool: Spool, state: str, *, prompt: str = APPLY_PROMPT, **kw: Any) -> Job:
    job = spool.create_job(
        role="builder", context="clear", prompt=prompt, origin="kit", kit_id=new_kit_id(), **kw
    )
    spool.transition(job, "running")
    return spool.transition(job, state)


@pytest.mark.parametrize("state", ["orphaned", "failed"])
def test_a_resume_rule_resends_an_applys_own_prompt_not_the_resume_line(
    tmp_home: Path, workdir: Path, state: str
) -> None:
    engine, recorder = engine_for(
        tmp_home, workdir, RESUME_BOOK, builder={"resume_line": "Resume WORKPLAN.md"}
    )
    job = an_apply(engine.spool, state)
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert [(e["prompt"], e["context"], e["resumed_from"]) for e in recorder.enqueued] == [
        (APPLY_PROMPT, "clear", job.id)
    ]


def test_a_resume_of_a_resumed_apply_resends_the_first_jobs_prompt(
    tmp_home: Path, workdir: Path
) -> None:
    """§43's chain walk: the resume carries no `kit_id`; `resumed_from` leads back."""
    engine, recorder = engine_for(
        tmp_home, workdir, RESUME_BOOK, builder={"resume_line": "Resume WORKPLAN.md"}
    )
    first = an_apply(engine.spool, "orphaned")
    again = engine.spool.create_job(
        role="builder", context="clear", prompt="something else", origin="playbook",
        resumed_from=first.id,
    )
    engine.spool.transition(again, "running")
    again = engine.spool.transition(again, "orphaned")
    run(engine.on_job_start(again))
    run(engine.on_job(again))
    assert [e["prompt"] for e in recorder.enqueued] == [APPLY_PROMPT]


def test_a_resume_rule_on_any_other_builder_job_still_sends_the_resume_line(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(
        tmp_home, workdir, RESUME_BOOK, builder={"resume_line": "Resume WORKPLAN.md"}
    )
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    engine.spool.transition(job, "running")
    job = engine.spool.transition(job, "orphaned")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert [e["prompt"] for e in recorder.enqueued] == ["Resume WORKPLAN.md"]


def limit_manager(tmp_home: Path, workdir: Path) -> tuple[LimitManager, Spool]:
    from hands.config import parse_config

    cfg = parse_config(
        {
            "roles": {
                "builder": {"cwd": str(workdir), "resume_line": "Resume WORKPLAN.md"},
                "aux": {"cwd": str(workdir)},
            },
            "limits": {"backoff_minutes": 30, "max_resumes": 3},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    spool = Spool(tmp_home / ".hands")

    async def enqueue(**kwargs: Any) -> Job:
        return spool.create_job(**kwargs)

    async def sleep(_seconds: float) -> None:
        return None

    return LimitManager(cfg, spool, enqueue=enqueue, sleep=sleep), spool


def limited(spool: Spool, job: Job) -> Job:
    spool.transition(job, "running")
    return spool.transition(
        job, "limited",
        limit={"category": "rate_limit", "message": "Usage limit reached", "reset_at": None},
    )


@pytest.mark.parametrize("kind", ["apply", "kickoff"])
def test_a_limit_resume_resends_an_applys_prompt_and_a_kickoffs_resume_line(
    tmp_home: Path, workdir: Path, kind: str
) -> None:
    """§6 with §45: a limited apply is resumed with its own prompt; a limited
    kickoff, as today, with `[roles.builder] resume_line`."""
    manager, spool = limit_manager(tmp_home, workdir)
    if kind == "apply":
        job = spool.create_job(
            role="builder", context="clear", prompt=APPLY_PROMPT, origin="kit",
            kit_id=new_kit_id(),
        )
        expected = APPLY_PROMPT
    else:
        job = spool.create_job(
            role="builder", context="clear", origin="cli",
            prompt="Read meta/BUILDER-29-PROMPT.md and execute the mission below its divider.",
        )
        expected = "Resume WORKPLAN.md"
    job = limited(spool, job)

    async def scenario() -> None:
        await manager.on_job_finished(job)
        await manager.drain()

    run(scenario())
    (resume,) = [record for record in spool.list_jobs() if record.resumed_from]
    assert (resume.prompt, resume.context, resume.resumed_from) == (expected, "clear", job.id)


def test_a_limit_resume_of_a_resumed_apply_resends_the_first_jobs_prompt(
    tmp_home: Path, workdir: Path
) -> None:
    manager, spool = limit_manager(tmp_home, workdir)
    first = an_apply(spool, "orphaned")
    again = limited(spool, spool.create_job(
        role="builder", context="clear", prompt="Resume WORKPLAN.md", origin="playbook",
        resumed_from=first.id,
    ))

    async def scenario() -> None:
        await manager.on_job_finished(again)
        await manager.drain()

    run(scenario())
    (resume,) = [record for record in spool.list_jobs() if record.resumed_from == again.id]
    assert resume.prompt == APPLY_PROMPT


# --------------------------- §32 asked of the chain's first job: the kickoff follows

ORPHAN_RESUME = '\n[[rule]]\non = "builder.orphaned"\nthen = "resume"\n'


def test_an_engine_approved_apply_orphaned_resumed_and_landing_is_followed_by_the_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    """§45: "§32's test of an apply the engine approved is asked of the chain's first
    job, so a resumed apply that lands is followed by the engine's kickoff as the
    first would have been" — under a role-mode autonomous playbook."""
    engine, recorder = engine_for(
        tmp_home, workdir, AUTONOMOUS + ORPHAN_RESUME, architect=workdir,
        builder={"resume_line": "Resume WORKPLAN.md"},
    )
    spool = engine.spool
    apply = filed_kit(spool)
    assert apply.gate is not None
    gate = decide(apply.gate, decision="approved", decided_by="playbook", reason="r")
    spool.transition(apply, "queued", gate=gate)
    run(engine.on_job_start(spool.transition(spool.load_job(apply.id), "running")))
    orphaned = spool.transition(spool.load_job(apply.id), "orphaned")
    run(engine.on_job(orphaned))
    assert [(e["prompt"], e["resumed_from"]) for e in recorder.enqueued] == [
        ("Apply the kit.", apply.id)
    ]
    resumed = spool.create_job(
        role="builder", context="clear", prompt="Apply the kit.", origin="playbook",
        resumed_from=apply.id,
    )
    run(engine.on_job_start(spool.transition(resumed, "running")))
    verdict = "VERDICT: kit applied abc1234"
    landed = spool.transition(spool.load_job(resumed.id), "done", verdict=verdict, result=verdict)
    run(engine.on_job(landed))
    assert [sent["prompt"] for sent in recorder.sent] == [
        "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."
    ], strip_paths(str(engine.state.stop_reason))
    assert engine.state.last_rule is not None and engine.state.last_rule["rule"] == -1


def test_the_handbooks_section_3_quotes_the_direct_prompts_added_sentence() -> None:
    handbook = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    section = handbook.split("\n## 3.")[1].split("\n## 4.")[0]
    quoted = " ".join(section.split("The apply prompt:")[1].split("\n\n")[1].split())
    assert quoted.endswith(
        f"and pushes. {ADDED} Change nothing else. Reply with one line: "
        "VERDICT: kit applied <sha>."
    ), quoted
    assert ADDED == kit_mod.DIRECT_REFUSED_PUSH
