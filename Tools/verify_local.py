#!/usr/bin/env python3
"""Local verification for the syc-audio-to-text skill without calling ASR."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import os
import json

SKILL_DIR = Path(__file__).resolve().parents[1]
RUN_SH = SKILL_DIR / "run.sh"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)


def verify_mock_stepfun_asr(sample: Path) -> bool:
    import sys
    from unittest.mock import patch

    sys.path.insert(0, str(SKILL_DIR / "Tools"))
    import stepfun_asr

    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self, decode_unicode=True):
            events = [
                {"type": "transcript.text.delta", "delta": "你"},
                {"type": "transcript.text.delta", "delta": "好"},
                {"type": "transcript.text.done", "text": "你好"},
            ]
            for event in events:
                yield "data: " + json.dumps(event, ensure_ascii=False)
            yield "data: [DONE]"

    def fake_post(url, headers, json, stream, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["stream"] = stream
        captured["timeout"] = timeout
        return FakeResponse()

    with patch.object(stepfun_asr.requests, "post", side_effect=fake_post):
        text = stepfun_asr.transcribe_file(sample, api_key="Bearer test-key", language="zh", timeout=12)

    if text != "你好":
        print(f"mock ASR text mismatch: {text}")
        return False
    if captured.get("url") != "https://api.stepfun.com/step_plan/v1/audio/asr/sse":
        print(f"mock ASR URL mismatch: {captured.get('url')}")
        return False
    headers = captured.get("headers", {})
    if headers.get("Authorization") != "Bearer test-key":
        print("mock ASR Authorization header mismatch")
        return False
    payload = captured.get("json", {})
    transcription = payload.get("audio", {}).get("input", {}).get("transcription", {})
    audio_format = payload.get("audio", {}).get("input", {}).get("format", {})
    if transcription.get("model") != "stepaudio-2.5-asr":
        print("mock ASR model mismatch")
        return False
    if transcription.get("language") != "zh":
        print("mock ASR language mismatch")
        return False
    if audio_format.get("type") != "mp3":
        print("mock ASR audio format mismatch")
        return False
    if not payload.get("audio", {}).get("data"):
        print("mock ASR missing base64 audio data")
        return False
    return True


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        sample = tmpdir / "sample.mp3"
        output = tmpdir / "out.json"
        subtitle = tmpdir / "sample.vtt"

        make_audio = run([
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            "32k",
            str(sample),
        ])
        if make_audio.returncode != 0:
            print(make_audio.stderr)
            return 1

        dry_run = run(["bash", str(RUN_SH), "--input", str(sample), "--dry-run", "--format", "json", "--output", str(output)])
        if dry_run.returncode != 0:
            print(dry_run.stdout)
            print(dry_run.stderr)
            return 1
        if not output.exists() or "DRY RUN" not in output.read_text(encoding="utf-8"):
            print("dry-run output missing expected content")
            return 1

        batch_in = tmpdir / "batch-in"
        batch_out = tmpdir / "batch-out"
        nested = batch_in / "nested"
        nested.mkdir(parents=True)
        batch_one = batch_in / "one.mp3"
        batch_two = nested / "two.m4a"
        for target, frequency in ((batch_one, "550"), (batch_two, "660")):
            make_batch_audio = run([
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration=1",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-b:a",
                "32k",
                str(target),
            ])
            if make_batch_audio.returncode != 0:
                print(make_batch_audio.stderr)
                return 1

        batch_run = run([
            "bash",
            str(RUN_SH),
            "--input-dir",
            str(batch_in),
            "--output-dir",
            str(batch_out),
            "--format",
            "json",
            "--recursive",
            "--dry-run",
            "--continue-on-error",
        ])
        if batch_run.returncode != 0:
            print(batch_run.stdout)
            print(batch_run.stderr)
            return 1
        report_path = batch_out / "_batch_report.json"
        expected_outputs = [batch_out / "one.json", batch_out / "nested" / "two.json"]
        if not report_path.exists() or not all(path.exists() for path in expected_outputs):
            print("batch dry-run outputs missing")
            return 1
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("total") != 2 or report.get("ok") != 2 or report.get("failed") != 0:
            print(f"batch report mismatch: {report}")
            return 1

        batch_skip = run([
            "bash",
            str(RUN_SH),
            "--input-dir",
            str(batch_in),
            "--output-dir",
            str(batch_out),
            "--format",
            "json",
            "--recursive",
            "--dry-run",
            "--skip-existing",
        ])
        if batch_skip.returncode != 0:
            print(batch_skip.stdout)
            print(batch_skip.stderr)
            return 1
        skip_report = json.loads(report_path.read_text(encoding="utf-8"))
        if skip_report.get("skipped") != 2:
            print(f"batch skip report mismatch: {skip_report}")
            return 1

        download_cmd = run([
            "python3",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str((SKILL_DIR / 'Tools')).__repr__()}); "
                "from pathlib import Path; "
                "from transcribe import build_download_command; "
                "print(' '.join(build_download_command('https://example.com/video', Path('/tmp/downloads'), 'video')))"
            ),
        ])
        if (
            download_cmd.returncode != 0
            or "--merge-output-format mp4" not in download_cmd.stdout
            or "-f bv*+ba/b" not in download_cmd.stdout
            or "/tmp/downloads" not in download_cmd.stdout
        ):
            print(download_cmd.stdout)
            print(download_cmd.stderr)
            return 1

        subtitle.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n你好\n\n00:00:01.000 --> 00:00:02.000\n世界\n", encoding="utf-8")
        parse_subtitle = run([
            "python3",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str((SKILL_DIR / 'Tools')).__repr__()}); "
                "from transcribe import parse_subtitle; "
                f"print(parse_subtitle(__import__('pathlib').Path({str(subtitle).__repr__()})))"
            ),
        ])
        if parse_subtitle.returncode != 0 or "你好 世界" not in parse_subtitle.stdout:
            print(parse_subtitle.stdout)
            print(parse_subtitle.stderr)
            return 1

        sse_parse = run([
            "python3",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str((SKILL_DIR / 'Tools')).__repr__()}); "
                "from stepfun_asr import extract_text_from_event; "
                "print(extract_text_from_event({'type':'transcript.text.delta','delta':'增量'})); "
                "print(extract_text_from_event({'type':'transcript.text.done','text':'完整文本'}))"
            ),
        ])
        if sse_parse.returncode != 0 or "增量\n完整文本" not in sse_parse.stdout:
            print(sse_parse.stdout)
            print(sse_parse.stderr)
            return 1

        if not verify_mock_stepfun_asr(sample):
            return 1

    print("syc-audio-to-text local verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
