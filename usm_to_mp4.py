import struct, sys, os, tempfile, subprocess, shutil

FPS_MAP = {
    1: "23.976", 2: "24", 3: "25",
    4: "29.97", 5: "30", 6: "50",
    7: "59.94", 8: "60"
}

def detect_fps(m2v_path):
    with open(m2v_path, 'rb') as f:
        data = f.read(65536)
    idx = data.find(b'\x00\x00\x01\xb3')
    if idx < 0 or idx + 8 > len(data):
        return "30"
    h = data[idx + 4:idx + 8]
    frc = h[3] & 0x0F
    return FPS_MAP.get(frc, "30")

def demux(path, tmpdir):
    base = os.path.splitext(os.path.basename(path))[0]
    vpath = os.path.join(tmpdir, base + ".m2v")
    apath = os.path.join(tmpdir, base + ".adx")

    f = open(path, 'rb')
    fsize = os.path.getsize(path)
    v = open(vpath, 'wb')
    a = open(apath, 'wb')

    off = 0
    while off + 32 <= fsize:
        f.seek(off)
        hdr = f.read(32)
        sig = hdr[0:4]
        size = struct.unpack('>I', hdr[4:8])[0]
        hdr_off = hdr[9]
        if size == 0:
            break
        payload_off = off + 8 + hdr_off
        payload_len = size - hdr_off
        if payload_len < 0:
            break
        f.seek(payload_off)
        payload = f.read(payload_len)

        if sig == b'@SFV' and payload[:3] == b'\x00\x00\x01':
            v.write(payload)
        elif sig == b'@SFA' and payload[:4] not in (b'@UTF',) and payload[:1] != b'#':
            if payload[:2] != b'\x80\x00' and payload_len >= 24 and payload[-24:] == bytes(24):
                payload = payload[:-24]
            a.write(payload)

        off += 8 + size

    f.close(); v.close(); a.close()
    has_audio = os.path.getsize(apath) > 36
    return vpath, apath, has_audio

def find_ffmpeg():
    for name in ('ffmpeg.exe', 'ffmpeg'):
        exe = shutil.which(name)
        if exe:
            return exe
    local = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(local):
        for root, dirs, files in os.walk(local):
            if 'ffmpeg.exe' in files:
                return os.path.join(root, 'ffmpeg.exe')
    return None


MANUAL_HELP = """请手动安装 FFmpeg（以下任选其一），安装后重新打开终端再运行本脚本：

  Windows : winget install --id Gyan.FFmpeg -e
  macOS   : brew install ffmpeg
  Linux   : sudo apt install -y ffmpeg

注意：不要执行 pip install ffmpeg —— PyPI 上的同名包不是 FFmpeg 本体。"""


def build_install_cmd():
    if sys.platform == 'win32':
        if not shutil.which('winget'):
            return None, "未找到 winget（应用安装程序），无法自动安装。"
        return ['winget', 'install', '--id', 'Gyan.FFmpeg', '-e',
                '--accept-source-agreements', '--accept-package-agreements'], None

    if sys.platform == 'darwin':
        if not shutil.which('brew'):
            return None, "未找到 Homebrew，无法自动安装。"
        return ['brew', 'install', 'ffmpeg'], None

    for name, cmd in (
        ('apt-get', ['apt-get', 'install', '-y', 'ffmpeg']),
        ('dnf', ['dnf', 'install', '-y', 'ffmpeg']),
        ('yum', ['yum', 'install', '-y', 'ffmpeg']),
        ('pacman', ['pacman', '-S', '--noconfirm', 'ffmpeg']),
        ('apk', ['apk', 'add', 'ffmpeg']),
    ):
        if shutil.which(name):
            if name in ('apt-get', 'dnf', 'yum') and shutil.which('sudo') \
                    and hasattr(os, 'geteuid') and os.geteuid() != 0:
                cmd = ['sudo'] + cmd
            return cmd, None

    return None, "未找到受支持的包管理器（apt-get / dnf / yum / pacman / apk），无法自动安装。"


def install_ffmpeg():
    cmd, err = build_install_cmd()
    if cmd is None:
        print(err)
        print(MANUAL_HELP)
        return False

    print("将执行以下命令：")
    print("  " + " ".join(cmd))
    print("安装过程可能需要管理员权限，请按提示操作 ...\n")
    try:
        subprocess.run(cmd, check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"\n安装失败：{e}")
        print(MANUAL_HELP)
        return False
    return True


_FFMPEG_CACHE = None

def ensure_ffmpeg():
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE:
        return _FFMPEG_CACHE

    exe = find_ffmpeg()
    if exe:
        _FFMPEG_CACHE = exe
        return exe

    print("未检测到 FFmpeg。")
    print("本工具的音视频合成依赖 FFmpeg，必须安装后才能继续。\n")

    # 非交互环境（如管道、CI）无法询问，直接给出指引
    if not sys.stdin.isatty():
        print("当前环境不支持交互输入，已跳过自动安装。")
        print(MANUAL_HELP)
        sys.exit(1)

    try:
        ans = input("是否现在自动配置 FFmpeg 环境？[y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        ans = ''

    if ans not in ('y', 'yes'):
        print("已取消。\n")
        print(MANUAL_HELP)
        sys.exit(1)

    print()
    if not install_ffmpeg():
        sys.exit(1)

    exe = find_ffmpeg()
    if exe:
        _FFMPEG_CACHE = exe
        print(f"\nFFmpeg 已就绪: {exe}\n")
        return exe

    print("\n安装命令已执行完毕，但仍未找到 ffmpeg。")
    print("通常是因为 PATH 尚未刷新，请重新打开终端后再运行本脚本。")
    print(MANUAL_HELP)
    sys.exit(1)


def mux(ffmpeg, vpath, apath, has_audio, outpath, fps):
    cmd = [
        ffmpeg, '-y',
        '-fflags', '+genpts',
        '-framerate', fps,
        '-i', vpath,
    ]
    if has_audio:
        cmd += ['-i', apath, '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-c:a', 'aac', '-r', fps, '-shortest']
    else:
        cmd += ['-c:v', 'copy', '-r', fps]
    cmd += [outpath]

    print("正在合成 MP4 ...")
    subprocess.run(cmd, check=True)
    print(f"完成: {outpath}")

def process(path, outpath=None):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if outpath is None:
        outpath = os.path.splitext(path)[0] + ".mp4"

    ffmpeg = ensure_ffmpeg()

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"解封装 {os.path.basename(path)} ...")
        vpath, apath, has_audio = demux(path, tmpdir)
        fps = detect_fps(vpath)
        print(f"检测到帧率: {fps} fps, 音频: {'有' if has_audio else '无'}")
        mux(ffmpeg, vpath, apath, has_audio, outpath, fps)

def main():
    if len(sys.argv) < 2:
        print("用法: python usm_to_mp4.py <输入.usm> [输出.mp4]")
        sys.exit(1)
    inpath = sys.argv[1]
    outpath = sys.argv[2] if len(sys.argv) > 2 else None

    if os.path.isdir(inpath):
        for fn in os.listdir(inpath):
            if fn.lower().endswith('.usm'):
                p = os.path.join(inpath, fn)
                process(p)
    else:
        process(inpath, outpath)

if __name__ == '__main__':
    main()
