# Tool Gateway 与工具平台专题

> 目标：把工具调用从"模型调函数"提升到生产级工具平台来理解。Tool Gateway 是 Agent 接触真实世界的安全边界，负责工具注册、检索、权限、参数校验、幂等、重试、沙箱、审计、限流、版本和测试。

---

## 一、一句话定义

**Tool Gateway 是 Agent Runtime 与真实工具/API/系统之间的治理层**：模型只提出工具调用意图，Tool Gateway 决定这个工具是否存在、当前主体是否有权调用、参数是否合法、是否需要审批、如何执行、如何重试、如何审计、结果如何回填。

最小心智模型：

```text
LLM proposes:
  tool = issue_refund
  args = {order_id: ORD-1001, amount: 120}

Tool Gateway checks:
  tool exists?
  schema valid?
  user has permission?
  risk requires approval?
  idempotency key exists?
  timeout / retry policy?
  audit event?

Only then execute.
```

**核心判断**：安全边界不在 prompt，而在 Tool Gateway。

---

## 二、为什么需要 Tool Gateway

Demo 里常见写法：

```python
if tool_name == "search":
    return search(**args)
if tool_name == "refund":
    return refund(**args)
```

这能跑通，但不能上线。

| 生产问题 | 直接调用函数的后果 | Gateway 能力 |
|---|---|---|
| 工具很多 | 全量塞 prompt，模型选错 | registry、namespace、tool retrieval |
| 工具有权限 | 模型可能越权调用 | principal、scope、policy check |
| 参数不可靠 | 类型/enum/业务规则错 | schema + semantic validation |
| 工具有副作用 | 重试重复扣款/发邮件 | idempotency、transaction log |
| 工具慢或失败 | Agent 卡死或乱重试 | timeout、retry、circuit breaker |
| 高风险动作 | 模型直接执行 | HITL、risk scoring |
| 结果很大 | context 爆炸 | artifact 化、摘要、分页 |
| 线上排障 | 不知道谁调了什么 | audit log、trace span |
| 接入第三方 | 工具质量参差不齐 | conformance test、sandbox |

---

## 三、Tool Gateway 在架构中的位置

```text
Agent Runtime
  -> Model Adapter
  -> tool call intent
  -> Tool Gateway
      -> Tool Registry
      -> Policy Engine
      -> Schema Validator
      -> Risk Scorer
      -> Approval Service
      -> Execution Adapter
      -> Result Normalizer
      -> Audit / Trace
  -> Tool Result
  -> Context Builder / State Store
```

它连接四类对象：

| 对象 | 说明 |
|---|---|
| 模型 | 只产出工具调用意图 |
| Runtime | 管 run、step、budget、checkpoint |
| 工具系统 | API、MCP server、数据库、浏览器、代码沙箱 |
| 治理系统 | IAM、policy、审批、审计、监控 |

---

## 四、核心能力拆解

### 4.1 Tool Registry

工具注册中心不是一个 Python dict，而是一套工具元数据系统。

```json
{
  "name": "issue_refund",
  "namespace": "commerce.billing",
  "description": "Issue a refund for an eligible order.",
  "input_schema": "IssueRefundInput.v2",
  "output_schema": "IssueRefundOutput.v1",
  "risk_level": "high",
  "side_effect": true,
  "required_scopes": ["refund:write"],
  "timeout_ms": 5000,
  "retry_policy": "no_retry_without_idempotency",
  "idempotency_key_template": "refund:{order_id}:{amount}:{reason}",
  "owner": "billing-platform",
  "version": "2026-06-01"
}
```

至少应记录：

| 字段 | 用途 |
|---|---|
| `name` | 模型看到的工具名 |
| `namespace` | 避免工具重名，便于分域 |
| `description` | 模型选择工具的主要依据 |
| `input_schema` | 参数校验 |
| `output_schema` | 结果规范 |
| `risk_level` | 风险分级 |
| `side_effect` | 是否写外部系统 |
| `required_scopes` | 权限要求 |
| `timeout_ms` | 超时 |
| `retry_policy` | 重试策略 |
| `owner` | 出问题找谁 |
| `deprecation` | 版本下线 |

### 4.2 Tool Discovery / Tool Retrieval

工具数量少时可以全量注入：

