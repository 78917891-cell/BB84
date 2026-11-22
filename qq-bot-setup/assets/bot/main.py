# -*- coding: utf-8 -*-
"""糍粑 QQ 机器人主入口。"""
import logging
import os
import sys

import yaml

from brain import Brain
from qq_bot import QQBot

BASE = os.path.dirname(os.path.abspath(__file__))


def setup_log(debug: bool):
    os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger()
    logger.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(os.path.join(BASE, "logs", "bot.log"), encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)


def load_config():
    path = os.path.join(BASE, "config.yaml")
    if not os.path.exists(path):
        print("找不到 config.yaml，请先复制 config.yaml.example 并填写。")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_config(cfg):
    qq, ds = cfg.get("qq", {}), cfg.get("deepseek", {})
    problems = []
    if str(qq.get("app_id", "")).startswith("YOUR") or not qq.get("app_id"):
        problems.append("qq.app_id 未填写")
    if str(qq.get("app_secret", "")).startswith("YOUR") or not qq.get("app_secret"):
        problems.append("qq.app_secret 未填写")
    if str(ds.get("api_key", "")).startswith("YOUR") or not ds.get("api_key"):
        problems.append("deepseek.api_key 未填写")
    if problems:
        print("配置未完成：")
        for p in problems:
            print("  -", p)
        sys.exit(1)


def main():
    cfg = load_config()
    setup_log(bool(cfg.get("bot", {}).get("debug", True)))
    check_config(cfg)
    log = logging.getLogger("main")

    brain = Brain(cfg["deepseek"], cfg.get("bot", {}), cfg.get("search", {}), cfg.get("memory", {}))
    bot = QQBot(cfg["qq"], brain, cfg.get("voice", {}))

    log.info("=" * 50)
    log.info("糍粑 QQ 机器人启动")
    log.info("  触发方式: %s", cfg["qq"].get("group_trigger", "at"))
    log.info("  模型: %s", cfg["deepseek"].get("model"))
    log.info("=" * 50)

    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("收到 Ctrl+C，退出")


if __name__ == "__main__":
    main()
