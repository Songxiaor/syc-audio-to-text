#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  export PATH="$SCRIPT_DIR/.venv/bin:$PATH"
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

for env_file in \
  "$HOME/.shared-skills/api-registry/.env" \
  "$HOME/.cc-switch/.env" \
  "$HOME/.stepfun.env"
do
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
done

"$PYTHON_BIN" "$SCRIPT_DIR/Tools/transcribe.py" "$@"
