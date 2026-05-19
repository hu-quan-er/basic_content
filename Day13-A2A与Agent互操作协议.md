# Day 13 — A2A 与 Agent 互操作协议

> 目标：理解为什么需要 Agent 互操作协议、A2A / MCP / ACP 等主流方案的设计差异、何时该用、怎么落地。这是 2025 年 Agent 生态级的关键演进。

---

## 一、为什么需要 Agent 互操作协议

### 1.1 当前 Agent 生态的碎片化问题
- 每家公司、每个团队都在自己造 Agent
- Agent 间无法对话 — 类比早期"每个 IM 都封闭"的年代
- 工具复用难（已被 MCP 部分解决）
- **跨组织 / 跨厂商协作几乎为零**

### 1.2 真实的跨 Agent 需求
- **企业内部**：HR Agent 要叫 IT Agent 帮新员工开账号 → IT Agent 又要叫安全 Agent 审批
- **B2B**：客户的 Agent 自动跟你公司的 Agent 谈合同 / 下单
- **C2B**：用户的 personal AI 帮他比价 / 预订，调用各厂家的 Agent
- **生态市场**：Agent 互相调用就像今天的 SaaS API 互调

### 1.3 协议要解决的 5 个问题
1. **发现（Discovery）**：怎么找到合适的 Agent？
2. **能力描述（Capability）**：Agent 能做什么？
3. **通信（Communication）**：消息格式怎么定？
4. **状态管理（Stateful Interaction）**：长任务、多轮怎么协作？
5. **安全（Auth/Security）**：身份、授权、审计

### 1.4 MCP 与 A2A 的本质区别（核心）

| 维度 | MCP | A2A |
|------|-----|-----|
| 范式 | 工具接入 | Agent 协作 |
| 关系 | Client-Server（不对等） | Peer-to-Peer（对等） |
| 调用方 | LLM 应用 | Agent |
| 被调用方 | 工具 / 资源 / 提示 | 另一个 Agent（自己也有 LLM、状态） |
| 状态 | 短期、跟随调用 | 长期任务、生命周期 |
| 智能 | 工具是"哑"的 | Agent 是"活"的，会主动反馈、要求澄清 |
| 类比 | USB-C（设备 → 外设） | Email/HTTP（人 → 人） |

**经典比喻**：
- MCP 是 Agent 的"手"（伸出去抓工具）
- A2A 是 Agent 的"嘴"（开口跟别的 Agent 说话）
- 两者**互补**，不替代

---

## 二、A2A（Agent-to-Agent Protocol）

### 2.1 来源与定位
- **Google 主导**，2025 年 4 月发布开放规范
- **联盟支持**：超过 50 家企业（Atlassian、PayPal、Salesforce、SAP、Workday、LangChain、LangGraph、Cohere 等）
- **开源**：协议 + Python/TypeScript/Java/.NET SDK
- **核心定位**：让任意两个 Agent 不论实现方式、不论厂商，都能协作

### 2.2 设计原则（Google 官方）

1. **拥抱 Agent 本质**：Agent 是自主的、状态的、协作的
2. **基于现有标准**：HTTP + JSON-RPC 2.0 + SSE（不重新发明轮子）
3. **默认安全**：企业级 Auth 一等公民
4. **支持长时间任务**：分钟、小时、天级的协作
5. **跨模态**：文本、图像、音频、视频、流
6. **不暴露内部**：Agent 之间不需要共享 prompt / tools / memory

### 2.3 核心概念

#### Agent Card（能力描述卡）
- 每个 Agent 必须暴露一份 JSON 元数据
- 位置约定：`https://example.com/.well-known/agent.json`
- 内容：
```json
{
  "name": "Travel Booking Agent",
  "description": "Books flights, hotels, and rental cars",
  "url": "https://agent.example.com/a2a",
  "version": "1.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "authentication": {
    "schemes": ["oauth2", "apikey"]
  },
  "defaultInputModes": ["text", "file"],
  "defaultOutputModes": ["text"],
  "skills": [
    {
      "id": "book_flight",
      "name": "Book a flight",
      "description": "Search and book flights",
      "tags": ["travel", "flights"],
      "examples": ["Book a flight from SFO to JFK next Monday"]
    }
  ]
}
```
- **意义**：发现协议 + 能力公告 + 认证要求

#### Task（任务，核心抽象）
- A2A 的**基本工作单元**
- 是有**生命周期的对象**，不是一次性 RPC
- 状态机：
```
submitted → working → completed
           ↓
         input-required → working
           ↓
         canceled / failed
```

**关键字段**：
- `id`：任务 ID
- `state`：当前状态
- `messages`：历史消息列表
- `artifacts`：产生的工件
- `metadata`：附加信息