```text
<20 tools: all tools in prompt
20-50 tools: namespace + filtered list
50+ tools: retrieval / router
100+ tools: hierarchical tool platform
```

Tool Retrieval 流程：

```text
user task
  -> query rewrite
  -> retrieve candidate tools by BM25/vector/tags
  -> permission filter
  -> risk filter
  -> top-k tool schemas injected
```

不要先召回再执行，必须先做权限过滤。否则模型会看到它不该知道的内部工具。

### 4.3 Schema Validation

Tool Gateway 要做两层校验：

```text
JSON/schema validation:
  type, required, enum, format

semantic validation:
  amount <= order.amount
  date range valid
  account belongs to tenant
  tool state transition allowed
```

错误要结构化返回给模型：

```json
{
  "error_type": "validation_error",
  "retryable_by_model": true,
  "field_errors": [
    {
      "path": "$.amount",
      "message": "amount must be <= original order amount 120"
    }
  ]
}
```

### 4.4 Permission / Policy

工具权限不是"当前用户有权限就让 Agent 继承全部权限"。

推荐取交集：

```text
effective_permission =
  user scopes
  ∩ agent scopes
  ∩ session scopes
  ∩ tool required scopes
  ∩ policy constraints
```

Policy Engine 应判断：

| 问题 | 示例 |
|---|---|
| 用户是否有权 | 当前用户能否退款 |
| Agent 是否有权 | 当前 Agent 是否允许写 billing |
| 租户是否匹配 | order 是否属于当前 tenant |
| 风险是否过高 | 金额是否超过阈值 |
| 是否需要审批 | 高风险写操作 |
| 是否允许外发 | 发邮件、发 webhook |

### 4.5 Risk Scoring 与 HITL

工具风险可按维度评分：

| 维度 | 示例 |
|---|---|
| side effect | 是否写系统 |
| reversibility | 是否可回滚 |
| money impact | 金额 |
| data sensitivity | PII/PHI/PCI |
| external exposure | 是否发外部消息 |
| privilege impact | 是否改权限 |
| confidence | 模型/证据置信度 |
| novelty | 是否首次调用 |

决策：

```text
allow
deny
require_approval
require_user_input
require_stronger_auth
dry_run_only
```

### 4.6 Idempotency

所有有副作用工具都要有幂等键。

```text
send_email: email:{tenant}:{recipient}:{template}:{business_id}
issue_refund: refund:{order_id}:{amount}:{reason}
create_ticket: ticket:{source_run_id}:{issue_hash}
```

Tool Gateway 要记录：

| 字段 | 说明 |
|---|---|
| idempotency_key | 幂等键 |
| request_hash | 参数摘要 |
| status | pending/succeeded/failed |
| external_id | 下游系统 ID |
| first_run_id | 第一次触发的 run |
| last_attempt | 最近尝试 |

如果 worker 在工具执行后、checkpoint 前崩溃，恢复时应先查幂等记录，而不是直接重放工具。

### 4.7 Timeout、Retry、Circuit Breaker

重试要区分错误类型：

| 错误 | 策略 |
|---|---|
| 429/rate limit | 指数退避，可能换 provider |
| 5xx/timeout | 读工具可重试，写工具需幂等 |
| 400/schema | 模型修复参数 |
| 401/403 | 不重试，返回权限错误 |
| business conflict | 让模型或用户选择 |
| policy deny | 不重试 |

Circuit breaker：

```text
tool error rate > threshold
  -> open circuit
  -> reject or fallback
  -> probe after cooldown
```

### 4.8 Result Normalization

工具返回不能随意塞回模型。Gateway 要统一结果格式：

```json
{
  "tool": "lookup_order",
  "ok": true,
  "data": {
    "order_id": "ORD-1001",
    "status": "lost",
    "amount": 120
  },
  "artifacts": [],
  "metadata": {
    "latency_ms": 231,
    "source": "orders_api",
    "schema_version": "LookupOrderOutput.v1"
  }
}
```

大结果要 artifact 化：

```text
10MB log
  -> object store artifact
  -> summary + artifact_ref back to model
```

### 4.9 Audit 与 Trace

每次工具调用都要能回答：

- 谁触发的？
- 哪个 Agent 触发的？
- 哪个 run/step？
- 模型为什么调用？
- 参数是什么？
- 权限如何判断？
- 是否审批？
- 工具结果是什么？
- 是否产生副作用？
- 下游事务 ID 是什么？

