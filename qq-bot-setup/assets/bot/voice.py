# -*- coding: utf-8 -*-
"""语音包：把文字回复合成 QQ 可发送的 silk 语音。

链路：文字 → TTS（mp3/wav）→ ffmpeg 转 PCM(24k 单声道) → pysilk 编码 silk。

TTS 后端（voice.backend）：
  edge —— Edge TTS，免费、无需 Key（默认）
  http —— 任意云端克隆/TTS 接口，配置驱动，支持四种返回形态：
          json_base64 / json_hex / json_url / binary

依赖：pysilk-mod（silk 编解码）+ ffmpeg（imageio-ffmpeg 或系统装）。
      edge 后端额外需要 edge-tts。
任一步缺失都返回 None，调用方降级为纯文字，绝不影响正常回复。
"""
import asyncio
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request

log = logging.getLogger("voice")

# 可选音色（Edge TTS 的 zh 系列）
VOICES = {
    "xiaoyi": "zh-CN-XiaoyiNeural",      # 活泼女声，贴合糍粑性格（默认）
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",  # 温柔女声
    "xiaobei": "zh-CN-liaoning-XiaobeiNeural",  # 东北话
    "xiaoni": "zh-CN-shaanxi-XiaoniNeural",    # 陕西话
    "hiuMaan": "zh-HK-HiuMaanNeural",    # 粤语女声
}

DEFAULT_VOICE = "zh-CN-XiaoyiNeural"

# 去掉不适合朗读的内容：代码块、Markdown 符号、链接、表情
_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.M)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_MD_MARKS = re.compile(r"[*_>#~|]+")
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF\uFE0F\u200D]+"
)


def _dig(obj, path):
    """按 "data.audio" 这种点路径取值，取不到返回 None。"""
    cur = obj
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
        if cur is None:
            return None
    return cur


