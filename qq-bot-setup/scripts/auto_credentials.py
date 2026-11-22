#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""半自动获取密钥：自动打开官方页面 -> 用户登录/扫码并点「复制」-> 脚本监听剪贴板自动写入配置。

说明（重要，诚实边界）：
- DeepSeek API Key 与 QQ AppID/AppSecret 都必须先登录账号才能创建，平台没有开放「程序化创建」接口，
  注册/登录还有手机验证码与人机验证，无法绕过。因此本脚本只把「复制 -> 粘贴 -> 改文件」这几步自动化，
  登录和扫码仍需用户本人完成。
- 不读取、不猜测用户的账号密码；只在你主动点「复制」后读取剪贴板里那一串内容。

用法：
  python scripts/auto_credentials.py --site deepseek --config <部署目录>/config.yaml
  python scripts/auto_credentials.py --site qq       --config <部署目录>/config.yaml
"""
import argparse
import os
import re
import shutil
import sys
import time
import webbrowser

DEEPSEEK_URL = "https://platform.deepseek.com/api_keys"
QQ_URL = "https://q.qq.com/qqbot/openclaw/login.html"

TIMEOUT = 240  # 每项等待秒数，由 --timeout 覆盖

# ---------- 剪贴板读取（不依赖 tkinter） ----------
# Windows 用原生 Win32 API；macOS 用 pbpaste；Linux 用 wl-paste/xclip。
def _read_clipboard_windows():
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    u.OpenClipboard.argtypes = [wintypes.HWND]
    u.GetClipboardData.argtypes = [wintypes.UINT]
    u.GetClipboardData.restype = wintypes.HANDLE
    k.GlobalLock.argtypes = [wintypes.HANDLE]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [wintypes.HANDLE]
    if not u.OpenClipboard(None):
        return ""
    try:
        h = u.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.c_wchar_p(p).value or ""
        finally:
            k.GlobalUnlock(h)
    finally:
        u.CloseClipboard()


def read_clipboard():
    if os.name == "nt":
        try:
            return _read_clipboard_windows()
        except Exception:
            return ""
    try:
        import subprocess
        if sys.platform == "darwin":
            cmd = ["pbpaste"]
        else:
            cmd = ["wl-paste", "-n"] if shutil.which("wl-paste") else ["xclip", "-selection", "clipboard", "-o"]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return ""


def wait_clipboard(before, accept, prompt, timeout=None, interval=0.4):
    """轮询剪贴板，直到出现符合条件的内容。

    若开始前剪贴板里已有符合条件的内容（用户提前复制过），直接采用，避免卡死。
    """
    timeout = TIMEOUT if timeout is None else timeout
    cur0 = (read_clipboard() or "").strip()
    if cur0 and accept(cur0):
        print(f"  检测到剪贴板已有可用内容：{cur0[:12]}…（长度 {len(cur0)}），直接采用。")
        print("  若这不是你要的值，请先在页面上重新复制一次再重跑本命令。")
        return cur0

    print(prompt)
    print("  （等待中…点页面上的「复制」按钮即可，Ctrl+C 可退出）")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(interval)
        cur = (read_clipboard() or "").strip()
        if cur and cur != before and accept(cur):
            print(f"  已捕获：{cur[:12]}…（长度 {len(cur)}）")
            return cur
    return None


def read_value(cfg_path, key):
    """读取 config.yaml 中某字段当前值（用于判断是否已填写）。"""
    with open(cfg_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(rf'^\s*{re.escape(key)}:\s*"(.*?)"\s*(?:#.*)?$', line)
            if m:
                return m.group(1).strip()
    return ""


def already_filled(cfg_path, key):
    v = read_value(cfg_path, key)
    return bool(v) and not v.startswith("YOUR")


def update_config(path, updates):
    """按 key 名替换 config.yaml 中对应行的值，保留注释与其他字段。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    for key, value in updates.items():
        # 保留行尾注释：key: "旧值"  # 注释
        pattern = re.compile(rf'^(\s*{re.escape(key)}:\s*)"(.*?)"(\s*(?:#.*)?)$', re.M)
        if not pattern.search(text):
            print(f"  警告：config.yaml 中找不到字段 {key}，跳过。")
            continue
        text = pattern.sub(lambda m: m.group(1) + '"' + value + '"' + m.group(3), text, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def do_deepseek(cfg_path, force=False):
    print("\n=== 获取 DeepSeek API Key ===")
    if already_filled(cfg_path, "api_key") and not force:
        print("  config.yaml 里已有 DeepSeek Key，跳过（如需替换加 --force）。")
        return True
    print("接下来会打开 DeepSeek 开放平台的 API Keys 页面。")
    print("步骤：登录（未注册先注册）→ 点「创建 API Key」→ 起个名字 → 点「复制」。")
    webbrowser.open(DEEPSEEK_URL)
    before = (read_clipboard() or "").strip()
    key = wait_clipboard(before, lambda s: s.startswith("sk-") and len(s) >= 20,
                         "等待剪贴板出现 sk- 开头的 Key…")
    if not key:
        print("超时未捕获到 Key。可稍后重跑本命令，或手动填入 config.yaml 的 deepseek.api_key。")
        return False
    update_config(cfg_path, {"api_key": key})
    print("  ✓ 已写入 deepseek.api_key")
    return True


def do_qq(cfg_path, force=False):
    print("\n=== 获取 QQ 机器人 AppID / AppSecret ===")
    has_secret = already_filled(cfg_path, "app_secret")
    has_id = already_filled(cfg_path, "app_id")
    if has_secret and has_id and not force:
        print("  config.yaml 里已有 AppID 和 AppSecret，跳过（如需替换加 --force）。")
        return True
    print("接下来会打开 QQ 机器人扫码创建页。")
    print("步骤：手机 QQ 扫码登录 → 点「创建机器人」→ 分别复制 AppID 和 AppSecret。")
    print("注意：AppSecret 通常只完整显示一次，先复制它更稳妥。")
    webbrowser.open(QQ_URL)

    before = (read_clipboard() or "").strip()

    # 先拿 AppSecret（字母数字混合、较长），再拿 AppID（纯数字）；已填的项跳过
    if not has_secret or force:
        secret = wait_clipboard(
            before,
            lambda s: len(s) >= 16 and not s.isdigit(),
            "第 1 步：请点 AppSecret 旁的「复制」…",
        )
        if not secret:
            print("超时未捕获到 AppSecret。")
            return False
        update_config(cfg_path, {"app_secret": secret})
        print("  ✓ 已写入 qq.app_secret")
        before = secret

    if not has_id or force:
        app_id = wait_clipboard(
            before,
            lambda s: s.isdigit() and 5 <= len(s) <= 20,
            "第 2 步：请点 AppID 旁的「复制」…",
        )
        if not app_id:
            print("超时未捕获到 AppID。")
            return False
        update_config(cfg_path, {"app_id": app_id})
        print("  ✓ 已写入 qq.app_id")
    return True


def main():
    ap = argparse.ArgumentParser(description="半自动获取并写入 DeepSeek / QQ 机器人凭证")
    ap.add_argument("--site", required=True, choices=["deepseek", "qq"], help="要获取哪一组凭证")
    ap.add_argument("--config", required=True, help="config.yaml 路径")
    ap.add_argument("--timeout", type=int, default=240, help="每项等待秒数，默认 240")
    ap.add_argument("--force", action="store_true", help="已有凭证也重新获取并覆盖")
    args = ap.parse_args()

    global TIMEOUT
    TIMEOUT = args.timeout

    cfg = os.path.abspath(args.config)
    if not os.path.exists(cfg):
        print(f"找不到配置：{cfg}\n请先运行 bootstrap.py 生成 config.yaml。")
        sys.exit(1)

    ok = do_deepseek(cfg, args.force) if args.site == "deepseek" else do_qq(cfg, args.force)
    print()
    if ok:
        print("完成 ✓ 可继续下一步（verify.py 验证连通性）。")
    else:
        print("未完成。可重跑本命令，重跑时会跳过已填好的项（不会覆盖已有密钥）。")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
