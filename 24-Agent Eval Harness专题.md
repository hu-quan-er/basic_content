# Agent Eval Harness 专题

> 目标：把 Agent 评估从"人工试几条"变成可运行、可回放、可阻断发布、可持续改进的工程系统。Eval Harness 是一套围绕数据集、运行器、评分器、trace replay、CI gate、线上采样和 failure pool 的评估基础设施。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Eval Harness 的数据集、运行器、trace replay、评分器、CI gate、failure pool、报告和发布阻断机制 | 评估概念总览、三层评估、LLM-as-Judge 基础和数据飞轮见 [07-评估与可观测性.md](./07-评估与可观测性.md) |

---

## 一、一句话定义

**Agent Eval Harness 是用于批量运行 Agent 测试用例、采集 trace、执行评分器、生成报告并驱动发布决策的评估运行框架。**

它不是一篇评分 prompt，也不是一个 LLM judge，而是一条流水线：

```text
eval dataset
  -> eval runner
  -> agent/runtime execution or trace replay
  -> evaluators
  -> aggregate metrics
  -> regression comparison
  -> CI/release gate
  -> failure pool
```

生产 Agent 没有 Eval Harness，就很难回答：

- 改了 prompt 有没有退化？
- 换模型后工具调用是否变差？
- 新增记忆策略有没有污染输出？
- 线上失败能否回放？
- 发布前能否自动阻断风险版本？

---

## 二、Eval Harness 与普通测试的区别

| 普通单元测试 | Agent Eval Harness |
|---|---|
| 输入输出确定 | 输出可能开放、多路径 |
| 断言简单 | 需要 outcome/step/trajectory 多层评分 |
| 执行快 | 可能调用模型、工具、检索 |
| 结果稳定 | 有非确定性，需要重复运行和阈值 |
| 只看最终值 | 要看 trace、工具、成本、延迟 |
| 主要在 CI | 还要接线上采样和 failure pool |

**核心判断**：Agent eval 是软件测试、数据评测、可观测和发布治理的交叉点。

---

## 三、三层评估对象

### 3.1 Outcome Eval

看最终任务是否完成。

```json
{
  "case_id": "refund_001",
  "input": "Refund order ORD-1001",
  "expected_outcome": {
    "status": "completed",
    "refund_issued": true
  }
}
```

适合：

- 最终答案正确性。
- 业务状态是否达成。
- 引用是否支持结论。
- 用户任务是否完成。

### 3.2 Step Eval

看每一步是否正确。

```text
Should call lookup_order before issue_refund.
Should not call issue_refund if order status is delivered.
Should ask for approval if amount > 50.
```

适合：

- 工具选择。
- 参数正确性。
- 状态补丁。
- 权限判断。
- 检索质量。

### 3.3 Trajectory Eval

看执行路径是否合理。

```text
Did the agent loop too many times?
Did it recover from tool failure?
Did it repeat the same action?
Did it stop too early?
Did it ignore evidence?
```

适合：

- 多步 Agent。
- Browser Agent。
- Deep Research。
- Coding Agent。
- 多 Agent 协作。

---

## 四、Eval Harness 架构

```text
                    +------------------+
Eval Dataset ------>| Eval Runner      |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                                     |
          v                                     v
 Live Agent Execution                 Trace Replay
          |                                     |
          +------------------+------------------+
                             |
                             v
                    +------------------+
                    | Trace Collector  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Evaluators       |
                    | rules / tests    |
                    | LLM judge        |
                    | human review     |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Metrics / Report |
                    +--------+---------+
                             |
                 +-----------+-----------+
                 v                       v
              CI Gate              Failure Pool
```

---

## 五、数据集设计

### 5.1 Case Schema

一个 eval case 至少包含：

```json
{
  "case_id": "refund_high_value_requires_approval",
  "suite": "refund_agent",
  "input": "Please refund order ORD-1001 because it was lost.",
  "initial_state": {
    "order": {
      "id": "ORD-1001",
      "amount": 120,
      "delivery_status": "lost"
    }
  },
  "expected": {
    "must_call": ["lookup_order", "issue_refund"],
    "must_request_approval": true,
    "final_status": "completed"
  },
  "rubric": {
    "task_success": 0.5,
    "safe_tool_use": 0.3,
    "user_explanation": 0.2
  },
  "tags": ["tool", "hitl", "high_risk", "refund"]
}
```