事件结构：

```json
{
  "event": "tool.executed",
  "run_id": "run_123",
  "step_id": "step_008",
  "tool": "issue_refund",
  "principal": {"user_id": "u1", "tenant_id": "t1", "agent_id": "refund_agent"},
  "args_hash": "sha256:...",
  "risk": "high",
  "policy_decision": "approved",
  "idempotency_key": "refund:ORD-1001:120:lost",
  "external_id": "RF-1001",
  "latency_ms": 481,
  "status": "succeeded"
}
```

---

## 五、工具类型与治理策略

| 工具类型 | 示例 | 风险 | 治理 |
|---|---|---|---|
| Read-only | search、lookup_order | 低到中 | 权限、限流、结果裁剪 |
| Internal write | update_tag、create_draft | 中 | 幂等、审计 |
| External write | send_email、post_slack | 中到高 | 审批、预览 |
| Money movement | refund、charge | 高 | HITL、强幂等、双人审批 |
| Privilege change | add_admin_role | 极高 | 默认禁止或强审批 |
| Code execution | run_python、shell | 极高 | 沙箱、网络隔离、资源限制 |
| Browser action | click、type、download | 中到高 | 域名 allowlist、页面验证 |
| MCP tool | remote server tool | 视 server 而定 | server 信任评级、scope |

---

## 六、MCP、OpenAPI 与内部 API 接入

### 6.1 OpenAPI 接入

OpenAPI 可自动生成工具 schema，但不能直接给模型用。

需要人工治理：

- 合并低价值 API。
- 给 operation 写模型友好的 description。
- 收紧 enum 和格式。
- 隐藏内部字段。
- 给高风险 API 加 risk_level。
- 给每个 operation 加 owner。

### 6.2 MCP 接入

MCP 解决工具/资源接入标准化，但不替代 Tool Gateway。

```text
Agent Runtime
  -> Tool Gateway
  -> MCP Client
  -> MCP Server
```

Gateway 仍要做：

- server allowlist。
- tool permission。
- arguments validation。
- result filtering。
- audit logging。
- prompt injection 防护。
- server 版本和健康检查。

### 6.3 内部 API 接入

内部 API 工具最好通过 adapter 层暴露，不要把原始 API 全给模型。

```text
raw API: PATCH /v1/orders/{id}

agent tool:
  update_order_shipping_address(order_id, address, reason)
```

Agent tool 应该更业务语义化、更窄、更安全。

---

## 七、工具描述怎么写

工具描述直接影响模型是否选对工具。

### 7.1 四要素

| 要素 | 说明 |
|---|---|
| 做什么 | 第一语句清楚说明能力 |
| 何时用 | 适用边界 |
| 何时不用 | 反例，减少误用 |
| 参数说明 | 格式、单位、来源、限制 |

示例：

```text
lookup_order
Use this tool to retrieve order status, amount, items, and delivery information by order_id.
Use it before deciding refund eligibility.
Do not use it to issue refunds or change order state.
order_id must be an exact ID like ORD-1001.
```

### 7.2 反例很重要

没有反例时，模型容易把一个工具当万能工具。

```text
Do not use send_email for internal notes.
Do not use issue_refund if the user is only asking about refund policy.
Do not use run_sql for write operations.
```

### 7.3 工具命名

| 差命名 | 好命名 |
|---|---|
| `process` | `issue_refund` |
| `update` | `update_shipping_address` |
| `query` | `lookup_order` |
| `send` | `send_customer_email` |

工具名应该是动词 + 业务对象。

---

## 八、工具结果设计

### 8.1 给模型的结果不是给人看的日志

错误：

```text
HTTP 200 OK. Raw response: ...
```

更好：

```json
{
  "ok": true,
  "order": {
    "id": "ORD-1001",
    "delivery_status": "lost",
    "amount": 120,
    "currency": "USD"
  },
  "refund_eligible": true,
  "evidence": "orders_api:ORD-1001:v3"
}
```

### 8.2 错误结果要可行动

```json
{
  "ok": false,
  "error_type": "permission_denied",
  "retryable": false,
  "message_for_model": "The current user cannot issue refunds over 50 USD.",
  "next_options": ["request_human_approval", "explain_limitation"]
}
```