#### Message（消息）
- Agent 间的通信单位
- 由多个 `Part` 组成（multipart 思想）
- Part 类型：
  - **TextPart**：纯文本
  - **FilePart**：文件（URI 或 base64）
  - **DataPart**：结构化 JSON 数据

例：
```json
{
  "role": "user",
  "parts": [
    {"type": "text", "text": "Help me book a hotel in NYC"},
    {"type": "data", "data": {"check_in": "2025-06-01", "check_out": "2025-06-05"}}
  ]
}
```

#### Artifact（工件）
- Agent 产生的**结果**（与消息区分）
- 比如：报告文件、生成的图片、查询结果
- 用 Part 表达，可流式产生

### 2.4 协议层：JSON-RPC 2.0 over HTTP

**核心方法**：

| 方法 | 含义 |
|------|------|
| `tasks/send` | 提交任务（同步等结果） |
| `tasks/sendSubscribe` | 提交任务并订阅 SSE 流式更新 |
| `tasks/get` | 查询任务状态 |
| `tasks/cancel` | 取消任务 |
| `tasks/pushNotification/set` | 设置 webhook 用于异步通知 |
| `tasks/resubscribe` | 重连流式订阅 |

**举例：发送任务**
```http
POST https://agent.example.com/a2a
Authorization: Bearer ...

{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "id": "req-1",
  "params": {
    "id": "task-001",
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Book SFO→JFK Mon"}]
    }
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "result": {
    "id": "task-001",
    "state": "completed",
    "messages": [...],
    "artifacts": [{"parts": [{"type": "text", "text": "Booking confirmed: ..."}]}]
  }
}
```

### 2.5 三种交互模式

#### 同步（Synchronous）
- 简单 `tasks/send` → 等返回
- 适合：快任务（< 30s）
- 类似 HTTP 请求响应

#### 流式（Streaming via SSE）
- `tasks/sendSubscribe` → 服务端 Server-Sent Events 推送更新
- 适合：长任务可见进度、Agent thinking 流式
- 客户端实时看到 status / artifact 更新

#### 异步推送（Push Notifications）
- `tasks/pushNotification/set` 注册 webhook
- 任务状态变化时服务端 POST 到 webhook
- 适合：超长任务（小时级）、不能保持连接的场景

### 2.6 Multi-turn 与 `input-required`

A2A 支持**任务中途要求补充输入**：

```
Agent A 发任务 → Agent B
B 处理中发现需要更多信息
B 把任务状态设为 "input-required"
B 在消息中说明需要什么
A 看到状态 → 补充信息（同任务 ID 继续 send）
B 继续 "working" → 最终 "completed"
```

**关键**：同一 `task.id` 多轮交互，状态保持。这是 A2A 与简单 RPC 的本质区别。

### 2.7 安全模型

**身份认证**：
- OAuth 2.0（推荐）
- API Key
- mTLS
- 自定义 scheme

**授权**：
- Scope-based（per-skill 授权）
- 调用方需在 Agent Card 中声明的 auth scheme 完成认证

**审计**：
- 协议层不强制，但 SDK 提供 trace ID 透传
- 跨 Agent 链路可串起来

**Opaque 设计**：
- Agent 之间**不共享 prompt / context / memory**
- 防止 IP 泄露、防止 indirect injection 跨 Agent 传染
- 每个 Agent 是黑盒（A 只看 B 输出，不看 B 内部）

### 2.8 与 MCP 的协作

A2A 不替代 MCP，反而**经常组合使用**：

```
[Agent A]
   ├─ MCP server: file tools             ← A 用 MCP 调本地工具
   ├─ MCP server: database
   └─ A2A client → calls [Agent B]      ← A 通过 A2A 调远程 Agent
                          ├─ MCP server: payment API
                          └─ A2A client → calls [Agent C]
```

**Anthropic 与 Google 也在协调**：MCP 处理"LLM 与工具"，A2A 处理"Agent 与 Agent"，定位不冲突。

---

## 三、其他协议方案

### 3.1 ACP（Agent Communication Protocol）— IBM
- IBM 推出，BeeAI / agent.bee.ai 项目核心
- 也是基于 REST 的 Agent 间通信
- 强调 **stateless** 设计（每次调用不依赖之前状态）
- 与 A2A 思路相似但更轻量
- 现状：与 A2A 在协议层有重合，未来可能融合
- IBM 也是 A2A 联盟成员

### 3.2 LangChain Agent Protocol（早期）
- LangChain 在 A2A 之前的尝试
- 偏 LangChain 生态内部使用
- A2A 出来后向 A2A 靠拢

### 3.3 OpenAI 的方案
- 目前没有公开的 Agent 间协议
- 内部用 Agents SDK + Handoff
- OpenAI 也是 A2A 联盟早期未加入者，但生态压力下未来可能支持

