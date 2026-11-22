#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境体检：Python 版本 + 关键域名连通性（只读取，不修改任何东西）。"""
import sys
import socket
import urllib.request

HOSTS = [
    ("DeepSeek API", "api.deepseek.com", 443),
    ("QQ Token", "bots.qq.com", 443),
    ("QQ Gateway", "api.sgroup.qq.com", 443),
    ("QQ 开放平台", "q.qq.com", 443),
]


def check_python():
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 9)
    print(f"[Python] {v.major}.{v.minor}.{v.micro}  {'OK' if ok else '过低，需 3.9+'}")
    return ok


def check_net(host, port, timeout=4):
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        print(f"[网络] {host}:{port}  可达")
        return True
    except Exception as e:
        print(f"[网络] {host}:{port}  不可达 ({e})")
        return False


def main():
    print("=== 环境体检 ===\n")
    py_ok = check_python()
    print()
    net = {name: check_net(host, port) for name, host, port in HOSTS}
    print("\n=== 结论 ===")
    if not py_ok:
        print("- 请先安装 Python 3.10+ 并勾选 Add to PATH：https://www.python.org/downloads/")
    bad = [n for n, ok in net.items() if not ok]
    if bad:
        print("- 以下域名不可达：" + "、".join(bad))
        print("  网络受限可配置代理，或稍后重试；装依赖时脚本会尝试国内镜像。")
    if py_ok and not bad:
        print("环境就绪 ✓ 可以继续第 1 步（拿 DeepSeek Key）。")
    sys.exit(0 if py_ok else 1)


if __name__ == "__main__":
    main()
