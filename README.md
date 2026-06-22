# syc-audio-to-text 🎤

> 给本地 AI Agent（Codex、Claude Code 等）用的音视频转文字技能。  
> 支持 YouTube / B站 / 抖音等主流平台 URL 转写，也支持本地文件批量处理。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)]()

---

## ✨ 快速安装（10 秒）

打开终端，复制粘贴这一条命令：

```bash
bash -c "$(curl -sL https://raw.githubusercontent.com/Songxiaor/syc-audio-to-text/main/install.sh)"
```

安装脚本会自动：
1. 克隆仓库到 `~/.codex/skills/syc-audio-to-text`
2. 创建独立 Python 虚拟环境
3. 安装 `requests` 和 `yt-dlp`
4. 检测 `ffmpeg` 是否就绪

---

## ✅ 验证安装

```bash
# 第一步：配置 API Key（交互式，不会在屏幕显示密钥）
bash ~/.codex/skills/syc-audio-to-text/run.sh --configure-key

# 第二步：检查依赖和配置
bash ~/.codex/skills/syc-audio-to-text/run.sh --check

# 第三步：真实 ASR 冒烟测试（生成 2 秒音频 → 调用 API → 返回文字）
bash ~/.codex/skills/syc-audio-to-text/run.sh --live-test
```

> 💡 **没有 API Key？**  
> 本技能使用 [StepFun Step Plan ASR](https://platform.stepfun.com/) 进行语音识别。  
> 你需要去 StepFun 官网注册并申请 API Key。  
> 或者将 `--asr-engine whisper` 参数传给 run.sh，使用本地 Whisper（需 `pip install openai-whisper`）。

---

## 📖 快速上手

### 转写 YouTube / B站 视频

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxx" \
  --output ~/Desktop/transcript.md \
  --format md
```

### 转写本地视频/音频

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input ~/Downloads/video.mp4 \
  --output ~/Desktop/transcript.md \
  --format md
```

### 批量转写整个文件夹

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input-dir ~/Downloads/media \
  --output-dir ~/Desktop/transcripts \
  --format md \
  --recursive \
  --skip-existing \
  --continue-on-error
```

### 只下载视频，不转写

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxx" \
  --download-only
```

---

## 🔧 进阶选项

| 参数 | 作用 |
|---|---|
| `--format txt\|md\|json` | 输出格式，默认 txt |
| `--language zh\|en\|auto` | ASR 语言，默认 zh |
| `--asr-engine auto\|stepfun\|whisper` | ASR 引擎：auto（默认，StepFun 优先，失败自动降级 Whisper）、stepfun（仅 StepFun）、whisper（直接本地 Whisper） |
| `--no-subtitle` | 跳过 URL 字幕抓取，强制走 ASR |
| `--chunk-minutes 15` | 长音频切片分钟数，默认 25 |
| `--include "*.mp3,*.mp4"` | 批量时按文件类型筛选 |
| `--dry-run` | 只验证，不调用 ASR |
| `--download-type video\|audio` | 下载类型 |
| `--download-dir ~/Downloads` | 下载目录 |

---

## 🗑 卸载

```bash
rm -rf ~/.codex/skills/syc-audio-to-text
# 可选：删除 API Key 配置
rm -f ~/.stepfun.env
```

---

## 在 AI Agent 中使用

安装后，直接对你的 Agent（Codex、Claude Code、NewMax 等）说：

> 用 syc-audio-to-text 转写这个视频链接：https://...
> 用 syc-audio-to-text 批量转写这个文件夹
> 用 syc-audio-to-text 把这个视频下载到本地

Agent 会自动调用 `run.sh` 完成工作。

---

## 支持平台

由 `yt-dlp` 驱动，支持 YouTube、Bilibili、抖音、TikTok、小红书、微博、X/Twitter、Instagram、Facebook、Vimeo、SoundCloud、Apple Podcasts、喜马拉雅、AcFun、优酷、爱奇艺、Zoom、Loom 等。  
部分平台需要登录态或 Cookie。

---

## 安全说明

- 本仓库不含任何 API Key
- API Key 仅保存在 `~/.stepfun.env`（权限 600）
- `--check` 只会显示 Key 是否已配置和长度，不会打印内容
- `.gitignore` 已排除 `.env` 和 `.stepfun.env`