### 3.4 AGNTCY（联盟）
- 由 Cisco、LangChain、Galileo 等发起
- 目标：定义 Agent 全栈标准（不只通信，还含身份、可观测、安全）
- 与 A2A 互补：A2A 是协议、AGNTCY 是更宏观的标准化运动

### 3.5 NLIP（Natural Language Interaction Protocol）
- IEEE-style 提案
- 强调用自然语言作为 Agent 间通信媒介
- 早期、理论性强

### 3.6 协议对比矩阵

| 维度 | MCP | A2A | ACP | NLIP |
|------|-----|-----|-----|------|
| 主导 | Anthropic | Google + 50+ 厂商 | IBM | IEEE 提案 |
| 范式 | Client-Server | Peer Agent | Peer Agent | 自然语言 |
| 状态 | 短期 | 长期 Task | 多偏 stateless | NA |
| 流式 | 部分 | SSE 一等公民 | 是 | NA |
| 多模态 | 部分 | 是 | 是 | NA |
| 成熟度 | 高（落地多） | 中（增长快） | 早期 | 提案 |
| 推荐场景 | LLM ↔ 工具 | Agent ↔ Agent | 类似 A2A 但更轻 | 研究 |

---

## 四、典型协作模式（设计模式）

### 4.1 Agent-as-a-Service
- 每个 Agent 暴露 A2A endpoint，成为可被调用的"服务"
- 类比微服务化
- 客户端可以是其他 Agent / 应用 / 用户 UI

### 4.2 Supervisor-Worker（跨组织版）
- 主 Agent 在自家
- Worker Agent 来自外部供应商（差旅、报销、IT 等）
- 主 Agent 通过 A2A 把子任务派出去

### 4.3 Agent Marketplace
- 用户向公开市场发 task
- 多个 Agent 应答（"我能做"+ 报价）
- 选优中标
- 类比 Uber for AI

### 4.4 Federated Agents
- 多组织各自的 Agent 通过 A2A 协作
- 例：供应链中买卖双方各自 Agent 谈合同
- 数据不出本组织，结果交换

### 4.5 Personal AI ↔ Service Agents
- 用户的 personal AI 代为操作
- 调用各家服务的 Agent（餐厅、银行、医院）
- 类比"个人 AI 助手 = 你的代理律师"

### 4.6 Hierarchical Pipeline
- 上下游链式：Sales Agent → Pricing Agent → Inventory Agent → Shipping Agent
- 每一步明确边界、明确数据交换

---

## 五、A2A 工程实战要点

### 5.1 实现一个 A2A Server（伪代码）

```python
# 简化骨架
from a2a_sdk import AgentServer, Skill

class TravelAgent(AgentServer):
    agent_card = {
        "name": "Travel Agent",
        "skills": [
            Skill(id="book_flight", description="Book flights"),
            Skill(id="book_hotel", description="Book hotels"),
        ],
        "capabilities": {"streaming": True},
        "authentication": {"schemes": ["oauth2"]},
    }

    async def handle_task(self, task, stream):
        msg = task.messages[-1]
        # 调用内部 LLM / 工具完成任务
        result = await self.llm.run(msg)

        # 流式产出更新
        await stream.update(state="working", message="Searching flights...")
        # ...
        await stream.complete(artifacts=[result_artifact])

server.run(host="0.0.0.0", port=8080)
```

**关键点**：
- 暴露 `.well-known/agent.json`
- 实现 `tasks/send`、`sendSubscribe`、`get`、`cancel`
- 内部仍然是你自己的 Agent 实现（LangGraph / 自研都行）
- A2A 只是协议层"皮肤"

### 5.2 调用方代码

```python
from a2a_sdk import A2AClient

client = A2AClient("https://travel.example.com/a2a", auth=oauth_token)
card = await client.fetch_agent_card()

task = await client.send_task(
    skill="book_flight",
    parts=[{"type":"text","text":"SFO to JFK on Monday"}],
)
async for event in client.subscribe(task.id):
    print(event.state, event.message)
```

### 5.3 长任务设计要点

- **使用 push notification**：避免长连接掉线
- **idempotency**：同 task.id 重发不会重复执行
- **超时与心跳**：Server 定期推 keep-alive update
- **可取消**：每个工作单元检查 cancel 标志

### 5.4 错误处理

A2A 用 JSON-RPC 标准错误码 + 业务错误：
- `-32700` Parse error
- `-32600` Invalid request
- `-32601` Method not found
- `-32602` Invalid params
- 业务错误：状态 → `failed` + error message

### 5.5 安全工程

- **认证**：OAuth flow 完整支持
- **数据脱敏**：跨组织时把 PII 抽出独立 channel
- **审计**：透传 `traceparent` (W3C Trace Context)
- **限流**：在 A2A endpoint 前加 gateway
- **Prompt Injection 防御**：把来自其他 Agent 的 message 视为 untrusted data（哪怕对方"看起来"是合作方）

### 5.6 可观测