### 5.2 数据集类型

| 类型 | 用途 |
|---|---|
| Golden Set | 核心成功路径，发布必跑 |
| Regression Set | 历史失败和线上事故，防回归 |
| Adversarial Set | 注入、越权、恶意输入 |
| Edge Set | 边界条件、空数据、异常状态 |
| Tool Failure Set | 429、timeout、500、权限错误 |
| Long-horizon Set | 多轮、长上下文、长任务 |
| Cost Set | 成本/延迟压力 |
| Shadow Set | 线上采样匿名化后回放 |

### 5.3 数据来源

```text
人工设计核心 case
  + 历史工单/客服记录
  + 线上失败 trace
  + 红队样本
  + 合成数据
  + 模型升级差异样本
```

不要只用合成数据。合成数据覆盖面好，但真实分布差。

---

## 六、Eval Runner

Eval Runner 负责批量执行 case。

### 6.1 Runner 输入

```json
{
  "suite": "refund_agent_v3",
  "agent_version": "2026-06-08",
  "model": "gpt-4.1",
  "prompt_version": "refund_prompt.v12",
  "tool_schema_version": "billing_tools.v5",
  "cases": ["refund_001", "refund_002"]
}
```

### 6.2 Runner 输出

```json
{
  "eval_run_id": "eval_20260608_001",
  "summary": {
    "pass_rate": 0.94,
    "avg_score": 0.87,
    "p95_latency_ms": 8120,
    "avg_cost_usd": 0.043
  },
  "failures": [
    {
      "case_id": "refund_timeout_003",
      "failure_modes": ["tool_retry_failed", "bad_final_status"]
    }
  ]
}
```

### 6.3 隔离原则

Eval Runner 不应污染生产：

- 使用 mock/staging tool。
- 使用测试租户。
- 禁止真实付款、发信、删除。
- 副作用工具默认 dry-run。
- 数据库用 sandbox fixture。
- 所有 eval run 有独立 trace_id。

---

## 七、Trace Replay

Agent eval 不一定每次都要重新跑模型。Trace replay 有两种：

### 7.1 Full Replay

重新执行：

```text
same input
same initial state
same tools or mock tools
new model/prompt
```

用于评估新版本真实效果。

### 7.2 Judge Replay

不重新执行 Agent，只用旧 trace 跑新 evaluator：

```text
stored trace
  -> evaluator v2
  -> compare previous eval result
```

用于升级评估器、重新标注 failure pool。

### 7.3 Replay 需要的 trace 字段

| 字段 | 用途 |
|---|---|
| input | 重放用户请求 |
| initial_state | 重建环境 |
| messages/context manifest | 分析上下文 |
| model calls | 观察模型输出 |
| tool calls/results | step eval |
| state patches | 状态正确性 |
| artifacts | 引用/截图/文件 |
| policy decisions | 安全评估 |
| final output | outcome eval |
| versions | 对比 prompt/model/tool/schema |

没有足够 trace，就没有真正的回放。

---

## 八、Evaluator 设计

### 8.1 规则评估器

能用程序判断就不用 LLM judge。

| 规则 | 示例 |
|---|---|
| schema valid | final output 符合 JSON Schema |
| tool called | 必须调用 lookup_order |
| tool not called | 不得调用 delete_user |
| order | lookup_order 必须早于 issue_refund |
| status | final status == completed |
| budget | steps <= 8 |
| citation | 每个 claim 有 evidence_ref |

### 8.2 LLM Judge

适合开放质量：

- 回答是否完整。
- 解释是否清晰。
- 报告结构是否合理。
- 引用是否看似支持 claim。
- 语气是否符合品牌。

LLM judge 要结构化输出：

```json
{
  "score": 0.82,
  "passed": true,
  "failure_modes": ["missing_detail"],
  "rationale": "The answer resolves the issue but omits refund timeline."
}
```

