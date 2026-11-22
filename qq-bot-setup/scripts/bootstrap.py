#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键部署：复制机器人源码 -> 建 venv -> 装依赖 -> 写 config.yaml。"""
import argparse
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_SRC = os.path.join(SKILL_DIR, "assets", "bot")

CFG_TEMPLATE = """# QQ 官方机器人配置（由 qq-bot-setup 自动生成）
qq:
  app_id: "{app_id}"
  app_secret: "{app_secret}"
  intents:
    group_at_message: true
    group_all_message: false
    c2c_message: true
  group_trigger: "at"
  trigger_prefix: "糍粑 "

deepseek:
  api_key: "{deepseek_key}"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
  temperature: 0.7
  max_tokens: 2048
  timeout: 60

search:
  enabled: true
  in_group: true
  timeout: 20
  max_results: 3
  weather_enabled: true
  weather_city: "深圳"

# 长期记忆：随对话自动积累（本地 sqlite，零依赖）
memory:
  enabled: true
  db_path: "memory.db"
  max_items_per_user: 300
  inject_limit: 8
  llm_extract: true
  extract_every: 6

# 语音包：默认关闭（只发文字）。要开再改成 true，并装 pysilk-mod + edge-tts
voice:
  enabled: false
  backend: "edge"
  voice: "zh-CN-XiaoyiNeural"
  rate: "+0%"
  max_chars: 100
  send_text: true

bot:
  name: "糍粑"
  history_rounds: 10
  rate_limit_seconds: 1.5
  max_chunk_chars: 1000
  keep_markdown: false
  debug: true
"""


def venv_python(target):
    if os.name == "nt":
        return os.path.join(target, ".venv", "Scripts", "python.exe")
    return os.path.join(target, ".venv", "bin", "python")


def run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def install_deps(py):
    req = os.path.join(BOT_SRC_DEST, "requirements.txt")
    # 先官方源，失败回退清华镜像
    for idx, extra in enumerate([[], ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]]):
        try:
            run([py, "-m", "pip", "install", *extra, "-r", req])
            return True
        except subprocess.CalledProcessError:
            print(f"  依赖安装第 {idx+1} 次失败" + ("，尝试国内镜像…" if idx == 0 else "。"))
    return False


BOT_SRC_DEST = ""


def main():
    global BOT_SRC_DEST
    ap = argparse.ArgumentParser(description="一键部署糍粑 QQ 机器人")
    ap.add_argument("--target", required=True, help="部署目录（不存在会自动创建）")
    ap.add_argument("--app-id", help="QQ 机器人 AppID")
    ap.add_argument("--app-secret", help="QQ 机器人 AppSecret")
    ap.add_argument("--deepseek-key", help="DeepSeek API Key")
    ap.add_argument("--interactive", action="store_true", help="逐项提示输入密钥")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    BOT_SRC_DEST = target
    os.makedirs(target, exist_ok=True)
    print(f"部署目录：{target}\n")

    # 1. 复制源码（ VenV / logs / config.yaml 不覆盖已有配置）
    print("[1/4] 复制机器人源码…")
    for name in os.listdir(BOT_SRC):
        s = os.path.join(BOT_SRC, name)
        d = os.path.join(target, name)
        if not os.path.isfile(s):
            continue
        if name == "config.yaml" and os.path.exists(d):
            continue
        shutil.copy2(s, d)
    print("  完成\n")

    # 2. 收集密钥
    print("[2/4] 写入配置…")
    app_id = args.app_id
    app_secret = args.app_secret
    ds_key = args.deepseek_key
    if args.interactive:
        app_id = app_id or input("  QQ AppID（纯数字）: ").strip()
        app_secret = app_secret or input("  QQ AppSecret: ").strip()
        ds_key = ds_key or input("  DeepSeek API Key (sk-...): ").strip()
    cfg_path = os.path.join(target, "config.yaml")
    if not (app_id and app_secret and ds_key):
        # 先落一份占位配置，再交给 auto_credentials 逐项抓取
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(CFG_TEMPLATE.format(
                app_id=app_id or "YOUR_APP_ID",
                app_secret=app_secret or "YOUR_APP_SECRET",
                deepseek_key=ds_key or "YOUR_DEEPSEEK_API_KEY"))
        print("  凭证未齐，已先生成占位 config.yaml")
        print("  将逐项引导获取（需你在浏览器登录/扫码后点「复制」）\n")
        print("[2/4] 自动获取凭证…")
        creds_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_credentials.py")
        if not ds_key:
            subprocess.run([sys.executable, creds_script, "--site", "deepseek", "--config", cfg_path])
        if not (app_id and app_secret):
            subprocess.run([sys.executable, creds_script, "--site", "qq", "--config", cfg_path])
    else:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(CFG_TEMPLATE.format(app_id=app_id, app_secret=app_secret, deepseek_key=ds_key))
    print("  config.yaml 已写入\n")

    # 3. 建 venv + 装依赖
    print("[3/4] 创建虚拟环境并安装依赖…")
    py = venv_python(target)
    if not os.path.exists(py):
        try:
            run([sys.executable, "-m", "venv", os.path.join(target, ".venv")])
        except subprocess.CalledProcessError:
            print("  建 venv 失败，试试用 py -3 手动执行本脚本。")
            sys.exit(1)
    if not install_deps(py):
        print("  依赖安装失败，请检查网络或手动运行目录内「1.首次安装.bat」。")
        sys.exit(1)
    print("  依赖就绪\n")

    print("[4/4] 完成 ✓")
    print(f"  下一步：python scripts/verify.py --config {os.path.join(target, 'config.yaml')}")
    print(f"  启动：  python scripts/start.py --target {target}")


if __name__ == "__main__":
    main()
