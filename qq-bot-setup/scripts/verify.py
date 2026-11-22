#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连通性验证：DeepSeek Key / QQ access_token / WebSocket 网关。"""
import argparse
import json
import os
import sys
import urllib.request

try:
    import yaml
except ImportError:
    yaml = None


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        if yaml:
            return yaml.safe_load(f)
        # 极简回退：仅支持本技能生成的扁平结构，避免强依赖 PyYAML
        cfg = {}
        section = None
        for line in f:
            s = line.rstrip("\n")
            if not s or s.lstrip().startswith("#"):
                continue
            if not s.startswith(" "):
                key = s.split(":", 1)[0].strip()
                if s.rstrip().endswith(":"):
                    section = key
                    cfg[section] = {}
                continue
            if ":" in s and section:
                k, v = s.strip().split(":", 1)
                v = v.strip().strip('"').strip("'")
                cfg[section][k.strip()] = v
        return cfg


def post(url, payload, headers=None, timeout=20):
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser(description="验证机器人配置连通性")
    ap.add_argument("--config", required=True, help="config.yaml 路径")
    args = ap.parse_args()

    cfg = load_config(os.path.abspath(args.config))
    qq = cfg.get("qq", {})
    ds = cfg.get("deepseek", {})
    results = []

    # 1. DeepSeek
    try:
        status, body = post(
            str(ds.get("base_url", "https://api.deepseek.com")).rstrip("/") + "/v1/chat/completions",
            {"model": ds.get("model", "deepseek-chat"),
             "messages": [{"role": "user", "content": "ping，回复 pong 即可"}],
             "max_tokens": 16},
            {"Authorization": "Bearer " + str(ds.get("api_key", ""))},
        )
        ok = status == 200 and "choices" in body
        results.append(("DeepSeek Key", ok, f"HTTP {status}" + ("" if ok else " · " + body[:120])))
    except Exception as e:
        results.append(("DeepSeek Key", False, str(e)))

    # 2. QQ access_token
    qq_token = None
    try:
        status, body = post(
            "https://bots.qq.com/app/getAppAccessToken",
            {"appId": str(qq.get("app_id", "")), "clientSecret": qq.get("app_secret", "")},
        )
        data = json.loads(body)
        qq_token = data.get("access_token")
        ok = bool(qq_token)
        results.append(("QQ AppID/Secret", ok, "换取 access_token 成功" if ok else body[:120]))
    except Exception as e:
        results.append(("QQ AppID/Secret", False, str(e)))

    # 3. Gateway（需要 QQBot token 鉴权）
    try:
        headers = {"Authorization": f"QQBot {qq_token}"} if qq_token else {}
        status, body = get("https://api.sgroup.qq.com/gateway", headers=headers)
        data = json.loads(body)
        ok = bool(data.get("url"))
        results.append(("QQ WebSocket 网关", ok, "可获取网关地址" if ok else body[:120]))
    except Exception as e:
        results.append(("QQ WebSocket 网关", False, str(e)))

    print("=== 连通性验证 ===\n")
    all_ok = True
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        all_ok = all_ok and ok
    print("\n" + ("三项全绿 ✓ 可以启动机器人。" if all_ok
                  else "有项目失败，请按提示修复后重试；详见 references/troubleshooting.md"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