- Trace：跨 Agent 链路用 OpenTelemetry
- Metrics：每个 skill 调用频次、成功率、延迟、cost
- 日志：完整 message + artifact，注意 PII

### 5.7 Agent Card 的发现机制

- **静态**：固定域名 `https://known.com/.well-known/agent.json`
- **目录服务**：未来可能有 Agent registry（类似 DNS）
- **OpenID-style**：动态发现 + 多 Agent 路由

---

## 六、高频面试题（含答案）

### Q1：A2A 和 MCP 是什么关系？为什么需要两个协议？

**答**：

**核心区别**：定位完全不同，互补不替代。

| 维度 | MCP | A2A |
|------|-----|-----|
| 解决问题 | LLM 接入工具 / 数据 | Agent 之间协作 |
| 通信对象 | LLM 应用 ↔ 工具服务器 | Agent ↔ Agent |
| 关系 | Client-Server，工具是被动的 | Peer-to-Peer，双方都是自主 Agent |
| 状态 | 短期，跟随调用 | 长期 Task，多轮、生命周期 |
| 智能 | 工具是"哑"接口 | 对方 Agent 有自己 LLM、记忆、决策 |
| 透明度 | 工具完全暴露给 LLM | Agent 内部对外不透明 |

**比喻**：
- MCP 是 Agent 的"手"（伸手抓工具）
- A2A 是 Agent 的"嘴"（开口跟别的 Agent 协商）

**为什么不合并成一个？**

1. **抽象层次不同**：工具调用是无状态函数，Agent 协作是有状态对话
2. **安全边界不同**：MCP 工具被 Agent 完全控制；A2A 对方 Agent 是黑盒、对等
3. **互操作语义不同**：调工具要尽快返回结果；调 Agent 可能要等几小时

**实战常组合**：
```
Agent A
  ├─ MCP servers → local tools
  └─ A2A client → remote Agent B (B 内部也用 MCP)
```

**面试加分**：提到 Anthropic 和 Google 在协议设计上明确**互补定位**，没有竞争关系。

---

### Q2：A2A 的核心抽象是什么？为什么设计成 Task？

**答**：

**核心抽象**：**Task**（任务对象）。

**为什么不直接 RPC**：

如果只是 RPC（"调一次返一次"），不足以表达 Agent 协作：
1. **长任务**：可能跑几小时甚至几天
2. **多轮交互**：中途可能要求补充信息（input-required）
3. **流式更新**：客户端要看进度
4. **可取消**：长任务必须能中止
5. **状态持久化**：服务方需要管理 task lifecycle

**Task 的关键特性**：
- 有 ID（可重连、可查询）
- 有状态机（submitted / working / input-required / completed / failed / canceled）
- 累积消息历史
- 产出 Artifacts
- 支持 push notification

**举例**：
- 调用 "Book travel Agent" 任务
  - 启动 → working
  - "需要您的护照信息" → input-required
  - 用户补充 → working
  - "等待支付确认" → working
  - completed + artifact 是预订确认单

这种范式 **HTTP RPC 表达不了**，必须用 Task 抽象。

**类比**：
- 像 Workflow Orchestrator（Temporal / Airflow）的 Job
- 但单位更细 + 多了多轮人机协作

---

### Q3：A2A 的发现机制是什么？

**答**：

**核心机制**：**Agent Card** + well-known URL。

**约定**：每个支持 A2A 的 Agent 在域名根目录暴露：
```
https://your-agent.com/.well-known/agent.json
```

**Agent Card 内容**：
- 基础信息（name、description、version）
- A2A endpoint URL
- 认证方案（OAuth、API Key、mTLS）
- 能力（streaming、pushNotification、stateTransitionHistory）
- 支持的输入输出模态
- **Skills 列表**（带描述、tags、examples）

**为什么用 well-known URL**：
- 跟 OAuth、OpenID、ACME 等成熟协议同思路
- 不需要中心注册中心，去中心化
- 简单标准，无依赖

**发现流程**：
```
1. 调用方拿到 Agent URL
2. GET {url}/.well-known/agent.json
3. 解析能力与认证要求
4. 完成 auth
5. POST {url}/a2a 发起 task
```

**未来演进**：
- Agent registry / marketplace（类似 npm registry）
- 按能力 search（用 LLM 语义匹配）
- 信任评分（评估 Agent 可靠性）

**面试加分**：
- 提到这与 MCP 不同（MCP 一般是本地启动或显式配置）
- 提到 Agent Card 既是"能力公告"也是"合同"
- 提到当前生态早期（无注册中心，但有公开 Agent 目录如 a2aprotocol.ai）

---

### Q4：A2A 的安全模型和 indirect prompt injection 风险？

**答**：

**A2A 安全分两层**：协议层 + 应用层。

**协议层安全**：

