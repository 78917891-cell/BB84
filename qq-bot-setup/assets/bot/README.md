# 糍粑 · QQ 官方机器人

把「她」（糍粑人设 + DeepSeek）部署成 QQ 官方机器人，支持**群聊 @回复**和**单聊**，本地 Windows 常驻运行。走 QQ 官方开放平台 API v2 的 WebSocket 模式，**无需公网 IP、无需备案、无需内网穿透**。

---

## 一、它是什么

- **人设**：女友型——黏人但懂分寸、有情绪也会自己修复、记得你说过的小事，同时保留完整技术能力（技术准确性优先）。角色核心与 `ai-her-plugin/lib/persona.js` 一致，渠道细则各自适配。想改她怎么叫你，改 `persona.py` 顶部的 `NICKNAME`。
- **模型**：DeepSeek（`deepseek-chat`），带每用户独立会话记忆、限流、消息自动分段。
- **场景**：群聊里 @它才回复（可改成全量/前缀触发）、单聊直接对话。支持 `/清空` `/帮助` 指令。
- **联网**：问天气、新闻、股价等实时信息时，会自动先查再答（见 `websearch.py`）。
- **长期记忆**：默认开启，随对话自动记住你说过的事（名字、城市、职业、喜好、让你记住的话），跨会话跨天都在（见 `memory.py`，本地 sqlite，零依赖）。按人隔离，群里不会串号。
- **语音包**：可让它用语音回复你（见 `voice.py`，Edge TTS + silk，免费；也支持接云端声音克隆，用同款嗓音说话）。

---

## 二、从 0 开始部署（约 15 分钟）

### 第 1 步：注册 QQ 开放平台并创建机器人

1. 打开 <https://q.qq.com>，用 QQ 账号登录。
2. 完成**主体认证**（个人认证即可，需姓名+身份证+手机号实名一致）。
   - 未认证机器人只能加你是群主/管理员的群，且不能公开；个人认证足够自用。
3. 进入机器人管理端 → **创建机器人**，填昵称、简介、头像（避免"官方""侵权"字样）。
4. 创建完成后，在机器人详情页记下：
   - **AppID**
   - **AppSecret**（只显示一次，立即复制保存）

### 第 2 步：配置机器人

在机器人管理页完成：

1. **事件订阅与回调地址** → 连接方式选 **WebSocket**（本项目用这个，不需要公网）。
2. **服务范围**：把你要测试的群加进去（未认证时只能加你当群主/管理员的群）。
3. **内部体验号码**（可选）：加自己的 QQ，方便测试。
4. 如需群聊全量消息（`group_all_message: true`），要另外申请"接收所有消息"权限；**默认用 @触发更稳妥**。

### 第 3 步：填写配置

1. 双击运行 `1.首次安装.bat`——它会自动从模板生成 `config.yaml`（首次会弹记事本）。
2. 编辑 `config.yaml`，填入三处必填项：

```yaml
qq:
  app_id: "你的AppID"
  app_secret: "你的AppSecret"
deepseek:
  api_key: "你的DeepSeek-API-Key"
```

DeepSeek Key 在 <https://platform.deepseek.com/api_keys> 申请。

### 第 4 步：安装依赖并启动

1. 再次双击 `1.首次安装.bat`——这次会创建虚拟环境、装依赖（约 1-2 分钟）。
2. 双击 `2.启动机器人.bat`——看到「糍粑 QQ 机器人启动」日志即成功。
3. 把机器人拉进你的测试群，**@它说句话**，它会以糍粑的口吻回复。

> 关闭启动窗口即停止机器人。日志在 `logs/bot.log`。

### 第 5 步（可选）：开启语音包

想让它用语音回你，按下面做：

1. 在部署目录装两个包（不装则语音开关无效，聊天不受影响）：
   ```
   .venv\Scripts\python.exe -m pip install pysilk-mod edge-tts
   ```
2. 确认本机有 ffmpeg。不用单独装——装了 Agent Reach 就自带了（`~/.agent-reach/tools/ffmpeg/bin/ffmpeg.exe`），脚本会自动找到；也可以用 `pip install imageio-ffmpeg` 或系统 ffmpeg。
3. 在 `config.yaml` 里改：
   ```yaml
   voice:
     enabled: true
     backend: "edge"                 # edge=免费现成音色
     voice: "zh-CN-XiaoyiNeural"
     max_chars: 100
     send_text: true
   ```
4. 重启机器人。之后它会在文字回复后追加一条语音；纯代码回复和超长回复只发文字。

音色可选：`zh-CN-XiaoyiNeural`（活泼女声，默认）、`zh-CN-XiaoxiaoNeural`（温柔）、`zh-CN-liaoning-XiaobeiNeural`（东北话）、`zh-HK-HiuMaanNeural`（粤语）。

#### 想用「视频里那个人的声音」——声音克隆

DeepSeek 只有对话接口，没有 TTS 和声音克隆，所以只能是「大脑用 DeepSeek + 嗓子用别家」。本目录已带三段可直接上传的参考音频（`../voice_ref/`，16kHz 单声道，已归一到 -16 LUFS）。

1. 试听 `ref_01.wav`（首选）/ `ref_02.wav` / `ref_03.wav`，挑一段。
2. 上传到支持声音克隆的平台（MiniMax / 火山引擎 / 阿里云百炼等）做音色克隆，拿到 `voice_id`。
3. 改配置，把后端切到 `http`：
   ```yaml
   voice:
     enabled: true
     backend: "http"
     http:
       url: "平台接口地址"
       headers: { Authorization: "Bearer 你的Key" }
       body:
         text: "{text}"
         voice_setting: { voice_id: "你克隆的音色ID" }
       response_type: "json_hex"     # json_base64 / json_hex / json_url / binary
   ```