### 8.3 Human Review

高风险 case 必须有人类锚点：

- 金融。
- 医疗。
- 法律。
- 安全策略。
- 大额操作。
- 模型升级关键样本。

Human review 不是每天全量人工评估，而是校准 judge 和确认高风险失败。

### 8.4 Evaluator Ensemble

推荐组合：

```text
hard rules first
  -> domain-specific verifier
  -> LLM judge
  -> human review for disputed/high-risk cases
```

---

## 九、LLM Judge 校准

LLM-as-Judge 常见偏差：

| 偏差 | 表现 | 治理 |
|---|---|---|
| 长度偏差 | 长答案得分更高 | rubric 加简洁性，长度归一 |
| 格式偏差 | 漂亮格式掩盖事实错 | 事实与格式分开打分 |
| 位置偏差 | 更偏爱第一个答案 | 随机化顺序 |
| 自我偏好 | 偏爱同模型输出 | cross-model judge |
| 过度宽容 | 看起来合理就通过 | evidence checking |
| 不稳定 | 多次评分不同 | 固定温度、多 judge 投票 |

### 9.1 Judge 也要被评估

用人工标注集评估 judge：

```text
judge_accuracy
judge_human_agreement
false_pass_rate
false_fail_rate
calibration_curve
```

### 9.2 Rubric 要具体

弱 rubric：

```text
Rate the answer from 1 to 5.
```

强 rubric：

```text
Score task_success:
1.0 = correctly issued refund or correctly blocked impossible refund.
0.5 = identified correct policy but did not complete required action.
0.0 = wrong action, unsafe action, or unsupported final answer.

If the trace contains a tool call that violates policy, task_success must be 0.
```

---

## 十、指标体系

### 10.1 质量指标

| 指标 | 含义 |
|---|---|
| pass_rate | 通过率 |
| avg_score | 平均分 |
| task_success_rate | 任务成功率 |
| tool_accuracy | 工具选择/参数正确率 |
| trajectory_score | 路径质量 |
| citation_accuracy | 引用支持率 |
| unsafe_action_rate | 不安全动作比例 |
| false_done_rate | 假完成比例 |
| human_override_rate | 人工纠正比例 |

### 10.2 工程指标

| 指标 | 含义 |
|---|---|
| p50/p95 latency | 延迟 |
| avg_cost | 平均成本 |
| token_usage | token 消耗 |
| retry_count | 重试次数 |
| tool_error_rate | 工具错误率 |
| max_steps_hit_rate | 达到步数上限比例 |
| context_overflow_rate | 上下文溢出比例 |
| cache_hit_rate | 缓存命中率 |

### 10.3 发布指标

| 指标 | 用途 |
|---|---|
| regression_delta | 新旧版本差异 |
| critical_case_pass | 关键 case 是否通过 |
| failure_mode_diff | 新增失败类型 |
| cost_delta | 成本变化 |
| latency_delta | 延迟变化 |
| judge_confidence | judge 可靠性 |

---

## 十一、CI Gate

CI 里不要跑所有 eval，只跑分层集合。

### 11.1 分层

| 层 | 内容 | 时机 |
|---|---|---|
| Smoke Eval | 20-50 个核心 case | 每次 PR |
| Regression Eval | 历史失败 case | merge 前 |
| Full Eval | 全量多维数据集 | nightly |
| Red Team Eval | 安全攻击样本 | release 前 |
| Load/Cost Eval | 成本延迟 | 周期性 |

### 11.2 Gate 规则

```text
block release if:
  critical_case_pass_rate < 100%
  overall_pass_rate drops > 3%
  unsafe_action_rate > 0
  tool_accuracy drops > 5%
  avg_cost increases > 20% without approval
  p95 latency exceeds SLO
```

### 11.3 Flaky Case

Agent eval 会有波动，不能简单忽略 flaky。

治理：

- 重复运行 N 次。
- 记录 variance。
- 把 non-deterministic case 单独标记。
- 看稳定失败还是偶发失败。
- 对关键 case 要求多次全通过。

---

## 十二、Failure Pool

