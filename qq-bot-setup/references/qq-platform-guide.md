# QQ 机器人创建指南（扫码快捷通道 + 完整版）

## 用脚本半自动抓取凭证

```bash
python scripts/auto_credentials.py --site qq --config <部署目录>/config.yaml
```

脚本打开扫码页，你扫码登录并点「创建机器人」后，**先点 AppSecret 的「复制」，再点 AppID 的「复制」**；脚本按规则自动识别（字母数字混合的较长串=AppSecret，纯数字=AppID）并写入配置。扫码这一步必须本人操作，无法代劳。

## 方式 A：扫码快捷通道（推荐，最快）

适用于个人快速体验，创建后立刻可用。

1. PC 浏览器打开：<https://q.qq.com/qqbot/openclaw/login.html>
2. 用**手机 QQ 扫码**登录（扫码的是你想作为机器人管理员的那个 QQ 号）。
3. 点击「创建机器人」——点击后**立刻创建成功**，机器人会给你的 QQ 发一条成功消息。
4. 头像、昵称、简介可自由修改。
5. **复制 AppID 和 AppSecret**：
   - AppID 是纯数字字符串；
   - AppSecret 通常只在创建时完整显示一次，立即复制保存。
6. 一个 QQ 号最多创建 5 个独立机器人。

限制：
- 快捷通道创建的机器人**仅创建人可用，暂时不支持拉入 QQ 群**。
- 适合单聊（C2C）场景验证；要群聊走方式 B。

## 方式 B：完整版开放平台（可用于群聊）

1. 打开 <https://q.qq.com>，用 QQ 账号或邮箱注册登录。
2. 完成**开发主体认证**（个人/企业/个体户；个人入口需姓名、身份证、实名手机一致）。
3. 创建机器人应用，拿到 AppID / AppSecret。
4. 在「机器人配置 / 事件订阅」里：
   - 接入方式选 **WebSocket**（本地单机无需公网 IP 和备案域名）；
   - 勾选 intents：`GROUP_AT_MESSAGE_CREATE`（群聊 @ 消息）、`C2C_MESSAGE_CREATE`（单聊）；
   - 若需群聊全量消息 `GROUP_MESSAGE_CREATE`，要单独申请「接收所有消息」权限。
5. 设置机器人服务范围（群/单聊），发布 link 场景或测试。

## 配置到本项目

机器人后端使用 QQ API v2 的 WebSocket 模式：
- token：`POST https://bots.qq.com/app/getAppAccessToken`（appId + clientSecret）
- 网关：`GET https://api.sgroup.qq.com/gateway`
- 鉴权头：`Authorization: QQBot <access_token>`
- intents 位：`1 << 25`（GROUP_AND_C2C）

本项目默认 `group_trigger: at`（群里只响应 @机器人），避免刷屏。群聊触发还可设为 `all`（需全量消息权限）或 `prefix`（前缀触发）。

> 注意：无论哪种方式，AppID/AppSecret 都只写入本地 `config.yaml`，不会上传到任何第三方。
