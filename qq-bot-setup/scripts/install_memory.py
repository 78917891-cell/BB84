#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""install_memory.py —— 可选组件：TencentDB Agent Memory（长期记忆）

它不是一个 pip 包，而是三容器栈（memory-core / memory-hub / proxy），
官方用 Docker 一键起。本脚本负责「装前体检 + 拉取部署脚本 + 生成接入片段」，
真正启动留给官方的交互式 start-all.sh（要现场填 LLM Key，无法代跑）。

用法：
  python install_memory.py --check              # 只体检，不动任何东西
  python install_memory.py --fetch              # 稀疏拉取 deploy/ 与 agents/
  python install_memory.py --print-config       # 打印 WorkBuddy / 机器人的接入片段
  python install_memory.py --dir D:/memory      # 指定安装目录

设计原则：任何一步不满足就停下来讲清楚原因和修法，不假装成功。
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys

REPO = "https://github.com/TencentCloud/TencentDB-Agent-Memory.git"
BRANCH = "feat/server_team"          # 官方默认分支（不是 main）
NEED_NODE = (22, 16)
PORTS = {8420: "Memory Core", 8125: "Panel UI", 8424: "Knowledge", 8096: "Proxy"}
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".memory-tencentdb")


def _utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run(cmd, timeout=600, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=cwd)


def have(name):
    return shutil.which(name) is not None


def port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def free_gb(path):
    probe = os.path.abspath(path)
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return shutil.disk_usage(probe).free / (1024 ** 3)
    except Exception:
        return -1


def node_version():
    if not have("node"):
        return None
    try:
        out = run(["node", "--version"], timeout=20).stdout.strip().lstrip("v")
        return tuple(int(x) for x in out.split(".")[:2])
    except Exception:
        return None


def check(dest):
    """体检：把能不能装讲清楚。返回 (ok, 问题列表)。"""
    problems = []
    print("=== 环境体检 ===")

    # Docker
    if have("docker"):
        v = run(["docker", "version", "--format", "{{.ServerVersion}}"], timeout=30)
        if v.returncode == 0 and v.stdout.strip():
            print(f"  [OK] docker {v.stdout.strip()}")
        else:
            print("  [!!] docker 已安装但守护进程没跑（Docker Desktop 未启动）")
            problems.append("启动 Docker Desktop 后重试")
    else:
        print("  [!!] docker 未安装 —— 三容器栈离不开它")
        problems.append("安装 Docker Desktop：https://www.docker.com/products/docker-desktop/")

    # Node
    nv = node_version()
    if nv:
        if nv >= NEED_NODE:
            print(f"  [OK] node {nv[0]}.{nv[1]}（要求 >= {NEED_NODE[0]}.{NEED_NODE[1]}）")
        else:
            print(f"  [!!] node {nv[0]}.{nv[1]} 太旧（要求 >= {NEED_NODE[0]}.{NEED_NODE[1]}）")
            problems.append("升级 Node.js：https://nodejs.org")
    else:
        print("  [!!] node 未安装")
        problems.append("安装 Node.js 22.16+")

    # git
    print("  [OK] git" if have("git") else "  [!!] git 未安装")
    if not have("git"):
        problems.append("安装 git（拉取部署脚本要用）")

    # 端口
    busy = [f"{p}({n})" for p, n in PORTS.items() if not port_free(p)]
    if busy:
        print(f"  [!!] 端口被占用：{', '.join(busy)}")
        problems.append("释放上述端口，或改 docker 端口映射")
    else:
        print(f"  [OK] 端口 {', '.join(str(p) for p in PORTS)} 都空闲")

    # 磁盘
    g = free_gb(os.path.abspath(dest))
    if g >= 0:
        if g >= 8:
            print(f"  [OK] 可用磁盘 {g:.1f} GB（镜像+数据建议 >= 8GB）")
        else:
            print(f"  [!!] 可用磁盘仅 {g:.1f} GB，三个镜像加数据可能不够")
            problems.append("清理磁盘或换到空间更大的盘")

    print(f"\n  安装目录：{os.path.abspath(dest)}")
    if problems:
        print("\n=== 还差这些 ===")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        return False, problems
    print("\n[OK] 环境满足，可以拉代码了")
    return True, []


