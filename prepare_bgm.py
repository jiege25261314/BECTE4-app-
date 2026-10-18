# -*- coding: utf-8 -*-
"""把你自己找的背景音乐处理成适合 App 的大小（裁剪 + 淡入淡出 + 压成 mp3）

    python prepare_bgm.py "C:\\Users\\你\\音乐\\lofi.mp3"
    python prepare_bgm.py "某首歌.mp4" --seconds 120 --kbps 96
    python prepare_bgm.py "长音频.mp3" --start 300          # 从第 5 分钟开始截

默认：取前 90 秒，单声道，64 kbps，开头 2 秒淡入、结尾 3 秒淡出 → 约 0.7 MB。
输出到 audio/bgm.mp3（覆盖同名文件），刷新 App 就生效。

为什么不直接放 1 小时的整段：1 小时 mp3 大约 30~60 MB，而整个 App 才 3.5 MB。
背景音乐本来就是循环播放的，剪 1~3 分钟足够，还能让手机秒开、不费流量。

需要 ffmpeg。没装的话脚本会提示怎么装；如果输入是 wav，会退化成用 Python 标准库处理。
"""

import math
import os
import shutil
import struct
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")


def human(n):
    return "%.1f MB" % (n / 1048576) if n > 1048576 else "%.0f KB" % (n / 1024)


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    for cand in ("C:/ffmpeg/bin/ffmpeg.exe", "C:/Program Files/ffmpeg/bin/ffmpeg.exe"):
        if os.path.exists(cand):
            return cand
    # 项目里放个便携版也能自动找到（_tools/ffmpeg/...）
    import glob
    for p in glob.glob(os.path.join(HERE, "_tools", "**", "ffmpeg*.exe"), recursive=True):
        return p
    return None


def install_help():
    print("没有找到 ffmpeg，所以没法把音频压成 mp3。三种办法：\n")
    print("  1) 用 winget 装（Win10/11 自带，最省事）：")
    print("       winget install --id Gyan.FFmpeg -e")
    print("     装完**重开一个命令行窗口**，再运行本脚本。\n")
    print("  2) 手动装：去 https://www.gyan.dev/ffmpeg/builds/ 下 ffmpeg-release-essentials.zip，")
    print("     解压后把里面的 bin 目录加到系统 PATH，重开命令行。\n")
    print("  3) 不装工具：用在线剪辑站（搜「在线音频剪辑」），剪出 1~3 分钟、导出 mp3，")
    print("     然后直接改名为 bgm.mp3 放进 audio/ 文件夹即可。\n")
    print("  ※ 如果你的文件是 .wav，可以加 --wav 让我用 Python 标准库直接剪（不压 mp3，文件会大一些）。")


def trim_wav(src, out, start, seconds, fade_in=2.0, fade_out=3.0):
    """纯标准库处理 wav：截取 + 淡入淡出 + 降成单声道 22050Hz"""
    try:
        w = wave.open(src, "rb")
    except Exception as e:
        print("这个文件不是标准 wav（%s）。如果是 mp3，请先装 ffmpeg。" % e)
        return False
    nch, sw, sr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    if sw != 2:
        print("只支持 16bit wav（当前 %d bit）" % (sw * 8))
        w.close()
        return False
    total = nframes / float(sr)
    start = max(0.0, min(start, max(0.0, total - 1)))
    seconds = min(seconds, max(0.1, total - start))
    w.setpos(int(start * sr))
    raw = w.readframes(int(seconds * sr))
    w.close()

    vals = struct.unpack("<%dh" % (len(raw) // 2), raw)
    # 多声道 -> 单声道
    if nch > 1:
        mono = [sum(vals[i:i + nch]) / nch for i in range(0, len(vals) - nch + 1, nch)]
    else:
        mono = list(vals)

    # 降采样到 22050（线性插值）
    target_sr = 22050
    if sr != target_sr:
        ratio = sr / float(target_sr)
        outn = int(len(mono) / ratio)
        res = []
        for i in range(outn):
            pos = i * ratio
            i0 = int(pos)
            frac = pos - i0
            a = mono[i0] if i0 < len(mono) else 0
            b = mono[i0 + 1] if i0 + 1 < len(mono) else a
            res.append(a + (b - a) * frac)
        mono = res
        sr = target_sr

    n = len(mono)
    fi = max(1, int(fade_in * sr))
    fo = max(1, int(fade_out * sr))
    for i in range(n):
        g = 1.0
        if i < fi:
            g = i / fi
        elif i > n - fo:
            g = max(0.0, (n - i) / fo)
        mono[i] *= g

    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(v)))) for v in mono))
    return True


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    src = args[0]
    start, seconds, kbps, full, use_wav = 0.0, 90.0, 64, False, False
    out = os.path.join(AUDIO, "bgm.mp3")
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--start":
            i += 1; start = float(args[i])
        elif a == "--seconds":
            i += 1; seconds = float(args[i])
        elif a == "--kbps":
            i += 1; kbps = int(args[i])
        elif a == "--full":
            full = True
        elif a == "--wav":
            use_wav = True
        elif a == "--out":
            i += 1; out = args[i]
        i += 1

    if not os.path.exists(src):
        print("找不到文件：%s" % src)
        return
    os.makedirs(AUDIO, exist_ok=True)
    print("输入：%s（%s）" % (src, human(os.path.getsize(src))))

    ff = find_ffmpeg()
    if ff and not use_wav:
        dur = seconds if not full else None
        fade_out_st = max(0, (dur or 0) - 3)
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-i", src]
        if dur:
            cmd += ["-t", str(dur)]
        cmd += ["-vn", "-ac", "1", "-ar", "44100", "-b:a", "%dk" % kbps, "-codec:a", "libmp3lame",
                "-af", "afade=t=in:st=0:d=2" + (",afade=t=out:st=%.1f:d=3" % fade_out_st if dur else "")]
        cmd.append(out)
        print("用 ffmpeg 处理中…")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print("ffmpeg 失败（返回码 %d）。检查输入文件是不是音频/视频。" % r.returncode)
            return
    else:
        if not use_wav:
            install_help()
            return
        out = os.path.join(AUDIO, "bgm.wav")
        print("用 Python 标准库处理 wav（不压 mp3）…")
        if not trim_wav(src, out, start, seconds):
            return

    print("\n输出：%s（%s）" % (out, human(os.path.getsize(out))))
    print("刷新 App → 设置 → 声音 → 音乐：开，就能听到。")
    print("提示：如果 audio/ 里同时存在 bgm.wav 和 bgm.mp3，会优先用 wav，记得删掉不用的那个。")


if __name__ == "__main__":
    main()
