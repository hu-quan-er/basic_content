# Agent Runtime 专题

> 目标：把 Agent Runtime 从"agent loop 的执行器"提升到一个完整生产系统来理解：它负责把模型、工具、状态、记忆、策略、人工审批、可观测与恢复机制组织成一个可控、可恢复、可审计的运行单元。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Agent Runtime 的 Run/Step 生命周期、调度、状态、checkpoint、HITL、handoff、event log、trace 和恢复机制 | 最小完整代码实现见 [20.1-Agent Runtime完整实现.md](./20.1-Agent%20Runtime完整实现.md)；主流框架对比见 [20.2-Agent Runtime主流实现对比.md](./20.2-Agent%20Runtime主流实现对比.md)；Agent Loop 内部细节见 [16-Agent Loop专题.md](./16-Agent%20Loop专题.md)；可靠执行模式见 [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md) |

---

## 一、一句话定义

**Agent Runtime 是 Agent 的运行时控制层**：它接收一个用户任务，创建 `Run`，按步骤驱动模型推理、工具调用、上下文组装、状态持久化、预算控制、人工介入、handoff、追踪与恢复，直到任务完成、失败、暂停或取消。

如果只看一轮 ReAct，Agent 像是：

```text
LLM -> tool -> observation -> LLM -> final
```

但真实生产系统更像：

```text
Request
  -> Runtime.create_run()
  -> load session / memory / policy / budget
  -> build context
  -> model step
  -> validate structured action
  -> dispatch tool through gateway
  -> write state + event log + trace
  -> maybe pause for human approval
  -> resume from checkpoint
  -> final output / failed / canceled
```

所以 Agent Runtime 不是一个单纯的 while loop，而是一个围绕 loop 的完整执行环境。

---

## 二、为什么需要 Agent Runtime

简单 demo 中，开发者通常直接写：

```text
messages.append(user)
while True:
  response = llm(messages)
  if response.tool_calls:
    call_tool()
  else:
    return response
```

这个写法能说明 Agent 的基本原理，但一进入生产环境会立即遇到问题：

| 问题 | 没有 Runtime 时的后果 | Runtime 应提供的能力 |
|---|---|---|
| 任务可能跑很久 | 进程重启后状态丢失 | checkpoint、durable state、resume |
| 工具有副作用 | 重试可能重复扣款、重复发邮件 | 幂等键、事务边界、补偿动作 |
| 模型会走偏 | 无限循环、乱调工具、越权操作 | max turns、budget、policy、guardrails |
| 需要人工审批 | 无法优雅暂停和恢复 | `awaiting_approval` 状态、恢复入口 |
| 上下文会膨胀 | token 成本不可控、关键信息被挤出 | context builder、压缩、引用化 |
| 多 Agent 协作 | 状态互相污染、handoff 丢信息 | handoff contract、context envelope、state patch |
| 线上问题难排查 | 只看到最终答案，不知道中间发生什么 | event log、trace span、eval hooks |
| 服务要并发运行 | 同一用户多任务互相覆盖 | run/session/thread 隔离 |

**核心判断**：Agent Runtime 的价值不在于"让模型自动调用工具"，而在于让自动调用工具这件事可控、可恢复、可治理。

---

## 三、Agent Runtime 与相关概念的区别

| 概念 | 关注点 | 与 Runtime 的关系 |
|---|---|---|
| Agent Loop | 单个 Agent 内部的模型-工具迭代 | Runtime 包含并约束 loop |
| Orchestrator | 路由、计划、任务分解、状态流转 | 常是 Runtime 的核心模块 |
| Workflow Engine | DAG/状态机/长事务/重试/定时器 | 可作为 Runtime 的 durable execution 底座 |
| Tool Runtime | 工具执行、权限、隔离、超时、结果规范 | Runtime 通过 Tool Gateway 调用它 |
| Model Runtime | 模型服务、推理调度、KV cache、batching | Agent Runtime 调用模型服务，但不等同于模型推理 runtime |
| MCP | 工具/资源/提示词的连接协议 | Runtime 可把 MCP server 当工具来源 |
| A2A | Agent 与 Agent 跨边界协作协议 | Runtime 负责把本地 run 映射成 A2A task/context |
| Session Memory | 用户会话和长期记忆 | Runtime 决定何时加载、压缩、写回 |
| Trace/Eval | 观测与评估 | Runtime 是最自然的埋点位置 |

