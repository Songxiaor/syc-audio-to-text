# Workflow: Transcribe

Convert a local file or URL into a transcript.

## Commands

Local file:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "/path/to/video.mp4"
```

URL:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "https://www.youtube.com/watch?v=..."
```

Download URL video without transcription:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "https://www.youtube.com/watch?v=..." --download-only
```

Download URL video to a custom folder:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "https://www.youtube.com/watch?v=..." --download-only --download-dir ~/Downloads
```

Custom output:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "/path/to/audio.mp3" --output ~/Desktop/transcript.md --format md
```

Batch local media:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input-dir "/path/to/media" --output-dir ~/Desktop/transcripts --format md
```

Batch recursively and skip existing outputs:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input-dir "/path/to/media" --output-dir ~/Desktop/transcripts --format md --recursive --skip-existing --continue-on-error
```

Batch selected formats:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input-dir "/path/to/media" --output-dir ~/Desktop/transcripts --include "*.mp3,*.m4a,*.mp4"
```

No API validation:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "/path/to/video.mp4" --dry-run
```

Check dependencies and StepFun config:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --check
```

Configure StepFun API key safely:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --configure-key
```

Run a real StepFun ASR smoke test:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --live-test
```

Split long media into shorter ASR chunks:

```bash
bash <SKILL_HOME>/syc-audio-to-text/run.sh --input "/path/to/long.mp3" --chunk-minutes 20
```

## Completion Response

Tell the user:

- transcript file path
- downloaded media file path when `--download-only` is used
- batch output directory and `_batch_report.json` path when batch mode is used
- character count
- whether subtitles or ASR was used
- short preview

Then ask only if useful: whether they want key points or structured notes.