Failure Pool 是线上改进的核心。

### 12.1 来源

```text
用户差评
  -> support ticket
  -> production trace failed
  -> human override
  -> policy deny
  -> incident review
  -> red team
```

### 12.2 Failure Record

```json
{
  "failure_id": "fail_20260608_001",
  "source": "production_trace",
  "run_id": "run_abc",
  "task_type": "refund",
  "failure_modes": ["wrong_tool_order", "missing_approval"],
  "severity": "high",
  "root_cause": "prompt allowed direct refund without policy check",
  "fixed_by": "tool_gateway_policy_v4",
  "added_to_eval": true
}
```

### 12.3 聚类

失败不要只堆积，要聚类：

| 聚类 | 行动 |
|---|---|
| 工具参数错 | 改 tool schema/description |
| 引用不支持 | 改 RAG/evidence verifier |
| 假完成 | 改 stop condition |
| 成本过高 | 改 loop/context/cache |
| 安全拦截 | 改 policy/tool scope |
| judge 误判 | 改 rubric/judge calibration |

---

## 十三、线上采样评估

离线 eval 再好，也可能不代表真实流量。

### 13.1 采样策略

| 采样 | 用途 |
|---|---|
| random sample | 估计整体质量 |
| high-risk sample | 安全审计 |
| failure-biased sample | 快速发现问题 |
| new-version sample | 灰度监控 |
| high-cost sample | 降本 |
| user-negative sample | 产品改进 |

### 13.2 脱敏与权限

线上 trace 进入 eval 前必须：

- PII 脱敏。
- secrets 清除。
- tenant 隔离。
- 用户授权策略明确。
- 数据保留 TTL。
- 高敏样本人工访问审计。

### 13.3 Shadow Eval

```text
production traffic
  -> current agent answers user
  -> candidate agent runs in shadow
  -> no side effects
  -> compare outcome/tool/latency/cost
```

Shadow eval 适合模型升级、prompt 改版、工具 schema 改版。

---

## 十四、不同 Agent 的 Eval Harness

### 14.1 RAG Agent

重点：

- context precision/recall。
- faithfulness。
- citation support。
- answer correctness。
- no-answer accuracy。

### 14.2 Tool Agent

重点：

- tool selection。
- args correctness。
- retry behavior。
- unsafe action rate。
- side effect correctness。

### 14.3 Browser Agent

重点：

- task success。
- step success。
- screenshot/DOM evidence。
- false done。
- recovery from UI changes。

### 14.4 Coding Agent

重点：

- tests pass。
- patch correctness。
- no unrelated changes。
- code review findings。
- benchmark pass。

### 14.5 Multi-Agent

重点：

- handoff correctness。
- state patch validity。
- conflict resolution。
- duplicated work。
- context leakage。

---

## 十五、端到端例子：退款 Agent Eval

### 15.1 Case

```json
{
  "case_id": "refund_lost_high_value",
  "input": "Refund order ORD-1001 because it was lost.",
  "initial_state": {
    "order": {"id": "ORD-1001", "amount": 120, "status": "lost"}
  },
  "expected": {
    "must_call_in_order": ["lookup_order", "issue_refund"],
    "must_request_approval": true,
    "final_output_contains": ["Refund", "ORD-1001"]
  },
  "critical": true
}
```

### 15.2 Evaluators

```text
rule_tool_order:
  trace tool calls must match lookup_order before issue_refund

rule_approval:
  issue_refund amount > 50 requires approval.requested event

rule_final:
  final_output must mention refund id or blocked reason

judge_user_explanation:
  score clarity and completeness
```

### 15.3 Gate

```text
critical cases: 100% pass
approval rule: 100% pass
unsafe action rate: 0
avg cost: <= baseline * 1.1
p95 latency: <= 10s
```

---

## 十六、Eval Report

一份有用的报告应包含：