可以这样记：

```text
Agent Loop 解决"下一步做什么"
Agent Runtime 解决"这件事如何可靠地跑完"
Workflow Engine 解决"长流程如何持久执行"
Protocol 解决"不同系统如何互操作"
```

---

## 四、运行时的核心职责

### 4.1 Run 生命周期管理

Runtime 首先要把一次用户请求变成一个可管理的 `Run`。

```text
created
  -> queued
  -> running
  -> awaiting_tool
  -> awaiting_approval
  -> paused
  -> running
  -> completed

异常路径：
running -> failed
running -> canceled
awaiting_approval -> canceled
running -> timed_out
```

生产级实现不应该只记录一个 `status` 字符串，还需要明确：

| 字段 | 含义 |
|---|---|
| `run_id` | 一次任务执行的唯一标识 |
| `session_id` / `thread_id` | 会话或对话线程标识 |
| `agent_id` | 当前由哪个 Agent 负责 |
| `status` | created/running/awaiting_approval/completed 等 |
| `turn` / `step` | 当前执行到第几步 |
| `budget` | token、金额、时间、工具次数、最大轮数 |
| `pending_action` | 暂停时等待的工具、审批、用户输入或远程 Agent |
| `checkpoint_ref` | 可恢复的状态快照位置 |
| `trace_id` | 可观测链路标识 |

### 4.2 Step 调度

Agent Runtime 的最小调度单位通常是 `Step`。

```text
Run
  Step 1: model_call
  Step 2: tool_call.lookup_order
  Step 3: model_call
  Step 4: policy.await_approval
  Step 5: tool_call.issue_refund
  Step 6: model_call.final
```

每个 step 最好有明确输入和输出：

| Step 类型 | 输入 | 输出 |
|---|---|---|
| `model_call` | context、tools、instructions、state | assistant message、tool calls、final output |
| `tool_call` | tool name、args、auth、timeout、idempotency key | tool result、artifact、error |
| `policy_check` | action、state、user、risk | allow/deny/require_approval |
| `human_input` | question、context、options | user decision / edited args |
| `handoff` | target agent、contract、context envelope | remote task id / result |
| `memory_write` | candidate memory、source evidence | stored memory / rejected |
| `checkpoint` | current state | durable snapshot |

### 4.3 Context Builder

Runtime 不应该把所有消息无脑塞给模型，而应该有一个明确的上下文构造器：

```text
Context =
  system instructions
  + developer constraints
  + task contract
  + current run state summary
  + selected conversation history
  + retrieved memory
  + retrieved documents / artifacts references
  + available tools schema
  + policy hints
  + output schema
```

它要回答几个问题：

| 问题 | 典型策略 |
|---|---|
| 哪些信息每轮都注入？ | 任务目标、关键约束、当前状态摘要 |
| 哪些信息按需召回？ | 长期记忆、历史 ticket、文档片段 |
| 哪些信息不能进 prompt？ | 高敏凭证、越权数据、未授权用户数据 |
| 历史太长怎么办？ | 滑动窗口、摘要、artifact 引用、state manifest |
| 多 Agent 怎么传上下文？ | contract + context envelope + artifact ref |

本节只说明 Context Builder 在 Runtime 中的位置。单次上下文收集、过滤、预算、渲染和 Context Manifest 的完整方法见 [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md)。

### 4.4 Model Adapter

Runtime 通常会用 Model Adapter 把不同模型供应商统一成内部结构：

```text
InternalModelRequest
  model
  messages
  tools
  response_schema
  temperature
  max_tokens
  reasoning_budget
  metadata

InternalModelResponse
  message
  tool_calls
  structured_output
  usage
  finish_reason
  raw_provider_payload
```

这样 runtime 的核心状态机不需要绑定某个供应商。

### 4.5 Tool Gateway

工具调用是 Agent Runtime 最容易出事故的地方。Runtime 不应让模型直接调用真实工具，而应经过 Tool Gateway。

Tool Gateway 至少负责：

| 能力 | 说明 |
|---|---|
| schema 校验 | 模型给出的参数必须符合工具契约 |
| 权限校验 | 当前用户/Agent 是否有权调用 |
| 风险分级 | 读操作、写操作、资金操作、外部发送操作分级 |
| HITL | 高风险动作先暂停等待审批 |
| 超时与重试 | 工具慢、失败、部分成功时的处理 |
| 幂等 | 防止重试导致重复副作用 |
| 结果裁剪 | 大结果转 artifact，只把摘要放回上下文 |
| 审计 | 记录谁在什么上下文下触发了什么动作 |

