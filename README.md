# Syc Audio to Text

一个给 Codex、Claude Code 等本地 Agent 使用的音视频转文案 Skill。它可以把本地音视频文件、YouTube/Bilibili 等公开视频链接转成文字稿，也可以只下载视频到本地而不转写。

## 功能

- 本地音频/视频转文字：`mp3`、`m4a`、`wav`、`mp4`、`mov`、`mkv` 等
- URL 转文字：优先抓取平台字幕；没有字幕时下载音频并调用 StepFun Step Plan ASR
- 批量转写本地文件夹，支持递归、跳过已有结果、失败后继续
- 只下载在线视频到本地，默认保存为视频文件
- 长音频自动切片，避免单次请求过大
- 输出 `txt`、`md`、`json`

## 依赖

- macOS / Linux
- Python 3.10+
- `git`
- `ffmpeg`
- StepFun Step Plan API Key

macOS 可用 Homebrew 安装：

```bash
brew install python@3.11 ffmpeg git
```

安装脚本会在 Skill 目录里创建独立 `.venv`，并在里面安装最新版 `requests` 和 `yt-dlp`。运行时会优先使用这个环境，避免新电脑 PATH 里的旧 Python / 旧 `yt-dlp` 导致 YouTube 下载失败或提示版本过低。

## 安装

### 方式一：发给 Codex / Claude Code / 任意 Agent 的安装 Prompt

把下面这段话发给你的本地 Agent：

```text
请帮我安装这个 GitHub Skill：https://github.com/Songxiaor/syc-audio-to-text

要求：
1. 克隆仓库到临时目录。
2. 运行仓库里的 install.sh。
3. 默认安装到 ~/.codex/skills/syc-audio-to-text；如果当前客户端使用其他 Skill 目录，请安装到对应目录。
4. 安装完成后运行 bash ~/.codex/skills/syc-audio-to-text/run.sh --check 检查依赖。
5. 不要让我在聊天里明文发送 API Key；让我用 --configure-key 在本机隐藏输入并写入 ~/.stepfun.env。
```

### 方式二：一条命令安装

macOS / Linux 终端执行：

```bash
tmp="$(mktemp -d)" && git clone https://github.com/Songxiaor/syc-audio-to-text.git "$tmp/syc-audio-to-text" && bash "$tmp/syc-audio-to-text/install.sh"
```

安装后配置 API Key：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --configure-key
```

检查是否使用了 Skill 自带的 Python 和 `yt-dlp`：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --check
```

### 方式三：手动安装

克隆仓库：

```bash
git clone https://github.com/Songxiaor/syc-audio-to-text.git
cd syc-audio-to-text
```

安装到 Codex Skill 目录：

```bash
bash install.sh
```

默认安装到：

```bash
~/.codex/skills/syc-audio-to-text
```

如果你使用自定义 Skill 目录：

```bash
SKILL_HOME="$HOME/.cc-switch/skills" bash install.sh
```

## 配置 API Key

本仓库不会包含任何 API Key。安装后需要配置你自己的 StepFun Step Plan API Key。

推荐用交互式配置：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --configure-key
```

这个命令会把密钥写入：

```bash
~/.stepfun.env
```

并设置权限为 `600`。

你也可以手动创建：

```bash
cat > ~/.stepfun.env <<'EOF'
STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1
STEPFUN_API_KEY=你的 StepFun API Key
EOF
chmod 600 ~/.stepfun.env
```

检查配置：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --check
```

真实 ASR 冒烟测试：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --live-test
```

## 使用方式

### 转写 YouTube / Bilibili 等链接

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxxx" \
  --output ~/Desktop/transcript.md \
  --format md
```

流程：

1. 先尝试抓取平台字幕。
2. 如果没有可用字幕，下载音频。
3. 调用 StepFun ASR 转写。
4. 输出文字稿。

强制跳过平台字幕，全部走 ASR：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxxx" \
  --output ~/Desktop/transcript.md \
  --format md \
  --no-subtitle
```

### 转写本地文件

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input ~/Downloads/video.mp4 \
  --output ~/Desktop/transcript.md \
  --format md
```

长音频可调整切片长度：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input ~/Downloads/long-audio.mp3 \
  --output ~/Desktop/transcript.md \
  --format md \
  --chunk-minutes 15
```

### 批量转写本地文件夹

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input-dir ~/Downloads/media \
  --output-dir ~/Desktop/transcripts \
  --format md \
  --recursive \
  --skip-existing \
  --continue-on-error
```

只处理指定格式：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input-dir ~/Downloads/media \
  --output-dir ~/Desktop/transcripts \
  --include "*.mp3,*.m4a,*.mp4"
```

批量模式会生成：

```bash
_batch_report.json
```

用于查看每个文件的处理结果。

### 只下载视频，不转写

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxxx" \
  --download-only
```

默认保存到：

```bash
~/Downloads
```

指定下载目录：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxxx" \
  --download-only \
  --download-dir ~/Downloads
```

只下载音频：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh \
  --input "https://www.youtube.com/watch?v=xxxx" \
  --download-only \
  --download-type audio
```

## 在 Codex / Claude Code 中使用

### 桌面端使用方式

安装后，你可以直接对 Codex、Claude Code 或其他本地 Agent 说：

```text
用 syc-audio-to-text 转写这个 YouTube 链接：https://...
```

或者：

```text
用 syc-audio-to-text 批量转写这个文件夹里的视频，输出成 Markdown。
```

或者：

```text
用 syc-audio-to-text 把这个视频链接下载到本地，不要转写。
```

### CLI 工具使用方式

直接调用：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --help
```

常用形式：

```bash
bash ~/.codex/skills/syc-audio-to-text/run.sh --input "<file-or-url>" --output ~/Desktop/transcript.md --format md
```

## 支持的平台

URL 能力来自 `yt-dlp`，所以支持范围取决于当前安装的 `yt-dlp` 版本。常见可用平台包括：

- YouTube
- Bilibili
- Douyin
- TikTok
- Xiaohongshu
- Weibo
- X / Twitter
- Instagram
- Facebook
- Vimeo
- Dailymotion
- Twitch
- SoundCloud
- Apple Podcasts
- Ximalaya
- AcFun
- Youku
- iQIYI
- Zoom
- Loom
- Panopto

部分平台可能需要登录态、Cookie、地区可访问性或公开视频权限。

## 常用命令

```bash
# 查看帮助
bash ~/.codex/skills/syc-audio-to-text/run.sh --help

# 检查依赖和 API Key
bash ~/.codex/skills/syc-audio-to-text/run.sh --check

# 不调用 ASR，只验证媒体解析
bash ~/.codex/skills/syc-audio-to-text/run.sh --input ~/Downloads/video.mp4 --dry-run

# 本地验证
python3 ~/.codex/skills/syc-audio-to-text/Tools/verify_local.py
```

## API Key 与安全

- 本项目不包含任何 StepFun API Key。
- 你的 API Key 只需要保存在本机 `~/.stepfun.env`，不需要写进仓库文件。
- 推荐使用 `--configure-key` 配置密钥，因为输入过程不会在终端显示。
- `~/.stepfun.env` 会被设置为 `600` 权限，只允许当前用户读取。
- `.gitignore` 已忽略常见 `.env` 文件，避免误提交本地密钥配置。
- `--check` 只显示 API Key 是否已配置和长度，不会打印密钥内容。
- 如果你 fork 或二次开发，请不要把真实 API Key 写进 README、脚本、Issue 或 PR。
