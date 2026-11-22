# -*- coding: utf-8 -*-
"""联网检索：给机器人接上实时信息能力。

两条通道：
- 天气：wttr.in（免费、无需 Key），问天气/气温/下雨时走这条，最快最准。
- 搜索：复用本机已装的 Agent Reach CLI（agent-reach web search），零额外 Key。

都用 try/except 包住：任何一路失败都返回空，绝不影响正常聊天。
"""
import json
import logging
import os
import shutil
import subprocess
import urllib.parse
import urllib.request

log = logging.getLogger("websearch")

# 触发联网的关键词：出现这些词才去查，避免每句话都搜（慢且费额度）
DEFAULT_KEYWORDS = [
    "今天", "现在", "最新", "新闻", "天气", "气温", "温度", "下雨", "降雨",
    "股价", "行情", "汇率", "油价", "比分", "赛程", "实时", "刚刚", "最近",
    "今年", "开幕", "发布会", "多少钱", "票价", "航班", "高铁", "限行",
    "查一下", "搜一下", "帮我查", "搜搜",
]

WEATHER_WORDS = ("天气", "气温", "温度", "下雨", "降雨", "冷不冷", "热不热")


class WebSearch:
    def __init__(self, cfg: dict = None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.in_group = bool(cfg.get("in_group", True))
        self.timeout = int(cfg.get("timeout", 20))
        self.max_results = int(cfg.get("max_results", 3))
        self.keywords = list(cfg.get("trigger_keywords") or DEFAULT_KEYWORDS)
        self.weather_enabled = bool(cfg.get("weather_enabled", True))
        self.weather_city = str(cfg.get("weather_city") or "深圳")
        self._exe = None
        self._exe_checked = False

    # ---------- Agent Reach 可执行文件定位 ----------
    def _find_exe(self):
        if self._exe_checked:
            return self._exe
        self._exe_checked = True
        p = shutil.which("agent-reach")
        if not p:
            local = os.path.join(os.path.expanduser("~"), ".local", "bin")
            for cand in ("agent-reach", "agent-reach.exe"):
                fp = os.path.join(local, cand)
                if os.path.exists(fp):
                    p = fp
                    break
        self._exe = p
        if not p:
            log.warning("未找到 agent-reach，联网搜索将不可用（可运行 install_reach.py 安装）")
        return p

    def should_search(self, text: str, is_group: bool = False) -> bool:
        if not self.enabled:
            return False
        if is_group and not self.in_group:
            return False
        t = text or ""
        return any(k in t for k in self.keywords)

    # ---------- 天气 ----------
    def weather(self, city: str = None) -> str:
        if not self.weather_enabled:
            return ""
        city = city or self.weather_city
        try:
            url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=3&lang=zh"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8", "replace").strip()
        except Exception as e:
            log.debug("天气查询失败: %s", e)
            return ""

    # ---------- 搜索 ----------
    def search(self, query: str) -> str:
        exe = self._find_exe()
        if not exe:
            return ""
        try:
            r = subprocess.run(
                [exe, "web", "search", query, "--limit", str(self.max_results)],
                capture_output=True, text=True, timeout=self.timeout,
            )
            data = json.loads((r.stdout or "").strip() or "{}")
            if not data.get("ok"):
                log.info("搜索未成功: %s", (data.get("error") or {}) or r.stderr[:120])
                return ""
            lines = []
            for it in (data.get("items") or [])[: self.max_results]:
                title = (it.get("title") or "").strip()
                text = " ".join((it.get("text") or "").split())
                if title or text:
                    lines.append(f"- {title}：{text[:300]}")
            return "\n".join(lines)
        except subprocess.TimeoutExpired:
            log.info("搜索超时（%ss）", self.timeout)
            return ""
        except Exception as e:
            log.info("搜索失败: %s", e)
            return ""

    # ---------- 组合成可注入的上下文 ----------
    def build_context(self, user_text: str, is_group: bool = False) -> str:
        if not self.should_search(user_text, is_group):
            return ""
        blocks = []
        if any(w in user_text for w in WEATHER_WORDS):
            w = self.weather()
            if w:
                blocks.append("【天气·实时】" + w)
        s = self.search(user_text[:100])
        if s:
            blocks.append("【联网搜索·实时】\n" + s)
        if not blocks:
            return ""
        return (
            "以下是刚刚联网查到的实时资料，只在和用户问题相关时采用；"
            "资料没覆盖到的实时信息不要编造，可以坦白说不太确定：\n\n"
            + "\n\n".join(blocks)
        )
