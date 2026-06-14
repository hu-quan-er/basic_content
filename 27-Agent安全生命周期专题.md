# Agent 安全生命周期专题

> 目标：把 Agent 安全从“防 prompt injection”扩展为覆盖设计、输入、上下文、模型、工具、执行、记忆、输出、观测、发布和运营的全生命周期治理体系。本文关注风险表现、分类、实现机制、预防手段和检测闭环。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Agent 全生命周期安全威胁建模、风险分类、防护机制、检测运营、安全测试、事故响应和上线清单 | 安全概念总览见 [09-安全与对齐.md](./09-安全与对齐.md)；工具执行安全见 [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)；模型调用治理见 [26-Model Gateway与模型治理专题.md](./26-Model%20Gateway与模型治理专题.md)；Buddy 产品安全场景见 [25.4-Buddy安全治理与评估体系.md](./25.4-Buddy安全治理与评估体系.md) |

---

## 一、一句话定义

**Agent 安全生命周期**是围绕“一个可自主读写和行动的 AI 系统”建立的持续风险治理流程：在需求设计阶段定义边界，在运行时隔离数据和能力，在工具执行前做策略决策，在输出和日志中防泄露，在上线后用评估、红队、观测和事故响应持续修正。

核心判断：

> Agent 的安全边界不在模型本身，而在系统边界、权限模型、数据流、工具网关、模型网关、运行时状态、审计和运营流程的组合。

---

## 二、为什么 Agent 安全需要单独研究

传统 LLM 应用主要风险是“回答错、泄露信息、生成不当内容”。Agent 的风险更高，因为它具备四个放大器：

| 放大器 | 含义 | 安全后果 |
|---|---|---|
| Autonomy | 能多步自主规划和执行 | 单次错误会被后续步骤放大 |
| Tool Use | 能调用真实系统 | 错误可能变成真实副作用 |
| External Context | 会读取网页、文档、邮件、代码、RAG 结果 | 外部数据可能携带间接注入 |
| Persistence | 有记忆、状态、checkpoint、长期任务 | 污染和权限问题可能跨会话持续 |

因此 Agent 安全不是一个单点过滤器，而是一套生命周期工程。

---

## 三、安全生命周期地图

```text
1. 需求与威胁建模
   -> 任务边界、自治等级、数据分级、动作风险、威胁假设

2. 输入与身份
   -> 用户身份、租户、会话权限、输入校验、注入检测

3. 上下文构建
   -> trusted/untrusted 分层、引用化、最小必要上下文、防污染

4. 模型调用
   -> provider policy、数据外发策略、模型路由、敏感字段脱敏

5. 工具调用
   -> tool registry、scope、schema、risk scoring、HITL、幂等、审计

6. 执行环境
   -> sandbox、命令权限、文件系统边界、网络边界、资源限制

7. 记忆与 RAG
   -> 索引投毒、权限过滤、记忆写入验证、遗忘和审计

8. 输出与下游处理
   -> 输出校验、HTML/SQL/代码处理、PII 检测、引用和免责声明

9. 观测与检测
   -> trace、audit log、异常检测、failure pool、安全事件

10. 发布与运营
    -> 安全 eval、红队、灰度、回滚、incident response、复盘
```

---

## 四、全生命周期风险分类

### 4.1 需求与设计阶段

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 任务边界不清 | Agent 被要求“尽力完成”，但没有禁止动作和失败定义 | 写清 allowed / denied actions、success criteria、human escalation |
| 自治等级过高 | 从建议型助手直接变成自动执行型系统 | 用 L0-L5 自治等级定义可自动执行范围 |
| 权限继承过宽 | Agent 默认拥有用户全部权限 | effective permission = user ∩ agent ∩ session ∩ tool scope ∩ policy |
| 没有威胁模型 | 只考虑正常用户路径 | 使用 data-flow + threat actor + abuse case 建模 |

### 4.2 输入层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 直接 prompt injection | 用户要求忽略系统指令、泄露 prompt、绕过策略 | 输入分类、策略拒绝、系统指令和用户数据隔离 |
| jailbreak | 角色扮演、编码、翻译、多轮诱导绕过限制 | 多层 guardrail、策略模型、输出二次检查 |
| 超长输入 DoS | 用长上下文消耗 token 和延迟 | token limit、rate limit、预算、输入截断 |
| 数据上传污染 | 用户上传带恶意指令的文档 | 文件扫描、来源标记、untrusted_data 隔离 |