1. **认证**：每个 Agent 必须声明 auth scheme（OAuth/API Key/mTLS）
2. **授权**：可 per-skill 授权（OAuth scope）
3. **传输**：HTTPS 必须
4. **审计**：trace 透传

**应用层风险（更重要）**：

**1. Indirect Prompt Injection 跨 Agent 传染**
- Agent B 返回的 message 进入 Agent A 的 context
- 如果 B 被注入，恶意 instruction 可以传到 A

**防御**：
- 把对方 Agent 返回视为 **untrusted data**（哪怕是合作方）
- 不要直接把对方输出作为指令执行
- 关键决策有独立判断

**2. Agent 冒充 / 钓鱼**
- 攻击者伪造 Agent，钓取 sensitive 数据
- 解决：强 auth + Agent identity verification
- 信任链：与已知供应商的合规协议绑定

**3. 数据泄露**
- A 把数据传给 B，B 是否会再传给 C？
- A2A 协议层不解决，必须**业务合同**约束
- 技术上：数据脱敏后再传

**4. 工具调用穿透**
- A 调 B，B 的工具调用是否会以"A 的身份"做事？
- 必须严格隔离：B 用自己的凭证，不能假冒 A

**5. 滥用 / DoS**
- 攻击者发大量 task 耗尽对方 Agent 配额
- 解决：rate limit + auth-based quota

**6. Reward Hacking 风险**
- 多 Agent 协作时，每个 Agent 优化自己的指标
- 可能形成 "互相奉承"的恶性平衡
- 需要**人工 oversight**关键决策

**Opaque 设计的安全价值**：
- A2A 故意让 Agent 之间**不共享 prompt / memory**
- 防止 IP 泄露
- 减少注入传染面（B 不能直接污染 A 的 system prompt）

**面试加分**：
- 把 A2A 风险类比成 **API 互信任风险**（已有成熟工程实践可借鉴）
- 提到 OAuth + Trace + 业务合同 三件套
- 提到 prompt injection 跨 Agent 是新风险，业界还在探索

---

### Q5：什么时候应该用 A2A 协议，什么时候直接 API 调用更好？

**答**：

**默认起点**：直接 API 调用更简单。

**用 A2A 的信号**：

1. **跨组织协作**：你不控制对方 Agent 的实现
2. **需要长任务**：小时 / 天级，传统 API 不适合
3. **多轮交互**：中途要 input-required，不是简单请求响应
4. **生态接入**：要让你的 Agent 被多家未来未知的客户调用
5. **想加入标准化生态**：未来想被 Agent marketplace 收录

**直接 API 调用更合适的场景**：

1. **内部紧耦合**：自家两个 Agent，紧密集成
2. **简短任务**：< 30s 完成，无多轮
3. **强类型 API**：业务领域已有成熟 OpenAPI 规范
4. **极致性能**：A2A 多一层封装有少量开销
5. **不需要发现机制**：调用关系硬编码

**实战决策**：
- **公司内部 Agent 互调**：可以选 A2A，也可以直接 API（取决于团队耦合度）
- **对外开放给客户 / 合作方的 Agent**：用 A2A 是未来趋势
- **服务集成**：传统 SaaS 集成依然是 OpenAPI 主流

**演进路径**：
- 起步：内部 API
- 成熟：抽出 A2A endpoint，对外开放
- 这两个**可以共存**（内部 API + 公开 A2A 双层）

**面试加分**：
- A2A 不是银弹，仍处早期
- 但**协议化是必然趋势**，类比 REST / GraphQL 当年的普及
- 强调"先用最简方案，需要互操作时再升 A2A"

---

### Q6：A2A 怎么处理长任务和异步通知？

**答**：

**三种交互模式**：

**1. 同步**（短任务）
```
client → POST tasks/send → wait → response
```
- 适合 < 30s
- 阻塞连接

**2. 流式（SSE）**（中等长度）
```
client → POST tasks/sendSubscribe → SSE stream → 多次 update → 最终 completed
```
- 适合几分钟，但要保持长连接
- 客户端可看进度
- 缺点：网络中断要 resubscribe

**3. 异步 Push Notification**（超长任务）
```
client → 注册 webhook → POST tasks/send  →（client 断开）
                                          ↓
                                  Agent 后台执行
                                          ↓
                                  状态变化时 → POST webhook
```
- 适合 小时 / 天级
- Client 无需保持连接
- Server 主动通知

**关键设计点**：

**1. Task ID 重连**
- 每个 task 有唯一 ID
- 网络中断后用 `tasks/resubscribe` 重新订阅 SSE
- 或用 `tasks/get` 拉取最新状态

**2. 心跳 / Keep-alive**
- 流式时 server 定期推空更新（防中间网关超时）
- 客户端 timeout 设置要大

**3. Idempotency**
- 同 task ID 重发请求不会重复执行
- 客户端可安全重试

