---
name: qq-bot-setup
description: "One-stop deployment of a QQ official bot (糍粑, a girlfriend persona) from zero to a working QR-code-onboarded bot: auto-capture the DeepSeek API key and QQ AppID/AppSecret via clipboard monitoring while the user logs in and scans the QR code, then automatically install Python deps, write config.yaml, verify connectivity and start the WebSocket bot. Use when the user says 从零部署 QQ 机器人 / deploy a QQ bot from scratch, 一站式安装 QQ 机器人 / one-stop install QQ bot, 扫码创建 QQ 机器人, 密钥自动获取, 把 DeepSeek 接到 QQ, 让 AI 能上网 / give the AI web access, install the QQ bot skill, 设定为女友 / 改成女朋友人设 / set the bot as my girlfriend, or asks how to install/use this skill in another AI (WorkBuddy, OpenClaw, Claude Code, Cursor). Credentials cannot be created fully unattended because login and QR scan are required; this skill automates everything after the user clicks Copy. Bundles the bot source, an optional Agent Reach integration for web search/reading, and three curated voice-cloning reference samples plus a config-driven HTTP TTS backend so the bot can speak in a cloned voice (use when asked 声音克隆 / 同款声音 / 让机器人用我的声音说话). Does not bundle a local model, uses the cloud DeepSeek API."
metadata:
  version: "1.0.0"
---

# QQ Bot Setup — 一站式部署糍粑 QQ 机器人

从「什么都没装」到「QQ 里能跟糍粑聊天」，全程引导 + 自动化。核心链路分两段：**需要用户本人操作的扫码/拿 Key**（AI 不能代替），和**AI 可以自动完成的装环境、写配置、验证、启动**。

先说一句「正在使用 qq-bot-setup 技能（一站式部署 QQ 机器人）」再开始。全流程用中文。

## 关键事实（先读，避免走弯路）

- QQ 官方已提供**扫码快捷建机器人**通道：PC 打开 `https://q.qq.com/qqbot/openclaw/login.html`，手机 QQ 扫码登录 → 点一次「创建机器人」→ 立刻拿到 **AppID + AppSecret**，机器人还会给你 QQ 发一条成功消息。一个 QQ 号最多建 5 个。这比走完整开发主体认证快得多，优先用这条。
- 该快捷通道创建的机器人**仅创建人可用，暂时不能拉进 QQ 群**；若要群聊，需走完整版 `https://q.qq.com` 的主体认证并在开放平台申请相应权限。
- 接入方式选 **WebSocket**（本地单机无需公网）；在开放平台「事件订阅 / 回调」也要选 WebSocket，intents 勾「群聊 @ 消息」和「单聊」。
- DeepSeek API Key 在 `https://platform.deepseek.com/api_keys` 注册后创建，形如 `sk-xxxxxxxx`，只在创建时完整显示，务必立即复制。
- 机器人后端是 `assets/bot/` 里的 Python 项目（QQ API v2 WebSocket + DeepSeek + 糍粑女友型人设），已内置人设，无需用户再提供。她对你默认称呼「宝」，改 `assets/bot/persona.py` 顶部的 `NICKNAME` 即可改。

## 一站式 SOP（按顺序执行）

### 第 0 步 · 环境体检
运行 `scripts/preflight.py` 检查 Python 版本（需 3.9+）、网络连通性（DeepSeek / QQ 网关）。若 Python 缺失或版本过低，先引导用户安装 Python 3.10+（<https://www.python.org/downloads/>，Windows 安装时勾选 Add to PATH）。
```bash
python scripts/preflight.py
```

> **关于「密钥自动获取」的边界（必须如实告知用户）**：DeepSeek API Key 和 QQ AppID/AppSecret 都必须先登录账号才能创建，注册/登录有手机验证码与人机验证，平台没有开放「程序化创建凭证」接口。所以**无法做到无人值守全自动**。本技能的做法是：脚本自动打开官方页面，用户只需登录/扫码后点一下页面上的「复制」，脚本监听剪贴板自动识别并写入配置——不需要手动粘贴或改文件。不要把这一步描述成「全自动」，也不要尝试绕过验证或使用他人共享 Key。