### 4.3 上下文层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 间接注入 | 网页、邮件、文档、工具返回中隐藏“覆盖系统指令” | trusted/untrusted context 分层；低信任内容不能直接驱动高风险动作 |
| 上下文混淆 | 模型无法区分指令、证据、用户偏好、工具结果 | Context Manifest、显式 source/type/trust_level |
| 敏感信息过度注入 | 把完整客户资料、代码、密钥、日志都塞给模型 | 最小必要上下文、字段级脱敏、按需检索 |
| 上下文污染持久化 | 本轮恶意内容被摘要或记忆写入后长期生效 | 写入前验证、记忆 quarantine、来源和版本审计 |

### 4.4 模型调用层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 数据外发不合规 | 敏感数据被发送到不允许的 provider 或 region | Model Gateway 按 data_class、tenant、region 路由 |
| fallback 绕过策略 | 主模型拒绝后切到较弱模型生成不应生成内容 | safety refusal 不进入普通 fallback |
| 模型版本漂移 | provider alias 变更导致安全行为变化 | model alias、版本锁定、eval gate、canary |
| 缓存串租户 | A 租户请求被 B 租户命中 | cache key 带 tenant、permission、prompt/model/schema version |

### 4.5 工具调用层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 越权工具调用 | Agent 调用了用户无权调用的 API | Tool Gateway 做 principal/scope/resource policy check |
| 参数注入 | 模型生成危险 SQL、shell、URL、路径 | schema validation、semantic validation、denylist、allowlist |
| 副作用不可控 | 删除、发邮件、退款、部署被自动执行 | risk scoring、HITL、dry-run、diff preview |
| 重试造成重复执行 | 超时后重复扣款或重复发送 | idempotency key、transaction log、compensation |
| 工具结果投毒 | 工具返回文本诱导后续模型泄露数据 | 工具结果按 observation 处理，不当作指令 |

### 4.6 执行环境层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 命令执行越界 | coding agent 执行破坏性命令 | sandbox、命令 allowlist、审批、最小文件权限 |
| 文件系统越界 | 修改项目外文件或读取敏感目录 | workspace jail、path normalization、read/write policy |
| 网络滥用 | SSRF、访问内网、下载不可信依赖 | egress allowlist、proxy、registry policy |
| 资源滥用 | fork bomb、无限循环、超大下载 | CPU/内存/时间/网络配额 |

### 4.7 记忆与 RAG 层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| RAG 索引投毒 | 攻击者把恶意文档写入知识库 | ingestion 审核、来源可信度、文档签名、索引版本 |
| 权限过滤缺失 | 检索返回用户不该看的文档 | retrieval-time ACL、document-level permission |
| embedding/vector weakness | 相似度被操纵，错误文档被召回 | hybrid retrieval、rerank、source trust、召回审计 |
| 记忆误写入 | 把攻击指令或错误事实写成长期偏好 | memory write validator、user confirmation、TTL |

### 4.8 输出与下游处理层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| insecure output handling | LLM 输出 HTML/SQL/代码被直接执行或渲染 | 输出编码、sandbox、SQL parameterization、代码审查 |
| 敏感信息泄露 | 输出包含 PII、密钥、内部链接、客户数据 | DLP、secret scanning、policy filter |
| 不当自动发送 | 输出未经确认发到外部人或群 | recipient preview、内容 diff、HITL |
| 过度依赖 | 用户把模型输出当作确定事实 | citation、confidence、evidence、限制自动决策 |

### 4.9 观测与运营层

| 风险 | 典型表现 | 预防手段 |
|---|---|---|
| 日志泄露 | prompt、工具结果、密钥、个人信息进入日志 | 日志脱敏、字段级采样、访问控制 |
| 无法追责 | 不知道谁触发了哪个工具、模型为什么这样选 | trace_id、run_id、principal、route_reason、audit log |
| 异常不可见 | 注入、越权、重复调用只在用户投诉后发现 | anomaly detection、security event、failure pool |
| 事故不可恢复 | 没有回滚、隔离、吊销和复盘机制 | incident playbook、kill switch、credential rotation |

---

