#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

echo "Installed syc-audio-to-text to: $TARGET_DIR"
echo "Next:"
echo "  bash $TARGET_DIR/run.sh --configure-key"
echo "  bash $TARGET_DIR/run.sh --check"
