# -*- coding: utf-8 -*-
"""轻量长期记忆：随对话积累、按用户隔离、零外部依赖（只用标准库 sqlite3）。

设计取舍
--------
1. **不做全量对话存档**。只存「他自己说过的稳定事实」和「明确让他记住的事」，
   否则记忆很快变成垃圾场，注入后反而干扰回答。
2. **抽取两条路**：规则（免费、确定性、覆盖常见自述句式）+ LLM（可选，每 N 轮一次，
   失败自动降级到规则，不影响回复）。
3. **检索不引第三方分词**。中文用字符 bigram 重叠打分 + 重要度 + 新近度，
   够用且没有额外依赖，方便随包分发给别人。

分区（scope）
------------
`u:<openid>`   这个人自己的记忆，跨群、跨单聊共享——她记得你，在哪都记得。
`g:<groupid>`  某个群共有的记忆（群里大家聊出来的公共信息）。
"""

import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scope       TEXT    NOT NULL,
    text        TEXT    NOT NULL,
    norm        TEXT    NOT NULL,
    kind        TEXT    NOT NULL DEFAULT 'fact',
    weight      REAL    NOT NULL DEFAULT 1.0,
    created_at  INTEGER NOT NULL,
    last_used   INTEGER NOT NULL DEFAULT 0,
    hits        INTEGER NOT NULL DEFAULT 0,
    UNIQUE(scope, norm)
);
CREATE INDEX IF NOT EXISTS idx_mem_scope ON memories(scope, last_used DESC);
"""

# 一句话里出现这些线索，才当"关于他的稳定信息"存下来
INFO_PATTERN = re.compile(
    r"记住[：:，,]?"
    r"|我(?:的名字)?叫"
    r"|我的名字"
    r"|我在.{0,12}(?:上班|工作|读书|上学|实习|念书)"
    r"|我(?:住在|家在|老家在)"
    r"|我今年"
    r"|我\s*\d{1,2}\s*岁"
    r"|我的生日"
    r"|我生日"
    r"|我(?:喜欢|爱|超爱|最爱|迷上)"
    r"|我(?:讨厌|不喜欢|受不了)"
    r"|我(?:养了|家有)"
)

PUNCT = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】~～…—\-]+")

MAX_LEN = 80          # 单条记忆最大字数
MIN_LEN = 4           # 太短的不存（多半是语气词）

LLM_PROMPT = (
    "从下面这句话里，只提取关于说话人本人、值得长期记住的稳定事实"
    "（姓名、城市、职业、年龄、生日、喜好、厌恶、宠物、家人、长期计划）。"
    "忽略一次性的情绪和临时状态。没有就返回空数组。\n"
    "只输出 JSON 数组，不要解释，格式：[{\"text\": \"简述\", \"kind\": \"fact|pref\"}]\n"
    "句子："
)


def _norm(text: str) -> str:
    """归一化用于去重：去标点、去空白、转小写。"""
    return PUNCT.sub("", (text or "").lower())


def _bigrams(text: str) -> set:
    s = _norm(text)
    if len(s) <= 1:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def extract_rules(text: str):
    """规则抽取：返回 [(句子, kind, weight)]。零成本、确定性。"""
    out = []
    # 保留标点，才能判断这一句是不是疑问句（"我叫什么名字？"不能当事实存）
    parts = re.split(r"([。！？!?\n]+)", text or "")
    for i in range(0, len(parts), 2):
        sent = parts[i].strip()
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        if "？" in delim or "?" in delim:
            continue
        if not (MIN_LEN <= len(sent) <= MAX_LEN):
            continue
        if re.search(r"(?:吗|呢|什么|啥|怎么|为什么|多少|几个)$", sent):
            continue
        if not INFO_PATTERN.search(sent):
            continue
        if sent.startswith("记住"):
            body = re.sub(r"^记住[：:，,]?\s*", "", sent).strip()
            if len(body) >= 2:
                out.append((body[:MAX_LEN], "core", 3.0))
            continue
        kind = "pref" if re.search(r"我(?:喜欢|爱|超爱|最爱|讨厌|不喜欢|受不了)", sent) else "fact"
        out.append((sent, kind, 2.0 if kind == "pref" else 1.6))
    return out


class Memory:
    def __init__(self, cfg: dict = None, llm_call=None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        raw_path = str(cfg.get("db_path") or "memory.db")
        # 相对路径按模块所在目录解析，保证随包搬到别的机器也能写对地方
        if not os.path.isabs(raw_path):
            raw_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), raw_path)
        self.path = raw_path
        self.max_items = int(cfg.get("max_items_per_user", 300))
        self.inject_limit = int(cfg.get("inject_limit", 8))
        self.llm_extract = bool(cfg.get("llm_extract", True))
        self.extract_every = max(1, int(cfg.get("extract_every", 6)))
        self.llm_call = llm_call
        self._turns = {}
        self._lock = threading.Lock()
        self._ready = False
        if self.enabled:
            self._init_db()

    # ---------- 存储 ----------
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=8)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        try:
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)   # 目录不存在时别静默失败
            with closing(self._conn()) as c, c:
                c.executescript(SCHEMA)
            self._ready = True
        except Exception:
            self.enabled = False
            self._ready = False

    def remember(self, scope: str, text: str, kind: str = "fact", weight: float = 1.0) -> bool:
        """存一条。同 scope 下同文本不重复存，只累加命中次数。"""
        if not (self.enabled and self._ready) or not scope:
            return False
        text = (text or "").strip()[:MAX_LEN]
        norm = _norm(text)
        if len(norm) < 2:
            return False
        now = int(time.time())
        try:
            with closing(self._conn()) as c, c:
                cur = c.execute(
                    "INSERT OR IGNORE INTO memories(scope,text,norm,kind,weight,created_at,last_used)"
                    " VALUES(?,?,?,?,?,?,0)",
                    (scope, text, norm, kind, float(weight), now))
                inserted = cur.rowcount > 0
                if not inserted:
                    c.execute("UPDATE memories SET hits=hits+1, last_used=?,"
                              " weight=max(weight, ?) WHERE scope=? AND norm=?",
                              (now, float(weight), scope, norm))
            if inserted:
                self._prune(scope)
            return inserted
        except Exception:
            return False

    def _prune(self, scope: str):
        """超过上限时，按 重要度低 + 最久没用 + 最旧 淘汰。"""
        try:
            with closing(self._conn()) as c, c:
                n = c.execute("SELECT COUNT(*) FROM memories WHERE scope=?", (scope,)).fetchone()[0]
                if n <= self.max_items:
                    return
                c.execute(
                    "DELETE FROM memories WHERE id IN ("
                    " SELECT id FROM memories WHERE scope=?"
                    " ORDER BY weight ASC, last_used ASC, created_at ASC LIMIT ?)",
                    (scope, n - self.max_items))
        except Exception:
            pass

    # ---------- 检索 ----------
    def recall(self, scopes, query: str, limit: int = None):
        """按 相关度 / 重要度 / 新近度 打分取前 N 条。"""
        if not (self.enabled and self._ready):
            return []
        scopes = [s for s in (scopes or []) if s]
        if not scopes:
            return []
        limit = int(limit or self.inject_limit)
        marks = ",".join("?" * len(scopes))
        try:
            with closing(self._conn()) as c, c:
                rows = c.execute(
                    f"SELECT text,kind,weight,created_at,last_used FROM memories"
                    f" WHERE scope IN ({marks}) ORDER BY last_used DESC, id DESC LIMIT 500",
                    scopes).fetchall()
        except Exception:
            return []
        if not rows:
            return []

        q = _bigrams(query)
        now = time.time()
        max_w = max((r["weight"] for r in rows), default=1.0) or 1.0
        scored = []
        for r in rows:
            m = _bigrams(r["text"])
            overlap = len(q & m) / ((len(q) * len(m)) ** 0.5) if (q and m) else 0.0
            w = r["weight"] / max_w
            ts = r["last_used"] or r["created_at"]
            days = max(0.0, (now - ts) / 86400.0)
            fresh = 0.5 ** (days / 30.0)          # 半衰期 30 天
            score = 0.55 * overlap + 0.25 * w + 0.20 * fresh
            if r["kind"] == "core":
                score += 0.35                      # 明确让他记住的，永远优先
            if overlap <= 0 and r["kind"] != "core" and fresh < 0.45:
                continue                           # 既不相关、又不新，别占位
            scored.append((score, r["text"]))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:limit]]

    def build_context(self, scopes, query: str) -> str:
        """拼成一段可注入 system 的文本；没有记忆时返回空串。"""
        items = self.recall(scopes, query)
        if not items:
            return ""
        lines = ["【关于他的记忆（他自己提过或让你记住的，可能不全）】",
                 "- 自然带到对话里就好，别逐条复述，也别硬套；和他现在说的话冲突时，以他现在的说法为准。"]
        lines += [f"- {t}" for t in items]
        return "\n".join(lines)

    # ---------- 学习（对话后调用） ----------
    def learn(self, scopes, user_text: str, llm_call=None):
        """从用户这句话里抽记忆。规则先跑，LLM 每 N 轮补一次（失败静默）。"""
        if not (self.enabled and self._ready):
            return 0
        scopes = [s for s in (scopes or []) if s]
        if not scopes:
            return 0
        count = 0
        for text, kind, weight in extract_rules(user_text):
            for sc in scopes:
                if self.remember(sc, text, kind, weight):
                    count += 1

        if not self.llm_extract or not (llm_call or self.llm_call):
            return count

        primary = scopes[0]
        with self._lock:
            self._turns[primary] = self._turns.get(primary, 0) + 1
            n = self._turns[primary]
        if n % self.extract_every != 0:
            return count

        fn = llm_call or self.llm_call
        try:
            raw = fn(LLM_PROMPT + user_text[:300]) or ""
            start, end = raw.find("["), raw.rfind("]")
            if start < 0 or end <= start:
                return count
            items = json.loads(raw[start:end + 1])
            for it in items if isinstance(items, list) else []:
                if not isinstance(it, dict):
                    continue
                t = str(it.get("text") or "").strip()[:MAX_LEN]
                k = str(it.get("kind") or "fact")
                if len(_norm(t)) < 2:
                    continue
                if k not in ("fact", "pref", "core"):
                    k = "fact"
                for sc in scopes:
                    if self.remember(sc, t, k, 1.4):
                        count += 1
        except Exception:
            pass
        return count

    # ---------- 管理 ----------
    def forget(self, scope: str, text: str = None) -> int:
        """删记忆：给 text 删匹配的那条，不给就清空整个 scope。"""
        if not (self.enabled and self._ready):
            return 0
        try:
            with closing(self._conn()) as c, c:
                if text is None:
                    cur = c.execute("DELETE FROM memories WHERE scope=?", (scope,))
                else:
                    cur = c.execute("DELETE FROM memories WHERE scope=? AND norm=?",
                                    (scope, _norm(text)))
                return cur.rowcount
        except Exception:
            return 0

    def stats(self, scope: str = None) -> dict:
        if not (self.enabled and self._ready):
            return {"enabled": False}
        try:
            with closing(self._conn()) as c, c:
                if scope:
                    n = c.execute("SELECT COUNT(*) FROM memories WHERE scope=?", (scope,)).fetchone()[0]
                    return {"enabled": True, "scope": scope, "count": n}
                rows = c.execute("SELECT scope, COUNT(*) n FROM memories GROUP BY scope").fetchall()
                return {"enabled": True, "total": sum(r["n"] for r in rows),
                        "scopes": {r["scope"]: r["n"] for r in rows}}
        except Exception:
            return {"enabled": False}