### 8.3 大结果要分层

```text
summary: 给模型决策用
artifact_ref: 需要细节时可取
raw: 审计/复现用，不进 prompt
```

---

## 九、沙箱与隔离

高风险工具必须隔离执行。

### 9.1 Code Execution

| 控制 | 要求 |
|---|---|
| 文件系统 | 只读根目录 + 临时工作目录 |
| 网络 | 默认无网，白名单 |
| CPU/内存 | 限额 |
| 时间 | 超时 kill |
| 包管理 | 禁止任意安装或走白名单 |
| secrets | 不注入环境变量 |
| 审计 | stdout/stderr/files 全留痕 |

### 9.2 Browser Tool

| 控制 | 要求 |
|---|---|
| 域名 | allowlist |
| 下载 | 隔离目录和扫描 |
| 上传 | 只允许指定 artifact |
| 输入 secrets | 由 secret manager 填，不给模型看 |
| 高风险点击 | 审批 |
| 截图 | PII 脱敏 |

### 9.3 MCP Server

| 控制 | 要求 |
|---|---|
| server 来源 | allowlist / signature |
| roots | 最小文件范围 |
| network | 限制外联 |
| tool list | 按 session 过滤 |
| audit | 记录每个 MCP tool call |

---

## 十、工具测试与评估

Tool Gateway 要有自己的测试体系。

### 10.1 Tool Contract Test

检查：

- schema 能解析。
- required 字段完整。
- 正常参数能执行。
- 错误参数返回结构化错误。
- timeout 生效。
- 权限不足被拒绝。
- 幂等键生效。

### 10.2 Tool Selection Eval

数据集：

```json
{
  "user_input": "Can you refund order ORD-1001?",
  "expected_tool": "lookup_order",
  "forbidden_tool": "issue_refund",
  "reason": "Need to inspect order before refund."
}
```

指标：

| 指标 | 含义 |
|---|---|
| tool precision | 调用的工具是否应该调用 |
| tool recall | 该调用时是否调用 |
| args accuracy | 参数是否正确 |
| unsafe call rate | 是否触发危险工具 |
| unnecessary call rate | 是否多调 |

### 10.3 Shadow Mode

工具上线前可 shadow：

```text
model proposes tool call
  -> old path executes
  -> new gateway only validates/logs
  -> compare decisions
```

---

## 十一、端到端例子：退款工具平台

### 11.1 工具清单

| 工具 | 风险 | 策略 |
|---|---|---|
| `lookup_order` | low | read-only，限流 |
| `check_refund_policy` | low | deterministic rules |
| `issue_refund` | high | 幂等 + HITL |
| `send_customer_email` | medium | 预览 + 审批 |
| `create_support_ticket` | low | 幂等 |

### 11.2 执行路径

```text
User asks refund
  -> tool retrieval returns lookup_order, check_refund_policy
  -> model calls lookup_order
  -> model calls check_refund_policy
  -> model proposes issue_refund
  -> gateway sees amount=120 high risk
  -> approval required
  -> approved
  -> gateway executes issue_refund with idempotency key
  -> result normalized
  -> audit event written
```

### 11.3 关键事件

```json
{
  "event": "tool.approval_required",
  "tool": "issue_refund",
  "reason": "refund_amount_over_threshold",
  "amount": 120,
  "run_id": "run_001"
}
```

```json
{
  "event": "tool.executed",
  "tool": "issue_refund",
  "idempotency_key": "refund:ORD-1001:120:lost",
  "external_id": "RF-1001",
  "status": "succeeded"
}
```

---

## 十二、主流实现映射

| 平台/框架 | Tool Gateway 相关能力 |
|---|---|
| OpenAI Agents SDK | tools、handoffs、guardrails、tracing，应用层仍需权限/幂等 |
| Anthropic Tool Use | `input_schema`、tool_choice、computer use，应用层执行工具 |
| Google ADK | function tools、built-in tools、tool context、events |
| LangChain / LangGraph | tool abstraction、graph node、middleware、state/checkpoint |
| MCP | 标准 tools/resources/prompts 接入协议 |
| CrewAI | tools 绑定到 Agent/Task |
| LlamaIndex | FunctionTool、QueryEngineTool、workflow tools |
| Semantic Kernel | plugin/function abstraction |
| OPA / Cedar | 可作为外部 policy engine |
| E2B / Daytona / Modal | code sandbox 执行环境 |