## 五、威胁模型：从数据流而不是从 prompt 开始

Agent 安全建模应从数据流图开始：

```text
User / Tenant
  -> Product API
  -> Agent Runtime
  -> Context Builder
  -> Model Gateway
  -> Tool Gateway
  -> External Systems
  -> Memory / RAG / Artifact Store
  -> Output Channels
```

每条边都要问五个问题：

1. 这条边传输的数据是什么级别？
2. 谁能影响这条边的输入？
3. 这条边是否会触发真实副作用？
4. 这条边的结果会不会进入长期状态？
5. 如果这条边被操控，最坏后果是什么？

---

## 六、关键安全控制面

### 6.1 Policy Engine

Policy Engine 是 Agent 安全的决策中枢，输入是主体、资源、动作、上下文和风险信号。

```text
decision = policy.evaluate(
  principal=user/service/agent,
  action=tool_or_model_action,
  resource=document/api/customer/file,
  context=tenant/session/data_class/risk_score,
)
```

输出不只是 allow/deny：

| 决策 | 含义 |
|---|---|
| allow | 自动执行 |
| deny | 阻断并解释 |
| require_approval | 进入 HITL |
| require_redaction | 脱敏后继续 |
| require_sandbox | 只允许隔离执行 |
| degrade | 降级为草稿或建议 |

### 6.2 Identity 与 Permission Boundary

不要让 Agent “借用用户完整权限”。推荐分层：

```text
effective_permission =
  user_permission
  ∩ tenant_policy
  ∩ agent_role
  ∩ session_scope
  ∩ tool_required_scope
  ∩ data_policy
```

关键机制：

- Agent 有独立身份，不能只是用户 token 的透明代理。
- 每次工具调用都带 `principal`、`session_id`、`run_id`、`scope`。
- 高风险 scope 使用短期 capability token。
- 权限变更需要审计和回放。

### 6.3 Trust Boundary 与 Context Manifest

上下文必须带来源和信任级别：

```json
{
  "context_items": [
    {
      "type": "system_policy",
      "trust": "trusted",
      "source": "internal_policy_v3"
    },
    {
      "type": "web_page",
      "trust": "untrusted",
      "source": "external_url",
      "allowed_use": "evidence_only"
    }
  ]
}
```

原则：

- trusted 指令可以约束行为。
- untrusted 内容只能作为证据或数据，不应成为系统指令。
- 高风险动作必须回溯到用户意图或可信业务规则。

### 6.4 Tool Gateway

Tool Gateway 是最重要的副作用边界。

必须覆盖：

- tool registry：工具元数据、owner、版本、risk_level。
- schema validation：类型、枚举、范围、格式。
- semantic validation：业务约束和资源权限。
- risk scoring：金额、外发、删除、权限、生产环境。
- HITL：审批者、审批内容、审批超时、审批后恢复。
- audit：谁、何时、为何、调用什么、结果是什么。

### 6.5 Model Gateway

Model Gateway 是数据外发和模型行为漂移的边界。

必须覆盖：

- data_class 到 provider/region 的路由策略。
- safety refusal 不参与普通 fallback。
- 模型版本、prompt 版本、schema 版本绑定。
- token/cost/latency/fallback trace。
- 敏感字段进入模型前的脱敏策略。

### 6.6 Sandbox

对于 code agent、browser agent、data agent，sandbox 不是可选项。

最小要求：

- 文件系统隔离：限制读写根目录。
- 网络隔离：默认禁出网或使用 allowlist。
- 进程隔离：CPU、内存、时间限制。
- secret 隔离：默认不注入生产密钥。
- 命令策略：危险命令审批或禁止。
- 可恢复：执行前快照、执行后 diff。

---

## 七、典型攻击表现与防护映射