**4. Webhook 注册**
```json
{
  "method": "tasks/pushNotification/set",
  "params": {
    "taskId": "task-001",
    "url": "https://my-app.com/webhook/a2a",
    "authentication": {"scheme": "bearer", "token": "..."}
  }
}
```

**5. State 持久化**
- Server 端必须持久化 task state（不能纯内存）
- DB / Redis / 持久消息队列
- 防 server 重启丢任务

**6. 取消**
- `tasks/cancel` 触发协作式中止
- Server 端检查 cancel flag，在 safe point 退出

**典型架构**：
```
[Client] ────POST tasks/send────────→ [A2A Gateway]
                                              ↓
                                       [Task Queue (Redis)]
                                              ↓
                                       [Worker Pool]
                                              ↓
                                       [Agent Logic]
                                              ↓
                                   ─POST webhook─→ [Client Webhook]
```

---

### Q7：A2A vs ACP（IBM）有何区别？未来谁会赢？

**答**：

**两者背景**：
- **A2A**：Google 主导，2025.04 发布，联盟 50+ 厂商
- **ACP**：IBM 主导，BeeAI 项目核心

**设计相似点**：
- 都是 Agent 间通信协议
- 都基于 HTTP + JSON
- 都关注发现 + 能力描述 + 通信

**设计差异**：

| 维度 | A2A | ACP |
|------|-----|-----|
| 主导者 | Google + 联盟 | IBM |
| 状态模型 | 强（Task 生命周期） | 偏 stateless |
| 流式 | SSE 一等公民 | 支持但简化 |
| 复杂度 | 中等（功能全） | 更轻量 |
| 生态 | 大（50+ 厂商） | 主要 IBM 圈 |

**谁会赢**：

**短期**：
- A2A 联盟更大，落地更快
- 大厂支持的多了：Atlassian、Salesforce、SAP、Workday 都跟进
- Microsoft 也宣布 Copilot Studio 接 A2A

**长期可能**：
- A2A 成为主流（类似 OpenAPI 在 API 领域）
- ACP / 其他协议**与 A2A 收敛**或被吸收
- IBM 自己也是 A2A 联盟成员 → 两个协议长期可能融合
- 标准化运动 AGNTCY 推更高层抽象

**面试加分**：
- 历史类比："REST vs SOAP" 当年也并存几年，最后 REST 赢
- 强调**协议战的胜者不只看技术，看生态联盟**
- A2A 联盟里有 Google 加 50 多家，碾压性优势

**实战建议**：
- 短期：以 A2A 为主投入
- 但抽象设计上 protocol-agnostic（核心 Agent 逻辑别绑死协议）

---

### Q8：A2A 协议里的 Agent 之间能否共享 memory？

**答**：

**答案：不能，且这是有意的设计。**

**为什么 A2A 不让 Agent 共享 memory**：

1. **隔离与封装**：每个 Agent 是黑盒，对方不知道你的 prompt / memory / tool 实现
2. **IP 保护**：你的 prompt、few-shot、训练数据都是商业资产
3. **安全**：避免 indirect prompt injection 跨 Agent 传染
4. **可替换性**：未来换实现不影响外部协议
5. **多组织协作**：不同组织的数据合规要求各不相同

**那 Agent 间怎么交换上下文**：

**1. 通过 Message 显式传递**
- 调用方在 task message 里塞需要的上下文
- 例：调用 Travel Agent 时把"用户偏好"作为 DataPart 传

**2. 通过 Artifact 返回**
- 被调用方产出工件，调用方可用于后续 task
- 例：Booking Agent 返回 booking_id，下次取消时传回去

**3. 关联 Task ID**
- 同一 Task ID 跨多轮，状态由 Server 端保持
- 调用方不需要重传完整历史

**4. 业务级 ID 关联**
- 用户 ID / 订单 ID 等业务标识
- 两端各自查询自己的 memory，业务 ID 对应

**对比：紧耦合时怎么共享**
- 自家两个 Agent 共享 Redis、共享 DB → 性能好但耦合死
- 但这就**不算 A2A 协作**了，是单一系统两个进程

**面试加分**：
- 这种 "opaque" 设计是协议的核心哲学
- 类比 REST 的 "服务边界封装" 思想
- 提到设计权衡：松耦合 + 安全 ↔ 性能 + 共享便利

---

### Q9：A2A 协议会让 OpenAI Anthropic Google 走向"Agent 互操作"还是相反？

**答**：

**当前态势**：

**支持 A2A 的**：
- **Google**（推动者）
- **Microsoft**（Copilot Studio 接入）
- **Anthropic**（虽未官方加入，但 MCP + A2A 互补）
- **50+ 企业软件公司**：Salesforce、SAP、Workday、Atlassian、Cohere、LangChain、PayPal、Box、ServiceNow ...

