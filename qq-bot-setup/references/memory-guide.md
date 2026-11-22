# 长期记忆

机器人有两种记忆方案，**默认已经用上第一种，不需要你做任何事**。

| | 内置轻量记忆（默认） | TencentDB Agent Memory（本文后半） |
|---|---|---|
| 依赖 | 无，标准库 sqlite3 | Docker + 四端口 + 常驻 proxy |
| 装法 | 自带，`memory.db` 自动创建 | 三容器，交互式启栈 |
| 记什么 | 他自己说过的稳定事实 + `记住：` 指令 | 对话、文档、代码，提炼成四类资产 |
| 隔离 | 按 openid 分区，跨群共享、群内互不串 | Team / Agent / Task 三级 |
| 谁用 | 一个 QQ 机器人 | 多个 Agent 共享同一份项目记忆 |
| 成本 | 零 | 一个 LLM Key + 磁盘 + 常驻进程 |

**先确认默认那套是否够用**：她记不住你叫什么、忘了你说过爱吃辣——这些内置记忆都能解决。只有当你要「WorkBuddy、Claude Code、Codex 同时写一个仓库，共享同一份踩坑经验」时，才需要往下看。

内置记忆的字段与行为见 `references/config-reference.md` 的 `memory` 段；源码是 `assets/bot/memory.py`，测试 `python test_memory.py`。

---

# TencentDB Agent Memory（可选，重型）

给 Agent 加**跨会话、跨 Agent 的团队记忆**。它不是一个 pip 包，而是三容器栈，靠 Docker 起。

- 仓库：<https://github.com/TencentCloud/TencentDB-Agent-Memory>（默认分支是 `feat/server_team`，**不是 `main`**）
- 体量：约 64 MB 源码，TypeScript，31k stars
- 许可：README 标 MIT，但 GitHub 接口识别为 `NOASSERTION`（LICENSE 文本非标准），商用前建议自己核一遍

它把对话、文档、代码提炼成四类可复用资产：Chat Memory、Skill、LLM-Wiki、Code-Graph，并支持多个 Agent 共用。

## 硬性前提：Docker

`deploy/global-images/start-all.sh` 起的是 **memory-core + memory-hub + proxy 三个容器**。没有 Docker 就没有任何降级方案——这不是能靠 pip 装出来的东西。

其余要求：Node.js ≥ 22.16、git、8 GB 以上空闲磁盘、一个 OpenAI 兼容或 Anthropic 的 LLM Key（内部提炼记忆、以及 proxy 转发上游都要用）。

## 三个端口别记错

| 服务 | 端口 | 用途 |
|------|------|------|
| Memory Core | 8420 | 记忆读写、鉴权、skill/RAG 数据面 |
| Panel UI | 8125 | 网页控制台（建 Team / Agent / Task） |
| Knowledge | 8424 | Wiki / Code-Graph 服务 |
| Proxy | 8096 | LLM 请求代理，同时支持 Anthropic 与 OpenAI 协议 |

存储默认是容器卷里的 sqlite + sqlite-vec，零额外依赖。MongoDB 后端是实验特性，官方不建议当生产默认，且**切换后端不会迁移数据**。

## 怎么装

```bash
python scripts/install_memory.py --check     # 先体检，缺什么会逐条列出
python scripts/install_memory.py --fetch     # 稀疏拉取 deploy/ 与 agents/（约几 MB，不是 64MB 全量）
```

体检和拉取都能自动化，**启动不能**：`start-all.sh` 是交互式的，会逐个让你填 memory 组与 proxy 组的 LLM 地址、Key、模型名，并当场探活。所以最后一步得你自己执行：

```bash
cd ~/.memory-tencentdb/deploy/global-images
./start-all.sh        # Windows 用 Git Bash 跑
```

起成功后脚本会把随机生成的 `user_key`（形如 `sk-mem-...`）写进 `deploy/global-images/.admin-key`，并打印一段可直接使用的接入配置。

常用命令：`./verify.sh` 只体检不起容器（加 `--skip-llm` 跳过探活）、`./stop-all.sh` 停容器保数据、`./stop-all.sh --purge` 连数据一起清。

## 接进 WorkBuddy

改 `~/.workbuddy/models.json`，往数组里加一项：

```json
{
  "id": "claude-opus-4.7-1m",
  "name": "mem-proxy",
  "vendor": "Custom",
  "url": "http://127.0.0.1:8096/workbuddy/default",
  "apiKey": "sk-mem-你的user_key",
  "supportsToolCall": true,
  "supportsImages": false,
  "supportsReasoning": false,
  "useCustomProtocol": false
}
```

`id` 必须填 Proxy 上游实际支持的模型名（填错会 404 或 400）；`url` 里的 `default` 是 memory 实例 ID。配完在模型选择器的「自定义模型」里选它，然后按 Team → Agent → Task 初始化会话。

想跳过交互式选择，直接在请求里带 `x-tdai-team-id` / `x-tdai-agent-id` / `x-tdai-task-id` 三个 header 即可；不带则**静默透传**——不报错、也不注入记忆，这是官方有意的设计。

## 接进糍粑（QQ 机器人）

思路是把机器人的 LLM 出口指到 proxy，让 proxy 负责转发 + 注入记忆：

```yaml
deepseek:
  api_key: "sk-mem-你的user_key"
  base_url: "http://127.0.0.1:8096"
  model: "deepseek-chat"
```

> ⚠️ **这条未实测**。proxy 的路径前缀是按不同客户端适配器分的（`/codex/...`、`/workbuddy/...` 等），机器人走的是标准 OpenAI Chat Completions，需要对照 `agents/` 里最接近的适配器确认实际路径。建议先把 WorkBuddy 侧跑通、确认 proxy 能正常转发，再改机器人，避免两头同时排查。

接了之后的变化：现在是 `bot.history_rounds`（默认 10 轮）的滑动窗口，超出就忘；接上 memory 后是跨会话、跨天的长期记忆，她能记住你上周说过的事。

代价也要清楚：**所有对话内容都会经过本地 proxy，再转发到你配的上游 LLM**。如果只是想让她记住几个偏好，写进 `persona.py` 的成本远低于起三个容器。

## 排错

| 现象 | 原因 | 处理 |
|------|------|------|
| `start-all.sh` 卡在探活 | LLM 地址/Key/模型名任一不对 | 它会要求重填，按提示改；先用 `./verify.sh --skip-llm` 确认容器能起 |
| 8420 连不上 | 容器没起来，或端口被占 | `docker ps` 看容器状态；体检脚本会检查这四个端口 |
| `/health` 返回 `degraded` | 部分子服务未就绪 | 等一两分钟；仍如此看容器日志 |
| Panel「Not enabled」 | 分析用 ClickHouse 未配 | `curl /v3/analytics/config` 确认，未配不影响记忆读写 |
| Wiki / CodeGraph 一直不是 ready | 两者是**异步构建** | 等；大仓库耗时更久 |
| 换存储后端后数据没了 | sqlite 与 MongoDB 数据目录独立，不迁移 | 切换前手动备份 |
| 面板登录不进去 | 没拿到 user_key | 看 `.admin-key`，或用 `--print-config` 读出来 |

## 一句实话

这套东西是给**多人、多 Agent、长期项目**用的团队级记忆中枢。单人用一个 QQ 机器人，它带来的复杂度（Docker、四端口、一个 proxy 常驻、所有流量绕行）明显高于收益——那种场景用内置记忆就够了。

真正值得用的场景是：你同时用 WorkBuddy、Claude Code、Codex 写同一个项目，希望它们共享同一份「这个项目怎么跑、有哪些坑」的记忆。
