# -*- coding: utf-8 -*-
"""DeepSeek 对话 + 每用户会话管理。"""
import threading
import time
from collections import defaultdict, deque

import requests

from memory import Memory
from persona import build_system_prompt
from websearch import WebSearch


class ChatSession:
    """单个用户/群的会话：系统提示词 + 有限轮历史。"""

    def __init__(self, key: str, is_group: bool, history_rounds: int):
        self.key = key
        self.system = build_system_prompt(is_group=is_group)
        self.history = deque(maxlen=history_rounds * 2)
        self.last_call = 0.0


class Brain:
    def __init__(self, ds_cfg: dict, bot_cfg: dict, search_cfg: dict = None,
                 memory_cfg: dict = None):
        self.cfg = ds_cfg
        self.history_rounds = int(bot_cfg.get("history_rounds", 10))
        self.rate_limit = float(bot_cfg.get("rate_limit_seconds", 1.5))
        self.sessions = {}
        self.lock = threading.Lock()
        self.search = WebSearch(search_cfg or {})
        self.memory = Memory(memory_cfg or {}, llm_call=self._extract_llm)

    @staticmethod
    def _scopes(key: str):
        """会话 key → 记忆分区。单聊只有个人；群聊是「个人 + 本群」两份。"""
        parts = (key or "").split(":")
        if parts[0] == "c2c" and len(parts) >= 2:
            return [f"u:{parts[1]}"]
        if parts[0] == "group" and len(parts) >= 3:
            return [f"u:{parts[2]}", f"g:{parts[1]}"]
        return [f"k:{key}"] if key else []

    def _extract_llm(self, prompt: str) -> str:
        """供记忆模块做 LLM 抽取用的小请求（低温度、短输出）。"""
        url = self.cfg["base_url"].rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 300,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""

    def _session(self, key: str, is_group: bool) -> ChatSession:
        with self.lock:
            if key not in self.sessions:
                self.sessions[key] = ChatSession(key, is_group, self.history_rounds)
            return self.sessions[key]

    def _check_rate(self, session: ChatSession):
        now = time.time()
        gap = now - session.last_call
        if gap < self.rate_limit:
            time.sleep(self.rate_limit - gap)
        session.last_call = time.time()

    def clear(self, key: str):
        """重置某会话（用于 /清空 指令）。"""
        with self.lock:
            if key in self.sessions:
                self.sessions[key].history.clear()

    def reply(self, key: str, user_text: str, is_group: bool = False) -> str:
        """根据用户输入返回糍粑的回复（非流式，QQ 一次性发）。"""
        session = self._session(key, is_group)
        self._check_rate(session)

        messages = [{"role": "system", "content": session.system}]
        # 长期记忆：检索出跟这句话相关的旧事，作为 system 段注入（不进历史）
        scopes = self._scopes(key)
        mem = self.memory.build_context(scopes, user_text)
        if mem:
            messages.append({"role": "system", "content": mem})
        # 需要实时信息时，把联网检索结果作为额外 system 段注入（不进历史，每次现查）
        ref = self.search.build_context(user_text, is_group=is_group)
        if ref:
            messages.append({"role": "system", "content": ref})
        messages.extend(session.history)
        messages.append({"role": "user", "content": user_text})

        url = self.cfg["base_url"].rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.cfg["model"],
            "messages": messages,
            "temperature": float(self.cfg.get("temperature", 0.7)),
            "max_tokens": int(self.cfg.get("max_tokens", 2048)),
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers,
                             timeout=int(self.cfg.get("timeout", 60)))
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        if not answer:
            answer = "啊…我刚刚脑子瓦特了一下，你再说一遍？（_err_empty）"

        # 写入历史（用户一句 + 助手一句）
        session.history.append({"role": "user", "content": user_text})
        session.history.append({"role": "assistant", "content": answer})
        # 从这句话里积累长期记忆（规则必跑，LLM 每 N 轮补一次，失败不影响回复）
        try:
            self.memory.learn(scopes, user_text)
        except Exception:
            pass
        return answer
