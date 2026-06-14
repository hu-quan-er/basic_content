# Model Gateway 与模型治理专题

> 目标：把“调用模型 API”提升为一层可治理的生产基础设施来理解。Model Gateway 负责统一模型接入、路由、限流、预算、缓存、版本、灰度、fallback、观测和安全边界，是生产级 Agent 的模型控制面。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Model Gateway / LLM Gateway 的架构、路由、模型注册、fallback、预算、缓存、观测、版本发布和治理 | Agent Runtime 生命周期见 [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md)；工具执行治理见 [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)；Agent 全生命周期安全治理见 [27-Agent安全生命周期专题.md](./27-Agent安全生命周期专题.md)；性能成本通用方法见 [08-工程化性能成本可靠性.md](./08-工程化性能成本可靠性.md)；发布运维总蓝图见 [08.1-生产级Agent应用工程.md](./08.1-生产级Agent应用工程.md) |

---

## 一、一句话定义

**Model Gateway 是业务系统 / Agent Runtime 与模型供应商之间的治理层**：上游只表达“我要完成什么类型的模型调用”，Gateway 决定用哪个 provider、哪个模型、哪个版本、走什么参数、是否命中缓存、是否允许调用、如何计费、如何重试、如何观测。

最小心智模型：

```text
Agent Runtime
  -> Model Gateway
      -> Model Registry
      -> Routing Policy
      -> Budget / Rate Limit
      -> Prompt / Model Version
      -> Cache
      -> Provider Adapter
      -> Observability
  -> OpenAI / Anthropic / Gemini / Bedrock / Azure / vLLM / local model
```

核心判断：

> 生产系统里不应该让业务代码直接散落调用各家模型 SDK。模型调用要像数据库、支付、消息队列一样被统一封装、治理和观测。

---

## 二、为什么需要 Model Gateway

Demo 里常见写法：

```python
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(
    model="gpt-4.1",
    messages=messages,
)
```

这能跑通，但不能支撑生产级 Agent。

| 生产问题 | 直接调模型 API 的后果 | Model Gateway 能力 |
|---|---|---|
| 多供应商 | 业务代码到处写 provider SDK | 统一 API、Provider Adapter |
| 模型频繁升级 | 修改代码、难回滚 | Model Alias、版本锁定、灰度 |
| 成本失控 | 不知道哪个功能烧钱 | token/cost 归因、预算、限额 |
| 延迟不稳定 | 单 provider 抖动影响全局 | fallback、hedging、load balancing |
| 上下文敏感 | PII、机密、越权数据可能发给错误模型 | 数据分级、region/provider policy |
| 质量回退 | 换模型后工具调用或格式变差 | eval gate、shadow、A/B、canary |
| 提示词散落 | prompt 版本不可追踪 | prompt/model/schema 绑定版本 |
| 线上排障难 | 只看到最终错误 | model call trace、usage、provider error taxonomy |

---

## 三、Model Gateway 和相关概念的区别

| 概念 | 关注点 | 与 Model Gateway 的关系 |
|---|---|---|
| Model Adapter | 把某个 provider 的请求/响应转成内部统一结构 | Gateway 内部组件 |
| Model Gateway | 模型调用的统一入口、路由、治理、观测和成本控制 | 本文主角 |
| Agent Runtime | 管 run、step、state、checkpoint、HITL | Runtime 通过 Gateway 调模型 |
| Tool Gateway | 管工具注册、权限、幂等、沙箱和审计 | 与 Model Gateway 平行，分别管模型和工具 |
| Inference Runtime | vLLM/TGI/Triton 等模型服务和 GPU 调度 | Gateway 可以把自托管 inference 当 provider |
| Eval Harness | 验证模型/prompt/路由变更是否退化 | Gateway 发布策略的质量闸 |
| Observability Platform | 统一 trace、metrics、logs | Gateway 是模型调用埋点入口 |

可以这样记：

```text
Agent Runtime 决定“这个任务下一步要推理”
Model Gateway 决定“这次推理用哪个模型、怎样安全低成本地调用”
Inference Runtime 决定“模型在 GPU 上怎样高效跑”
```

---

## 四、架构位置

