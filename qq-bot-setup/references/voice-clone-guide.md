# 声音克隆接入指南

目标：让机器人用**和视频里同一个人的声音**说话，而不是微软的现成音色。

## 先纠正一个前提：DeepSeek 不做语音

DeepSeek 开放平台只提供对话/推理接口（`/chat/completions`），**没有 TTS，也没有声音克隆**。所以"用 DeepSeek 做克隆"这条路不存在。

唯一可行的组合是：**大脑用 DeepSeek，嗓子用另一家**。本项目的 `voice.py` 就是按这个结构写的——`brain.py` 负责说话的内容，`voice.py` 负责把文字变声音，两者通过 `voice.backend` 解耦。

## 三条路线

| 路线 | 成本 | 门槛 | 像不像"你" | 适合 |
|------|------|------|-----------|------|
| Edge TTS 现成音色 | 免费 | 无需注册 | 不像（是微软的音色） | 只要"有声音"就行 |
| 云端声音克隆 | 按字符计费；克隆音色多为一次性或按月 | 实名认证 + API Key | 高（几秒到几十秒样本） | 要"同款声音"，能联网 |
| 本地克隆（GPT-SoVITS / IndexTTS） | 电费 | 需 NVIDIA GPU + 约 5GB 依赖 | 最高，还能继续微调 | 离线、隐私、长期不花钱 |

本机条件已经摸过底：RTX 5060 Laptop 8GB 显存跑本地克隆够用，但当前**没有可复用的 PyTorch**，且实测网速约 40KB/s，装齐依赖要几十小时——短期内不现实。所以先走云端。

## 云端克隆：通用四步

不同平台按钮叫法不同（"音色克隆"/"声音复刻"/"Voice Clone"），流程一致：

1. **选样本**：试听 `assets/voice_ref/ref_01.wav ~ ref_03.wav`，挑音色最符合的一段（只用一个人的声音）。
2. **上传克隆**：在平台的音色克隆页面上传，勾选"已获得说话人授权"之类的确认。
3. **等训练完成**：多数平台几秒到几分钟出结果，返回一个 `voice_id`（火山叫 `speaker_id`，百炼叫 `voice` 或 `timbre`）。
4. **填进配置**：把 `voice_id` 与接口地址写进 `config.yaml` 的 `voice.http` 段，`backend` 改成 `http`。

## 平台与 `response_type` 的对应

`voice.py` 的 http 后端支持四种返回形态，选错会报"找不到音频字段"或合成出杂音：

| 平台 | 常见 `response_type` | 音频字段 |
|------|---------------------|---------|
| MiniMax（海螺） | `json_hex` | `data.audio`（十六进制字符串） |
| 阿里云百炼 CosyVoice | `json_url` | `data.audio_url` 或 `output.audio_url` |
| 火山引擎 / 豆包语音 | `binary` 或 `json_base64` | 视接口，通常 `data` |
| 自建 GPT-SoVITS / api_v2 | `binary` 或 `json_base64` | `data` 或响应体本身 |

具体字段名与参数**以各家当期官方文档为准**，本表只做归类，不保证长期有效。

## 配置示例（以 MiniMax 形状为例）

```yaml
voice:
  enabled: true
  backend: "http"
  max_chars: 100
  send_text: true
  http:
    url: "https://api.minimax.chat/v1/t2a_v2?GroupId=你的GroupId"
    method: "POST"
    headers:
      Authorization: "Bearer 你的APIKey"
      Content-Type: "application/json"
    body:
      model: "speech-01-turbo"
      text: "{text}"
      stream: false
      voice_setting:
        voice_id: "你克隆出来的音色ID"
        speed: 1.0
    response_type: "json_hex"
    audio_key: "data.audio"
    timeout: 30
```

要点：

- `body` 里的字符串支持 `{text}` 占位符，会递归替换成要朗读的正文；嵌套结构（如 `voice_setting`）同样支持。
- `headers` 里的值不做占位替换，Key 直接写死或用环境变量自行拼。
- 返回体里音频字段的路径用点号表示层级，数组下标写数字，如 `data.list.0.audio`。

## 代码上的接入点（已实现）

`voice.py` 里 TTS 只占一个函数，克隆后端只是替换它：

```
文字 → _tts_to_mp3()  ── edge: edge_tts.Communicate().save()
                      └─ http: _http_to_mp3()  urllib 请求 + 解析四种返回
     → ffmpeg 转 PCM(24k 单声道) → pysilk 编码 → msg_type=7 富媒体发送
```

后半段（ffmpeg → silk → 上传发送）与后端无关，所以**换嗓子不影响已经验证过的发送链路**。

## 验证

```bash
python test_voice.py
```

它会起一个本地 mock 服务，把四种返回形态各跑一遍，再跑一次真实的 Edge TTS 往返。全绿输出 `21/21 PASS` 说明管线正常；此时只要把 `config.yaml` 的 url/Key/voice_id 换成真的，就能出声。

## 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 401 / 403 | 缺 `Authorization`，或 GroupId 没带在 URL 上 | 对照平台鉴权文档补 `headers` / `url` 参数 |
| 合成出来是刺耳杂音 | `response_type` 选错，把 hex 当 base64 解了 | 改成 `json_hex` |
| "响应里没找到音频字段" | `audio_key` 路径不对 | 把接口原始返回贴出来，逐层核对 |
| 返回 200 但没声音 | 克隆音色还在训练中 | 等平台状态变成"可用"再试 |
| 语音很长、发得慢 | `max_chars` 太大 | 调到 60~100，长回复只发文字 |
| 克隆出来不像 | 样本混了 BGM 或多人 | 换干净的单人录音，20~30 秒 |
| 合成报错但机器人正常 | 语音失败自动降级为纯文字 | 看日志里的 `语音合成失败` 一行 |

## 关于样本质量

`assets/voice_ref/` 里的三段取自短视频音轨，LRA 只有 0.5~0.8（被强压缩过），人声下面始终垫着 BGM。这类样本克隆出来会偏闷、带一点乐感。

**最有效的改进是换一段干净录音**：安静房间、手机距嘴 20~30cm、正常语速读 20~30 秒、不要背景音乐和其他人声。存成 `ref_01.wav` 覆盖即可，不用改代码。
