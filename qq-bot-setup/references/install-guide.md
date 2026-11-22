# 技能安装与打包分发指南

本技能是标准 Agent Skill（SKILL.md 格式），一份目录可在多个支持该格式的 AI 中使用。

## 各 AI 的安装目录

| AI 工具 | 技能目录 |
|---------|----------|
| WorkBuddy | `~/.workbuddy/skills/qq-bot-setup/` |
| OpenClaw（龙虾） | `~/.openclaw/skills/qq-bot-setup/`（或对应 skills 目录） |
| Claude Code | `~/.claude/skills/qq-bot-setup/` |
| Cursor | 项目 `.cursor/rules/` 或全局 skills 目录（依版本） |

把整个 `qq-bot-setup/` 文件夹（含 SKILL.md、scripts/、references/、assets/）复制进去即可。目录名须与 SKILL.md 里的 `name` 一致（`qq-bot-setup`）。

## 校验

用 skill-creator 的校验脚本确认结构合规：

```bash
python <skill-creator目录>/scripts/quick_validate.py <qq-bot-setup目录>
```

输出 `Skill is valid!` 即通过。校验检查：YAML frontmatter、name 命名规范、description 完整性、尖括号等。

## 打包分发

```bash
python <skill-creator目录>/scripts/package_skill.py <qq-bot-setup目录> [输出目录]
```

生成 `qq-bot-setup.zip`，内含完整目录结构。对方解压到上表对应 skills 目录即可使用。打包脚本会先自动校验，校验失败不会出包。

## 触发方式

安装后，对方 AI 读到 SKILL.md 的 `description` 字段，在用户说「一站式部署 QQ 机器人」「从零装 QQ bot」「扫码创建 QQ 机器人」「把 DeepSeek 接到 QQ」等场景会自动触发本技能。也可直接说「使用 qq-bot-setup 技能」。

## 联网能力（可选组件）

包内 `assets/reach/` 是 Agent Reach 技能的离线副本，`scripts/install_reach.py` 负责安装 CLI 并把技能放到目标 AI：

```bash
python scripts/install_reach.py                                  # 默认装到 ~/.workbuddy/skills
python scripts/install_reach.py --skills-dir ~/.claude/skills    # 装到 Claude Code
python scripts/install_reach.py --skills-dir ~/.openclaw/skills  # 装到 OpenClaw
```

装好后该 AI 就具备网页/B站/YouTube/GitHub/V2EX/小红书/雪球等平台的只读检索能力。用法见 `references/reach-guide.md`。

## 分发注意事项

- assets/bot/ 里已排除 `.venv/`、日志和用户的 `config.yaml`，不含任何密钥，可安全分发。
- 运行时的密钥由目标用户在本地部署时填写，不随技能包传播。
- 机器人依赖云端的 DeepSeek API（需用户自己的 Key 与额度），技能包不内置模型。
- assets/reach/ 为第三方开源项目 Agent Reach 的技能文件副本，版权与许可以上游仓库 <https://github.com/Panniantong/Agent-Reach> 为准。
- **assets/voice_ref/ 是可替换的音色样本，不是通用素材**：三段音频截取自特定人的视频音轨，涉及说话人声音权益。仅在自己使用或已获授权的范围内保留；对外分发前建议清空该目录（只留 `manifest.json` 与 `README.md`），或在包里说明用 `scripts/prepare_voice_ref.py` 让使用者自行生成。默认清空的打包命令：
  ```bash
  rm -f assets/voice_ref/ref_0*.wav && python <skill-creator目录>/scripts/package_skill.py .
  ```
- 包体积：含三段样本约 880KB，清空样本后约 70KB。