```text
[Product / API]
      ↓
[Agent Runtime / Workflow]
      ↓
[Context Builder]
      ↓
[Model Gateway]
  ├─ Auth / Tenant / Feature Context
  ├─ Prompt + Model Registry
  ├─ Routing Policy
  ├─ Budget / Rate Limit
  ├─ Cache
  ├─ Provider Adapter
  ├─ Retry / Fallback / Circuit Breaker
  └─ Trace / Cost / Quality Event
      ↓
[Provider / Inference Backend]
  OpenAI / Anthropic / Gemini / Azure / Bedrock / vLLM / local
```

Model Gateway 的输入不应只是 `model="xxx"`，而应携带完整调用上下文：

| 输入 | 说明 |
|---|---|
| `task_type` | chat、tool_planning、code_edit、summarize、judge、embedding、rerank |
| `quality_tier` | low、standard、high、critical |
| `latency_slo_ms` | 本次调用允许的延迟预算 |
| `budget_class` | 免费用户、企业用户、内部任务、离线批处理 |
| `data_class` | public、internal、confidential、regulated |
| `tenant_id` / `feature_id` | 成本、权限、灰度和观测归因 |
| `prompt_version` | prompt 与模型版本绑定 |
| `output_contract` | JSON schema、tool args schema、final output schema |

---

## 五、核心能力拆解

### 5.1 Provider Adapter：统一模型接口

不同 provider 在消息格式、tool calling、streaming、reasoning 参数、错误码、token 计费上都不一致。

Gateway 内部应统一成内部协议：

```json
{
  "model_call_id": "mc_001",
  "task_type": "tool_planning",
  "messages": [],
  "tools": [],
  "response_schema": null,
  "routing_hint": {
    "quality_tier": "standard",
    "latency_slo_ms": 3000
  },
  "metadata": {
    "tenant_id": "t_acme",
    "feature": "refund_agent",
    "run_id": "run_123"
  }
}
```

Provider Adapter 输出也要统一：

```json
{
  "provider": "openai",
  "model": "gpt-4.1",
  "finish_reason": "tool_calls",
  "message": {},
  "tool_calls": [],
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 180,
    "cached_tokens": 900
  },
  "latency_ms": 1320,
  "raw_error": null
}
```

### 5.2 Model Registry：别让业务写死模型名

业务代码不应写：

```text
model = "provider-specific-model-name"
```

而应写逻辑别名：

```text
model_alias = "agent.tool_planner.standard"
model_alias = "agent.final_answer.high"
model_alias = "eval.llm_judge.strict"
model_alias = "coding.patch_generator.high"
```

Registry 负责把别名映射到具体 provider/model/deployment：

| 字段 | 用途 |
|---|---|
| `alias` | 业务可见模型名 |
| `task_type` | 适配哪类任务 |
| `provider` | OpenAI、Anthropic、Gemini、Bedrock、vLLM 等 |
| `model` | 真实模型名 |
| `deployment` | Azure deployment、自托管 endpoint、region |
| `version` | 固定版本或受控 alias |
| `capabilities` | tools、vision、audio、JSON schema、long context |
| `cost_profile` | 输入/输出/缓存 token 成本 |
| `latency_profile` | p50/p95/p99 |
| `risk_class` | 是否允许处理敏感数据 |
| `eval_status` | 是否通过当前回归集 |

### 5.3 Routing Policy：模型选择不是 if-else

路由要综合多个约束：

```text
候选模型 =
  capability match
  ∩ data policy
  ∩ tenant allowlist
  ∩ region / compliance
  ∩ budget
  ∩ latency SLO
  ∩ eval passed
```

常见路由策略：

| 策略 | 适用 |
|---|---|
| capability routing | tool calling、vision、long context、JSON schema |
| cost routing | 低价值任务走小模型，高价值任务走强模型 |
| latency routing | 在线交互走低延迟模型，离线任务走高质量模型 |
| data routing | 敏感数据只走企业合规 provider 或自托管模型 |
| tenant routing | 不同客户有不同模型白名单和预算 |
| eval routing | 只有通过对应任务 eval 的模型才能接流量 |
| canary routing | 新模型只接 1% 或指定租户流量 |
| fallback routing | 主模型失败或超时后切备用模型 |

### 5.4 Retry、Fallback 与 Circuit Breaker

