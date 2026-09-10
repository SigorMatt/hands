#!/usr/bin/env bash
# hands v0 dispatcher — used only until `hands send` exists.
#
# Usage:
#   dispatch.sh <role-dir> [--resume <session_id>] "<prompt>"
#
# Runs `claude -p` detached in <role-dir>, JSON output to
# ~/.hands/bootstrap/<n>.json, stderr to <n>.err, pid to <n>.pid.
# Prints the job number, pid and spool path. Never blocks.
#
# Read the result when the pid is gone:
#   jq -r '.session_id, .result' ~/.hands/bootstrap/<n>.json
set -euo pipefail

SPOOL="$HOME/.hands/bootstrap"
mkdir -p "$SPOOL"

if [ $# -lt 2 ]; then
  echo "usage: $0 <role-dir> [--resume <session_id>] \"<prompt>\"" >&2
  exit 2
fi

DIR="$1"; shift
RESUME=()
if [ "${1:-}" = "--resume" ]; then
  RESUME=(--resume "$2"); shift 2
fi
PROMPT="$1"

if [ ! -d "$DIR" ]; then
  echo "no such directory: $DIR" >&2
  exit 2
fi

N=1
while [ -e "$SPOOL/$N.json" ]; do N=$((N + 1)); done

(
  cd "$DIR"
  nohup claude -p "${RESUME[@]}" \
    --output-format json \
    --dangerously-skip-permissions \
    "$PROMPT" > "$SPOOL/$N.json" 2> "$SPOOL/$N.err" < /dev/null &
  echo $! > "$SPOOL/$N.pid"
)

printf 'job %s pid %s -> %s/%s.json\n' "$N" "$(cat "$SPOOL/$N.pid")" "$SPOOL" "$N"
