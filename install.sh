#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SOURCE_DIR="$(cd "$(dirname "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd || pwd)"
REPO_URL="${SYC_AUDIO_TO_TEXT_REPO:-https://github.com/Songxiaor/syc-audio-to-text.git}"

if [[ ! -f "$SOURCE_DIR/SKILL.md" || ! -f "$SOURCE_DIR/run.sh" ]]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required for remote installation." >&2
    exit 1
  fi
  TMP_DIR="$(mktemp -d)"
  git clone --depth 1 "$REPO_URL" "$TMP_DIR/syc-audio-to-text"
  exec bash "$TMP_DIR/syc-audio-to-text/install.sh"
fi

TARGET_ROOT="${SKILL_HOME:-${CODEX_HOME:-$HOME/.codex}/skills}"
TARGET_DIR="$TARGET_ROOT/syc-audio-to-text"

find_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return 0
  fi
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      if [[ $? -eq 0 ]]; then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

tar \
  --exclude ".git" \
  --exclude ".env" \
  --exclude ".stepfun.env" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  -C "$SOURCE_DIR" \
  -cf - . | tar -C "$TARGET_DIR" -xf -

chmod +x "$TARGET_DIR/run.sh"

PYTHON_PATH="$(find_python || true)"
if [[ -z "$PYTHON_PATH" ]]; then
  echo "Python 3.10+ is required. Install Python 3.11+ and rerun install.sh." >&2
  echo "macOS Homebrew example: brew install python@3.11" >&2
  exit 1
fi

"$PYTHON_PATH" -m venv "$TARGET_DIR/.venv"
"$TARGET_DIR/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"$TARGET_DIR/.venv/bin/python" -m pip install --upgrade requests yt-dlp >/dev/null

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg is not installed. Install it before transcribing local video/audio." >&2
  echo "macOS Homebrew example: brew install ffmpeg" >&2
fi

echo "Installed syc-audio-to-text to: $TARGET_DIR"
echo "Runtime Python: $TARGET_DIR/.venv/bin/python"
echo "Runtime yt-dlp: $TARGET_DIR/.venv/bin/yt-dlp"
echo "Next:"
echo "  bash $TARGET_DIR/run.sh --configure-key"
echo "  bash $TARGET_DIR/run.sh --check"
