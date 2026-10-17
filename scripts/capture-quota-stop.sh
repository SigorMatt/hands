#!/usr/bin/env bash
# capture-quota-stop.sh <project> [<job>] — DESIGN §40, docs/OPERATIONS.md
# ("A usage-limit stop").
#
# Writes ~/quota-capture-<project>-<time>.txt, mode 600, with what the first real
# usage-limit stop looked like: `hands status`, `hands jobs -n 5`, `hands
# pipeline`, the newest job record of the project's spool (or the job named as the
# second argument), that job's stream-json tail and its lines about a limit, the
# tail of the transcript the record names, the daemon journal's lines that name
# the job, and the inbox's tail.
#
# Read-only: the one file it writes is that output, created new (never over an
# existing file). Nothing needs the daemon to be up: a command that fails is
# recorded in the file with its exit status, and the capture goes on.
#
# Redacted before anything reaches the file: every project's command secret
# (`[notify] cmd_secret` of each ~/.hands/*.toml and each ~/.hands/*.cmd_secret)
# and notification token (`ntfy_token`), and the notification user's token and
# password where this machine keeps them (~/.hands/ntfy.token,
# ~/.hands/ntfy.password), each matched as a fixed string — raw, as JSON writes
# it and URL-encoded — never as a regular expression built from the value; then
# keys and bearer tokens by pattern. Read the file before you send it anywhere:
# a secret this script does not know of is not redacted.

set -u
umask 077

usage() {
    echo "usage: bash scripts/capture-quota-stop.sh <project> [<job>]" >&2
    exit 2
}

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
project=$1
job=${2:-}
case $project in
    '' | .* | */*) echo "capture-quota-stop: bad project name: $project" >&2; exit 2 ;;
esac
case $job in
    .* | */*) echo "capture-quota-stop: bad job id: $job" >&2; exit 2 ;;
esac

hands_dir="$HOME/.hands"
spool="$hands_dir/$project"
out="$HOME/quota-capture-$project-$(date +%Y%m%d-%H%M%S).txt"
if [ -e "$out" ] || [ -L "$out" ]; then
    echo "capture-quota-stop: $out exists; run it again in a second" >&2
    exit 1
fi

CUT=4000  # the longest line kept: transcript and stream lines can be megabytes

section() {
    printf '\n== %s ==\n' "$1"
}

# Run a command; on a non-zero exit, say so in the capture and go on.
run() {
    "$@" 2>&1
    local status=$?
    [ "$status" -eq 0 ] || printf '(failed: exit %s: %s)\n' "$status" "$*"
    return 0
}

collect() {
    echo "quota capture: project $project, $(date -Is), by scripts/capture-quota-stop.sh"
    echo "(read-only; secrets redacted by value and by pattern, see the script's header)"

    section "hands --project $project status"
    run hands --project "$project" status
    section "hands --project $project jobs -n 5"
    run hands --project "$project" jobs -n 5
    section "hands --project $project pipeline"
    run hands --project "$project" pipeline

    if [ -z "$job" ]; then
        if [ -d "$spool/jobs" ]; then
            # Job ids are fixed-width base36 milliseconds, so the newest sorts last.
            job=$(find "$spool/jobs" -maxdepth 1 -name '*.json' -printf '%f\n' 2>/dev/null \
                | sort | tail -n 1)
            job=${job%.json}
        fi
    fi
    if [ -z "$job" ]; then
        section "job record"
        echo "(no job record under $spool/jobs)"
        return 0
    fi
    record="$spool/jobs/$job.json"
    section "job record $record"
    if [ -f "$record" ]; then
        run cat "$record"
        echo
    else
        echo "(no such file)"
    fi

    stream="$spool/jobs/$job.stream.jsonl"
    section "stream-json tail, last 40 lines: $stream"
    if [ -f "$stream" ]; then
        tail -n 40 "$stream" | cut -c1-"$CUT"
    else
        echo "(no such file)"
    fi
    section "stream-json lines about a limit (limit, quota, rate, reset, retry, 429, overloaded)"
    if [ -f "$stream" ]; then
        grep -n -i -E 'limit|quota|rate|reset|retry|429|overloaded' "$stream" | tail -n 60 \
            | cut -c1-"$CUT"
    else
        echo "(no such file)"
    fi

    transcript=""
    if [ -f "$record" ]; then
        transcript=$(python3 -I -c '
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("transcript_path") or "")
except Exception:
    pass
' "$record" 2>/dev/null)
    fi
    section "transcript tail, last 40 lines: ${transcript:-(no record, or it names no transcript)}"
    if [ -n "$transcript" ] && [ -f "$transcript" ]; then
        tail -n 40 "$transcript" | cut -c1-"$CUT"
    elif [ -n "$transcript" ]; then
        echo "(no such file)"
    fi

    section "journalctl --user -u handsd@$project, lines naming $job"
    journal=$(journalctl --user -u "handsd@$project" --no-pager -o short-iso 2>&1)
    status=$?
    printf '%s\n' "$journal" | grep -F -- "$job" | tail -n 100 | cut -c1-"$CUT"
    [ "$status" -eq 0 ] || printf '(failed: exit %s: journalctl)\n%s\n' "$status" \
        "$(printf '%s\n' "$journal" | tail -n 3)"

    section "inbox tail, last 30 events: $spool/inbox.jsonl"
    if [ -f "$spool/inbox.jsonl" ]; then
        tail -n 30 "$spool/inbox.jsonl" | cut -c1-"$CUT"
    else
        echo "(no such file)"
    fi
    return 0
}