重点：这些框架提供 tool abstraction，但生产 Tool Gateway 的权限、幂等、审计、风险和测试通常仍要应用方设计。

---

## 十三、反模式

| 反模式 | 问题 |
|---|---|
| 把所有工具全量注入 prompt | 成本高，模型混乱，泄露内部能力 |
| 工具权限只写在 prompt | 模型可忽略，不是安全边界 |
| 副作用工具无幂等 | 重试导致重复执行 |
| 错误返回自然语言 | 模型难以可靠修复 |
| 工具描述只写一句话 | 误调用率高 |
| OpenAPI 自动生成后直接上线 | 描述差、风险不分级 |
| MCP server 默认全信任 | 供应链和权限风险 |
| 大结果直接塞回上下文 | context 爆炸 |
| 无 tool eval | 改 description 后不知道是否退化 |
| 审计只记录最终答案 | 无法复盘真实动作 |

---

## 十四、自测清单

- [ ] 能解释 Tool Gateway 为什么是真实安全边界。
- [ ] 能设计 Tool Registry 元数据。
- [ ] 能区分 schema validation 和 semantic validation。
- [ ] 能设计 effective permission 交集模型。
- [ ] 能为副作用工具设计 idempotency key。
- [ ] 能给工具错误设计结构化返回。
- [ ] 能说明 MCP 为什么不替代 Tool Gateway。
- [ ] 能设计 tool selection eval。
- [ ] 能为 code/browser tool 设计沙箱。
- [ ] 能解释如何处理 100+ 工具。

---

## 十五、高频问题

### Q1：为什么不能让模型直接调用真实 API？

模型输出只是意图，不是授权决策。真实 API 调用需要权限、参数校验、幂等、限流、审计、风险评估和错误处理。缺少 Gateway 时，一次误调用就可能变成真实业务事故。

### Q2：Tool Retrieval 为什么要先做权限过滤？

如果先把无权限工具展示给模型，即使最后拦住执行，也已经泄露了内部能力和工具 schema。工具召回必须结合用户、租户、Agent scope 和 session policy。

### Q3：有了 MCP 还需要 Tool Gateway 吗？

需要。MCP 标准化工具接入，不负责你的业务权限、审批、幂等、审计、风险分级和工具质量。生产系统通常是 Tool Gateway 调 MCP server，而不是让 Agent 直接裸连所有 MCP server。

### Q4：幂等键怎么设计？

幂等键要代表业务上"同一个副作用动作"，通常由业务对象、动作、关键参数和原因组成。不能包含每次变化的随机 run_id，否则重试无法命中；也不能太粗，否则不同动作被误合并。

### Q5：工具错误要不要回填给模型？

临时错误和参数错误可以结构化回填，让模型修复或选择替代路径；权限拒绝、policy deny、高风险审批不能让模型自行绕过，应直接阻断、转人工或解释限制。

---

## 十六、关联阅读

- [03-工具调用.md](./03-工具调用.md)：工具调用基础、并行、Tool RAG。
- [03.1-MCP.md](./03.1-MCP.md)：MCP tools/resources/prompts 协议。
- [08.1-生产级Agent应用工程.md](./08.1-生产级Agent应用工程.md)：生产 Agent 中的 Tool Gateway。
- [09-安全与对齐.md](./09-安全与对齐.md)：权限、注入、HITL。
- [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md)：Runtime 如何调度工具。
- [22-结构化输出与约束解码专题.md](./22-结构化输出与约束解码专题.md)：工具参数和结果 schema。

---

## 十七、官方资料入口

- OpenAI Function Calling: <https://platform.openai.com/docs/guides/function-calling>
- OpenAI Agents SDK Tools: <https://openai.github.io/openai-agents-python/tools/>
- Anthropic Tool Use: <https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview>
- Anthropic Writing tools for agents: <https://www.anthropic.com/engineering/writing-tools-for-agents>
- Google ADK Tools: <https://google.github.io/adk-docs/tools/>
- Model Context Protocol Specification: <https://modelcontextprotocol.io/specification>
- Open Policy Agent: <https://www.openpolicyagent.org/docs/latest/>
- Cedar Policy Language: <https://www.cedarpolicy.com/en>
