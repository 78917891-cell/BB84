# -*- coding: utf-8 -*-
"""voice.py 回归测试：edge 真实往返 + http 后端四种返回形态 + 失败降级。"""
import base64
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice  # noqa: E402

MP3 = b""


def get_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


PORT = get_port()
BASE = "http://127.0.0.1:%d" % PORT


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _audio(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(MP3)))
        self.end_headers()
        self.wfile.write(MP3)

    def do_GET(self):
        if self.path == "/static.mp3":
            self._audio()
        else:
            self.send_error(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = {}
        p = self.path
        if p == "/b64":
            self._json({"data": {"audio": base64.b64encode(MP3).decode()}})
        elif p == "/hex":
            self._json({"data": {"audio": MP3.hex()}})
        elif p == "/url":
            self._json({"data": {"audio_url": BASE + "/static.mp3"}})
        elif p == "/bin":
            self._audio()
        elif p == "/empty":
            self._json({"data": {}})
        elif p == "/err500":
            self.send_error(500)
        elif p == "/echo":
            self._json({"data": {"audio": base64.b64encode(MP3).decode()}, "echo": payload})
        elif p == "/auth":
            if self.headers.get("Authorization") == "Bearer testkey":
                self._json({"data": {"audio": base64.b64encode(MP3).decode()}})
            else:
                self.send_error(401)
        else:
            self.send_error(404)


def is_silk(b):
    return bool(b) and (b.startswith(b"#!SILK") or b.startswith(b"\x02#!SILK"))


def mk(path, **kw):
    cfg = {
        "enabled": True,
        "backend": "http",
        "max_chars": 100,
        "http": {"url": BASE + path, "timeout": 15,
                 "body": {"text": "{text}", "voice_id": "v1"}},
    }
    cfg["http"].update(kw)
    return cfg


results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail and not ok else ""))


def main():
    global MP3
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # 先造一个真 mp3 当夹具
    import asyncio
    import edge_tts
    probe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe.mp3")
    asyncio.run(edge_tts.Communicate("测试音频", "zh-CN-XiaoyiNeural").save(probe))
    with open(probe, "rb") as f:
        MP3 = f.read()
    os.remove(probe)
    check("夹具 mp3 生成", len(MP3) > 2000, "%d 字节" % len(MP3))

    # 1. edge 后端真实往返
    v = voice.Voice({"enabled": True, "voice": "zh-CN-XiaoyiNeural"})
    check("edge 后端 available()", v.available())
    s = v.synth("你好呀，我是糍粑。")
    check("edge 合成出合法 silk", is_silk(s), "%d 字节" % (len(s) if s else 0))

    # 2. http + json_base64
    v = voice.Voice(mk("/b64"))
    check("http/base64 available()", v.available())
    s = v.synth("你好呀，我是糍粑。")
    check("http/base64 合成出合法 silk", is_silk(s), "%d 字节" % (len(s) if s else 0))

    # 3. http + json_hex（MiniMax 用十六进制）
    s = voice.Voice(mk("/hex", response_type="json_hex")).synth("你好呀")
    check("http/json_hex 合成出合法 silk", is_silk(s), "%d 字节" % (len(s) if s else 0))

    # 4. http + json_url（百炼返回音频地址）
    s = voice.Voice(mk("/url", response_type="json_url")).synth("你好呀")
    check("http/json_url 合成出合法 silk", is_silk(s), "%d 字节" % (len(s) if s else 0))

    # 5. http + binary
    s = voice.Voice(mk("/bin", response_type="binary")).synth("你好呀")
    check("http/binary 合成出合法 silk", is_silk(s), "%d 字节" % (len(s) if s else 0))

    # 6. {text} 占位符注入 + 自定义字段
    v = voice.Voice(mk("/echo", body={"text": "{text}", "voice_setting": {"voice_id": "{text}x"}}))
    s = v.synth("注入测试")
    check("http 占位符注入后仍能出 silk", is_silk(s))

    # 7. 自定义鉴权头
    s = voice.Voice(mk("/auth", headers={"Authorization": "Bearer testkey"})).synth("你好呀")
    check("http 自定义鉴权头生效", is_silk(s))

    # 8. 失败降级
    check("http 500 返回 None", voice.Voice(mk("/err500")).synth("你好呀") is None)
    check("http 响应缺音频字段返回 None", voice.Voice(mk("/empty")).synth("你好呀") is None)
    check("http 404 返回 None", voice.Voice(mk("/nope")).synth("你好呀") is None)

    # 9. 未配 url 时 available() 为 False
    v = voice.Voice({"enabled": True, "backend": "http", "http": {}})
    check("http 未配 url 时 available()=False", v.available() is False)
    check("http 未配 url 时 synth()=None", v.synth("你好呀") is None)

    # 10. 文本清洗与发声判断
    v = voice.Voice({"enabled": True})
    cleaned = v.clean_text("看这个 ```js\n1\n```")
    check("代码块被替换为占位", "（代码略过）" in cleaned and "```" not in cleaned, repr(cleaned))
    check("纯代码不发声", v.should_speak("```py\nprint(1)\n```") is False)
    check("超长文本不发声", v.should_speak("字" * 200) is False)
    check("正常短句发声", v.should_speak("今天天气不错") is True)

    # 11. 关闭后彻底静音（合成入口就该拦住，不只依赖调用方）
    off = voice.Voice({"enabled": False})
    check("关闭时 should_speak=False", off.should_speak("今天天气不错") is False)
    check("关闭时 synth 返回 None", off.synth("今天天气不错") is None)

    srv.shutdown()

    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("\n%d/%d PASS" % (ok, total))
    for n, p, d in results:
        if not p:
            print("  失败：%s %s" % (n, d))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