# The redactor reads the secrets itself, so no value is ever on a command line or
# in the environment, and replaces each as a fixed string (str.replace), longest
# first; the patterns come after.
REDACT='
import json, re, sys, tomllib
from pathlib import Path
from urllib.parse import quote

hands_dir = Path(sys.argv[1])
values = set()

def take(value):
    if isinstance(value, str) and value.strip():
        values.add(value.strip())

for config in sorted(hands_dir.glob("*.toml")):
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        # Unparseable: take the two keys line by line, as written.
        try:
            text = config.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(
            r"(?m)^\s*(?:cmd_secret|ntfy_token)\s*=\s*([\"\x27])(.*)\1\s*(?:#.*)?$", text
        ):
            take(match.group(2))
        continue
    for table in ("notify", "server"):
        section = data.get(table)
        if isinstance(section, dict):
            for key in ("cmd_secret", "ntfy_token"):
                take(section.get(key))
for name in [*sorted(hands_dir.glob("*.cmd_secret")), hands_dir / "ntfy.token",
             hands_dir / "ntfy.password"]:
    try:
        take(Path(name).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        pass

forms = set()
for value in values:
    forms.add(value)
    forms.add(json.dumps(value)[1:-1])
    forms.add(json.dumps(value, ensure_ascii=False)[1:-1])
    forms.add(quote(value, safe=""))
forms.discard("")

PATTERNS = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
     "[redacted]"),
    (r"(?i)(authorization[\"\x27]?\s*[:=]\s*[\"\x27]?(?:basic|bearer|token)?\s*)"
     r"[^\s\"\x27,;]+", r"\1[redacted]"),
    (r"(?i)\b(bearer)(\s+|%20)[A-Za-z0-9._~+/=-]{8,}", r"\1\2[redacted]"),
    (r"(?i)([?&]auth=)[^&\s\"\x27]+", r"\1[redacted]"),
    (r"\bsk-ant-[A-Za-z0-9_-]{8,}", "[redacted]"),
    (r"\bsk-[A-Za-z0-9_-]{16,}", "[redacted]"),
    (r"\btk_[A-Za-z0-9]{8,}", "[redacted]"),
    (r"\bgh[pousr]_[A-Za-z0-9]{16,}", "[redacted]"),
    (r"\bgithub_pat_[A-Za-z0-9_]{16,}", "[redacted]"),
    (r"\bAKIA[0-9A-Z]{16}\b", "[redacted]"),
    (r"\bxox[abposr]-[A-Za-z0-9-]{8,}", "[redacted]"),
    (r"\btskey-[A-Za-z0-9-]{8,}", "[redacted]"),
    (r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?", "[redacted]"),
    (r"(?i)\b((?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|"
     r"client[_-]?secret|cmd_secret|ntfy_token|password|passwd|secret|token)"
     r"[\"\x27]?\s*[:=]\s*[\"\x27]?)[^\s\"\x27,;}]{6,}", r"\1[redacted]"),
]

text = sys.stdin.read()
for form in sorted(forms, key=len, reverse=True):
    text = text.replace(form, "[redacted]")
for pattern, replacement in PATTERNS:
    text = re.sub(pattern, replacement, text)
sys.stdout.write(text)
'

set -o noclobber
collect | python3 -I -c "$REDACT" "$hands_dir" > "$out" || {
    echo "capture-quota-stop: writing $out failed" >&2
    exit 1
}
echo "wrote $out"