模型调用失败不能简单“再试一次”。

| 失败 | 处理 |
|---|---|
| 429 / rate limit | 换 deployment、退避、切同能力备用模型 |
| 5xx / provider outage | circuit breaker，短期熔断 provider |
| timeout | 根据任务是否可重试决定重试或降级 |
| context too long | 触发压缩、换长上下文模型或失败返回 |
| schema invalid | repair loop 或切更稳的结构化输出模型 |
| safety refusal | 不应盲目 fallback 绕过，需要进入策略层 |
| quality regression | 由 eval/canary 发现后停止放量 |

生产里要区分：

```text
retry: 同 provider / 同模型重试
fallback: 换 provider / 换模型
degrade: 降低任务能力，例如从自动执行变成建议草稿
block: 安全或合规原因直接阻断
```

### 5.5 Budget、Rate Limit 与 Chargeback

Model Gateway 是成本控制的天然位置。

需要记录：

| 维度 | 示例 |
|---|---|
| tenant | 哪个客户或团队 |
| feature | 哪个产品功能 |
| run | 哪个 Agent 任务 |
| model alias | 哪类能力消耗 |
| provider/model | 实际消耗在哪家模型 |
| prompt version | 哪个 prompt 版本导致成本变化 |
| cache hit | 是否命中缓存 |
| fallback count | 是否因失败多花钱 |

预算策略：

```text
per user daily token limit
per tenant monthly spend limit
per feature cost budget
per run max model calls
per task_type max reasoning budget
```

一旦超预算：

| 场景 | 处理 |
|---|---|
| 低风险问答 | 切小模型或返回简版 |
| 长任务 Agent | 暂停并请求用户确认继续 |
| 企业客户核心流程 | 走预留预算或高优先级队列 |
| 离线批处理 | 延后到低峰或批量执行 |

### 5.6 Cache：模型缓存不是只有一种

| 缓存类型 | 缓存什么 | 适用 | 风险 |
|---|---|---|---|
| response cache | 完整请求到完整响应 | 固定 FAQ、分类、标准提示 | 用户上下文变化导致错答 |
| semantic cache | 相似请求复用响应 | 高频相似问法 | 语义误判、事实过期 |
| prompt/prefix cache | system、tools、长前缀 | 长上下文 Agent、tool schema 大 | provider 支持差异 |
| embedding cache | 文档/查询向量 | RAG、tool retrieval | embedding 版本变更 |
| rerank cache | query-doc 排序 | 高重复检索 | 文档更新后失效 |

缓存必须带隔离键：

```text
tenant_id
user_or_session_scope
model_alias / real_model
prompt_version
tool_schema_version
data_policy_version
```

核心判断：

> 缓存省钱，但不能跨租户、跨权限、跨数据版本复用。缓存命中率不是唯一目标，安全隔离和正确性优先。

### 5.7 Prompt、Model、Schema 的绑定发布

生产 Agent 中，模型不是独立变更对象。一次真实发布通常包含：

```text
prompt version
model alias mapping
tool schema version
output schema version
context policy version
eval suite version
```

错误做法：

```text
把 gpt-x 换成 gpt-y，其他都不动，直接全量上线
```

正确做法：

```text
shadow replay
  -> offline eval
  -> small canary
  -> online metrics
  -> gradual rollout
  -> rollback plan
```

### 5.8 Observability：每次模型调用都要可解释

至少记录：

| 字段 | 说明 |
|---|---|
| `model_call_id` | 单次模型调用 ID |
| `run_id` / `step_id` | 所属 Agent 任务 |
| `tenant_id` / `feature_id` | 成本和问题归因 |
| `model_alias` | 业务模型名 |
| `provider` / `real_model` | 实际调用目标 |
| `prompt_version` | 输入版本 |
| `route_reason` | 为什么选这个模型 |
| `fallback_chain` | 是否发生 fallback |
| `usage` | input/output/cache token |
| `latency` | TTFT、total latency |
| `cost` | 估算或账单成本 |
| `quality_signal` | eval、用户反馈、规则检查结果 |
| `error_type` | provider error、gateway error、policy block |

这类 trace 后续会进入：

