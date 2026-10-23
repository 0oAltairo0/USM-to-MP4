# USM-to-MP4
A tool for USM from Initial D,etc.
# usm2mp4

**中文** | [English](#usm2mp4-english)

将 CRI Sofdec 的 **USM 视频容器**一键转换为带声音的标准 **MP4** 文件。

输入一个 `.usm`，输出一个可以直接播放的 `.mp4` —— 中间的解封装、帧率探测、音视频合成都由脚本自动完成，无需手动拼参数。

---

## 特性

- **一条命令完成**：`python usm_to_mp4.py input.usm` 即可得到 `input.mp4`
- **视频零损失**：MPEG 视频流直接 `-c:v copy` 封装，不重新编码，画质与原始资源完全一致
- **自动识别帧率**：从 MPEG 序列头读取 `frame_rate_code`，正确区分 23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 fps
- **修复音频块填充错位**：自动剥离 ADX 音频块尾部的 24 字节零填充，解决导出视频「没有声音」的问题
- **缺失依赖可自助安装**：检测不到 FFmpeg 时会询问是否自动配置环境（`y/n`），确认后按平台自动调用 winget / brew / apt 等完成安装
- **支持批量**：传入目录，自动处理其中所有 `.usm`
- **不污染磁盘**：中间文件（`.m2v` / `.adx`）写入临时目录，结束后自动清理
- **无第三方 Python 依赖**：只用标准库，不需要 pip 安装任何包

---

## 依赖安装

### 1. 安装 Python

需要 **Python 3.6 或更高版本**。

- Windows：从 [python.org](https://www.python.org/downloads/) 下载安装包，安装时**勾选 "Add Python to PATH"**
- macOS：`brew install python3`（或使用系统自带版本）
- Linux：`sudo apt install python3`

确认安装成功：

```bash
python --version
# 若系统上 python 指向 Python 2，请改用 python3
```

### 2. 安装 FFmpeg

本项目的音视频合成完全依赖 FFmpeg，**这是必须安装的外部程序**。

Windows（推荐使用 winget）：

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

macOS：

```bash
brew install ffmpeg
```

Linux：

```bash
sudo apt update && sudo apt install -y ffmpeg
```

确认安装成功：

```bash
ffmpeg -version
```

> **也可以跳过这一步**：直接运行脚本，若检测不到 FFmpeg，会提示「是否现在自动配置 FFmpeg 环境？[y/N]」，输入 `y` 即按当前平台自动调起包管理器安装；输入 `n` 则打印手动安装指引并退出。
>
> ⚠️ **常见误区**：不要执行 `pip install ffmpeg` 或 `pip install ffmpeg-python`。PyPI 上的这些包并不是 FFmpeg 本体，装完后命令仍然找不到 `ffmpeg`。

### 3. 安装 Python 依赖

本项目**没有**任何第三方 Python 包依赖，因此这一步只是走个流程、确认环境正常：

```bash
pip install -r requirements.txt
```

该文件全部是注释说明，执行后不会安装任何包 —— 这是预期结果。

### 4. 获取代码

```bash
git clone https://github.com/<你的用户名>/usm2mp4.git
cd usm2mp4
```

---

## 使用方法

### 单个文件

```bash
python usm_to_mp4.py input.usm
```

输出 `input.mp4`，与输入文件在同一目录。

### 指定输出路径

```bash
python usm_to_mp4.py input.usm output.mp4
```

### 批量处理整个目录

```bash
python usm_to_mp4.py "D:\game_assets\movies"
```

会遍历该目录（不递归）下所有 `.usm` 文件并逐个转换，每个文件输出同名 `.mp4`。

Windows 路径含空格时请用双引号包裹。

### 运行时的输出示例

```
解封装 advinfo1.usm ...
检测到帧率: 60 fps, 音频: 有
正在合成 MP4 ...
完成: advinfo1.mp4
```

首次运行且系统缺少 FFmpeg 时，会出现如下交互：

```
未检测到 FFmpeg。
本工具的音视频合成依赖 FFmpeg，必须安装后才能继续。

是否现在自动配置 FFmpeg 环境？[y/N]: y

将执行以下命令：
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
安装过程可能需要管理员权限，请按提示操作 ...
```

---

## 命令行参数

| 参数 | 是否必填 | 说明 |
|------|----------|------|
| 第 1 个参数 | 必填 | 输入的 `.usm` 文件路径，或包含 `.usm` 的目录路径 |
| 第 2 个参数 | 可选 | 输出的 `.mp4` 路径；省略时自动使用输入文件的同名 `.mp4` |

未提供参数时会打印用法提示并以退出码 `1` 退出。

---

## 工作原理

### 为什么需要这个工具

USM（CRI Sofdec Universal Media）是 SEGA / CRI 系游戏常用的一种视频容器，它把视频流和音频流切成小块、交错存放在同一个文件里，因此无法被播放器直接识别。转换的核心就是把这两条流重新分离出来，再装进 MP4 容器。

### 处理流程

1. **解析容器**
   USM 由一系列带签名的块顺序组成，每个块的头部结构为：

   | 偏移 | 长度 | 含义 |
   |------|------|------|
   | 0 | 4 | 块签名（`CRID` / `@SFV` / `@SFA` / `@SFD` 等） |
   | 4 | 4 | 块总长度（大端序） |
   | 8 | 24 | 媒体头（含 1 字节的数据偏移量） |

   脚本从文件起始位置顺序遍历，遇到 `@SFV` 取视频数据，遇到 `@SFA` 取音频数据，跳过 `@UTF` 等元信息块。

2. **提取视频流**
   `@SFV` 块的有效载荷以 MPEG 起始码 `00 00 01` 开头，直接顺序拼接即可得到完整的 `.m2v` 裸流。

3. **提取音频流**
   `@SFA` 块拼接后得到 `.adx`（CRI ADX 音频）。
   **关键修复点**：每个音频块的有效载荷固定为 1824 字节，而其中真正的 ADX 数据是前 1800 字节，末尾 24 字节为零填充。如果把这些填充一并拼进流里，就会破坏 ADX 固定的 18 字节帧网格，解码器在几十毫秒后就会判定数据非法并终止 —— 表现出的现象正是**导出的视频完全没有声音**。脚本会在拼接前剥离这段填充。

4. **探测帧率**
   在 `.m2v` 中查找序列头 `00 00 01 B3`，从其第 4 个字节的低 4 位读取 `frame_rate_code`，映射为实际帧率。

5. **合成 MP4**
   MPEG 裸流本身不携带时间戳，因此使用 `-fflags +genpts` 让 FFmpeg 按帧率重新生成时间戳，再以 `-c:v copy` 无损封装视频、`-c:a aac` 编码音频，并用 `-shortest` 对齐两条流的时长。

### 适用范围

- 已在 1080p60 与 1080p30、含独立视频流与音频流的 USM 上验证通过
- 视频编码为 MPEG-2，音频编码为 ADX（48 kHz 立体声）
- **输入必须是已解密的 USM**。若原始文件仍处于加密状态（例如游戏内被二次封装的 `.opt` 等），请先用对应工具解密，本脚本不处理加密层

---

## 常见问题

**Q：导出的 MP4 没有声音？**
A：请确认使用的是最新版脚本。早期版本未剥离 ADX 块尾部的 24 字节零填充，会导致音频解码中断。可用 `ffprobe` 检查音频流时长，正常应与视频时长基本一致：

```bash
ffprobe -v error -show_entries stream=codec_type,duration -of default=noprint_wrappers=1 input.mp4
```

**Q：提示「未检测到 FFmpeg」？**
A：脚本会询问是否自动安装。选 `y` 由脚本调用系统包管理器安装；选 `n` 则按提示手动安装。若自动安装后仍提示找不到，通常是 `PATH` 尚未刷新，**重新打开终端**再运行即可。

**Q：视频时长与预期不符 / 播放速度异常？**
A：帧率探测依赖标准的 MPEG 序列头。若源文件使用了非常规封装，脚本会回退到 30 fps。此时可用 `-framerate` 手动指定，或先运行 `ffprobe` 查看实际帧率。

**Q：转换时终端出现 `Error during demuxing: Invalid data found`？**
A：这是 ADX 流结尾最后几个字节不完整导致的解码器提示，不影响已产出的音频数据。可对比音频与视频时长确认，通常相差不足 20 毫秒。

**Q：可以处理 `.bin` 或其它格式吗？**
A：不可以，脚本只接受 `.usm`。其它格式需要先转换成 USM 或使用其它工具。

---

## 项目结构

```
usm2mp4/
├── usm_to_mp4.py      # 主脚本
├── requirements.txt   # 依赖说明（无第三方 Python 依赖）
└── README.md
```

---

## 免责声明

本项目仅用于**格式转换与个人学习研究**，不包含任何解密、破解或绕过版权保护的功能。

请仅对你**合法拥有**或**已获授权**的媒体文件使用本工具。请勿将转换所得内容用于传播、再分发或任何商业用途。因使用本工具产生的一切后果由使用者自行承担。

---

## 许可

建议以 MIT License 发布，请在仓库根目录补充 `LICENSE` 文件。

---
---

# usm2mp4 (English)

[中文](#usm2mp4) | **English**

Convert **USM video containers** (CRI Sofdec) into standard **MP4** files with audio — in a single command.

Give it a `.usm`, get back a playable `.mp4`. Demuxing, frame-rate detection and A/V muxing are all handled automatically; no manual FFmpeg flags required.

---

## Features

- **One command**: `python usm_to_mp4.py input.usm` produces `input.mp4`
- **Lossless video**: the MPEG video stream is remuxed with `-c:v copy`, never re-encoded — pixel-identical to the source asset
- **Automatic frame rate detection**: reads `frame_rate_code` from the MPEG sequence header and correctly distinguishes 23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 fps
- **Fixes broken audio**: strips the 24-byte zero padding at the end of each ADX audio chunk, which is the root cause of "exported video has no sound"
- **Self-service dependency setup**: if FFmpeg is missing, the script asks `y/n` and can install it automatically via winget / brew / apt depending on your platform
- **Batch mode**: pass a directory and every `.usm` inside is converted
- **No temp-file litter**: intermediate `.m2v` / `.adx` files go to a temporary directory that is cleaned up automatically
- **Zero third-party Python dependencies**: standard library only, nothing to `pip install`

---

## Installation

### 1. Install Python

**Python 3.6+** is required.

- Windows: download from [python.org](https://www.python.org/downloads/) and **check "Add Python to PATH"** during setup
- macOS: `brew install python3` (or use the bundled system Python)
- Linux: `sudo apt install python3`

Verify:

```bash
python --version
# If python points to Python 2 on your system, use python3 instead
```

### 2. Install FFmpeg

A/V muxing relies entirely on FFmpeg, **which is a required external program**.

Windows (winget recommended):

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

macOS:

```bash
brew install ffmpeg
```

Linux:

```bash
sudo apt update && sudo apt install -y ffmpeg
```

Verify:

```bash
ffmpeg -version
```

> **You may skip this step.** Just run the script — if FFmpeg is not found it will prompt `是否现在自动配置 FFmpeg 环境？[y/N]` (install FFmpeg now?). Answer `y` and it invokes the right package manager for your platform; answer `n` and it prints manual instructions and exits.
>
> ⚠️ **Common mistake**: do not run `pip install ffmpeg` or `pip install ffmpeg-python`. Those PyPI packages are not the FFmpeg binary, and the `ffmpeg` command will still be missing afterwards.

### 3. Install Python dependencies

This project has **no** third-party Python dependencies, so this step merely validates your environment:

```bash
pip install -r requirements.txt
```

The file contains only comments and installs nothing — that is expected.

### 4. Get the code

```bash
git clone https://github.com/<your-username>/usm2mp4.git
cd usm2mp4
```

---

## Usage

### Single file

```bash
python usm_to_mp4.py input.usm
```

Writes `input.mp4` next to the source file.

### Custom output path

```bash
python usm_to_mp4.py input.usm output.mp4
```

### Batch a whole directory

```bash
python usm_to_mp4.py "D:\game_assets\movies"
```

Every `.usm` in that directory (non-recursive) is converted to an `.mp4` of the same name.

Quote paths containing spaces on Windows.

### Sample output

```
解封装 advinfo1.usm ...
检测到帧率: 60 fps, 音频: 有
正在合成 MP4 ...
完成: advinfo1.mp4
```

On a first run without FFmpeg installed, you will see:

```
未检测到 FFmpeg。
本工具的音视频合成依赖 FFmpeg，必须安装后才能继续。

是否现在自动配置 FFmpeg 环境？[y/N]: y

将执行以下命令：
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
安装过程可能需要管理员权限，请按提示操作 ...
```

---

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| 1st | Yes | Path to the input `.usm`, or a directory containing `.usm` files |
| 2nd | No | Output `.mp4` path; defaults to the input filename with `.mp4` |

Running without arguments prints usage and exits with code `1`.

---

## How it works

### Why this tool exists

USM (CRI Sofdec Universal Media) is a video container widely used by SEGA / CRI titles. It interleaves video and audio in small chunks inside one file, so ordinary players cannot open it. Converting simply means splitting those two streams back out and repackaging them into MP4.

### Pipeline

1. **Parse the container**
   A USM file is a sequence of signed chunks. Each chunk header is:

   | Offset | Size | Meaning |
   |--------|------|---------|
   | 0 | 4 | Chunk signature (`CRID` / `@SFV` / `@SFA` / `@SFD`, etc.) |
   | 4 | 4 | Total chunk size (big-endian) |
   | 8 | 24 | Media header (includes a 1-byte data offset) |

   The script walks chunks from offset 0, takes payloads from `@SFV` (video) and `@SFA` (audio), and skips metadata chunks such as `@UTF`.

2. **Extract video**
   `@SFV` payloads begin with the MPEG start code `00 00 01`; concatenating them in order yields a complete `.m2v` elementary stream.

3. **Extract audio**
   Concatenating `@SFA` payloads yields `.adx` (CRI ADX audio).
   **The critical fix**: each audio payload is a fixed 1824 bytes, but only the first 1800 bytes are real ADX data — the trailing 24 bytes are zero padding. Appending that padding breaks ADX's fixed 18-byte frame grid; the decoder flags invalid data and aborts after a few dozen milliseconds. The symptom is exactly **a video with no sound at all**. The script strips this padding before concatenating.

4. **Detect frame rate**
   It locates the sequence header `00 00 01 B3` in the `.m2v`, reads `frame_rate_code` from the low 4 bits of byte 4, and maps it to the real frame rate.

5. **Mux to MP4**
   MPEG elementary streams carry no timestamps, so `-fflags +genpts` makes FFmpeg regenerate them from the frame rate. Video is remuxed losslessly with `-c:v copy`, audio is encoded with `-c:a aac`, and `-shortest` aligns both stream durations.

### Scope

- Verified on 1080p60 and 1080p30 USM files with separate video and audio streams
- Video codec: MPEG-2; audio codec: ADX (48 kHz stereo)
- **Input must already be decrypted.** If the file is still encrypted (for example, repackaged as `.opt` inside a game), decrypt it first — this script does not touch the encryption layer

---

## FAQ

**Q: The exported MP4 has no audio.**
A: Make sure you are on the latest version. Earlier releases did not strip the 24-byte zero padding at the end of ADX chunks, which aborts audio decoding. Check stream durations with `ffprobe` — audio should closely match video:

```bash
ffprobe -v error -show_entries stream=codec_type,duration -of default=noprint_wrappers=1 input.mp4
```

**Q: It says FFmpeg was not found.**
A: The script asks whether to install it. Choose `y` to let it invoke your system package manager, or `n` to install manually as instructed. If it still cannot be found after an automatic install, your `PATH` has not refreshed — **open a new terminal** and rerun.

**Q: Duration is wrong / playback speed is off.**
A: Frame-rate detection relies on a standard MPEG sequence header. On unusual containers the script falls back to 30 fps. Specify `-framerate` manually, or inspect the real rate with `ffprobe`.

**Q: I see `Error during demuxing: Invalid data found` during conversion.**
A: This is a decoder warning caused by the last few incomplete bytes of the ADX stream. The produced audio is unaffected; compare audio and video durations — the difference is typically under 20 ms.

**Q: Can it handle `.bin` or other formats?**
A: No, only `.usm`. Other formats must be converted to USM first or handled with a different tool.

---

## Project layout

```
usm2mp4/
├── usm_to_mp4.py      # main script
└── README.md
```

---

## Disclaimer

This project is intended for **format conversion and personal study/research only**. It contains no decryption, cracking, or DRM-circumvention functionality.

Use it only on media you **lawfully own** or are **authorized to process**. Do not redistribute converted content or use it commercially. You are solely responsible for any consequences of using this tool.

---

## License

MIT License is recommended — add a `LICENSE` file to the repository root.