**态度不明**：
- **OpenAI**：当前未公开支持 A2A
  - 自己推 Agents SDK + Handoff
  - 也未阻止
  - 生态压力下可能跟进

**互操作的两种未来**：

**未来 1：标准化生态（A2A 赢）**
- 类比今天的 HTTP / REST
- 任何 Agent 都可互调
- 用户 Personal AI 调任何服务 Agent
- Agent Marketplace 兴起

**未来 2：碎片化（各家圈地）**
- OpenAI 圈 + Google 圈 + Anthropic 圈
- 用户需要在不同生态间手动桥接
- 类似今天的"微信不能直接调 WhatsApp"

**真实走向**：
- 短期偏未来 1，因为联盟太大了
- 但厂商有动机做**部分互操作**而非完全开放
- 关键节点是消费级 Personal AI 出现后用户的呼声

**面试加分**：
- 历史类比："Email 协议（SMTP）让所有邮箱互通"
- 类比 RCS / iMessage（厂商抵制互操作的反例）
- **生态学视角**：标准化通常先在中间层（B2B）形成，再向消费级渗透

---

## 七、场景设计题（含答案）

### 场景 1：企业 HR Agent 跨组织协作

**题目**：A 公司的 HR Agent 要为新员工自动开通 IT 账号。IT 系统是 B 公司提供的 SaaS，B 公司也有自家 Agent。设计跨组织协作方案。

**答案**：

**架构选择**：**A2A 协议**（典型跨组织场景）

**核心流程**：

```
[A 公司 HR Agent]
    ↓ (1) Discovery
GET https://b-saas.com/.well-known/agent.json
    ↓
[B 公司 IT Agent]
    ↓ (2) Auth
OAuth2.0 (Client Credentials)
    ↓
    ↓ (3) Submit Task
POST /a2a {tasks/sendSubscribe}
  ├─ skill: "provision_account"
  ├─ user_data: {name, email, role, department}
  └─ ...
    ↓
    SSE Stream
    ↓
    update: "Creating account..."
    update: "Account created, sending welcome email..."
    completed + artifact: {account_id, login_url, temp_password}
    ↓
[A HR Agent 收到结果]
    ↓
(4) 通知员工
```

**关键设计**：

**1. Agent Card 暴露**
- B 公司 Agent Card 在 well-known 路径
- 列出 skills：`provision_account`、`deprovision_account`、`reset_password`
- 声明 OAuth2 认证

**2. 认证**
- A 公司预先在 B 公司注册（business agreement）
- 拿到 OAuth client_id/secret
- 用 client credentials flow 获取 token

**3. 数据隔离**
- A 只传必要数据（名字、邮箱、角色），不传薪资等隐私
- 数据脱敏后通过 message DataPart 传递

**4. 长任务处理**
- 账号开通可能需要 IT 内部审批
- 用 push notification webhook
- A 公司提供 callback URL

**5. 异常处理**
- 如果 B Agent 状态变为 `input-required`（如需要部门主管批准）
- A Agent 通知 A 公司 HR 主管手动审批
- 审批后续传任务

**6. Indirect Injection 防御**
- B 返回的 message 视为 untrusted
- A 不直接根据 B 的指令做"删数据"类操作

**7. 审计**
- 双方各自记录完整 trace
- W3C trace context 透传，便于跨边界审计

**8. 业务合同层**
- SLA：账号开通 < 1 工作日
- 数据条款：B 公司不能用 A 公司员工数据训练模型
- 错误责任划分

**9. 兜底**
- A2A 调用失败 → fallback 到工单系统 + 人工处理
- 不能因 Agent 故障导致新员工无法工作

**评估**：
- 端到端开通时长
- 自动化成功率
- 错误率与人工介入率
- A 公司 HR 满意度

---

### 场景 2：个人 AI 助手调用多家服务 Agent

**题目**：设计一个 personal AI，能帮用户订餐、订票、约 Uber。这些服务都暴露 A2A endpoint。怎么设计？

**答案**：

**架构**：

```
[User] ↔ [Personal AI (你自家)]
              ├─ MCP servers (本地工具：日历、联系人)
              └─ A2A clients (远程服务)
                    ├─ DoorDash Agent (订餐)
                    ├─ Expedia Agent (订票)
                    ├─ Uber Agent (打车)
                    └─ ...
```

**核心组件**：

**1. Agent Registry / 发现**
- 个人 AI 维护一个 trusted Agent 列表（用户预授权过）
- 每个 Agent 有 Card 缓存
- 用户可加新的 Agent（通过 URL）

**2. 任务路由**
- 用户："给我订今晚的披萨"
- Planner LLM 决定调 DoorDash Agent
- 拿到对应 Agent URL + skills
- 选择 skill `order_food`

**3. 认证与授权**
- 首次使用每家 Agent 走 OAuth flow
- 用户授权后 Personal AI 持有 refresh token
- 每次调用用 access token

