#!/usr/bin/env python3
"""Audio/video/URL to transcript CLI."""

from __future__ import annotations

import argparse
import fnmatch
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from stepfun_asr import get_config_status, transcribe_file

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".pcm"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
DEFAULT_CHUNK_MINUTES = 25
SUPPORTED_EXTS = AUDIO_EXTS | VIDEO_EXTS


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "www."))


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"缺少依赖 `{name}`。请先安装：brew install {name}")
    return path


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def run_check() -> int:
    status = get_config_status()
    yt_dlp_path = shutil.which("yt-dlp") or "missing"
    yt_dlp_version = "missing"
    if yt_dlp_path != "missing":
        version_result = run(["yt-dlp", "--version"], timeout=30)
        if version_result.returncode == 0:
            yt_dlp_version = version_result.stdout.strip()
    checks = [
        ("python", True, f"{sys.version.split()[0]} ({sys.executable})"),
        ("requests", True, "ok"),
        ("ffmpeg", command_exists("ffmpeg"), shutil.which("ffmpeg") or "missing"),
        ("ffprobe", command_exists("ffprobe"), shutil.which("ffprobe") or "missing"),
        ("yt-dlp", command_exists("yt-dlp"), f"{yt_dlp_version} ({yt_dlp_path})"),
        ("STEPFUN_API_KEY", status["api_key_configured"], f"configured length={status['api_key_length']}" if status["api_key_configured"] else "missing"),
    ]
    ok = True
    for name, passed, detail in checks:
        marker = "ok" if passed else "missing"
        print(f"{marker} - {name}: {detail}")
        ok = ok and passed
    print(f"config - base_url: {status['base_url']}")
    print(f"config - model: {status['model']}")
    if not ok:
        print("\n依赖或 API Key 不完整。dry-run 可用；真实 ASR 需要补齐 missing 项。")
        return 1
    return 0


def configure_key() -> int:
    key = getpass.getpass("请输入 StepFun Step Plan API Key（输入不会显示）：").strip()
    if not key:
        print("未输入 API Key，未写入配置。")
        return 1
    env_path = Path.home() / ".stepfun.env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    next_lines = [line for line in lines if not line.strip().startswith(("STEPFUN_API_KEY=", "STEP_API_KEY=", "STEP_AUDIO_API_KEY="))]
    next_lines.append(f"STEPFUN_API_KEY={key}")
    env_path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    env_path.chmod(0o600)
    print(f"已写入：{env_path}")
    print("已设置文件权限：600")
    print("可运行 `bash ~/.codex/skills/syc-audio-to-text/run.sh --check` 验证。")
    return 0


def timestamp_path(fmt: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"transcript_{ts}.{fmt}"


def get_duration_seconds(path: Path) -> float:
    require_command("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = run(cmd, timeout=60)
    if result.returncode != 0:
        return 0.0
    try:
        return max(0.0, float(result.stdout.strip()))
    except ValueError:
        return 0.0


def parse_subtitle(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"WEBVTT.*?\n\n", "", text, flags=re.DOTALL)
    text = re.sub(r"\d{1,2}:\d{2}:\d{2}[\.,]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[\.,]\d{3}.*?\n", "", text)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned == previous:
            continue
        lines.append(cleaned)
        previous = cleaned
    return " ".join(lines).strip()


def try_fetch_subtitles(url: str, tmpdir: Path) -> str:
    require_command("yt-dlp")
    out = tmpdir / "subtitle"
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang",
        "zh-Hans,zh,zh-Hant,en",
        "--sub-format",
        "vtt/srt/best",
        "--skip-download",
        "--no-playlist",
        "-o",
        str(out),
        url,
    ]
    result = run(cmd, timeout=90)
    if result.returncode != 0:
        return ""
    for path in sorted(tmpdir.iterdir()):
        if path.name.startswith("subtitle") and path.suffix.lower() in {".vtt", ".srt"}:
            text = parse_subtitle(path)
            if len(text) > 80:
                return text
    return ""


def download_audio(url: str, tmpdir: Path) -> Path:
    require_command("yt-dlp")
    audio = tmpdir / "audio.%(ext)s"
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "32K",
        "--no-playlist",
        "-o",
        str(audio),
        url,
    ]
    result = run(cmd, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载音频失败：{result.stderr[-800:]}")
    candidates = sorted(tmpdir.glob("audio.*"))
    if not candidates:
        raise RuntimeError("yt-dlp 未生成音频文件。")
    return candidates[0]


def resolve_download_dir(path_arg: str) -> Path:
    return Path(path_arg).expanduser() if path_arg else Path.home() / "Downloads"


def build_download_command(url: str, output_dir: Path, download_type: str) -> list[str]:
    template = "%(title).200B [%(id)s].%(ext)s"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--paths",
        str(output_dir),
        "-o",
        template,
        "--print",
        "after_move:filepath",
    ]
    if download_type == "audio":
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
    else:
        cmd.extend(["-f", "bv*+ba/b", "--merge-output-format", "mp4"])
    cmd.append(url)
    return cmd


