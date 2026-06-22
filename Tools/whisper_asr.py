#!/usr/bin/env python3
"""本地 Whisper ASR 降级模块。

当 StepFun ASR 不可用（风控拦截、API Key 缺失、网络超时等）时，
自动降级到本地 whisper CLI 作为兜底。

依赖：pip install openai-whisper
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def require_whisper() -> str:
    """检查 whisper CLI 是否可用，返回路径。"""
    path = shutil.which("whisper")
    if not path:
        raise RuntimeError(
            "本地 whisper 不可用。请安装：pip install openai-whisper"
        )
    return path


def transcribe_audio(
    audio_path: str | Path,
    *,
    language: str = "zh",
    model: str = "small",
) -> str:
    """使用本地 whisper CLI 转写音频文件。

    Args:
        audio_path: 音频文件路径（mp3/wav/ogg 等）
        language: 语言代码（zh/en/auto 等）
        model: whisper 模型大小（tiny/base/small/medium/large）

    Returns:
        转写文本

    Raises:
        FileNotFoundError: 音频文件不存在
        RuntimeError: whisper 不可用或转写失败
    """
    path = Path(audio_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在：{path}")

    whisper_bin = require_whisper()

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        cmd = [
            whisper_bin,
            str(path),
            "--model", model,
            "--language", language,
            "--output_format", "txt",
            "--output_dir", str(tmpdir),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Whisper 转写失败：{result.stderr[-800:]}")

        # whisper 会在 output_dir 写入 <audio_stem>.txt
        txt_path = tmpdir / f"{path.stem}.txt"
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="ignore").strip()

        # 兜底：从 stdout 解析
        return result.stdout.strip()
