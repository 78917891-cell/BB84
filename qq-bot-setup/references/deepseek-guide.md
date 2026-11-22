# DeepSeek API Key 获取指南

## 最省事的方式：脚本自动抓取

```bash
python scripts/auto_credentials.py --site deepseek --config <部署目录>/config.yaml
```

脚本自动打开 API Keys 页面；你登录后点「创建 API Key」→「复制」，脚本监听剪贴板自动识别 `sk-` 开头的字符串并写入配置。**你只需要登录和点一次复制**，不用手动粘贴或改文件。

> 为什么不能全自动：Key 必须登录账号才能创建，登录有手机验证码与人机验证，平台也没有提供「程序化创建 Key」的接口。任何声称全自动的方案都要绕过验证或使用他人共享 Key，不安全也不合规。

## 手动步骤（想自己操作时）

1. 打开 <https://platform.deepseek.com/api_keys>（国内可直接访问，无需翻墙）。
2. 注册 / 登录账号（支持手机号）。
3. 进入「API Keys」页面，点「创建 API Key」。
4. 给 Key 起个名字（如 `qq-bot`），创建后立即复制完整字符串。
   - 形如 `sk-xxxxxxxxxxxxxxxxxxxxxxxx`；
   - **完整 Key 只在创建时显示一次**，之后只能看到前缀，务必当场复制。
5. 新账号通常有少量免费额度；用完后在「充值」里按需充值。

## 在本项目中的用法

Key 只写入部署目录的 `config.yaml`：

```yaml
deepseek:
  api_key: "sk-你的完整Key"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"        # 通用对话，便宜快速
  # model: "deepseek-reasoner"  # 深度思考，更慢更贵
  temperature: 0.7
  max_tokens: 2048
  timeout: 60
```

- 默认模型 `deepseek-chat` 适合闲聊与问答；复杂推理可换 `deepseek-reasoner`。
- 若用兼容 OpenAI 的第三方中转，改 `base_url` 为对应地址（需含 https://）。
- Key 泄露后立即在该页面删除重建。

## 验证

部署后运行：

```bash
python scripts/verify.py --config <部署目录>/config.yaml
```

第一项 `[PASS] DeepSeek Key` 即表示 Key 有效、可正常调用。
