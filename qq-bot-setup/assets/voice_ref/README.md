# 声音克隆参考音频（voice_ref）

这个目录放的是**给声音克隆用的参考音频**。机器人自己的发声走 `voice.py`（Edge TTS 或云端克隆接口），而克隆接口需要一段"这个人的声音"作为样本——本目录就是那段样本。

## 里面有什么

| 文件 | 时长 | 规格 | 说明 |
| --- | --- | --- | --- |
| `ref_01.wav` | 9.6s | 16kHz / 单声道 / 16bit | **首选**，原始电平最高、人声最突出 |
| `ref_02.wav` | 8.2s | 同上 | 备选，响度最贴合 -16 LUFS |
| `ref_03.wav` | 9.0s | 同上 | 备选，取自连续区间的中段 |
| `manifest.json` | — | — | 每段的时间窗、来源文件、实测响度/峰值 |

三段都做了 `highpass=70Hz` 去低频轰鸣 + `loudnorm -16 LUFS` 响度归一，峰值控制在 -1.5 ~ -2.5 dB，没有削波。

## 用法

1. 先试听三段，挑出**音色最符合你想要的那一个**（务必只用一个说话人的样本）。
2. 上传到克隆平台，得到一个 `voice_id`（各平台叫法不同：voice_id / speaker_id / timbre_id）。
3. 把 `voice_id` 填进 `config.yaml` 的 `voice` 段，并把 `voice.backend` 改成对应平台。

具体平台要求、字段名与接入方式见 `references/voice-clone-guide.md`。

## 用自己的录音替换（推荐）

视频音轨里必然混着 BGM，克隆出来的音色会发闷、带乐感。**最有效的提升就是换一段干净录音**：

- 安静房间，手机贴近嘴 20~30cm，正常语速朗读 20~30 秒，不要背景音乐、不要其他人说话。
- 直接存成 `ref_01.wav` 覆盖本文件，或另存新名字再改 `config.yaml` 里的路径。

本目录下的三段可以留作占位，也可以删掉。

## 从视频里重新取段

包里带了一个自动取段脚本（自动找最长无静音区间、居中裁剪、统一响度）：

```bash
python scripts/prepare_voice_ref.py "D:/videos/某个视频.mp4" --out assets/voice_ref/ref_01.wav
```

也可以手动指定区间：

```bash
python scripts/prepare_voice_ref.py "D:/videos/某个视频.mp4" --start 6.8 --duration 8.2 --out assets/voice_ref/ref_01.wav
```

脚本复用 `voice.py` 同一套 ffmpeg 查找逻辑（优先 `imageio-ffmpeg`，其次系统 `ffmpeg`，再退到 Agent Reach 自带的 ffmpeg），不需要额外装依赖。

## 规格速查

各家克隆接口的硬性下限大致是：**采样率 ≥16kHz、单声道、时长 10s~5min、wav/mp3/m4a**。本目录的样本卡在 8~10 秒，正好够最低门槛但偏短；如果平台支持，建议换 20~30 秒的录音，克隆稳定度会明显提升。
