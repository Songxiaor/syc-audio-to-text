#!/usr/bin/env python3
"""StepFun Step Plan ASR client."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Iterable

import requests

DEFAULT_BASE_URL = "https://api.stepfun.com/step_plan/v1"
DEFAULT_MODEL = "stepaudio-2.5-asr"
DEFAULT_MAX_AUDIO_BYTES = 24 * 1024 * 1024


def normalize_api_key(value: str) -> str:
    text = (value or "").strip()
    lowered = text.lower()
    if lowered.startswith("authorization:"):
        text = text.split(":", 1)[1].strip()
        lowered = text.lower()
    if lowered.startswith("bearer "):
        text = text[7:].strip()
    return text


def load_api_key() -> str:
    for name in ("STEPFUN_API_KEY", "STEP_API_KEY", "STEP_AUDIO_API_KEY"):
        value = normalize_api_key(os.environ.get(name, ""))
        if value:
            return value

    for env_path in (
        Path.home() / ".shared-skills/api-registry/.env",
        Path.home() / ".cc-switch/.env",
        Path.home() / ".stepfun.env",
    ):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() in {"STEPFUN_API_KEY", "STEP_API_KEY", "STEP_AUDIO_API_KEY"}:
                loaded = normalize_api_key(value.strip().strip("\"'"))
                if loaded:
                    return loaded
    return ""


def infer_audio_format(path: Path) -> dict:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"mp3", "wav", "ogg"}:
        return {"type": suffix}
    if suffix == "pcm":
        return {"type": "pcm", "rate": 16000, "bits": 16, "channel": 1}
    return {"type": "mp3"}


def get_config_status() -> dict:
    key = load_api_key()
    return {
        "api_key_configured": bool(key),
        "api_key_length": len(key),
        "base_url": os.environ.get("STEPFUN_BASE_URL") or DEFAULT_BASE_URL,
        "model": os.environ.get("STEPFUN_ASR_MODEL") or DEFAULT_MODEL,
    }


def iter_sse_lines(response: requests.Response) -> Iterable[str]:
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("data:"):
            yield line[5:].strip()


def extract_text_from_event(event: dict) -> str:
    delta = event.get("delta")
    if isinstance(delta, str) and delta:
        return delta

    candidates = [
        event.get("text"),
        event.get("content"),
        event.get("result", {}).get("text") if isinstance(event.get("result"), dict) else "",
        delta.get("text") if isinstance(delta, dict) else "",
    ]
    for value in candidates:
        if isinstance(value, str) and value:
            return value

    data = event.get("data")
    if isinstance(data, dict):
        for key in ("text", "content"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def transcribe_file(
    audio_path: str | Path,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    language: str = "zh",
    enable_itn: bool = True,
    timeout: int = 300,
    max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
) -> str:
    path = Path(audio_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在：{path}")
    if path.stat().st_size > max_audio_bytes:
        mb = path.stat().st_size / 1024 / 1024
        limit_mb = max_audio_bytes / 1024 / 1024
        raise RuntimeError(f"音频分片过大：{mb:.1f} MB，超过单次请求限制 {limit_mb:.1f} MB。请缩短 --chunk-minutes 或降低音频码率。")

    key = normalize_api_key(api_key or load_api_key())
    if not key:
        raise RuntimeError("缺少 STEPFUN_API_KEY。请先设置环境变量，或写入 ~/.shared-skills/api-registry/.env。")

    endpoint = (base_url or os.environ.get("STEPFUN_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    url = f"{endpoint}/audio/asr/sse"
    model_name = model or os.environ.get("STEPFUN_ASR_MODEL") or DEFAULT_MODEL

    audio_data = base64.b64encode(path.read_bytes()).decode("ascii")
    payload = {
        "audio": {
            "data": audio_data,
            "input": {
                "transcription": {
                    "model": model_name,
                    "language": "" if language == "auto" else language,
                    "enable_itn": bool(enable_itn),
                    "enable_timestamp": False,
                },
                "format": infer_audio_format(path),
            },
        }
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    with requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout) as response:
        if response.status_code >= 400:
            detail = response.text[:500]
            raise RuntimeError(f"StepFun ASR 请求失败：HTTP {response.status_code} {detail}")

        parts: list[str] = []
        final_text = ""
        for data in iter_sse_lines(response):
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            event_type = str(event.get("type") or event.get("event") or "")
            if "error" in event_type:
                raise RuntimeError(f"StepFun ASR 返回错误：{json.dumps(event, ensure_ascii=False)}")
            text = extract_text_from_event(event)
            if not text:
                continue
            if event_type == "transcript.text.done":
                final_text = text
            elif event_type == "transcript.text.delta":
                parts.append(text)
            else:
                parts.append(text)

        if final_text:
            return final_text.strip()
        return "".join(parts).strip()