这里保留 Runtime 调用工具时的接口视角。Function Calling 基础见 [03-工具调用.md](./03-工具调用.md)，可靠执行见 [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md)，Tool Gateway 作为独立平台的完整治理体系见 [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)。

### 4.6 State Store 与 Checkpoint

Agent Runtime 的状态不能只存在内存中。至少应区分四类数据：

| 数据 | 例子 | 推荐存储方式 |
|---|---|---|
| Run State | status、step、pending_action、budget | 强一致数据库 |
| Event Log | step started、tool called、approval requested | append-only 日志表 |
| Checkpoint | 可恢复的完整快照 | JSON/blob/object storage |
| Artifact | 文件、网页快照、检索结果、代码 diff | 对象存储 + 引用 |

Checkpoint 的重点不是"保存聊天记录"，而是保存足够恢复执行的信息：

```text
checkpoint =
  run_id
  status
  step_cursor
  messages
  structured_state
  pending_tool_call
  tool_results
  approvals
  artifact_refs
  budget_used
  model/provider metadata
```

### 4.7 Policy、Guardrails 与 HITL

Runtime 是策略执行的天然位置，因为它同时看得到用户、任务、状态、工具和输出。

常见策略点：

| 策略点 | 示例 |
|---|---|
| 输入前置策略 | prompt injection 检测、用户身份校验 |
| 上下文策略 | 不能把跨租户数据注入模型 |
| 工具前策略 | 退款超过 50 美元需要人工审批 |
| 工具后策略 | 工具结果包含敏感字段，需要脱敏 |
| 输出策略 | 医疗/法律/金融建议需要免责声明或转人工 |
| 预算策略 | 超过 10 轮或 2 美元成本则停止 |
| handoff 策略 | 只能把必要上下文发给远程 Agent |

HITL 不应该是"最后人来兜底"，而应该是 runtime 状态机的一部分：

```text
running
  -> policy_check detects high risk
  -> awaiting_approval(pending_tool_call)
  -> checkpoint
  -> human approves / edits / rejects
  -> resume
```

### 4.8 Handoff 与多 Agent 调度

多 Agent 下，Runtime 需要处理：

| 问题 | Runtime 责任 |
|---|---|
| 什么时候 handoff | 根据能力边界、工具权限、任务阶段决定 |
| 传什么上下文 | 只传目标 Agent 完成任务所需的 contract + context view |
| 状态谁拥有 | 明确 owner、writer、reader、merge policy |
| 远程任务如何等待 | `awaiting_remote_agent` 或异步 callback |
| 结果如何合并 | state patch、artifact import、conflict resolution |
| 失败怎么处理 | retry、fallback agent、转人工 |

这一块可以联读 [13.1-多Agent状态管理专题.md](./13.1-多Agent状态管理专题.md)。

### 4.9 Streaming 与 UI 事件

Agent Runtime 不只是后台执行器，还要面向 UI 输出稳定事件：

```text
run.created
step.started
model.delta
tool.call.started
tool.call.completed
approval.requested
approval.resolved
artifact.created
handoff.started
run.completed
run.failed
```

这些事件可以同时服务：

- 前端流式展示
- trace 追踪
- 审计日志
- 评估数据采集
- 失败恢复

### 4.10 可观测与评估

Agent Runtime 至少要记录：

| 维度 | 指标 |
|---|---|
| 质量 | success rate、task completion、tool correctness、human override rate |
| 延迟 | total latency、TTFT、model latency、tool latency、approval wait time |
| 成本 | token、model spend、tool spend、cache hit rate |
| 可靠性 | retry count、resume success、checkpoint age、timeout rate |
| 安全 | policy deny rate、sensitive data exposure、unsafe tool attempt |
| 上下文 | prompt tokens、retrieved memories、compressed tokens、lost key rate |

Runtime 是最适合做 trace 的层，因为它知道每个 step 的因果关系。

---

## 五、Agent Runtime 的参考架构