| 攻击/风险 | 表现 | 主要防护层 |
|---|---|---|
| 直接 prompt injection | 用户要求忽略系统规则、泄露系统 prompt | input guardrail、policy engine、output filter |
| 间接 prompt injection | 网页/文档/邮件诱导 Agent 调工具或外发数据 | context trust boundary、tool policy、HITL |
| tool injection | 工具返回内容诱导后续模型改变目标 | observation 隔离、source marking、step verifier |
| data exfiltration | 敏感数据被输出、发邮件或传到外部服务 | DLP、Model Gateway policy、Tool Gateway policy |
| excessive agency | Agent 自动执行高风险动作 | autonomy level、risk scoring、approval |
| insecure output handling | 输出被下游当 SQL/HTML/代码执行 | output validation、sandbox、下游安全编码 |
| vector/RAG weakness | 检索被投毒或权限过滤缺失 | ingestion governance、ACL retrieval、rerank |
| unbounded consumption | 长输入、循环、重试导致成本/资源异常 | budget、rate limit、max_steps、circuit breaker |
| supply chain | 模型、依赖、MCP server、工具插件不可信 | allowlist、SBOM/AIBOM、签名、依赖审查 |
| model/prompt drift | 升级后安全行为退化 | eval gate、canary、rollback |
| logging leakage | 日志记录 prompt、密钥、PII | redaction、log access control、sampling |
| agent hijacking | 本地端口、浏览器、插件或会话被劫持 | auth、local binding、CSRF/CORS、session isolation |

---

## 八、防护实现模式

### 8.1 分层防御，不信单点护栏

```text
Input Guardrail
  -> Context Trust Boundary
  -> Model Gateway Policy
  -> Tool Gateway Policy
  -> Sandbox
  -> Output Guardrail
  -> Audit / Detection
```

任何单点都可能失败。安全设计应假设：

- prompt 可以被绕过。
- 模型可能误判。
- 工具参数可能不可信。
- 外部内容可能恶意。
- 日志和缓存也可能成为泄露面。

### 8.2 风险动作统一建模

为所有工具动作建立统一风险字段：

| 字段 | 示例 |
|---|---|
| `side_effect` | true / false |
| `risk_level` | low / medium / high / critical |
| `data_class` | public / internal / confidential / regulated |
| `external_exposure` | none / internal / partner / public |
| `reversible` | true / false |
| `requires_approval` | true / false |
| `owner` | 工具责任团队 |

### 8.3 高风险动作审批内容

审批界面不能只问“是否允许”。必须展示：

- Agent 想做什么。
- 为什么要做。
- 会影响哪些资源。
- 输入证据来自哪里。
- 是否可回滚。
- 执行后如何验证。

### 8.4 安全事件标准化

每个安全相关事件应统一格式：

```json
{
  "event_type": "policy_block",
  "run_id": "run_123",
  "step_id": "step_004",
  "principal": "user_456",
  "tenant_id": "tenant_a",
  "action": "send_email",
  "resource": "external_recipient",
  "risk_level": "high",
  "decision": "require_approval",
  "reason": "external_exposure+confidential_context",
  "timestamp": "2026-06-14T10:00:00Z"
}
```

---

## 九、安全测试与评估

### 9.1 安全评估集

安全 eval 不应只测模型拒答，还要测系统边界。

| 测试集 | 覆盖 |
|---|---|
| direct injection set | 用户输入层注入 |
| indirect injection set | 网页、文档、邮件、工具结果注入 |
| data leak set | PII、secret、内部文档泄露 |
| tool misuse set | 越权、危险参数、高风险动作 |
| sandbox escape set | 文件、命令、网络边界 |
| RAG poisoning set | 恶意文档、权限绕过、过期知识 |
| output handling set | HTML/SQL/code/URL 下游风险 |
| cost abuse set | 长上下文、循环、重试、并发滥用 |

### 9.2 安全指标

| 指标 | 含义 |
|---|---|
| attack success rate | 攻击样例成功绕过比例 |
| policy block precision | 策略阻断是否准确 |
| false positive rate | 正常请求被误拦比例 |
| approval rejection rate | 审批被拒绝比例 |
| permission violation rate | 越权请求比例 |
| data leak rate | 敏感信息泄露比例 |
| unsafe tool call rate | 不安全工具调用比例 |
| incident time to detect | 安全事件发现时间 |
| incident time to contain | 安全事件遏制时间 |

### 9.3 发布闸门

安全相关变更必须经过：

```text
security regression set
  -> trace replay
  -> red-team sample
  -> policy diff review
  -> canary
  -> monitoring guardrail
  -> rollback plan
```

适用变更：

- model/prompt/schema 更新。
- 新工具接入。
- 权限策略变更。
- RAG 数据源变更。
- sandbox/network policy 变更。
- 输出渠道变更。

