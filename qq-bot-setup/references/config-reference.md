# config.yaml 配置字段说明

由 `bootstrap.py` 自动生成，一般无需手改。需要调整行为时参考下表。

## qq（QQ 机器人）

| 字段 | 说明 | 默认 |
|------|------|------|
| `app_id` | 机器人 AppID，纯数字字符串 | 必填 |
| `app_secret` | 机器人 AppSecret | 必填 |
| `intents.group_at_message` | 响应群聊 @机器人 消息 | true |
| `intents.group_all_message` | 响应群聊所有消息（需申请全量权限） | false |
| `intents.c2c_message` | 响应单聊消息 | true |
| `group_trigger` | 群聊触发方式：`at` / `all` / `prefix` | at |
| `trigger_prefix` | `prefix` 模式下的触发前缀 | 糍粑 |

## deepseek（AI 大脑）

| 字段 | 说明 | 默认 |
|------|------|------|
| `api_key` | DeepSeek API Key | 必填 |
| `base_url` | 接口地址 | https://api.deepseek.com |
| `model` | 模型名 | deepseek-chat |
| `temperature` | 随机性，越低越稳定 | 0.7 |
| `max_tokens` | 单次回复最大 token | 2048 |
| `timeout` | 请求超时秒数 | 60 |

## search（联网能力）

| 字段 | 说明 | 默认 |
|------|------|------|
| `enabled` | 是否开启联网检索 | true |
| `in_group` | 群里是否也联网（关掉可省额度、防刷屏） | true |
| `timeout` | 单次搜索超时秒数 | 20 |
| `max_results` | 最多取几条搜索结果 | 3 |
| `trigger_keywords` | 命中这些词才联网 | 今天/最新/新闻/天气/股价… |
| `weather_enabled` | 天气走 wttr.in（免费无需 Key） | true |
| `weather_city` | 天气城市，按所在地改 | 深圳 |

搜索复用本机 Agent Reach（`agent-reach web search`），没装时静默降级、不影响聊天。天气走独立通道，不依赖 Agent Reach。

## voice（语音包）

| 字段 | 说明 | 默认 |
|------|------|------|
| `enabled` | 是否用语音回复 | false |
| `backend` | TTS 后端：`edge`（免费）/ `http`（云端克隆或自建接口） | edge |
| `voice` | Edge TTS 音色（仅 `backend=edge` 生效） | zh-CN-XiaoyiNeural |
| `rate` | 语速，如 `+10%` / `-10%` | +0% |
| `max_chars` | 超过字数只发文字（太长合成慢） | 100 |
| `send_text` | 是否同时发文字（false=只发语音） | true |

### voice.http（`backend=http` 时生效）

| 字段 | 说明 | 默认 |
|------|------|------|
| `url` | 接口地址，必填 | — |
| `method` | 请求方法 | POST |
| `headers` | 附加请求头（如 `Authorization`） | — |
| `body` | 请求体，字符串里可用 `{text}` 占位，递归替换 | `{"text": "{text}"}` |
| `response_type` | 返回形态：`json_base64` / `json_hex` / `json_url` / `binary` | json_base64 |
| `audio_key` | `json_*` 时音频字段的点路径 | data.audio |
| `audio_url_key` | `json_url` 时地址字段的点路径 | data.audio_url |
| `timeout` | 请求超时秒数 | 30 |

四种返回形态对应关系：MiniMax 是 `json_hex`（`data.audio` 为十六进制）；阿里云百炼 CosyVoice 多为 `json_url`；火山引擎/豆包与自建 GPT-SoVITS 视接口而定，常见 `binary` 或 `json_base64`。填错时典型症状是"合成出来是杂音"或"找不到音频字段"，对照官方文档改 `response_type` 即可。

克隆音色的完整接入步骤见 `references/voice-clone-guide.md`。

### 常用音色（Edge TTS）

| 值 | 音色 |
|----|------|
| `zh-CN-XiaoyiNeural` | 晓伊，活泼女声（默认，贴合糍粑性格） |
| `zh-CN-XiaoxiaoNeural` | 晓晓，温柔女声 |
| `zh-CN-liaoning-XiaobeiNeural` | 东北话女声 |
| `zh-CN-shaanxi-XiaoniNeural` | 陕西话女声 |
| `zh-HK-HiuMaanNeural` | 粤语女声 |

依赖 `pysilk-mod` + ffmpeg，`backend=edge` 另需 `edge-tts`。ffmpeg 自动探测：imageio-ffmpeg → 系统 PATH → Agent Reach 自带。

## bot（机器人行为）

| 字段 | 说明 | 默认 |
|------|------|------|
| `name` | 机器人显示名 | 糍粑 |
| `history_rounds` | 每个用户/群保留的对话轮数 | 10 |
| `rate_limit_seconds` | 同一用户两次请求最小间隔（防刷屏） | 1.5 |
| `max_chunk_chars` | 超过此长度自动分段发送 | 1000 |
| `keep_markdown` | false=把 ``` 代码块转纯文本（QQ 显示更友好） | false |
| `debug` | 调试日志开关 | true |

## memory（长期记忆）

默认开启，本地 sqlite，零外部依赖。只存「他自己说过的稳定事实」和「明确让你记住的事」，不做全量对话存档。

| 字段 | 说明 | 默认 |
|------|------|------|
| `enabled` | 是否开启长期记忆 | true |
| `db_path` | 数据库位置，相对路径按程序目录解析 | memory.db |
| `max_items_per_user` | 每人记忆上限，超了淘汰「不重要 + 最久没用」的 | 300 |
| `inject_limit` | 每次最多注入几条（多了挤占上下文） | 8 |
| `llm_extract` | 除规则抽取外，再让大模型补抽 | true |
| `extract_every` | 每几轮触发一次 LLM 抽取 | 6 |

分区规则：单聊只写这个人的 `u:<openid>`；群聊写 `u:<openid>` + `g:<groupid>` 两份，所以她既记得「你」，也记得「这个群的事」。

触发写入的句式（规则层）：`我叫/我的名字`、`我在…上班/读书`、`我住在/家在`、`我今年…岁`、`我的生日`、`我喜欢/我爱/讨厌/受不了`、`我养了/家有`，以及任何以 `记住：` 开头的话（这类权重最高，永不淘汰）。疑问句不会误存。

管理：`Memory.forget(scope)` 清空某人记忆、`Memory.stats()` 看各分区条数。

## 人设

糍粑是**女友型**人设：黏人但懂分寸、有情绪也会自己修复、记得你说过的小事，同时保留完整技术能力（技术准确性永远优先）。角色核心与 `ai-her-plugin/lib/persona.js` 共享，渠道细则各自适配——QQ 侧多了群聊收敛与实时资料规则，插件侧多了 `WRITE_FILE` 协议。

写在 `assets/bot/persona.py`，由 `build_system_prompt(is_group)` 拼装：

| 改什么 | 改哪里 |
|--------|--------|
| 她对你的称呼 | 文件顶部 `NICKNAME = "宝"` |
| 性格 / 口吻 / 背景 / 口头禅 | `PERSONALITY` / `TONE` / `BACKGROUND` / `CATCHPHRASES` |
| 相处细则（生气方式、黏人尺度、群里怎么收敛…） | `EXTRA_LINES` |
| 硬性底线 | `BOUNDARIES` |

改完重启机器人生效。`EXTRA_LINES` 的优先级最高，想覆盖任何行为都在这里加一条即可。