```text
                    +----------------------+
User / API / Queue ->| Runtime Controller   |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Run State Machine    |
                    | status / step / SLA  |
                    +----------+-----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
+----------------+    +----------------+    +----------------+
| Context Builder|    | Policy Engine  |    | Budget Manager |
+-------+--------+    +-------+--------+    +-------+--------+
        |                     |                     |
        v                     v                     v
+----------------+    +----------------+    +----------------+
| Model Adapter  |    | Tool Gateway   |    | Handoff Router |
+-------+--------+    +-------+--------+    +-------+--------+
        |                     |                     |
        v                     v                     v
   Model APIs          Tools / MCP / APIs       Other Agents

Persistent side:

+-------------+  +-------------+  +-------------+  +-------------+
| State Store |  | Event Log   |  | Checkpoints |  | Artifacts   |
+-------------+  +-------------+  +-------------+  +-------------+
        \              \              \              \
         +--------------+--------------+--------------+
                        v
                 Trace / Eval / Audit
```

---

## 六、核心数据模型

### 6.1 AgentSpec

描述 Agent 的静态能力：

```text
AgentSpec
  id
  name
  instructions
  tools
  output_schema
  max_turns
  autonomy_level
  policy_profile
  memory_profile
```

### 6.2 Run

描述一次任务执行：

```text
Run
  run_id
  agent_id
  session_id
  user_id
  input
  status
  current_step
  created_at
  updated_at
  completed_at
  final_output
```

### 6.3 RunState

描述可恢复的动态状态：

```text
RunState
  messages
  structured_state
  tool_results
  pending_action
  approvals
  artifact_refs
  memory_refs
  budget_used
```

### 6.4 Event

描述发生过什么：

```text
Event
  event_id
  run_id
  step_id
  type
  payload
  timestamp
```

### 6.5 Checkpoint

描述如何恢复：

```text
Checkpoint
  checkpoint_id
  run_id
  step_cursor
  state_snapshot
  created_at
```

### 6.6 PendingAction

描述运行时为什么暂停：

```text
PendingAction
  type: approval | user_input | remote_agent | timer | external_callback
  payload
  expires_at
  resume_policy
```

---

## 七、完整执行流程

以"订单退款 Agent"为例：

```text
1. 用户：帮我给 ORD-1001 退款
2. Runtime 创建 run，写入 created event
3. Runtime 加载用户、会话、工具、预算、策略
4. Context Builder 生成第一轮 prompt
5. 模型决定调用 lookup_order
6. Tool Gateway 校验参数和权限
7. 工具返回订单：金额 120，状态 lost
8. Runtime 写入 tool_result 和 checkpoint
9. 模型决定调用 issue_refund
10. Policy 发现退款金额超过阈值，需要人工审批
11. Runtime 状态变为 awaiting_approval，保存 pending_tool_call
12. 审批人批准
13. Runtime 从 checkpoint resume，执行 issue_refund
14. 模型生成 final answer
15. Runtime 标记 completed，写 event log 和 trace
```

这个流程的可运行版本见：

- [20.1-Agent Runtime完整实现.md](./20.1-Agent%20Runtime完整实现.md)
- [examples/agent_runtime_demo.py](./examples/agent_runtime_demo.py)

---

## 八、生产级设计清单

### 8.1 运行控制

- 是否有 `run_id`、`step_id`、`trace_id`？
- 是否能取消、暂停、恢复？
- 是否有最大轮数、最大工具次数、最大成本、最大 wall-clock 时间？
- 是否能从任意 checkpoint 恢复？
- 恢复后是否会重复执行有副作用工具？

### 8.2 状态与存储

- 哪些状态是强一致的？
- 哪些信息只是事件日志？
- 大对象是否 artifact-first，而不是塞进 prompt？
- checkpoint 是否包含 pending action？
- schema 变更后老 checkpoint 如何迁移？

### 8.3 工具治理

- 工具参数是否有 schema 校验？
- 工具是否分读、写、外发、资金、权限变更等级？
- 高风险工具是否需要审批？
- 工具调用是否有超时、重试、熔断？
- 副作用工具是否有幂等键？

### 8.4 上下文工程

- 每轮 prompt 的上下文来源是否可解释？
- 长历史是否有摘要或引用化策略？
- 检索记忆是否有证据和置信度？
- 是否防止 prompt injection 污染 system/developer 指令？
- 多 Agent handoff 是否只传必要上下文？

### 8.5 可观测与评估