### 第 1 步 · 自动获取 DeepSeek API Key（脚本辅助）
```bash
python scripts/auto_credentials.py --site deepseek --config <部署目录>/config.yaml
```
脚本会打开 <https://platform.deepseek.com/api_keys>，引导用户登录 → 创建 Key → 点「复制」。脚本自动监听剪贴板，识别 `sk-` 开头的字符串并写入 `deepseek.api_key`。已有值会跳过（`--force` 可覆盖）。
详细说明见 `references/deepseek-guide.md`。

### 第 2 步 · 自动获取 QQ 机器人凭证（扫码 + 脚本辅助）
```bash
python scripts/auto_credentials.py --site qq --config <部署目录>/config.yaml
```
脚本打开 `https://q.qq.com/qqbot/openclaw/login.html`，用户手机 QQ 扫码登录 → 点「创建机器人」→ 先复制 AppSecret 再复制 AppID。脚本按规则自动识别（字母数字混合的较长串=AppSecret，纯数字=AppID）并写入配置。快捷通道机器人仅创建人可用；群聊需完整认证，见 `references/qq-platform-guide.md`。

### 第 3 步 · 部署与配置（AI 自动）
`scripts/bootstrap.py` 一键完成：复制源码 → 建 venv → 装依赖 → 写 config.yaml。**不带凭证参数时会自动串联第 1、2 步的剪贴板抓取**，形成一条连贯流程。
```bash
# 全自动串起来（凭证通过剪贴板抓取）
python scripts/bootstrap.py --target <部署目录>

# 或凭证已知时直接传入
python scripts/bootstrap.py --target <部署目录> --app-id <AppID> --app-secret <AppSecret> --deepseek-key <sk-xxx>
```
- Windows 若 `python` 不可用，试 `py -3`。依赖装不上时脚本已内置国内镜像回退。
- 配置字段含义见 `references/config-reference.md`。

### 第 4 步 · 连通性验证（AI 自动）
运行 `scripts/verify.py` 验证：① DeepSeek Key 能否调用 chat/completions；② QQ AppID/Secret 能否换取 access_token；③ WebSocket 网关地址是否可取。三项全绿再启动，失败按输出提示逐项修。
```bash
python scripts/verify.py --config <部署目录>/config.yaml
```

### 第 5 步 · 启动机器人（AI 自动或指导用户）
前台调试：`python scripts/start.py --target <部署目录>`，看到 `机器人已连接，等待消息…` 即成功。
后台常驻（Windows）：优先用 `assets/bot/3.后台静默启动.vbs`（双击即后台运行，日志写到 logs/）；停止用 `4.停止后台.vbs`。跨平台可用 `python scripts/start.py --target <目录> --daemon`。
首次验证：让用户用机器人创建者本人的 QQ 发一条消息（快捷通道机器人仅创建人可用），确认收到糍粑的回复。

## 排障

连接失败、Token 报错、收不到消息等见 `references/troubleshooting.md`。核心检查项：开放平台事件订阅是否选了 WebSocket、intents 是否勾对、Key/Secret 是否带错空格、AppID 是否为纯数字字符串。

## 可选：让 AI 能上网（Agent Reach）

部署完机器人后，可一句话给 AI 助手装上联网检索能力，之后查资料、读 B 站/YouTube 字幕、搜 GitHub/小红书/V2EX/雪球都不再受内置搜索限制。

```bash
python scripts/install_reach.py
```

脚本按官方流程执行：检测是否已装 → 用 uv 安装 Agent Reach（GitHub release，非 PyPI 同名包）→ `agent-reach setup` 开启默认渠道 → 把技能复制到目标 AI 的 skills 目录。装到别的 AI 用 `--skills-dir ~/.claude/skills` 等。

- 只读：仅搜索与读取，不发帖、不评论、不替你登录、不要密码。
- 装好后用 `agent-reach channels` 自检；`agent-reach read <url>` 按链接自动选渠道。
- 详细用法、手动安装命令与排障见 `references/reach-guide.md`。

### 机器人也能联网（已内置）

除了 AI 助手侧，**QQ 机器人本身也接了联网**：`assets/bot/websearch.py` 复用本机 Agent Reach 做搜索，用 wttr.in 查天气。当消息命中实时类关键词（今天/最新/新闻/天气/股价…）时，自动先查再答，并在群里先回一句「等我一下，我上网查查～」。

- 开关与城市在 `config.yaml` 的 `search` 段（`enabled` / `in_group` / `weather_city` / `trigger_keywords`）。
- 没装 Agent Reach 时自动降级：搜索静默跳过，不影响正常聊天；天气走独立通道仍可用。
- 字段说明见 `references/config-reference.md`。