def fetch(dest):
    """稀疏拉取：只要 deploy/ 与 agents/，不要 64MB 全量。"""
    print(f"=== 拉取部署脚本 → {dest} ===")
    if os.path.isdir(os.path.join(dest, ".git")):
        print("  已存在仓库，尝试更新…")
        r = run(["git", "-C", dest, "pull", "--ff-only"], timeout=600)
        print("  " + ("更新完成" if r.returncode == 0 else "更新失败（可忽略，继续用现有版本）"))
        return True
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    cmd = ["git", "clone", "--depth", "1",
           "--filter=blob:none", "--sparse",
           "--branch", BRANCH, REPO, dest]
    print("  " + " ".join(cmd))
    r = run(cmd, timeout=900)
    if r.returncode != 0:
        print("[FAIL] 克隆失败：\n" + (r.stderr or r.stdout)[-600:])
        return False
    r2 = run(["git", "-C", dest, "sparse-checkout", "set",
              "deploy/global-images", "agents"], timeout=600)
    if r2.returncode != 0:
        print("[FAIL] 稀疏检出失败：\n" + (r2.stderr or "")[-600:])
        return False
    size = 0
    for root, _, files in os.walk(dest):
        for f in files:
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    print(f"[OK] 已拉取，约 {size / 1024 / 1024:.1f} MB")
    return True


def print_next(dest):
    dep = os.path.join(dest, "deploy", "global-images")
    key_file = os.path.join(dep, ".admin-key")
    print("=== 下一步（必须你本人执行，因为要现场填 LLM Key）===")
    print(f"  cd {dep}")
    print("  ./start-all.sh          # Windows 用 Git Bash 执行；交互式，会逐个探活 LLM")
    print("  ./verify.sh             # 只体检不起容器（不想现在启动时用）")
    print("  ./stop-all.sh           # 停容器，保留数据")
    print("  ./stop-all.sh --purge   # 连数据一起清")
    print("\n  启动成功后会生成 user_key（形如 sk-mem-...），存在：")
    print(f"  {key_file}")
    if os.path.exists(key_file):
        try:
            with open(key_file, encoding="utf-8") as f:
                k = f.read().strip()
            print(f"  [OK] 已找到：{k[:12]}…（共 {len(k)} 字符）")
        except OSError:
            pass
    else:
        print("  （还没生成——说明三容器尚未成功启动过）")
    print("\n  四个服务：")
    for p, n in PORTS.items():
        print(f"    {n:12s} http://127.0.0.1:{p}")


def print_config(dest):
    key_file = os.path.join(dest, "deploy", "global-images", ".admin-key")
    key = "<sk-mem-从面板获取的 user_key>"
    if os.path.exists(key_file):
        try:
            with open(key_file, encoding="utf-8") as f:
                key = f.read().strip() or key
        except OSError:
            pass

    print("=== 1) 接入 WorkBuddy（写入 ~/.workbuddy/models.json 的数组）===")
    snippet = [{
        "id": "claude-opus-4.7-1m",
        "name": "mem-proxy",
        "vendor": "Custom",
        "url": "http://127.0.0.1:8096/workbuddy/default",
        "apiKey": key,
        "supportsToolCall": True,
        "supportsImages": False,
        "supportsReasoning": False,
        "useCustomProtocol": False,
    }]
    print(json.dumps(snippet, ensure_ascii=False, indent=2))
    print("\n  说明：id 要填 Proxy 上游实际支持的模型名；url 里的 default 是 memory 实例 ID。")
    print("  配好后在 WorkBuddy 模型选择器里选「自定义模型」。")

    print("\n=== 2) 接入 QQ 机器人（config.yaml）===")
    print("""  deepseek:
    api_key: "%s"                     # 用 user_key 占位，具体看 proxy 的鉴权要求
    base_url: "http://127.0.0.1:8096"   # 指向 proxy，由它转发到真正的上游
    model: "deepseek-chat"
  # 注意：proxy 的路径前缀按 agents/ 里最接近的适配器确认（codex / opencode 都走
  #       OpenAI 兼容协议），本组合未实测，先跑通 WorkBuddy 侧再改机器人。""" % key)

    print("\n=== 3) 验证 ===")
    print("  curl http://127.0.0.1:8420/health      # 应返回 status ok/degraded")
    print("  浏览器打开 http://127.0.0.1:8125        # 面板，建 Team/Agent/Task")


def main():
    _utf8()
    ap = argparse.ArgumentParser(description="部署 TencentDB Agent Memory（可选组件）")
    ap.add_argument("--dir", default=DEFAULT_DIR, help=f"安装目录（默认 {DEFAULT_DIR}）")
    ap.add_argument("--check", action="store_true", help="只体检")
    ap.add_argument("--fetch", action="store_true", help="拉取部署脚本")
    ap.add_argument("--print-config", action="store_true", help="打印接入片段")
    args = ap.parse_args()

    dest = os.path.abspath(os.path.expanduser(args.dir))

    if args.print_config:
        print_config(dest)
        return 0

    ok, _ = check(dest)
    if args.check:
        return 0 if ok else 1
    if not ok:
        print("\n体检没过，先修上面的问题。修好后重跑：python install_memory.py --fetch")
        return 1

    if not fetch(dest):
        return 1

    print_next(dest)
    print("\n要把记忆接进 WorkBuddy 或机器人，跑：")
    print(f"  python install_memory.py --dir {dest} --print-config")
    return 0


if __name__ == "__main__":
    sys.exit(main())