def download_url(input_value: str, *, output_dir: Path, download_type: str, dry_run: bool) -> Path | None:
    require_command("yt-dlp")
    output_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://{input_value}" if input_value.startswith("www.") else input_value
    if not is_url(url):
        raise ValueError("--download-only 只支持 URL 输入。")

    cmd = build_download_command(url, output_dir, download_type)
    if dry_run:
        cmd = cmd[:-1] + ["--simulate", "--print", "title", url]
        result = run(cmd, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp 下载预检失败：{result.stderr[-800:]}")
        print("下载预检完成")
        print(f"目录：{output_dir}")
        print(f"类型：{download_type}")
        if result.stdout.strip():
            print(f"标题：{result.stdout.strip().splitlines()[-1]}")
        return None

    result = run(cmd, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载视频失败：{result.stderr[-1200:]}")

    paths = [Path(line.strip()).expanduser() for line in result.stdout.splitlines() if line.strip()]
    existing = [path for path in paths if path.exists()]
    if not existing:
        candidates = sorted(output_dir.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
        existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RuntimeError("yt-dlp 已结束，但未找到下载后的文件。")

    downloaded = existing[0]
    print("下载完成")
    print(f"文件：{downloaded}")
    print(f"大小：{downloaded.stat().st_size} bytes")
    return downloaded


def extract_audio(input_path: Path, tmpdir: Path) -> Path:
    suffix = input_path.suffix.lower()
    if suffix in {".mp3", ".wav", ".ogg"}:
        return input_path

    require_command("ffmpeg")
    audio = tmpdir / "audio.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "32k",
        str(audio),
    ]
    result = run(cmd, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败：{result.stderr[-800:]}")
    return audio


def split_audio(audio_path: Path, tmpdir: Path, chunk_minutes: int) -> list[Path]:
    duration = get_duration_seconds(audio_path)
    if chunk_minutes <= 0 or duration <= chunk_minutes * 60:
        return [audio_path]

    require_command("ffmpeg")
    chunk_dir = tmpdir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    pattern = chunk_dir / "chunk_%03d.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "32k",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_minutes * 60),
        "-reset_timestamps",
        "1",
        str(pattern),
    ]
    result = run(cmd, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 音频切片失败：{result.stderr[-800:]}")
    chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("ffmpeg 未生成音频切片。")
    return chunks


def transcribe_audio_chunks(audio_path: Path, tmpdir: Path, *, language: str, chunk_minutes: int, dry_run: bool) -> tuple[str, dict]:
    chunks = split_audio(audio_path, tmpdir, chunk_minutes)
    metadata = {
        "audio_path": str(audio_path),
        "duration_seconds": round(get_duration_seconds(audio_path), 2),
        "chunk_count": len(chunks),
        "chunk_minutes": chunk_minutes,
        "chunks": [{"path": str(path), "bytes": path.stat().st_size} for path in chunks],
    }

    if dry_run:
        total_bytes = sum(item["bytes"] for item in metadata["chunks"])
        return f"[DRY RUN] 媒体处理成功：{len(chunks)} 个音频分片，总大小 {total_bytes} bytes。", metadata

    texts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"调用 StepFun ASR：分片 {index}/{len(chunks)}...", flush=True)
        texts.append(transcribe_file(chunk, language=language))
    return "\n\n".join(text.strip() for text in texts if text.strip()).strip(), metadata


def write_output(text: str, output: Path, fmt: str, metadata: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        payload = {"text": text, "metadata": metadata}
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if fmt == "md":
        body = [
            "# 转写稿",
            "",
            f"- 来源：{metadata.get('input', '')}",
            f"- 方式：{metadata.get('source_type', '')}",
            f"- 字数：{len(text)}",
            "",
            "## 正文",
            "",
            text,
            "",
        ]
        output.write_text("\n".join(body), encoding="utf-8")
        return
    output.write_text(text, encoding="utf-8")


def resolve_output(path_arg: str, fmt: str) -> Path:
    if path_arg:
        return Path(path_arg).expanduser()
    return timestamp_path(fmt)


def resolve_batch_output_dir(path_arg: str) -> Path:
    if path_arg:
        return Path(path_arg).expanduser()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"transcripts_{ts}"


def parse_include_patterns(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def matches_include(path: Path, rel_path: Path, patterns: list[str]) -> bool:
    if not patterns:
        return path.suffix.lower() in SUPPORTED_EXTS
    rel_text = rel_path.as_posix()
    return any(fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel_text, pattern) for pattern in patterns)


def collect_batch_inputs(input_dir: Path, *, recursive: bool, include: str) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"目录不存在：{input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"不是目录：{input_dir}")

    patterns = parse_include_patterns(include)
    iterator = input_dir.rglob("*") if recursive else input_dir.iterdir()
    files: list[Path] = []
    for path in iterator:
        if not path.is_file():
            continue
        rel_path = path.relative_to(input_dir)
        if matches_include(path, rel_path, patterns):
            files.append(path)
    return sorted(files)


def output_for_batch_item(input_path: Path, *, input_dir: Path, output_dir: Path, fmt: str) -> Path:
    rel_path = input_path.relative_to(input_dir)
    return (output_dir / rel_path).with_suffix(f".{fmt}")


def make_test_audio(path: Path, *, duration: int = 2) -> None:
    require_command("ffmpeg")
    say_bin = shutil.which("say")
    if say_bin:
        speech_path = path.with_suffix(".aiff")
        say_result = run(
            [say_bin, "-o", str(speech_path), "你好，这是音频转文字测试。"],
            timeout=120,
        )
        if say_result.returncode == 0 and speech_path.exists():
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(speech_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-b:a",
                "32k",
                str(path),
            ]
            result = run(cmd, timeout=120)
            speech_path.unlink(missing_ok=True)
            if result.returncode == 0:
                return

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "32k",
        str(path),
    ]
    result = run(cmd, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"生成测试音频失败：{result.stderr[-800:]}")


def transcribe_input(args: argparse.Namespace, *, input_value: str, output: Path) -> int:
    if input_value.startswith("www."):
        input_value = f"https://{input_value}"

    metadata = {
        "input": input_value,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_type": "",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        text = ""
        audio_path: Path | None = None

        if is_url(input_value):
            metadata["source_type"] = "subtitle" if not args.no_subtitle else "asr"
            if not args.no_subtitle:
                print("尝试抓取现成字幕...", flush=True)
                text = try_fetch_subtitles(input_value, tmpdir)
            if text:
                print("字幕抓取成功，跳过 ASR。", flush=True)
            else:
                print("无可用字幕，下载音频...", flush=True)
                audio_path = download_audio(input_value, tmpdir)
                metadata["source_type"] = "asr"
        else:
            input_path = Path(input_value).expanduser()
            if not input_path.exists():
                raise FileNotFoundError(f"文件不存在：{input_path}")
            print(f"处理本地文件：{input_path}", flush=True)
            audio_path = extract_audio(input_path, tmpdir)
            metadata["source_type"] = "asr"

        if args.dry_run and not text:
            if not audio_path:
                raise RuntimeError("dry-run 未解析出音频文件。")
            text, audio_meta = transcribe_audio_chunks(audio_path, tmpdir, language=args.language, chunk_minutes=args.chunk_minutes, dry_run=True)
            metadata.update(audio_meta)
            metadata["source_type"] = "dry-run"
        elif not text:
            if not audio_path:
                raise RuntimeError("没有可转写的音频。")
            text, audio_meta = transcribe_audio_chunks(audio_path, tmpdir, language=args.language, chunk_minutes=args.chunk_minutes, dry_run=False)
            metadata.update(audio_meta)

        write_output(text, output, args.format, metadata)
        print("\n转写完成")
        print(f"文件：{output}")
        print(f"字数：{len(text)}")
        print(f"方式：{metadata['source_type']}")
        print("\n前 300 字预览：")
        print(text[:300])
        if len(text) > 300:
            print("...")
        return 0


def run_batch(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).expanduser()
    output_dir = resolve_batch_output_dir(args.output_dir)
    files = collect_batch_inputs(input_dir, recursive=args.recursive, include=args.include)
    if not files:
        print(f"未找到可处理的媒体文件：{input_dir}")
        return 1

    print(f"批量转写开始：{len(files)} 个文件")
    print(f"输入目录：{input_dir}")
    print(f"输出目录：{output_dir}")

    results: list[dict] = []
    failed = 0
    skipped = 0
    for index, input_path in enumerate(files, start=1):
        output = output_for_batch_item(input_path, input_dir=input_dir, output_dir=output_dir, fmt=args.format)
        if args.skip_existing and output.exists():
            skipped += 1
            results.append({
                "input": str(input_path),
                "output": str(output),
                "status": "skipped",
                "reason": "output exists",
            })
            print(f"\n[{index}/{len(files)}] 跳过已存在：{output}")
            continue

        print(f"\n[{index}/{len(files)}] {input_path}")
        try:
            transcribe_input(args, input_value=str(input_path), output=output)
            results.append({"input": str(input_path), "output": str(output), "status": "ok"})
        except Exception as error:
            failed += 1
            results.append({
                "input": str(input_path),
                "output": str(output),
                "status": "failed",
                "error": str(error),
            })
            print(f"错误：{error}", file=sys.stderr)
            if not args.continue_on_error:
                break

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "format": args.format,
        "total": len(files),
        "ok": sum(1 for item in results if item["status"] == "ok"),
        "failed": failed,
        "skipped": skipped,
        "continue_on_error": bool(args.continue_on_error),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }
    report_path = output_dir / "_batch_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n批量转写完成")
    print(f"成功：{report['ok']}")
    print(f"失败：{failed}")
    print(f"跳过：{skipped}")
    print(f"报告：{report_path}")
    return 1 if failed else 0


def run_live_test(args: argparse.Namespace) -> int:
    status = get_config_status()
    if not status["api_key_configured"]:
        print("缺少 STEPFUN_API_KEY，无法运行 live test。")
        print("先运行：bash ~/.codex/skills/syc-audio-to-text/run.sh --configure-key")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "stepfun_live_test.mp3"
        make_test_audio(sample)
        output = Path(args.output).expanduser() if args.output else Path("/tmp/syc-audio-to-text-live-test.txt")
        live_args = argparse.Namespace(**vars(args))
        live_args.dry_run = False
        live_args.no_subtitle = True
        live_args.format = args.format
        print(f"生成测试音频：{sample}")
        return transcribe_input(live_args, input_value=str(sample), output=output)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地音视频或 URL 转文字稿")
    parser.add_argument("--input", "-i", default="", help="本地文件路径或 URL")
    parser.add_argument("--input-dir", default="", help="批量转写：本地媒体目录")
    parser.add_argument("--output", "-o", default="", help="输出路径")
    parser.add_argument("--output-dir", default="", help="批量转写：输出目录，默认写入 ~/Downloads/transcripts_<timestamp>")
    parser.add_argument("--download-only", action="store_true", help="只下载 URL 视频/音频到本地，不转写")
    parser.add_argument("--download-type", choices=["video", "audio"], default="video", help="下载类型，默认 video")
    parser.add_argument("--download-dir", default="", help="下载目录，默认 ~/Downloads")
    parser.add_argument("--format", "-f", choices=["txt", "md", "json"], default="txt", help="输出格式")
    parser.add_argument("--language", default="zh", help="ASR 语言：zh、en 或 auto")
    parser.add_argument("--no-subtitle", action="store_true", help="跳过 URL 字幕抓取")
    parser.add_argument("--chunk-minutes", type=int, default=DEFAULT_CHUNK_MINUTES, help="ASR 前按分钟切分长音频，默认 25")
    parser.add_argument("--include", default="", help="批量转写：逗号分隔 glob，如 '*.mp3,*.m4a,*.mp4'；默认处理常见音视频后缀")
    parser.add_argument("--recursive", action="store_true", help="批量转写：递归处理子目录")
    parser.add_argument("--skip-existing", action="store_true", help="批量转写：输出文件已存在时跳过")
    parser.add_argument("--continue-on-error", action="store_true", help="批量转写：单个文件失败后继续处理后续文件")
    parser.add_argument("--dry-run", action="store_true", help="只验证媒体解析，不调用 ASR API")
    parser.add_argument("--check", action="store_true", help="检查依赖和 StepFun 配置")
    parser.add_argument("--configure-key", action="store_true", help="隐藏输入 StepFun API Key 并写入 ~/.stepfun.env")
    parser.add_argument("--live-test", action="store_true", help="生成短测试音频并调用 StepFun ASR")
    args = parser.parse_args()

    if args.configure_key:
        return configure_key()
    if args.check:
        return run_check()
    if args.live_test:
        try:
            return run_live_test(args)
        except Exception as error:
            print(f"错误：{error}", file=sys.stderr)
            return 1
    if args.input and args.input_dir:
        parser.error("--input and --input-dir cannot be used together")
    if args.download_only:
        if args.input_dir:
            parser.error("--download-only requires --input URL, not --input-dir")
        if args.output or args.output_dir:
            parser.error("--download-only uses --download-dir, not --output or --output-dir")
        if not args.input:
            parser.error("--download-only requires --input URL")
        try:
            download_url(
                args.input.strip(),
                output_dir=resolve_download_dir(args.download_dir),
                download_type=args.download_type,
                dry_run=args.dry_run,
            )
            return 0
        except Exception as error:
            print(f"错误：{error}", file=sys.stderr)
            return 1
    if args.input_dir:
        if args.output:
            parser.error("--output is only for single input; use --output-dir with --input-dir")
        try:
            return run_batch(args)
        except Exception as error:
            print(f"错误：{error}", file=sys.stderr)
            return 1
    if not args.input:
        parser.error("--input or --input-dir is required unless --check, --configure-key, or --live-test is used")

    output = resolve_output(args.output, args.format)
    input_value = args.input.strip()

    try:
        return transcribe_input(args, input_value=input_value, output=output)
    except Exception as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