### 语音包（可选，默认关闭）

机器人默认只发文字。想让她用语音回你，再打开这个开关——链路是：文字 → TTS → ffmpeg 转 PCM → pysilk 编码 silk → QQ 富媒体发送。

关闭状态下代码不会调用任何 TTS、也不会上传富媒体，`requirements.txt` 里也没装语音依赖，纯文字部署更轻。要开：

```bash
# 在部署目录的 venv 里装
pip install pysilk-mod edge-tts
```

ffmpeg 来源按优先级自动探测：`imageio-ffmpeg` → 系统 PATH → **Agent Reach 自带**（装了 Agent Reach 就不用另装）。然后在 `config.yaml` 打开：

```yaml
voice:
  enabled: true
  backend: "edge"                # edge=免费现成音色 / http=云端克隆或自建 TTS
  voice: "zh-CN-XiaoyiNeural"     # xiaoyi 活泼 / xiaoxiao 温柔 / hiuMaan 粤语
  max_chars: 100                 # 超长只发文字
  send_text: true                # 是否同时发文字
```

- 只在文字长度合适、且不是纯代码时发语音；语音作为文字之后追加的一条，受被动回复次数限制（群 5 次、私聊 4 次）。
- 任一步失败（TTS/编码/上传）都静默降级为纯文字，不影响正常回复。
- 音色列表与字段说明见 `references/config-reference.md`。

### 声音克隆（要「同款声音」走这里）

想让它用**视频里那个人的声音**说话，而不是微软的现成音色。

> **先说清边界**：DeepSeek 只有对话接口，没有 TTS、也没有声音克隆。所以只能是「大脑用 DeepSeek + 嗓子用另一家」。

包里已经放了三段可直接上传的参考音频：

| 文件 | 时长 | 规格 | 说明 |
|------|------|------|------|
| `assets/voice_ref/ref_01.wav` | 9.6s | 16kHz/单声道/16bit | **首选**，人声占比最大、BGM 相对最轻 |
| `assets/voice_ref/ref_02.wav` | 8.2s | 同上 | 备选 |
| `assets/voice_ref/ref_03.wav` | 9.0s | 同上 | 备选 |

全部做过 `highpass=70Hz` + 两遍 `loudnorm` 归一到 -16 LUFS（实测 -15.7 ~ -15.9），峰值不超 -1.5 dB。来源与裁剪时间窗写在 `assets/voice_ref/manifest.json`。

流程：试听选一段 → 上传到平台做音色克隆 → 拿到 `voice_id` → 把 `voice.backend` 改成 `http` 并填 `voice.http`（url / headers / body / response_type）→ 重启。

- `voice.py` 的 http 后端支持四种返回形态：`json_base64` / `json_hex`（MiniMax）/ `json_url`（百炼）/ `binary`，配置驱动，不需要改代码。
- 平台选型、字段对照、常见报错见 `references/voice-clone-guide.md`。
- 想换样本（推荐，短视频音轨必然混 BGM）：用手机安静环境录 20~30 秒覆盖 `ref_01.wav`；或从任意视频自动取段：
  ```bash
  python scripts/prepare_voice_ref.py "D:/videos/x.mp4" --out assets/voice_ref/ref_01.wav
  ```
- 改完跑一次 `python test_voice.py`，四种返回形态 + Edge 真实往返 + 关闭静音共 21 项，全绿再上真 Key。


### 长期记忆

机器人默认带**轻量长期记忆**，不用额外装任何东西：本地 sqlite，随对话自动积累，跨会话、跨天都记得。

- **记什么**：只存「他自己说过的稳定事实」（`我叫/我在…上班/我住在/我喜欢/我讨厌/我养了` 等句式）和任何 `记住：…` 的话，不做全量对话存档——否则记忆会变成垃圾场、注入后反而干扰回答。
- **按人隔离**：单聊写 `u:<openid>`；群聊写 `u:<openid>` + `g:<groupid>`，所以她既记得你，也记得这个群的事，不会串号。
- **怎么用**：每次回复前按相关度取最多 8 条，作为一段 system 注入（`inject_limit` 可调）；`记住：` 开头的权重最高，永不淘汰。
- **存哪**：程序目录下 `memory.db`，可直接备份/删除；换机器搬走它就是搬走记忆。
- **开关**：`config.yaml` 的 `memory` 段；关掉后既不写也不读。
- **自检**：`python test_memory.py`，28 项（抽取 / 去重 / 隔离 / 检索 / 淘汰 / 持久化 / LLM 降级）。

