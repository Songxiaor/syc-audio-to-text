---
name: syc-audio-to-text
description: Convert single or batch local audio/video files and online video URLs into transcripts, or download online videos directly to local storage, for Codex, Claude Code, and other shell-capable agents. Uses yt-dlp for subtitles/downloads, then StepFun Step Plan ASR (with automatic Whisper fallback) when speech recognition is needed.
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

Prefer the shell entrypoint (adjust path to your install location):

```bash
bash /Users/song/.cc-switch/skills/syc-audio-to-text/run.sh --input "<file-or-url>"
```

Batch local media:

```bash
bash /Users/song/.cc-switch/skills/syc-audio-to-text/run.sh --input-dir "<media-folder>" --output-dir "<transcript-folder>" --format md
```

Download online video without transcription:

```bash
bash /Users/song/.cc-switch/skills/syc-audio-to-text/run.sh --input "<video-url>" --download-only
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
--asr-engine auto|stepfun|whisper
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
6. 展示规范（重要）：
   - **完整展示转写内容**：转写完成后，必须直接在回复中展示完整文本（而非只给路径），让用户无需点开文件就能阅读。如果内容过长（>5000 字），拆分展示或折叠展示。
   - **文件路径做成可点击链接**：用 Markdown 格式 `[📄 描述](file://绝对路径)` 输出文件链接，用户点击即可在本地编辑器/浏览器中打开文件。
   - **同时提供**：完整内容 + 可点击文件链接 + 基本统计（字数/引擎/耗时）。

## Notes

- URL inputs use `yt-dlp`: subtitles first, then downloaded audio if no usable subtitles exist.
- `--download-only` saves the online media file locally and does not call ASR.
- Local video inputs use `ffmpeg` to extract 16k mono mp3.
- Long audio is split before ASR with `--chunk-minutes` to avoid oversized one-shot requests.
- Batch mode preserves relative paths under `--output-dir` and writes `_batch_report.json`.
- Configure StepFun key with `--configure-key`; it writes `~/.stepfun.env` with `600` permissions.
- Run `--live-test` after key configuration to prove the real StepFun ASR path.
- StepFun Step Plan ASR endpoint: `https://api.stepfun.com/step_plan/v1/audio/asr/sse`.
- ASR 引擎选择 (`--asr-engine`)：
  - `auto`（默认）：优先 StepFun，失败（API Key 缺失、风控拦截、网络超时等）自动降级到本地 Whisper
  - `stepfun`：仅使用 StepFun，不降级
  - `whisper`：直接使用本地 Whisper（需 `pip install openai-whisper`）
- whisper 降级时不分片，whisper 自带长音频分段处理能力。