```text
Eval Run: refund_agent_v4_20260608
Compared to: refund_agent_v3_20260601

Quality:
  pass_rate: 94.0% -> 96.5% (+2.5)
  critical_pass: 100% -> 100%
  unsafe_action_rate: 0% -> 0%

Regression:
  new failures: 3
  fixed failures: 12
  worsened suites: browser_refund (-4%)

Cost/Latency:
  avg_cost: $0.041 -> $0.047 (+14.6%)
  p95_latency: 8.2s -> 9.1s

Top Failure Modes:
  missing_citation: 8
  tool_timeout_recovery_failed: 3
  verbose_final_answer: 2

Release Decision:
  canary only, monitor browser_refund suite
```

---

## 十七、反模式

| 反模式 | 问题 |
|---|---|
| 只用 10 条手工样本 | 覆盖不足 |
| 只看最终答案 | 工具和路径错误不可见 |
| 只用 LLM judge | 偏差大，安全错误可能漏 |
| 没有版本记录 | 不知道退化来自模型、prompt 还是工具 |
| 线上失败不进 eval | 永远重复同类错误 |
| CI 不阻断 | eval 只是报告，不影响发布 |
| 不评估成本 | 质量提升可能不可承受 |
| judge 不校准 | 分数看似精确但不可信 |
| 用生产工具跑 eval | 可能产生真实副作用 |
| 只跑成功路径 | 一上线就被边界 case 打穿 |

---

## 十八、自测清单

- [ ] 能区分 outcome、step、trajectory eval。
- [ ] 能设计 eval case schema。
- [ ] 能解释 trace replay 的两种模式。
- [ ] 能设计 rule evaluator 和 LLM judge 的组合。
- [ ] 能说明 judge 偏差和校准方法。
- [ ] 能设计 CI gate。
- [ ] 能设计 failure pool 数据结构。
- [ ] 能设计线上采样评估策略。
- [ ] 能为 Tool Agent、Browser Agent、RAG Agent 分别设计指标。
- [ ] 能解释为什么 eval harness 是发布基础设施。

---

## 十九、高频问题

### Q1：Agent 没有标准答案，怎么评估？

先拆成 outcome、step、trajectory。能程序判断的用规则和状态验证，开放质量用 LLM judge，高风险样本用人工校准。不要试图只用一个分数概括所有行为。

### Q2：为什么 trace 对 Agent eval 这么重要？

最终答案看不出路径是否安全、是否多调工具、是否绕过审批、是否浪费成本。Trace 让 eval 能判断工具、状态、上下文、策略和路径质量。

### Q3：线上失败怎么进入 eval？

把失败 trace 脱敏后写入 failure pool，标注 failure mode、severity、root cause，再转成 regression case。修复后该 case 必须长期留在回归集。

### Q4：LLM judge 能不能作为上线 gate？

可以作为一部分，但不能单独作为高风险 gate。高风险发布 gate 应以硬规则、业务状态、工具审计和人工校准为主，LLM judge 负责开放质量维度。

### Q5：怎么处理 eval 波动？

固定模型版本和参数，记录 seed/temperature，关键 case 多次运行，统计 variance。对非确定性 case 用阈值和置信区间，不要凭单次结果下结论。

---

## 二十、关联阅读

- [07-评估与可观测性.md](./07-评估与可观测性.md)：Agent 评估总览。
- [08.1-生产级Agent应用工程.md](./08.1-生产级Agent应用工程.md)：上线门槛和评估体系。
- [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md)：可靠执行和 failure pool。
- [16-Agent Loop专题.md](./16-Agent%20Loop专题.md)：trajectory 与 loop 评估。
- [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md)：event log 与 trace。
- [21-Computer Use与Browser Agent专题.md](./21-Computer%20Use与Browser%20Agent专题.md)：Browser Agent 评估。
- [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)：工具测试与 tool eval。

---

## 二十一、官方资料入口

- OpenAI Evals guide: <https://platform.openai.com/docs/guides/evals>
- OpenAI Agents SDK Tracing: <https://openai.github.io/openai-agents-python/tracing/>
- Anthropic Demystifying evals for AI agents: <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>
- OpenTelemetry GenAI semantic conventions: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- Ragas: <https://docs.ragas.io/>
- DeepEval: <https://docs.confident-ai.com/>
- LangSmith Evaluation: <https://docs.smith.langchain.com/evaluation>
