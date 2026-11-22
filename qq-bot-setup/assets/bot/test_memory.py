# -*- coding: utf-8 -*-
"""memory.py 回归测试：抽取 / 去重 / 分区隔离 / 检索 / 淘汰 / 持久化 / LLM 兜底。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory as M  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail and not ok else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="memtest_")
    db = os.path.join(tmp, "m.db")
    try:
        # 1. 建库
        m = M.Memory({"enabled": True, "db_path": db, "llm_extract": False})
        check("建库并可用", m.enabled and m._ready and os.path.exists(db))

        # 2. 规则抽取
        rules = M.extract_rules("我叫小明，我在深圳上班。")
        check("抽取：自我介绍", any(k == "fact" for _, k, _ in rules), str(rules))
        check("抽取：职业", any("深圳" in t for t, _, _ in rules), str(rules))
        r2 = M.extract_rules("记住：我周三下午有课")
        check("抽取：显式指令→core", r2 and r2[0][1] == "core" and r2[0][2] >= 3.0, str(r2))
        r3 = M.extract_rules("我喜欢吃火锅")
        check("抽取：喜好→pref", r3 and r3[0][1] == "pref", str(r3))
        check("抽取：闲聊不入库", M.extract_rules("今天好累啊") == [])
        check("抽取：疑问句不误存", M.extract_rules("我叫什么名字？") == [])

        # 3. 写入与去重
        ua = "u:AAA"
        check("写入成功", m.remember(ua, "我叫小明", "fact", 1.6))
        check("重复写入不新增", m.remember(ua, "我叫小明", "fact", 1.6) is False)
        s = m.stats(ua)
        check("去重后只有 1 条", s["count"] == 1, str(s))

        # 4. 分区隔离
        m.remember("u:BBB", "我叫小红", "fact", 1.6)
        a_items = m.recall([ua], "名字", limit=20)
        check("A 看不到 B 的记忆", all("小红" not in t for t in a_items), str(a_items))
        check("B 有自己的一条", m.stats("u:BBB")["count"] == 1)

        # 5. 检索命中
        m.remember(ua, "我喜欢吃火锅", "pref", 2.0)
        hit = m.recall([ua], "火锅好吃吗", limit=5)
        check("相关检索命中火锅", any("火锅" in t for t in hit), str(hit))

        # 6. core 必带
        m.remember(ua, "我周三下午有课", "core", 3.0)
        got = m.recall([ua], "今天天气怎么样", limit=5)
        check("core 记忆优先注入", any("周三" in t for t in got), str(got))

        # 7. 注入上限
        m2 = M.Memory({"enabled": True, "db_path": os.path.join(tmp, "m2.db"),
                       "llm_extract": False, "inject_limit": 2})
        for i in range(6):
            m2.remember("u:C", f"我喜欢第{i}种口味", "pref", 2.0)
        check("inject_limit 生效", len(m2.recall(["u:C"], "口味")) <= 2, str(m2.recall(["u:C"], "口味")))

        # 8. 上限淘汰
        m3 = M.Memory({"enabled": True, "db_path": os.path.join(tmp, "m3.db"),
                       "llm_extract": False, "max_items_per_user": 2})
        for i in range(4):
            m3.remember("u:D", f"我叫测试{i}", "fact", 1.6)
        check("超上限自动淘汰", m3.stats("u:D")["count"] == 2, str(m3.stats("u:D")))

        # 9. 持久化
        m4 = M.Memory({"enabled": True, "db_path": db, "llm_extract": False})
        check("重开仍在（持久化）", m4.stats(ua)["count"] == s["count"] + 2, str(m4.stats(ua)))

        # 10. build_context
        ctx = m4.build_context([ua], "火锅")
        check("build_context 带表头", ctx.startswith("【关于他的记忆"), ctx[:40])
        check("build_context 含条目", "- " in ctx)

        # 11. LLM 抽取（mock，不真调 API）
        calls = {"n": 0}

        def fake_llm(prompt):
            calls["n"] += 1
            return '```json\n[{"text":"他养了一只边牧叫豆豆","kind":"fact"}]\n```'

        m5 = M.Memory({"enabled": True, "db_path": os.path.join(tmp, "m5.db"),
                       "llm_extract": True, "extract_every": 2}, llm_call=fake_llm)
        m5.learn(["u:E"], "今天带狗去公园了")
        check("第 1 轮不触发 LLM", calls["n"] == 0, str(calls))
        m5.learn(["u:E"], "它跑得可快了")
        check("第 2 轮触发 LLM", calls["n"] == 1, str(calls))
        check("LLM 抽到的记忆入库",
              any("边牧" in t for t in m5.recall(["u:E"], "狗", limit=10)),
              str(m5.recall(["u:E"], "狗", limit=10)))

        # 12. LLM 失败降级
        def bad_llm(prompt):
            raise RuntimeError("网络挂了")

        m6 = M.Memory({"enabled": True, "db_path": os.path.join(tmp, "m6.db"),
                       "llm_extract": True, "extract_every": 1}, llm_call=bad_llm)
        n = m6.learn(["u:F"], "我叫小刚，喜欢打篮球")
        check("LLM 失败仍靠规则入库", n >= 1 and m6.stats("u:F")["count"] >= 1, f"n={n}")

        # 13. 关闭后不写不读
        m7 = M.Memory({"enabled": False, "db_path": os.path.join(tmp, "m7.db")})
        check("关闭时 remember 返回 False", m7.remember("u:G", "我叫小美") is False)
        check("关闭时 recall 为空", m7.recall(["u:G"], "名字") == [])
        check("关闭时 build_context 为空", m7.build_context(["u:G"], "名字") == "")

        # 14. forget
        m.remember("u:H", "我叫小强", "fact", 1.6)
        check("删除单条", m.forget("u:H", "我叫小强") == 1)
        check("清空分区", m.stats("u:H")["count"] == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"\n{ok}/{total} PASS")
    for n, p, d in results:
        if not p:
            print("  失败：" + n + " " + d)
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
