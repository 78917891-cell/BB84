# -*- coding: utf-8 -*-
"""QQ 官方机器人 WebSocket 客户端（群聊 + 单聊 C2C）。

依据 QQ 机器人开放平台 API v2：
- 获取 access_token: POST https://bots.qq.com/app/getAppAccessToken
- 网关地址: GET https://api.sgroup.qq.com/gateway
- 鉴权: Authorization: QQBot <access_token>
- 发群消息: POST /v2/groups/{group_openid}/messages
- 发单聊消息: POST /v2/users/{user_openid}/messages
"""
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import websocket  # websocket-client

from voice import Voice

log = logging.getLogger("qqbot")

TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
API_BASE = "https://api.sgroup.qq.com"
GATEWAY_URL = API_BASE + "/gateway"

# Intent 位（QQ 官方定义）
INTENT_GUILD_MESSAGES = 1 << 30          # 频道消息（本项目不用）
INTENT_GROUP_AND_C2C = 1 << 25           # 群聊 + 单聊事件
INTENT_GROUP_AT = 1 << 26                # 部分文档里 @ 事件的位（备用）


class AccessToken:
    """自动获取与刷新 access_token。"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = str(app_id)
        self.app_secret = app_secret
        self._token = None
        self._expire_at = 0.0
        self._lock = threading.Lock()

    def get(self, force: bool = False) -> str:
        with self._lock:
            if not force and self._token and time.time() < self._expire_at - 120:
                return self._token
            log.info("获取 access_token ...")
            r = requests.post(
                TOKEN_URL,
                json={"appId": self.app_id, "clientSecret": self.app_secret},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError(f"获取 access_token 失败: {data}")
            self._token = token
            self._expire_at = time.time() + int(data.get("expires_in", 7200))
            log.info("access_token 获取成功，有效期 %ss", data.get("expires_in"))
            return self._token


class QQBot:
    def __init__(self, cfg: dict, brain, voice_cfg: dict = None):
        self.cfg = cfg
        self.brain = brain
        self.voice = Voice(voice_cfg or {})
        self.app_id = str(cfg["app_id"])
        self.token = AccessToken(self.app_id, cfg["app_secret"])
        self.trigger = cfg.get("group_trigger", "at")
        self.prefix = cfg.get("trigger_prefix", "糍粑 ")
        self.max_chunk = int(cfg.get("max_chunk_chars", 1000))
        self.debug = bool(cfg.get("debug", True))

        # intents 组合
        intents = 0
        if cfg.get("intents", {}).get("group_at_message", True) or cfg.get("intents", {}).get("group_all_message", False):
            intents |= INTENT_GROUP_AND_C2C
        if cfg.get("intents", {}).get("c2c_message", True):
            intents |= INTENT_GROUP_AND_C2C
        # 没配任何就用群+C2C
        if intents == 0:
            intents = INTENT_GROUP_AND_C2C
        self.intents = intents

        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="handler")
        self._seq = 0
        self._last_s = 0
        self._heartbeat_stop = threading.Event()
        self._running = True

    # ---------- HTTP 发送 ----------
    def _auth(self) -> dict:
        return {"Authorization": f"QQBot {self.token.get()}", "Content-Type": "application/json"}

    def send_group(self, group_openid: str, content: str, msg_id: str = None, seq: int = 1) -> bool:
        url = f"{API_BASE}/v2/groups/{group_openid}/messages"
        body = {"msg_type": 0, "content": content}
        if msg_id:
            body["msg_id"] = msg_id
            body["msg_seq"] = seq
        return self._post(url, body)

    def send_c2c(self, user_openid: str, content: str, msg_id: str = None, seq: int = 1) -> bool:
        url = f"{API_BASE}/v2/users/{user_openid}/messages"
        body = {"msg_type": 0, "content": content}
        if msg_id:
            body["msg_id"] = msg_id
            body["msg_seq"] = seq
        return self._post(url, body)

    def _post(self, url: str, body: dict) -> bool:
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, headers=self._auth(), timeout=20)
                if r.status_code == 200:
                    return True
                # token 过期则强制刷新重试
                if r.status_code in (401, 403):
                    log.warning("鉴权失败，刷新 token 重试: %s", r.text[:200])
                    self.token.get(force=True)
                    continue
                log.error("发送消息失败 [%s]: %s", r.status_code, r.text[:300])
                return False
            except Exception as e:
                log.error("发送消息异常: %s", e)
                if attempt == 0:
                    time.sleep(1)
        return False

    # ---------- 富媒体（语音） ----------
    def upload_media(self, kind: str, openid: str, data: bytes, file_type: int = 3):
        """上传富媒体，返回 file_info；失败返回 None。kind: 'group' | 'c2c'。"""
        ep = "groups" if kind == "group" else "users"
        url = f"{API_BASE}/v2/{ep}/{openid}/files"
        headers = {"Authorization": f"QQBot {self.token.get()}"}
        for attempt in range(2):
            try:
                r = requests.post(
                    url,
                    headers=headers,
                    data={"file_type": str(file_type), "srv_send_msg": "false"},
                    files={"file": ("voice.silk", data, "application/octet-stream")},
                    timeout=30,
                )
                if r.status_code == 200:
                    info = (r.json() or {}).get("file_info")
                    if info:
                        return info
                    log.warning("上传成功但无 file_info: %s", r.text[:200])
                    return None
                if r.status_code in (401, 403):
                    self.token.get(force=True)
                    continue
                log.error("上传语音失败 [%s]: %s", r.status_code, r.text[:300])
                return None
            except Exception as e:
                log.error("上传语音异常: %s", e)
                if attempt == 0:
                    time.sleep(1)
        return None

    def send_voice(self, kind: str, openid: str, file_info: str,
                   msg_id: str = None, seq: int = 1) -> bool:
        """发送语音消息（msg_type=7 富媒体）。"""
        ep = "groups" if kind == "group" else "users"
        url = f"{API_BASE}/v2/{ep}/{openid}/messages"
        body = {"msg_type": 7, "media": {"file_info": file_info}}
        if msg_id:
            body["msg_id"] = msg_id
            body["msg_seq"] = seq
        return self._post(url, body)

    def send_chunks(self, send_fn, text: str, msg_id: str = None, start_seq: int = 1) -> int:
        """按长度分段发送，避免超出 QQ 单条消息长度限制。

        start_seq 用于同一条被动回复里多次发送（如先发「我查一下」再发结果），
        保证 msg_seq 连续递增、不重复。返回最后使用的 seq。
        """
        chunks = self._split(text, self.max_chunk)
        last = start_seq - 1
        for i, chunk in enumerate(chunks, start_seq):
            send_fn(chunk, msg_id=msg_id, seq=i)
            last = i
        return last

    @staticmethod
    def _split(text: str, size: int):
        if len(text) <= size:
            return [text]
        out, cur = [], ""
        for para in text.split("\n"):
            if len(cur) + len(para) + 1 > size and cur:
                out.append(cur.rstrip())
                cur = ""
            # 超长单段再按字符切
            while len(para) > size:
                out.append(para[:size])
                para = para[size:]
            cur += para + "\n"
        if cur.strip():
            out.append(cur.rstrip())
        return out

    # ---------- 事件处理 ----------
    @staticmethod
    def _clean_mentions(text: str) -> str:
        """去掉消息里的 @ 标记 <@xxx> / <@all>，并合并多余空白。"""
        cleaned = re.sub(r"<@[^>]*>", "", text or "")
        return re.sub(r"\s+", " ", cleaned).strip()

    def _handle_event(self, t: str, d: dict):
        if t == "GROUP_AT_MESSAGE_CREATE":
            self._on_group(d, at_required=True)
        elif t == "GROUP_MESSAGE_CREATE":
            self._on_group(d, at_required=False)
        elif t == "C2C_MESSAGE_CREATE":
            self._on_c2c(d)
        else:
            if self.debug:
                log.debug("忽略事件: %s", t)

    def _on_group(self, d: dict, at_required: bool):
        # 过滤机器人自己发的消息
        author = d.get("author", {})
        if author.get("bot"):
            return
        raw = d.get("content", "")
        content = self._clean_mentions(raw)
        group_openid = d.get("group_openid")
        msg_id = d.get("id")
        if not group_openid or not content:
            return

        should_reply = False
        if self.trigger == "all":
            should_reply = True
        elif self.trigger == "prefix":
            should_reply = content.startswith(self.prefix)
            if should_reply:
                content = content[len(self.prefix):].strip()
        else:  # at
            should_reply = at_required  # @事件本身就是被@
        if not should_reply:
            return

        user_openid = author.get("member_openid") or author.get("id") or "unknown"
        session_key = f"group:{group_openid}:{user_openid}"
        self.pool.submit(self._reply_and_send, session_key, content, True,
                         lambda txt, mid, seq: self.send_group(group_openid, txt, mid, seq),
                         msg_id, ("group", group_openid))

    def _on_c2c(self, d: dict):
        author = d.get("author", {})
        if author.get("bot"):
            return
        content = self._clean_mentions(d.get("content", ""))
        user_openid = author.get("user_openid")
        msg_id = d.get("id")
        if not user_openid or not content:
            return
        session_key = f"c2c:{user_openid}"
        self.pool.submit(self._reply_and_send, session_key, content, False,
                         lambda txt, mid, seq: self.send_c2c(user_openid, txt, mid, seq),
                         msg_id, ("c2c", user_openid))

    def _reply_and_send(self, key, text, is_group, send_fn, msg_id, voice_ctx=None):
        # 支持简单指令
        if text in ("/清空", "清空记忆", "/reset"):
            self.brain.clear(key)
            self.send_chunks(send_fn, "好嘞，我把刚才的聊天记录清掉啦，重新开始～", msg_id)
            return
        if text in ("/帮助", "帮助", "/help"):
            hint = "我是糍粑～直接跟我聊天就行。\n/清空 = 重置对话记忆"
            if self.voice.enabled:
                hint += "\n（语音已开启，会用语音回你）"
            else:
                hint += "\n（群里 @我 或按配置前缀触发）"
            self.send_chunks(send_fn, hint, msg_id)
            return
        try:
            # 需要联网时先吱一声，避免用户以为没反应（搜索+生成可能要十几秒）
            next_seq = 1
            if self.brain.search.should_search(text, is_group=is_group):
                self.send_chunks(send_fn, "等我一下，我上网查查～", msg_id, start_seq=1)
                next_seq = 2
            answer = self.brain.reply(key, text, is_group=is_group)
            last_seq = self.send_chunks(send_fn, answer, msg_id, start_seq=next_seq)
            # 语音包：文字发完后追加一条语音（受被动回复次数限制）
            self._maybe_send_voice(answer, voice_ctx, msg_id, last_seq, is_group)
        except Exception as e:
            log.exception("回复失败: %s", e)
            self.send_chunks(send_fn, "呜…我刚刚卡了一下（网络或模型抽风），你再说一遍？", msg_id)

    def _maybe_send_voice(self, answer, voice_ctx, msg_id, last_seq, is_group):
        if not voice_ctx or not self.voice.should_speak(answer):
            return
        # 被动回复次数：群聊 5 次、单聊 4 次，语音要占一次
        limit = 5 if is_group else 4
        if last_seq + 1 > limit:
            if self.debug:
                log.debug("被动回复次数不足，跳过语音")
            return
        silk = self.voice.synth(answer)
        if not silk:
            return
        kind, openid = voice_ctx
        file_info = self.upload_media(kind, openid, silk)
        if not file_info:
            return
        ok = self.send_voice(kind, openid, file_info, msg_id, last_seq + 1)
        if self.debug:
            log.debug("语音发送%s", "成功" if ok else "失败")

    # ---------- WebSocket 主循环 ----------
    def _heartbeat(self, ws, interval_sec: float, stop_event: threading.Event):
        while not stop_event.wait(interval_sec):
            try:
                payload = {"op": 1, "d": self._last_s if self._last_s else None}
                ws.send(json.dumps(payload))
                if self.debug:
                    log.debug("发送心跳 op=1, s=%s", self._last_s)
            except Exception as e:
                log.warning("心跳发送失败: %s", e)
                break

    def run(self):
        while self._running:
            try:
                self._run_once()
            except Exception as e:
                log.exception("连接异常，5秒后重连: %s", e)
                time.sleep(5)

    def _run_once(self):
        # 获取网关
        r = requests.get(GATEWAY_URL, headers=self._auth(), timeout=20)
        r.raise_for_status()
        gw = r.json().get("url")
        if not gw:
            raise RuntimeError("网关地址为空")
        log.info("连接网关: %s", gw)

        ws = websocket.create_connection(gw, timeout=30)
        hb_stop = threading.Event()
        hb_thread = None
        # 每次连接重置心跳停止信号
        self._heartbeat_stop = hb_stop
        try:
            # 等 Hello
            hello = json.loads(ws.recv())
            if hello.get("op") != 10:
                raise RuntimeError(f"期望 Hello(op=10)，收到: {hello}")
            interval = int(hello["d"]["heartbeat_interval"]) / 1000.0
            log.info("收到 Hello，心跳周期 %.1fs", interval)

            # 鉴权 Identify
            identify = {
                "op": 2,
                "d": {
                    "token": f"QQBot {self.token.get()}",
                    "intents": self.intents,
                    "shard": [0, 1],
                    "properties": {
                        "$os": "windows",
                        "$browser": "qq-cichi-bot",
                        "$device": "qq-cichi-bot",
                    },
                },
            }
            ws.send(json.dumps(identify))
            log.info("已发送 Identify, intents=%s", self.intents)

            hb_thread = threading.Thread(target=self._heartbeat, args=(ws, interval, hb_stop), daemon=True)
            hb_thread.start()

            # 收消息主循环
            while self._running:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw:
                    log.warning("收到空帧，重连")
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                op = msg.get("op")
                if msg.get("s"):
                    self._last_s = msg["s"]
                if op == 0:  # Dispatch
                    t = msg.get("t")
                    d = msg.get("d", {})
                    if self.debug:
                        log.debug("事件 %s", t)
                    self._handle_event(t, d)
                elif op == 10:
                    pass
                elif op == 11:  # Heartbeat ACK
                    pass
                elif op == 9:  # Invalid Session
                    log.warning("Invalid Session，重新鉴权")
                    self.token.get(force=True)
                    break
                elif op == 7:  # Reconnect
                    log.warning("服务端要求重连")
                    break
        finally:
            hb_stop.set()
            try:
                ws.close()
            except Exception:
                pass
