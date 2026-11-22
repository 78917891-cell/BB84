#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动机器人：前台调试，或 --daemon 后台常驻（跨平台）。"""
import argparse
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def venv_python(target):
    if os.name == "nt":
        return os.path.join(target, ".venv", "Scripts", "python.exe")
    return os.path.join(target, ".venv", "bin", "python")


def main():
    ap = argparse.ArgumentParser(description="启动糍粑 QQ 机器人")
    ap.add_argument("--target", required=True, help="部署目录")
    ap.add_argument("--daemon", action="store_true", help="后台常驻运行")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    py = venv_python(target)
    if not os.path.exists(py):
        print(f"找不到虚拟环境：{py}\n请先运行 bootstrap.py。")
        sys.exit(1)
    main_py = os.path.join(target, "main.py")
    log_path = os.path.join(target, "logs", "start.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    if args.daemon:
        if os.name == "nt":
            # Windows：CREATE_NO_WINDOW + DETACHED_PROCESS 后台运行
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            with open(log_path, "a", encoding="utf-8") as lf:
                p = subprocess.Popen([py, main_py], cwd=target, stdout=lf, stderr=subprocess.STDOUT,
                                     creationflags=flags)
            print(f"机器人已后台启动，PID={p.pid}，日志：{log_path}")
            print("停止：在任务管理器结束该 PID，或用目录内「4.停止后台.vbs」。")
        else:
            with open(log_path, "a", encoding="utf-8") as lf:
                p = subprocess.Popen([py, main_py], cwd=target, stdout=lf, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            print(f"机器人已后台启动，PID={p.pid}，日志：{log_path}")
            print(f"停止：kill {p.pid}")
    else:
        print("前台启动（Ctrl+C 停止）…")
        try:
            subprocess.run([py, main_py], cwd=target, check=True)
        except KeyboardInterrupt:
            print("\n已停止。")


if __name__ == "__main__":
    main()