def _render(obj, text):
    """把配置里的 {text} 占位符替换成正文，递归处理 dict/list。"""
    if isinstance(obj, dict):
        return {k: _render(v, text) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render(v, text) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{text}", text)
    return obj


class Voice:
    def __init__(self, cfg: dict = None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.backend = str(cfg.get("backend") or "edge").strip().lower()
        self.voice = str(cfg.get("voice") or DEFAULT_VOICE)
        self.rate = str(cfg.get("rate") or "+0%")
        self.max_chars = int(cfg.get("max_chars", 100))
        self.send_text = bool(cfg.get("send_text", True))
        self.http = cfg.get("http") or {}
        self._deps_checked = False
        self._ok = False
        self._ffmpeg = None

    # ---------- 依赖检测 ----------
    def available(self) -> bool:
        if self._deps_checked:
            return self._ok
        self._deps_checked = True
        if self.backend == "http":
            if not str(self.http.get("url") or "").strip():
                log.warning("voice.backend=http 但没配 voice.http.url，语音不可用")
                return self._ok
        else:
            try:
                import edge_tts  # noqa: F401
            except Exception:
                log.warning("缺少 edge-tts，语音不可用（pip install edge-tts）")
                return self._ok
        try:
            import pysilk  # noqa: F401
        except Exception:
            log.warning("缺少 pysilk-mod，语音不可用（pip install pysilk-mod）")
            return self._ok
        self._ffmpeg = self._find_ffmpeg()
        if not self._ffmpeg:
            log.warning("缺少 ffmpeg，语音不可用（pip install imageio-ffmpeg）")
            return self._ok
        self._ok = True
        return True

    @staticmethod
    def _find_ffmpeg():
        # 1) imageio-ffmpeg 自带的二进制（若装了）
        try:
            import imageio_ffmpeg
            p = imageio_ffmpeg.get_ffmpeg_exe()
            if p and os.path.exists(p):
                return p
        except Exception:
            pass
        # 2) 系统 PATH
        p = shutil.which("ffmpeg")
        if p:
            return p
        # 3) Agent Reach 安装时自带的 ffmpeg（常见，可直接复用）
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

    # ---------- 文本清洗 ----------
    @staticmethod
    def clean_text(text: str) -> str:
        t = _CODE_BLOCK.sub("（代码略过）", text or "")
        t = _INLINE_CODE.sub(r"\1", t)
        t = _MD_LINK.sub(r"\1", t)
        t = _URL.sub("", t)
        t = _MD_MARKS.sub("", t)
        t = _EMOJI.sub("", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def should_speak(self, text: str) -> bool:
        if not self.enabled:
            return False
        if not self.available():
            return False
        clean = self.clean_text(text)
        if not clean or len(clean) > self.max_chars:
            return False
        # 纯代码/纯符号的回复不值得读出来
        if clean.strip() in ("（代码略过）", ""):
            return False
        if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", clean):
            return False
        return True

    # ---------- 合成 ----------
    async def _tts_to_mp3(self, text: str, mp3_path: str):
        if self.backend == "http":
            self._http_to_mp3(text, mp3_path)
            return
        import edge_tts
        comm = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await comm.save(mp3_path)

    def _http_to_mp3(self, text: str, mp3_path: str):
        """调用云端 TTS/克隆接口，把音频落到 mp3_path。

        配置（voice.http）：
          url          接口地址（必填）
          method       默认 POST
          headers      附加请求头，如 Authorization
          body         请求体，字符串里可用 {text} 占位
          response_type  json_base64(默认) / json_hex / json_url / binary
          audio_key    json_* 时音频字段的点路径，默认 data.audio
          audio_url_key json_url 时音频地址的点路径，默认 data.audio_url
          timeout      秒，默认 30
        """
        cfg = self.http
        url = str(cfg.get("url") or "").strip()
        if not url:
            raise RuntimeError("voice.http.url 未配置")
        timeout = float(cfg.get("timeout", 30))
        method = str(cfg.get("method") or "POST").upper()
        headers = {"Content-Type": "application/json"}
        headers.update({str(k): str(v) for k, v in (cfg.get("headers") or {}).items()})

        data = None
        if method != "GET":
            body = _render(cfg.get("body") or {"text": "{text}"}, text)
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()

        rtype = str(cfg.get("response_type") or "json_base64").strip().lower()
        if rtype == "binary":
            audio = raw
        else:
            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                raise RuntimeError("接口返回的不是 JSON，若为纯音频请设 response_type: binary")
            if rtype == "json_url":
                link = _dig(obj, cfg.get("audio_url_key") or "data.audio_url")
                if not link:
                    raise RuntimeError("响应里没找到音频地址（audio_url_key）")
                with urllib.request.urlopen(str(link), timeout=timeout) as r2:
                    audio = r2.read()
            elif rtype == "json_hex":
                s = _dig(obj, cfg.get("audio_key") or "data.audio")
                if not s:
                    raise RuntimeError("响应里没找到音频字段（audio_key）")
                audio = bytes.fromhex(str(s))
            else:
                s = _dig(obj, cfg.get("audio_key") or "data.audio")
                if not s:
                    raise RuntimeError("响应里没找到音频字段（audio_key）")
                audio = base64.b64decode(str(s))

        if not audio:
            raise RuntimeError("TTS 返回空音频")
        with open(mp3_path, "wb") as f:
            f.write(audio)

    def synth(self, text: str):
        """返回 silk 字节；失败或语音已关闭返回 None。"""
        if not self.enabled:
            return None
        if not self.available():
            return None
        clean = self.clean_text(text)
        if not clean:
            return None
        tmpdir = tempfile.mkdtemp(prefix="cichi_voice_")
        mp3 = os.path.join(tmpdir, "a.mp3")
        pcm = os.path.join(tmpdir, "a.pcm")
        try:
            asyncio.run(self._tts_to_mp3(clean, mp3))
            subprocess.run(
                [self._ffmpeg, "-y", "-loglevel", "error", "-i", mp3,
                 "-f", "s16le", "-ac", "1", "-ar", "24000", pcm],
                check=True, timeout=60,
            )
            with open(pcm, "rb") as f:
                raw = f.read()
            import pysilk
            silk = pysilk.encode(raw, sample_rate=24000)
            # 腾讯 silk 标准头为 \x02#!SILK_V3（部分实现无前缀），两种都接受
            if not silk or not (silk.startswith(b"#!SILK") or silk.startswith(b"\x02#!SILK")):
                log.warning("silk 编码结果异常：%r", silk[:12] if silk else silk)
                return None
            return silk
        except Exception as e:
            log.info("语音合成失败: %s", e)
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