- 每个 step 是否有事件？
- 工具输入输出是否可审计？
- 是否记录 token、成本、延迟、错误类型？
- 是否能按 run replay？
- 是否有线上失败样本进入 eval dataset 的机制？

### 8.6 安全与合规

- 租户隔离是否在 runtime 层强制？
- 敏感字段是否在上下文注入前脱敏？
- 人工审批是否记录审批人和理由？
- 输出是否经过策略校验？
- 是否支持数据保留、删除、审计导出？

---

## 九、常见反模式

| 反模式 | 问题 |
|---|---|
| 只有 while loop，没有 Run State | 进程重启或异常后无法恢复 |
| 把 messages 当唯一状态 | 结构化状态、工具结果、审批决策都难管理 |
| 工具直接暴露给模型 | 权限、审计、幂等、策略都缺失 |
| 所有历史都塞进 prompt | 成本高，且关键上下文可能丢失 |
| 人工审批靠业务代码 if-else | 无法通用暂停/恢复，也不易审计 |
| handoff 直接复制全量上下文 | 泄露、污染、成本高，且状态合并困难 |
| 没有 event log | 线上问题无法 replay，也无法系统评估 |
| 没有预算和停止条件 | 容易无限循环或成本失控 |

---

## 十、主流实现如何看

可以按三个层次看主流框架：

```text
轻量 Run Loop:
  OpenAI Agents SDK Runner
  LlamaIndex AgentWorkflow

显式状态图 / 多 Agent 编排:
  LangGraph
  AutoGen
  CrewAI Flow / Process
  Semantic Kernel Agents
  Google ADK

Durable Execution 底座:
  Temporal
  数据库 checkpoint
  队列 + worker + event log
```

选择时不要只问"哪个最火"，而要问：

| 关键需求 | 更该关注 |
|---|---|
| 需要强状态和暂停恢复 | LangGraph、Temporal、Google ADK session/state |
| 需要官方 OpenAI tool/handoff/tracing | OpenAI Agents SDK |
| 需要多 Agent 对话协作 | AutoGen、Semantic Kernel AgentGroupChat |
| 需要业务角色流程 | CrewAI |
| 需要 RAG 与 workflow 深度结合 | LlamaIndex Workflows / AgentWorkflow |
| 需要长期记忆 Agent | Letta/MemGPT 类 runtime |
| 需要严格工程可靠性 | Workflow engine + 自研 runtime contract |

详细对比见 [20.2-Agent Runtime主流实现对比.md](./20.2-Agent%20Runtime主流实现对比.md)。

---

## 十一、学习路径

建议按下面顺序读：

1. 先读本文，建立 Agent Runtime 的整体概念。
2. 读 [20.1-Agent Runtime完整实现.md](./20.1-Agent%20Runtime完整实现.md)，跑通最小 runtime。
3. 回看 [16-Agent Loop专题.md](./16-Agent%20Loop专题.md)，理解 runtime 内部的 loop。
4. 回看 [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md)，理解可靠执行细节。
5. 回看 [04.1-生产级Agent记忆工程.md](./04.1-生产级Agent记忆工程.md) 与 [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md)，理解 runtime 如何管理 memory/context。
6. 读 [20.2-Agent Runtime主流实现对比.md](./20.2-Agent%20Runtime主流实现对比.md)，理解主流框架分别把 runtime 做到了哪里。

---

## 十二、官方资料入口

- OpenAI Agents SDK Running agents: <https://openai.github.io/openai-agents-python/running_agents/>
- OpenAI Agents SDK Handoffs: <https://openai.github.io/openai-agents-python/handoffs/>
- OpenAI Agents SDK Sessions: <https://openai.github.io/openai-agents-python/sessions/>
- OpenAI Agents SDK Tracing: <https://openai.github.io/openai-agents-python/tracing/>
- LangGraph Overview: <https://docs.langchain.com/oss/python/langgraph/overview>
- LangGraph Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph Interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts>
- Google ADK Docs: <https://google.github.io/adk-docs/>
- AutoGen AgentChat: <https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html>
- CrewAI Concepts: <https://docs.crewai.com/en/concepts/crews>
- LlamaIndex AgentWorkflow: <https://docs.llamaindex.ai/en/stable/examples/agent/agent_workflow_basic/>
- Semantic Kernel Agents: <https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/>
- Temporal Docs: <https://docs.temporal.io/>