---

## 十、事故响应

Agent 安全事故不应只靠删日志和改 prompt。

### 10.1 发现

来源：

- policy block spike。
- unusual tool call pattern。
- data exfiltration alert。
- 用户举报。
- red team 命中。
- 成本异常。
- 外部供应商告警。

### 10.2 遏制

常见动作：

- 暂停高风险工具。
- 切换到建议模式。
- 禁用特定 provider、模型或 prompt version。
- 冻结相关 run/session。
- 吊销 capability token。
- 关闭外发渠道。
- 隔离受污染记忆或索引。

### 10.3 根因分析

至少回放：

- 原始用户输入。
- context manifest。
- model route decision。
- tool call proposal。
- policy decision。
- approval record。
- output channel。
- memory / RAG write。

### 10.4 修复

修复不应只有“加一句 prompt”。优先级：

1. 收紧权限和策略。
2. 修复工具 schema / validator / sandbox。
3. 调整上下文 trust boundary。
4. 更新安全 eval。
5. 最后才调整 prompt。

---

## 十一、与 OWASP / NIST / MITRE 的映射

| 外部框架 | 本文使用方式 |
|---|---|
| OWASP LLM Top 10 2025 | 用于 LLM 应用风险分类：prompt injection、sensitive information disclosure、supply chain、data/model poisoning、improper output handling、excessive agency、system prompt leakage、vector/embedding weaknesses、misinformation、unbounded consumption |
| OWASP Agentic AI Threats and Mitigations | 用于 Agentic AI 的 threat-model-based 风险视角，强调自治系统的能力、规模和风险扩大 |
| NIST AI RMF | 用于风险治理流程：把安全纳入设计、开发、使用、评估和持续管理 |
| MITRE ATLAS | 用于对抗性 AI 技术知识库和攻击链思考，辅助红队和检测 |

---

## 十二、联读关系

| 想解决的问题 | 联读 |
|---|---|
| 安全基础概念、prompt injection、jailbreak | [09-安全与对齐.md](./09-安全与对齐.md) |
| 工具权限、HITL、幂等、审计 | [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md) |
| 模型路由、数据外发、fallback、缓存隔离 | [26-Model Gateway与模型治理专题.md](./26-Model%20Gateway与模型治理专题.md) |
| Agent Runtime 状态、checkpoint、event log | [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md) |
| Eval、trace replay、CI gate | [24-Agent Eval Harness专题.md](./24-Agent%20Eval%20Harness专题.md) |
| Buddy 产品安全和评估 | [25.4-Buddy安全治理与评估体系.md](./25.4-Buddy安全治理与评估体系.md) |
| Context trust boundary | [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md) |
| Memory / RAG 安全 | [04.1-生产级Agent记忆工程.md](./04.1-生产级Agent记忆工程.md)、[05-RAG全景.md](./05-RAG全景.md) |

---

## 十三、官方资料入口

以下入口按 2026-06-14 校验，用于跟踪 Agent / LLM 安全分类和风险治理框架：

- OWASP Top 10 for LLM Applications：<https://owasp.org/www-project-top-10-for-large-language-model-applications/>
- OWASP LLM Top 10 2025：<https://genai.owasp.org/llm-top-10/>
- OWASP Agentic AI Threats and Mitigations：<https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/>
- NIST AI Risk Management Framework：<https://www.nist.gov/itl/ai-risk-management-framework>
- NIST Generative AI Profile：<https://doi.org/10.6028/NIST.AI.600-1>
- MITRE ATLAS：<https://atlas.mitre.org/>

---

## 十四、核心要点速记

1. Agent 安全是生命周期问题，不是 prompt 工程问题。
2. 最危险的边界是工具、副作用、数据外发、长期记忆和输出渠道。
3. untrusted 数据不能直接变成指令，高风险动作必须回溯可信意图。
4. Agent 权限应取用户、租户、Agent、会话、工具和数据策略的交集。
5. Tool Gateway 管副作用，Model Gateway 管模型调用和数据外发，Policy Engine 管决策。
6. 安全拒绝、合规阻断和权限失败不能通过 fallback 绕过。
7. 安全 eval 要测系统边界，而不是只测模型拒答。
8. 事故响应优先收紧权限、策略、sandbox 和 validator，最后才改 prompt。
