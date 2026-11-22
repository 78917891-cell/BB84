#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装/接入 Agent Reach，让 AI 助手具备联网检索能力（可选组件）。

官方安装流程（docs/install.md）：
  1. 装 uv（无则装）
  2. uv tool install https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip
  3. agent-reach setup    # 开启默认渠道并安装 AI 技能

本脚本在其上补两件事：做前置检测与友好报错；确保技能落到指定 AI 的 skills 目录。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

RELEASE_ZIP = "https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip"
BUNDLED_SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "assets", "reach")


def find_exe(name):
    """在 PATH 与 ~/.local/bin 里找可执行文件（兼容 Windows .exe）。"""
    p = shutil.which(name)
    if p:
        return p
    local = os.path.join(os.path.expanduser("~"), ".local", "bin")
    for cand in (name, name + ".exe"):
        fp = os.path.join(local, cand)
        if os.path.exists(fp):
            return fp
    return None


def run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=False, **kw)


def reach_version(exe):
    """读取 agent-reach version 的 JSON；旧版返回纯文本。"""
    try:
        r = subprocess.run([exe, "version"], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        try:
            data = json.loads(out)
            if data.get("ok"):
                return data.get("result", {}).get("version")
        except Exception:
            if out:
                return out.splitlines()[0]
    except Exception:
        pass
    return None


def ensure_uv():
    uv = find_exe("uv")
    if uv:
        print(f"  uv 已就绪：{uv}")
        return uv
    print("  未找到 uv，需要先安装（官方脚本，无需管理员权限）。")
    if os.name == "nt":
        print("  Windows 请在 PowerShell 运行：")
        print('    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
    else:
        print("  macOS/Linux 请运行：")
        print("    curl -LsSf https://astral.sh/uv/install.sh | sh")
    print("  安装后重开终端再跑本脚本。")
    return None


def deploy_skill(skills_dir):
    """把包内离线副本复制到目标 AI 的 skills 目录（setup 未覆盖时兜底）。"""
    if not os.path.isdir(BUNDLED_SKILL):
        print("  警告：包内未找到离线技能副本，跳过复制。")
        return False
    dest = os.path.join(os.path.expanduser(skills_dir), "agent-reach")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isdir(dest):
        print(f"  技能目录已存在，跳过：{dest}")
        return True
    shutil.copytree(BUNDLED_SKILL, dest)
    print(f"  ✓ 已复制技能到：{dest}")
    return True


def main():
    ap = argparse.ArgumentParser(description="安装 Agent Reach（让 AI 能上网）")
    ap.add_argument("--skills-dir", default="~/.workbuddy/skills",
                    help="把 agent-reach 技能装到哪个 AI 的 skills 目录，默认 WorkBuddy")
    ap.add_argument("--skip-setup", action="store_true", help="跳过 agent-reach setup")
    ap.add_argument("--skip-copy", action="store_true", help="跳过复制离线技能副本")
    args = ap.parse_args()

    print("=== Agent Reach 安装 / 检测 ===\n")

    exe = find_exe("agent-reach")
    version = reach_version(exe) if exe else None

    if version:
        print(f"[检测] Agent Reach 已安装：v{version}（{exe}）")
        print("[提示] 升级请运行：agent-reach update")
    else:
        print("[安装] 未检测到 Agent Reach，开始安装。")
        uv = ensure_uv()
        if not uv:
            print("\n缺少 uv，无法继续。请先按上面的命令安装 uv。")
            sys.exit(1)
        r = run([uv, "tool", "install", RELEASE_ZIP])
        if r.returncode != 0:
            print("\n安装失败。请检查网络，或手动执行：")
            print(f"  uv tool install {RELEASE_ZIP}")
            sys.exit(1)
        exe = find_exe("agent-reach")
        version = reach_version(exe) if exe else None
        if not version:
            print("\n程序已安装但当前终端找不到 agent-reach。")
            print("请运行 `uv tool update-shell` 后重开终端，再重跑本脚本。")
            sys.exit(1)
        print(f"  ✓ 安装完成：v{version}")

    if not args.skip_setup:
        print("\n[配置] 运行 agent-reach setup（开启默认渠道、安装 AI 技能）…")
        r = run([exe, "setup"])
        if r.returncode != 0:
            print("  setup 返回非零，可能部分渠道未就绪；可稍后手动运行 `agent-reach setup`。")

    if not args.skip_copy:
        print("\n[技能] 确保技能已部署到目标 AI…")
        deploy_skill(args.skills_dir)

    print("\n=== 完成 ===")
    print("自检：agent-reach channels   # 查看各渠道是否就绪")
    print("示例：agent-reach read https://www.v2ex.com/t/123")
    print("说明：Agent Reach 只读（搜索/读取），不发帖、不评论、不替你登录。")


if __name__ == "__main__":
    main()