为了让抽取更全，默认每 6 轮额外调一次小模型补抽（`llm_extract` + `extract_every`），失败自动降级到规则抽取，不影响回复。想省 token 就把 `llm_extract` 设 false。

#### 重型方案：TencentDB Agent Memory（可选，需 Docker）

如果你要的是**多个 Agent 共享同一份项目记忆**（WorkBuddy + Claude Code + Codex 同时写一个仓库），才需要它。三容器栈（memory-core / memory-hub / proxy），靠 Docker 起。

```bash
python scripts/install_memory.py --check     # 体检：Docker / Node 22.16+ / 端口 / 磁盘
python scripts/install_memory.py --fetch     # 稀疏拉取 deploy/ 与 agents/（几 MB，非 64MB 全量）
```

脚本能自动做体检和拉取，**启动留给官方交互式脚本**（要现场填 LLM Key，无法代跑）：

```bash
cd ~/.memory-tencentdb/deploy/global-images && ./start-all.sh
```

- 四个端口：8420 Core / 8125 面板 / 8424 Knowledge / 8096 Proxy。
- 接 WorkBuddy：改 `~/.workbuddy/models.json` 加一项自定义模型指向 `http://127.0.0.1:8096/workbuddy/default`。
- 接机器人：把 `deepseek.base_url` 指到 proxy（**未实测**，先跑通 WorkBuddy 侧再改）。
- 用 `python scripts/install_memory.py --print-config` 可直接生成两段接入配置。

> 提醒：这是给多人多 Agent 的团队级记忆中枢，单人单机器人用它，复杂度（Docker + 四端口 + 流量绕行）明显大于收益。**只想让她记住你的偏好，上面那套内置记忆就够了**，不用起容器。完整说明见 `references/memory-guide.md`。

## 把本技能安装到其他 AI（WorkBuddy / OpenClaw / Claude Code / Cursor）

本技能是标准 `SKILL.md` 格式（YAML frontmatter + Markdown 正文），各 AI 的 skills 目录通用。两种方式：

1. **直接复制目录**：把整个 `qq-bot-setup/` 文件夹复制到目标 AI 的 skills 目录：
   - WorkBuddy：`~/.workbuddy/skills/qq-bot-setup/`
   - OpenClaw：`~/.openclaw/skills/qq-bot-setup/`（或对应 skills 目录）
   - Claude Code：`~/.claude/skills/qq-bot-setup/`
   - Cursor：项目内 `.cursor/rules/` 或全局 skills 目录（依版本）
2. **打包分发**：运行 skill-creator 的 `package_skill.py <本技能目录>` 生成 `qq-bot-setup.zip`，对方解压到上述目录即可。

安装后，对方 AI 读到 SKILL.md 的 `description` 就会在用户说「一站式部署 QQ 机器人」等场景自动触发。打包与校验细节见 `references/install-guide.md`。

## 资源清单

- `scripts/preflight.py` — 环境体检
- `scripts/auto_credentials.py` — 自动获取 DeepSeek Key / QQ 凭证（打开页面 + 监听剪贴板 + 写配置）
- `scripts/bootstrap.py` — 一键部署（复制源码 + venv + 依赖 + 写配置，可自动串联取证）
- `scripts/verify.py` — 三项连通性验证
- `scripts/start.py` — 前台/后台启动
- `scripts/install_reach.py` — 安装 Agent Reach，给 AI 加上网能力
- `scripts/install_memory.py` — 部署 TencentDB Agent Memory（可选长期记忆，需 Docker）
- `scripts/prepare_voice_ref.py` — 从视频/音频自动生成合规的克隆参考音频（找最长人声段 + 两遍归一）
- `assets/bot/` — 完整 QQ 机器人源码（含糍粑女友型人设、联网、长期记忆 `memory.py`、语音包、`test_memory.py` / `test_voice.py`）
- `assets/voice_ref/` — 三段声音克隆参考音频 + `manifest.json`（来源、时间窗、实测响度）
- `assets/reach/` — Agent Reach 技能离线副本（安装兜底）
- `references/` — QQ 建机器人、DeepSeek Key、配置、排障、安装、联网、声音克隆、长期记忆的详细文档