- 成本报表。
- 质量回归分析。
- 线上 failure pool。
- 模型升级评估。
- 供应商 SLA 评估。

---

## 六、Routing 决策流程

```text
1. 解析调用意图
   task_type / quality_tier / data_class / latency_slo / budget

2. 过滤候选模型
   capability / tenant policy / data policy / region / eval status

3. 估算成本与延迟
   token estimate / p95 latency / cache possibility

4. 选择主模型
   route score = quality_score - cost_penalty - latency_penalty

5. 配置备用链
   fallback candidates / retry policy / timeout

6. 执行调用
   provider adapter / stream handling / structured output parsing

7. 记录结果
   trace / usage / cost / quality / errors

8. 反馈更新
   latency profile / failure rate / canary metrics / budget
```

伪代码：

```python
def route_model_call(req):
    candidates = registry.find(task_type=req.task_type)
    candidates = filter_capability(candidates, req.required_capabilities)
    candidates = filter_data_policy(candidates, req.data_class, req.tenant_id)
    candidates = filter_eval_status(candidates, req.eval_suite)
    candidates = filter_budget(candidates, req.budget_class)

    scored = []
    for model in candidates:
        score = (
            model.quality_score(req.task_type)
            - cost_penalty(model, req.estimated_tokens)
            - latency_penalty(model, req.latency_slo_ms)
            + cache_bonus(model, req.cache_key)
        )
        scored.append((score, model))

    primary = max(scored)[1]
    fallback_chain = build_fallback_chain(primary, candidates, req)
    return RouteDecision(primary=primary, fallbacks=fallback_chain)
```

---

## 七、典型策略矩阵

| 调用类型 | 推荐策略 |
|---|---|
| 简单分类 / 意图识别 | 小模型、低温度、短超时、强缓存 |
| 工具选择 / tool planning | 支持 tool calling 的稳定模型，优先 schema 合规率 |
| 最终回答生成 | 按用户等级和质量要求路由，允许流式 |
| 代码生成 / patch | 高质量模型，绑定测试和 review eval |
| LLM-as-Judge | 固定 judge 模型和 rubric 版本，不随意 fallback |
| 摘要压缩 | 小模型或专用 summarizer，关注信息保真 |
| 敏感企业数据 | 合规 provider、自托管或指定 region，禁跨境 |
| 离线批处理 | 低峰、batch、成本优先 |
| 语音实时 Agent | 低延迟模型、严格 timeout、可降级 |

---

## 八、与 Agent Runtime 的接口契约

Runtime 不应关心 provider 细节，只需要一个稳定接口：

```text
ModelGateway.invoke(ModelRequest) -> ModelResult
```

### 8.1 ModelRequest

```json
{
  "run_id": "run_123",
  "step_id": "step_004",
  "task_type": "tool_planning",
  "quality_tier": "standard",
  "latency_slo_ms": 3000,
  "data_class": "internal",
  "required_capabilities": ["tool_calling", "json_schema"],
  "prompt_version": "refund_agent.planner.v12",
  "messages": [],
  "tools": [],
  "output_schema": null,
  "metadata": {
    "tenant_id": "t_acme",
    "feature": "refund_agent"
  }
}
```

### 8.2 ModelResult

```json
{
  "model_call_id": "mc_789",
  "model_alias": "agent.tool_planner.standard",
  "provider": "anthropic",
  "real_model": "provider-model-id",
  "route_reason": "tool_calling+latency_slo+eval_passed",
  "message": {},
  "tool_calls": [],
  "structured_output": null,
  "usage": {
    "input_tokens": 1800,
    "output_tokens": 240
  },
  "cost": 0.012,
  "latency_ms": 1480,
  "fallback_used": false
}
```

---

## 九、常见实现形态

### 9.1 SDK Adapter 型

业务代码里封装一个 `ModelClient`，统一调用多家 SDK。

优点：

- 简单。
- 延迟最低。
- 小团队容易开始。

缺点：

- 多语言服务重复实现。
- 成本、审计、限流分散。
- 很难做统一灰度和预算。

适用：

- 单应用。
- 模型调用量不大。
- 没有多租户治理要求。

### 9.2 独立 Gateway 服务型

所有模型请求先到一个内部服务。

优点：

