# 常见问题排查

## 验证阶段（verify.py）

- **`[FAIL] DeepSeek Key: 401 / Invalid API key`**
  Key 填错、带了前后空格、或已删除。去 <https://platform.deepseek.com/api_keys> 重新创建，用 `--deepseek-key` 重新 bootstrap 或直接改 config.yaml。
- **`[FAIL] DeepSeek Key: 402 / Insufficient Balance`**
  账户余额不足，去 DeepSeek 平台充值。
- **`[FAIL] QQ AppID/Secret: 获取 access_token 失败`**
  AppID 必须是纯数字字符串；AppSecret 不要用错其他机器人的；检查是否带空格。快捷通道和完整版的凭证不能混用。
- **`[FAIL] QQ WebSocket 网关: 不可达`**
  网络问题或 QQ 服务临时故障，稍后重试；检查代理设置。

## 启动与收消息

- **启动后连不上 WebSocket / 频繁重连**
  在开放平台确认事件订阅方式选的是 **WebSocket**（不是 Webhook），intents 勾选了群 @ 与单聊；AppID/Secret 与开放平台一致。
- **机器人不上线 / 收不到私聊**
  快捷通道创建的机器人仅创建人可用，请用创建机器人本人的 QQ 发消息。要群聊需走完整认证并配置服务范围。
- **群里 @ 机器人没反应**
  `group_trigger` 默认 `at`，必须 @ 机器人；确认 intents 的 group_at_message 为 true。
- **收到消息但回复很慢**
  DeepSeek 首次调用有冷启动；`deepseek-reasoner` 模型更慢，可换回 `deepseek-chat`；降低 `max_tokens`。
- **回复被截断 / 乱序**
  调大 `max_chunk_chars`（QQ 单条消息有长度上限，过大反而失败），检查网络。

## 安装与环境

- **`python` 不是内部命令（Windows）**
  Python 没装或没进 PATH。重装 Python 3.10+ 并勾选 Add to PATH；或改用 `py -3 脚本名.py`。
- **pip 装依赖失败 / 超时**
  bootstrap.py 已内置清华镜像回退；仍失败可手动进入部署目录运行 `1.首次安装.bat`，或检查代理。
- **venv 创建失败**
  确认 Python 安装完整（含 venv 模块）；Linux 可能需装 `python3-venv` 包。
- **改了人设 / 配置不生效**
  重启机器人进程（前台 Ctrl+C 后重跑，或后台 vbs 停止再启动）。

## 仍无法解决

收集以下信息再求助：部署目录 `logs/bot.log` 的最近报错、`verify.py` 的完整输出、QQ 开放平台机器人的事件订阅截图。
