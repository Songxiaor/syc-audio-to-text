---
name: syc-audio-to-text
description: Convert single or batch local audio/video files and online video URLs into transcripts, or download online videos directly to local storage, for Codex, Claude Code, and other shell-capable agents. Use when the user asks to transcribe, batch transcribe, convert audio/video to text, extract subtitles, download YouTube/Bilibili/Xiaoyuzhou videos, save an online video locally, create transcript files, or summarize a transcript after transcription. Uses yt-dlp for subtitles/downloads, then StepFun Step Plan ASR when speech recognition is needed.
---

# Audio to Text

Turn local media files or online video URLs into transcript files.

## Trigger

Use this skill when the user asks for:

- 视频转文字、音频转文字、转写、字幕、听写
- YouTube / B站 / 小宇宙 / URL 转文字
- YouTube / B站 / 小宇宙 / URL 直接下载视频到本地
- 本地 mp4 / mov / mp3 / m4a / wav / ogg 转写
- 转写后继续摘要、提炼重点、整理笔记

## Entry Point

Prefer the shell entrypoint:

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --input "<file-or-url>"
```

Batch local media:

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --input-dir "<media-folder>" --output-dir "<transcript-folder>" --format md
```

Download online video without transcription:

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --input "<video-url>" --download-only
```

Useful options:

```bash
--output ~/Desktop/result.txt
--output-dir ~/Desktop/transcripts
--download-only
--download-type video|audio
--download-dir ~/Downloads
--format txt|md|json
--language zh|en|auto
--no-subtitle
--chunk-minutes 25
--input-dir /path/to/media
--include "*.mp3,*.m4a,*.mp4"
--recursive
--skip-existing
--continue-on-error
--dry-run
--check
--configure-key
--live-test
```

## Workflow

1. If the user asks only for transcription, run `Workflows/Transcribe.md`.
2. If the user asks to batch transcribe local files, use `--input-dir` and `--output-dir`; do not write an ad hoc shell loop unless the requested input source is unsupported.
3. If the user asks to download a video/link without transcription, use `--download-only`; default to video and `~/Downloads`.
4. If the user asks for summary, notes, key points, or rewrite after transcription, first transcribe, then run `Workflows/Extract.md`.
5. Never print API keys. The CLI reads `STEPFUN_API_KEY`, `STEP_API_KEY`, or `.env` files.
6. Report the output path, character count, and a short preview.

## Notes

- URL inputs use `yt-dlp`: subtitles first, then downloaded audio if no usable subtitles exist.
- `--download-only` saves the online media file locally and does not call ASR.
- Local video inputs use `ffmpeg` to extract 16k mono mp3.
- Long audio is split before ASR with `--chunk-minutes` to avoid oversized one-shot requests.
- Batch mode preserves relative paths under `--output-dir` and writes `_batch_report.json`.
- Configure StepFun key with `--configure-key`; it writes `~/.stepfun.env` with `600` permissions.
- Run `--live-test` after key configuration to prove the real StepFun ASR path.
- StepFun Step Plan ASR endpoint: `https://api.stepfun.com/step_plan/v1/audio/asr/sse`.