- 统一治理。
- 多团队复用。
- 易做预算、日志、限流、fallback、canary。

缺点：

- 多一跳网络延迟。
- Gateway 自身要高可用。
- 需要定义内部协议和运维责任。

适用：

- 企业内部多产品共用模型。
- 需要统一账单、审计、权限。
- 需要多 provider fallback。

### 9.3 API Gateway 插件型

在已有 API Gateway 上加 AI 插件或 AI 路由能力。

优点：

- 复用认证、限流、日志和流量治理。
- 易接入企业网关体系。

缺点：

- Agent 语义能力可能不足，需要额外服务补齐 prompt/model/eval 版本治理。

适用：

- 已有成熟 API Gateway。
- 首要诉求是统一代理、认证、流量控制。

### 9.4 托管 AI Gateway 型

使用 Cloudflare、Portkey 等托管 gateway。

优点：

- 上手快。
- 观测、缓存、限流、fallback 等能力开箱。

缺点：

- 数据、合规、成本模型要重新评估。
- 深度定制受产品边界影响。

适用：

- 快速验证。
- 中小团队。
- 非强合规场景。

---

## 十、主流实现映射

| 实现 | 典型能力 | 适合关注点 |
|---|---|---|
| LiteLLM Proxy | 统一多 provider 接口、虚拟 key、预算/限流、缓存、fallback、负载均衡、日志指标 | 自建轻量 Model Gateway |
| Cloudflare AI Gateway | 多 provider 接入、analytics/logging、caching、rate limiting、retry/fallback | 托管边缘 AI Gateway |
| Kong AI Proxy / AI Gateway | API Gateway 插件化，统一 OpenAI 风格格式，代理多 provider | 已有 Kong/API Gateway 体系 |
| Portkey AI Gateway | universal API、fallback、conditional routing、semantic cache、circuit breaker、load balancing、canary | 托管或自托管 AI Gateway |
| 自研 Gateway | 完全定制模型路由、成本、合规和 eval 发布链路 | 大型企业或强合规场景 |

这些实现的共同点不是“换一个 base_url”，而是把模型调用变成可治理、可观测、可回滚的基础设施。

---

## 十一、失败模式与治理

| 失败模式 | 表现 | 治理 |
|---|---|---|
| 模型名写死 | 升级或回滚要改代码 | model alias + registry |
| fallback 绕过安全 | 主模型拒绝后换模型生成危险内容 | safety refusal 不进入普通 fallback |
| 缓存串租户 | A 客户请求被 B 客户命中 | cache key 带 tenant/scope/policy |
| 只看平均成本 | 少数长任务烧掉预算 | per run / per tenant / p95 cost |
| 只看成功率 | 模型返回了但质量退化 | eval + user feedback + trace replay |
| 无版本锁定 | provider alias 自动变化导致行为漂移 | 固定版本 + controlled rollout |
| 无错误分类 | 所有失败都重试 | provider/gateway/policy/schema error taxonomy |
| 日志泄露 | prompt 和响应含 PII/secrets | DLP、脱敏、字段级日志策略 |
| 多 provider 输出不一致 | 同样 schema 某些 provider 更易漂移 | provider-specific eval + schema repair |
| Gateway 单点故障 | 所有模型调用不可用 | HA、降级、本地 fallback、健康检查 |

---

## 十二、设计清单

- [ ] 业务代码只调用 Model Gateway，不直接散落 provider SDK。
- [ ] 有 Model Registry 和业务 alias。
- [ ] 每个 alias 绑定 task type、capability、成本、延迟、eval 状态。
- [ ] 路由策略考虑 capability、数据分级、租户、region、预算、SLO。
- [ ] 有 fallback、retry、timeout、circuit breaker。
- [ ] 安全拒绝和合规阻断不会被普通 fallback 绕过。
- [ ] token/cost 按 tenant、feature、run、prompt version 归因。
- [ ] 缓存有租户、权限、模型、prompt、schema、数据版本隔离。
- [ ] prompt/model/tool schema/output schema 作为一组发布对象。
- [ ] 新模型上线必须经过 offline eval、shadow、canary、A/B 或等价流程。
- [ ] 每次 model call 有 trace、usage、latency、cost、route reason。
- [ ] provider error 与 gateway error 可区分。
- [ ] 有预算超限降级策略。
- [ ] 有供应商不可用时的降级和沟通机制。

