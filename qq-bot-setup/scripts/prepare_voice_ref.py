#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""prepare_voice_ref.py —— 从视频/音频生成声音克隆参考音频。

做三件事：
  1. 用 silencedetect 找出「最长的一段没有说话间隙」的区间（避开片头/片尾音乐）；
  2. 在区间内居中裁出指定长度（默认最多 20 秒）；
  3. 降混单声道 → 重采样 → 去低频轰鸣 → 两遍 loudnorm 精确归一，输出 16kHz 单声道 16bit WAV。

为什么是两遍 loudnorm：
  单遍是动态模式，实测偏差可达 4dB；两遍先测量再线性增益，能稳定命中 ±0.3dB。
  另外降混必须放在滤镜链内部（aformat），否则 -ac 1 在 loudnorm 之后执行，
  测的是立体声响度、降混后整体又掉 2~3dB，归一等于白做。

用法：
  python prepare_voice_ref.py 视频.mp4
  python prepare_voice_ref.py 视频.mp4 --out assets/voice_ref/ref_01.wav
  python prepare_voice_ref.py 视频.mp4 --start 6.8 --duration 8.2 --out ref_02.wav
  python prepare_voice_ref.py 音频.wav --scan-only      # 只看区间，不落盘

不依赖第三方库，ffmpeg 复用 voice.py 的查找顺序。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

TARGET_LUFS = "-16"
TARGET_TP = "-1.5"
TARGET_LRA = "11"