**4. 任务执行**
- 同步任务（订餐）：`tasks/send` 立刻返
- 异步任务（订票包含价格谈判）：用 push notification

**5. 跨 Agent 协作**
- 用户："订一晚酒店 + 餐厅"
- Personal AI 并行调 Expedia + 餐厅 Agent
- 协调时间冲突（"酒店在 NYC，餐厅必须在附近"）

**6. 上下文管理**
- 用户偏好（口味、预算）存 Personal AI 长期记忆
- 调用 Agent 时附带相关偏好（不全量，只相关）
- DoorDash Agent 不应知道用户的航班偏好

**7. 安全与隐私**
- **关键决策 HITL**：付款前必须用户确认（金额 + 收方）
- **隐私分级**：信用卡信息走加密通道，PII 最小化
- **跨 Agent 数据不共享**：DoorDash 不能拿到用户航班信息

**8. 错误处理**
- Agent 不可用 → 切备用（DoorDash 不行用 Uber Eats）
- 部分失败：订餐成功但 Uber 失败 → 通知用户决定是否回滚

**9. 信任与评分**
- 用户给每个外部 Agent 打分
- 不可信的 Agent 触发更严格 HITL
- 长期：Agent Reputation System

**10. 体验设计**
- 用户感知是"一个 AI"，不感知后台多 Agent
- 进度可视化（"正在订餐... 已下单"）
- 一次失败时 graceful：清楚说明哪一步失败

**业务挑战**：
- 各家 Agent 不一定都支持 A2A（当前生态早期）
- 兜底用 web automation / API 直连
- 商业利益：服务方愿意让 personal AI 接入吗（绕过推广）？
- 这正是 2025-2026 的看点

**面试加分**：
- 提到 "Personal AI" 是 Sam Altman、Mustafa Suleyman 都谈过的未来方向
- 提到 A2A 是这种愿景的关键基础设施
- 提到当前痛点：服务方不愿被中介化（类比 OTA / 携程 时代的酒店）

---

## 八、自测清单

- [ ] MCP vs A2A 的本质差异（5 个维度）
- [ ] A2A 的 4 个核心概念（Agent Card / Task / Message / Artifact）
- [ ] Task 的 6 个状态
- [ ] 3 种交互模式（同步 / 流式 SSE / 异步 push）
- [ ] Agent Card 的发现机制（well-known URL）
- [ ] A2A 的 6 个 JSON-RPC 方法
- [ ] Opaque 设计的 5 个理由
- [ ] A2A 安全的协议层 + 应用层
- [ ] indirect prompt injection 跨 Agent 风险
- [ ] A2A vs ACP 的差异
- [ ] 何时用 A2A 何时用直接 API
- [ ] AGNTCY 与 A2A 的关系

---

## 九、关键术语 Cheat Sheet

| 术语 | 含义 |
|------|------|
| A2A | Agent-to-Agent Protocol，Google 主导 |
| ACP | Agent Communication Protocol，IBM 推 |
| MCP | Model Context Protocol，Anthropic 推 |
| AGNTCY | Agent 全栈标准化联盟 |
| Agent Card | 公开能力描述卡片 |
| Task | A2A 工作单元，有生命周期 |
| Skill | Agent 的一项能力 |
| Message | Agent 间通信单位 |
| Part | Message / Artifact 内的内容片段（Text/File/Data） |
| Artifact | Agent 产生的结果工件 |
| Streaming (SSE) | Server-Sent Events 实时更新 |
| Push Notification | Webhook 异步通知 |
| Well-known URL | `/.well-known/agent.json` 标准位置 |
| Opaque Agent | 内部不对外暴露的 Agent |
| Federated Agents | 跨组织协作的 Agent 网络 |

---

## 十、延伸阅读

- Google — *Announcing the Agent2Agent Protocol (A2A)*（2025.04 官方博客）
- A2A 官方规范：github.com/google/A2A
- A2A Python/TS/Java SDK 代码
- IBM — *BeeAI / ACP* 文档
- Anthropic — *MCP* 文档（对比参考）
- AGNTCY 联盟资料
- LangChain Blog — *Working with A2A*
- 各厂商接入 A2A 的公告（Salesforce、Atlassian、SAP）

---

## 十一、面试金句

- "MCP 是 Agent 的手，A2A 是 Agent 的嘴 — 两者互补不替代"
- "A2A 的核心抽象是 Task（有生命周期），不是 RPC"
- "A2A 的 Opaque 设计同时保护 IP、阻断注入传染、保持松耦合"
- "Indirect prompt injection 在跨 Agent 时变成新风险，必须把对方输出视为 untrusted"
- "协议战的胜者不只看技术，看生态联盟 — A2A 联盟 50+ 厂商是决定性优势"
- "Personal AI 时代的基础设施就是 A2A — 用户的 AI 能调任何服务的 AI"