---

## 十三、核心问题（含解答）

### Q1：Model Gateway 和 Tool Gateway 最大区别是什么？

Model Gateway 管“模型推理资源”，解决 provider、模型、版本、成本、延迟、fallback、缓存和质量治理。Tool Gateway 管“真实世界动作”，解决工具权限、参数校验、幂等、沙箱、审批和审计。

两者都属于 Agent 的控制面，但风险不同：Model Gateway 的主要风险是质量、成本、数据外发和 provider 依赖；Tool Gateway 的主要风险是副作用、越权和真实系统被错误修改。

### Q2：为什么不能直接在业务代码里写模型名？

因为模型名是变化最快的生产依赖之一。直接写死会导致升级、回滚、灰度、A/B、成本归因和租户差异都变得困难。业务应使用稳定 alias，例如 `agent.tool_planner.standard`，由 Gateway 统一映射到真实 provider/model/deployment。

### Q3：Fallback 是否总是好事？

不是。超时、429、5xx 可以 fallback；schema 不稳定可以换更稳模型；但安全拒绝、权限阻断、合规策略失败不能通过 fallback 绕过。Fallback 是可靠性机制，不是绕过安全策略的机制。

### Q4：Model Gateway 如何省成本？

四类手段：

1. 路由：简单任务走小模型，复杂任务走强模型。
2. 缓存：固定请求、前缀、embedding、rerank 结果复用。
3. 预算：按用户、租户、功能、run 限制 token 和金额。
4. 观测：找到高成本 prompt、长上下文、低价值调用和失败重试。

### Q5：新模型上线为什么要绑定 eval？

模型升级会影响工具调用、结构化输出、事实性、安全拒绝、风格和延迟。只看少量人工样例不够。正确做法是用固定回归集和线上 shadow/canary 对比，再逐步放量，并保留快速回滚路径。

---

## 十四、和其他文档的联读关系

| 想解决的问题 | 联读 |
|---|---|
| Agent 运行时如何调用模型 | [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md) |
| 模型调用怎样降成本 | [08-工程化性能成本可靠性.md](./08-工程化性能成本可靠性.md)、[19.1-Agent推理加速落地.md](./19.1-Agent推理加速落地.md) |
| 工具调用如何治理 | [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md) |
| 模型变更如何评估 | [24-Agent Eval Harness专题.md](./24-Agent%20Eval%20Harness专题.md) |
| 生产级系统总蓝图 | [08.1-生产级Agent应用工程.md](./08.1-生产级Agent应用工程.md) |
| 敏感数据和合规 | [09-安全与对齐.md](./09-安全与对齐.md) |

---

## 十五、官方资料入口

以下入口按 2026-06-14 的官方文档校验，用来对照本文中的能力拆解和产品映射。

- LiteLLM Proxy Quick Start：<https://docs.litellm.ai/docs/proxy/quick_start>
- LiteLLM Routing / Load Balancing：<https://docs.litellm.ai/docs/routing>
- Cloudflare AI Gateway Overview：<https://developers.cloudflare.com/ai-gateway/>
- Cloudflare AI Gateway Caching：<https://developers.cloudflare.com/ai-gateway/features/caching/>
- Kong AI Proxy Plugin：<https://developer.konghq.com/plugins/ai-proxy/>
- Portkey AI Gateway：<https://portkey.ai/docs/product/ai-gateway>

---

## 十六、核心要点速记

1. Model Gateway 是模型调用控制面，不是简单 SDK 封装。
2. 业务代码应使用 model alias，不直接写 provider/model 名。
3. 路由要同时考虑能力、质量、成本、延迟、数据分级、租户和 eval 状态。
4. Fallback 只解决可靠性，不能绕过安全拒绝或合规阻断。
5. 缓存必须带租户、权限、模型、prompt、schema 和数据版本隔离。
6. prompt/model/schema/tool/context policy 应作为一组发布对象管理。
7. 每次模型调用都要记录 route reason、usage、latency、cost、fallback 和质量信号。
8. 新模型上线必须经过离线 eval、shadow/canary、线上观测和可回滚发布。