4. 重启。先用 `python test_voice.py` 跑一遍自检（21 项，含四种返回形态和 Edge 真实往返），全绿再上真 Key。

样本质量决定克隆效果：短视频音轨必然混 BGM，最好用手机在安静环境重录 20~30 秒覆盖 `ref_01.wav`。详见包内 `references/voice-clone-guide.md`。

#### 长期记忆（默认已开，无需配置）

她会自己记住你说过的事，不用你做什么：

- 想让她记牢某件事，直接说「**记住：我周三下午有课**」——这类记忆权重最高，永不淘汰。
- 记忆存在程序目录的 `memory.db`（sqlite）。删掉这个文件 = 全部忘掉；搬走它 = 把记忆搬到新机器。
- 只清某个人：`python -c "from memory import Memory; Memory({'db_path':'memory.db'}).forget('u:<openid>')"`。
- 想省 token：把 `memory.llm_extract` 设成 `false`，只走免费的规则抽取。
- 自检：`python test_memory.py`（28 项，覆盖抽取/去重/隔离/检索/淘汰/持久化）。

---

## 三、配置说明（config.yaml）

| 配置项 | 说明 |
|---|---|
| `qq.group_trigger` | `at`=群里@才回（推荐）；`all`=群里所有消息都回（需权限）；`prefix`=按前缀触发 |
| `qq.trigger_prefix` | prefix 模式的前缀，默认 `"糍粑 "` |
| `qq.intents.group_all_message` | 收群内全量消息，需在平台申请权限 |
| `bot.history_rounds` | 每用户保留的对话轮数，默认 10 |
| `bot.rate_limit_seconds` | 同一用户两次请求最小间隔，防刷屏 |
| `bot.max_chunk_chars` | 超长回复自动分段，默认 1000 字 |
| `bot.debug` | 调试日志开关 |
| `search.enabled` | 是否联网查实时信息（天气/新闻等） |
| `search.weather_city` | 天气城市，按你所在地改，默认深圳 |
| `memory.enabled` | 是否开启长期记忆（默认开，见第一节） |
| `memory.inject_limit` | 每次最多注入几条旧记忆，默认 8 |
| `memory.llm_extract` | 是否让大模型补抽记忆（默认开，每 6 轮一次） |
| `voice.enabled` | 是否用语音回复（见第 5 步） |
| `voice.backend` | `edge`=免费现成音色；`http`=云端克隆或自建 TTS |
| `voice.voice` | Edge 音色，默认 `zh-CN-XiaoyiNeural`（仅 backend=edge 生效） |

---

## 四、常见问题

**Q：启动报错"鉴权失败 / 401"**
A：检查 AppID、AppSecret 是否填错；确认开放平台里连接方式选的是 WebSocket；token 会自动刷新，若持续失败删掉 config.yaml 重新填。

**Q：群里 @它没反应**
A：①确认机器人已进群；②确认开放平台"服务范围"里加了这个群；③看 `logs/bot.log` 有没有收到 `GROUP_AT_MESSAGE_CREATE` 事件；④未认证机器人只能进你当群主的群。

**Q：收到事件但不回复**
A：看日志里的报错。多半是 DeepSeek Key 无效或余额不足（会打"网络或模型抽风"的兜底回复）。

**Q：单聊不回复**
A：确认 `intents.c2c_message: true`，且开放平台开启了单聊事件。

**Q：消息被截断/发不出去**
A：调小 `bot.max_chunk_chars`；群消息被动回复 60 分钟内每条最多回 5 次（管理员 50 次），超了要等。

**Q：想长期后台运行（关掉窗口也跑）**
A：双击 `3.后台静默启动.vbs`，机器人会无窗口在后台跑，日志照常写入 `logs/bot.log`；要停就双击 `4.停止后台.vbs`。开机自启可把 `3.后台静默启动.vbs` 的快捷方式放进「启动」文件夹（`Win+R` 输入 `shell:startup`）。

---

## 五、与浏览器插件的关系

本项目的 `persona.py` 与插件的 `lib/persona.js` 共享同一套「角色核心」（性格 / 口吻 / 背景 / 口头禅 / 边界），改动时两处一起改；渠道细则各自适配——QQ 侧多群聊收敛与实时资料规则，插件侧多 `WRITE_FILE` 协议。

> 注意：QQ 场景没有文件读写能力，插件里的 `WRITE_FILE` 写回协议在这里换成了"用 ``` 代码块包裹、方便复制"。角色核心相同，渠道细则不同。

---

## 六、文件结构

```
qq-cichi-bot/
├── config.yaml.example   # 配置模板
├── config.yaml           # 你的实际配置（gitignore，不提交）
├── requirements.txt      # 依赖
├── persona.py            # 糍粑人设（女友型，与插件共享角色核心）
├── brain.py              # DeepSeek 对话 + 会话管理
├── qq_bot.py             # QQ 官方 WebSocket 客户端
├── main.py               # 主入口
├── 1.首次安装.bat         # 建环境+装依赖
├── 2.启动机器人.bat       # 启动（有窗口，调试用）
├── 3.后台静默启动.vbs      # 后台无窗口运行
├── 4.停止后台.vbs          # 停止后台进程
└── logs/bot.log          # 运行日志
```
