# 联网能力：Agent Reach 集成说明

## 它解决什么问题

AI 助手自带的搜索和网页读取，对下面这些场景往往够不着：

- 需要登录才能看的内容（小红书笔记、X 账号动态、职位详情）
- 视频里的信息（B 站 / YouTube 字幕、YouTube 与小宇宙的语音转文字）
- 中文平台（B 站、小红书、V2EX、雪球）
- 结构化数据（雪球行情、V2EX 帖子与回复、GitHub 仓库与 issue）

Agent Reach 把这些平台背后的工具装好、测好，AI 一条命令就能用。**只读**：只搜索和读取，不发帖、不评论、不点赞、不私信，也从不替你登录或索要密码。

## 一键安装

```bash
python scripts/install_reach.py
```

脚本会：检测是否已安装 → 没有就用 uv 安装官方 release → 运行 `agent-reach setup` 开启默认渠道 → 把技能复制到目标 AI 的 skills 目录。

常用参数：

```bash
# 装到别的 AI（Claude Code / OpenClaw 等）
python scripts/install_reach.py --skills-dir ~/.claude/skills
python scripts/install_reach.py --skills-dir ~/.openclaw/skills

# 只装程序、不做 setup；或只做 setup、不复制技能
python scripts/install_reach.py --skip-setup
python scripts/install_reach.py --skip-copy
```

## 官方安装命令（脚本失败时手动执行）

```bash
# 1. 装 uv（Windows 在 PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 装 Agent Reach（只认 GitHub，PyPI 同名包不是本项目）
uv tool install https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip

# 3. 初始化
agent-reach setup
```

## 常用命令

```bash
agent-reach channels                        # 有哪些渠道、各能做什么
agent-reach bilibili search "大模型"         # <渠道> <动作> [参数]
agent-reach read https://www.v2ex.com/t/123 # 按链接自动选渠道
agent-reach update                          # 升级程序、渠道工具和技能
agent-reach add xiaohongshu                 # 加可选渠道（小红书等）
agent-reach remove v2ex                     # 移除渠道
```

所有命令输出一个 JSON：读 `ok`、`result`、`error.hint`。

## 常见问题

- **`agent-reach: command not found`**：运行 `uv tool update-shell`，重开终端。
- **setup 后技能没出现在 AI 里**：用 `--skills-dir` 指定目标 AI 的 skills 目录再跑一次，或手动复制包内 `assets/reach/` 到该目录。
- **某个渠道不可用**：`agent-reach channels` 看状态，按 `error.hint` 处理；登录类渠道需你本人登录。
- **升级后行为变化**：`agent-reach update` 会同时刷新技能；按提示的 `user_actions` 操作。

## 两个层面的联网（都在本包里）

1. **AI 助手侧**：安装 Agent Reach 后，AI 在帮你查资料、读 B 站/YouTube 字幕、搜 GitHub/小红书/V2EX/雪球时能上网。
2. **QQ 机器人侧**：`assets/bot/websearch.py` 复用同一个 agent-reach CLI 做搜索，另用 wttr.in 查天气。命中实时类关键词时机器人自动先查再答，并先回一句「等我一下，我上网查查～」。开关在 `config.yaml` 的 `search` 段。

两者共用本机这一份 Agent Reach，不需要额外 Key；没装时机器人的搜索会静默降级，聊天不受影响。

Agent Reach 为第三方开源项目（<https://github.com/Panniantong/Agent-Reach>），本包内的 `assets/reach/` 是其技能文件的离线副本，仅作安装兜底；版权与许可以上游仓库为准。