def _utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_ffmpeg():
    """与 voice.py 完全一致的查找顺序。"""
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    p = shutil.which("ffmpeg")
    if p:
        return p
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".agent-reach", "tools", "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(home, ".agent-reach", "tools", "ffmpeg", "bin", "ffmpeg"),
        os.path.join(home, ".local", "bin", "ffmpeg.exe"),
        os.path.join(home, ".local", "bin", "ffmpeg"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def run(ff, args, timeout=300):
    cmd = [ff, "-hide_banner", "-nostdin"] + args
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def probe_duration(ff, path):
    r = run(ff, ["-i", path])
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def probe_audio_line(ff, path):
    r = run(ff, ["-i", path])
    for line in (r.stderr or "").splitlines():
        if "Audio:" in line:
            return line.strip()
    return ""


def detect_spans(ff, path, noise_db, min_sil, total):
    """返回非静音区间列表 [(start, end), ...]。"""
    r = run(ff, ["-i", path,
                 "-af", "silencedetect=noise=%sdB:d=%s" % (noise_db, min_sil),
                 "-f", "null", "-"])
    text = r.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", text)]

    spans, cursor = [], 0.0
    for i, s_start in enumerate(starts):
        s_start = max(0.0, s_start)
        if s_start > cursor:
            spans.append((cursor, s_start))
        cursor = ends[i] if i < len(ends) else total
    if cursor < total:
        spans.append((cursor, total))
    return [(a, b) for a, b in spans if b - a > 0.3], len(starts)


def pick_window(spans, total, max_sec, min_sec):
    """挑最长区间并居中裁剪。"""
    if not spans:
        spans = [(0.0, total)]
    start, end = max(spans, key=lambda x: x[1] - x[0])
    span = end - start
    want = min(max_sec, span)
    if want < min_sec:
        want = span
    pad = 0.15 if span - want > 0.6 else 0.0
    s = max(start, start + pad + (span - want - 2 * pad) / 2.0)
    want = min(want, end - s)
    return round(s, 3), round(want, 3), (round(start, 3), round(end, 3))


def build_pre(sr, highpass):
    """降混 / 重采样 / 高通必须在 loudnorm 之前，且都写在滤镜链里。"""
    return "aformat=channel_layouts=mono,aresample=%d,highpass=f=%d" % (sr, highpass)


def measure_loudness(ff, src, start, dur, pre, lufs=TARGET_LUFS, tp=TARGET_TP):
    """第一遍：测出输入真实响度，供第二遍线性增益使用。"""
    af = "%s,loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (pre, lufs, tp, TARGET_LRA)
    r = run(ff, ["-ss", "%.3f" % start, "-t", "%.3f" % dur,
                 "-i", src, "-vn", "-af", af, "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if d.get("input_i") in (None, "-inf", "inf", "nan"):
        return None
    return d


def measure_integrated(ff, path):
    """量成品的实际综合响度与峰值，用于如实报告。"""
    r = run(ff, ["-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    m = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", r.stderr or "")
    lufs = m.group(1) if m else "?"
    r2 = run(ff, ["-i", path, "-af", "volumedetect", "-f", "null", "-"])
    m2 = re.search(r"max_volume:\s*(-?[\d.]+)", r2.stderr or "")
    return lufs, (m2.group(1) if m2 else "?")


def cut(ff, src, start, dur, out, sr, highpass, lufs, tp):
    pre = build_pre(sr, highpass)
    measured = measure_loudness(ff, src, start, dur, pre, lufs, tp)

    if measured:
        af = ("%s,loudnorm=I=%s:TP=%s:LRA=%s"
              ":measured_I=%s:measured_TP=%s:measured_LRA=%s"
              ":measured_thresh=%s:offset=%s:linear=true" % (
                  pre, lufs, tp, TARGET_LRA,
                  measured.get("input_i"), measured.get("input_tp"),
                  measured.get("input_lra"), measured.get("input_thresh"),
                  measured.get("target_offset", "0")))
        mode = "two-pass-linear"
    else:
        af = "%s,loudnorm=I=%s:TP=%s:LRA=%s" % (pre, lufs, tp, TARGET_LRA)
        mode = "single-pass-fallback"

    r = run(ff, ["-y",
                 "-ss", "%.3f" % start, "-t", "%.3f" % dur,
                 "-i", src,
                 "-vn", "-af", af,
                 "-ac", "1", "-ar", str(sr),
                 "-c:a", "pcm_s16le",
                 out])
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("ffmpeg 裁剪失败：\n" + (r.stderr or "")[-800:])
    return os.path.getsize(out), mode, measured


def main():
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="从视频/音频生成声音克隆参考音频")
    ap.add_argument("input", help="源文件（视频或音频）")
    ap.add_argument("--out", default="", help="输出 wav 路径")
    ap.add_argument("--start", type=float, default=None, help="手动起点（秒），指定后不做区间扫描")
    ap.add_argument("--duration", type=float, default=None, help="手动时长（秒）")
    ap.add_argument("--max-sec", type=float, default=20.0, help="自动取段最大时长（默认 20）")
    ap.add_argument("--min-sec", type=float, default=6.0, help="自动取段最小时长（默认 6）")
    ap.add_argument("--noise-db", type=float, default=-32.0, help="静音阈值（默认 -32）")
    ap.add_argument("--min-sil", type=float, default=0.35, help="静音最短时长（默认 0.35 秒）")
    ap.add_argument("--sample-rate", type=int, default=16000, help="输出采样率（默认 16000）")
    ap.add_argument("--highpass", type=int, default=70, help="高通截止 Hz（默认 70）")
    ap.add_argument("--lufs", default=TARGET_LUFS, help="响度目标（默认 -16 LUFS）")
    ap.add_argument("--tp", default=TARGET_TP, help="真峰值上限（默认 -1.5 dBTP）")
    ap.add_argument("--scan-only", action="store_true", help="只打印区间，不生成文件")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("[FAIL] 找不到文件：%s" % args.input)
        return 2
    ff = find_ffmpeg()
    if not ff:
        print("[FAIL] 没找到 ffmpeg。安装方式任选其一：")
        print("       pip install imageio-ffmpeg")
        print("       或安装 Agent Reach（自带 ffmpeg）：python scripts/install_reach.py")
        return 2

    total = probe_duration(ff, args.input)
    if not total:
        print("[FAIL] 读不出时长，确认文件是有效音视频：%s" % args.input)
        return 2

    spans, sil_count = detect_spans(ff, args.input, args.noise_db, args.min_sil, total)

    if args.start is not None:
        start = max(0.0, args.start)
        dur = args.duration if args.duration else min(args.max_sec, total - start)
        dur = min(dur, total - start)
        picked = None
    else:
        start, dur, picked = pick_window(spans, total, args.max_sec, args.min_sec)

    info = {
        "input": os.path.abspath(args.input),
        "source_duration_sec": round(total, 2),
        "audio_stream": probe_audio_line(ff, args.input),
        "silence_count": sil_count,
        "speech_spans": [[round(a, 2), round(b, 2)] for a, b in spans[:12]],
        "chosen_start_sec": round(start, 2),
        "chosen_duration_sec": round(dur, 2),
        "longest_span": list(picked) if picked else None,
    }

    if args.scan_only:
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print("源时长 %.2fs，静音段 %d 处" % (total, sil_count))
            print("非静音区间（最多显示 12 段）：")
            for a, b in spans[:12]:
                print("  %7.2fs ~ %7.2fs  (%.2fs)" % (a, b, b - a))
            print("建议取段：%.2fs 起，时长 %.2fs" % (start, dur))
        return 0

    out = args.out or ("ref_%d.wav" % int(total))
    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        size, mode, measured = cut(ff, args.input, start, dur, out, args.sample_rate,
                                   args.highpass, args.lufs, args.tp)
    except Exception as e:
        print("[FAIL] %s" % e)
        return 1

    real_i, real_tp = measure_integrated(ff, out)
    info.update({
        "output": os.path.abspath(out),
        "output_bytes": size,
        "spec": "%d Hz / mono / pcm_s16le" % args.sample_rate,
        "normalization": mode,
        "measured_integrated_lufs": real_i,
        "measured_peak_db": real_tp,
        "chain": "%s,loudnorm=I=%s:TP=%s:LRA=%s" % (
            build_pre(args.sample_rate, args.highpass), args.lufs, args.tp, TARGET_LRA),
    })
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print("[OK] %s" % out)
        print("     时长 %.2fs，体积 %.1f KB，%d Hz 单声道 16bit" % (dur, size / 1024.0, args.sample_rate))
        print("     归一方式 %s，实测 %.1f LUFS / 峰值 %s dB（目标 %s LUFS / %s dBTP）"
              % (mode, float(real_i) if real_i != "?" else -99, real_tp, args.lufs, args.tp))
        if picked:
            print("     取自最长连续区间 %.2fs~%.2fs（静音段 %d 处）" % (picked[0], picked[1], sil_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
