# Day 6 — 多 Agent 协作

> 目标：掌握主流多 Agent 拓扑、主流框架（LangGraph、AutoGen、CrewAI）核心机制，能针对场景选型。

---

## 一、核心概念

### 1.1 为什么需要多 Agent
- **角色分工**：复杂任务分给多个专长 Agent
- **上下文隔离**：每个 Agent 自己的 context，避免污染
- **并行加速**：独立子任务并发
- **模块化**：单个 Agent 可独立测试 / 替换
- **专业化模型**：不同 Agent 用不同模型（成本与能力平衡）

### 1.2 反对方观点（也是面试加分点）
**Cognition（Devin 团队）2024 的著名 blog《Don't Build Multi-Agents》**：
- 多 Agent 沟通带来**上下文割裂**
- 子 Agent 不知道全局意图，常做错决策
- 主 Agent 看到的子结果是"摘要"，丢失关键细节
- 单 Agent 长 context + 强模型反而更稳定

**结论**：多 Agent 不是银弹，先做单 Agent，证明瓶颈是上下文 / 专业化时再拆。

### 1.3 主流协作拓扑

#### Supervisor（中心调度）
```
       [Supervisor]
       /    |    \
   Agent1 Agent2 Agent3
```
- 一个 Supervisor 决定下一个谁干
- Workers 各司其职，不互相通信
- **优点**：路由清晰、可控
- **缺点**：Supervisor 是瓶颈

#### Hierarchical（多层级）
```
            [CEO]
           /     \
      [Team Lead A]   [Team Lead B]
        /    \         /    \
     Worker  Worker  Worker  Worker
```
- 多层 Supervisor
- 适合任务可层级分解（如"做一个产品" → 设计、开发、测试）

#### Network / Peer-to-Peer
```
   Agent A ←→ Agent B
      ↕         ↕
   Agent C ←→ Agent D
```
- 任意两 Agent 间可对话
- 适合：开放讨论、辩论
- 风险：无止境讨论

#### Swarm / Handoff
```
   Agent A ──handoff──→ Agent B ──handoff──→ Agent C
```
- 类似客服转接，谁能处理就接手
- 上下文随 handoff 传递
- OpenAI Swarm / Anthropic's swarm 模式

#### Pipeline / Sequential
```
   Agent A → Agent B → Agent C → Output
```
- 固定流水线
- 实际上接近 Workflow，不是真"Agent 协作"

### 1.4 角色范式
| 角色 | 职责 |
|------|------|
| **Planner** | 拆解任务、安排步骤 |
| **Executor / Worker** | 实际执行子任务 |
| **Critic / Reviewer** | 评估输出质量、给反馈 |
| **Router** | 决定下一步谁干 |
| **Aggregator / Synthesizer** | 汇总多个结果 |
| **Memory Keeper** | 维护共享上下文 |
| **Tool Specialist** | 专精某类工具调用 |

**经典组合**：
- Planner-Executor-Critic（PEC）
- Generator-Discriminator（GAN 思路）
- Multi-Expert + Aggregator

### 1.5 通信机制

#### 共享状态（Shared State）
- 所有 Agent 读写同一 state（如 LangGraph 的 StateGraph）
- 优点：信息透明
- 缺点：耦合高、并发冲突

#### 消息传递（Message Passing）
- Agent 间发消息（如 AutoGen GroupChat）
- 优点：松耦合
- 缺点：上下文割裂

#### Blackboard
- 共享公告板，Agent 自由读写
- 经典 AI 范式，现代少用

#### 工具传递
- Agent A 调用 Agent B 当作工具
- 简单直接，但不能复杂协作

### 1.6 关键设计问题

#### 何时拆分 Agent
**拆分信号**：
- 单 Agent context 频繁爆
- 任务有清晰角色边界（写 vs 审）
- 子任务可并行
- 需要不同模型 / prompt 专业化

**不拆分信号**：
- 任务高度耦合，子任务结果互相依赖
- 子任务都需要全局上下文
- 拆分后通信成本 > 隔离收益

#### Handoff 的信息粒度
- **全量传递**：所有上下文交接，token 爆
- **摘要传递**：只给摘要 + 子任务，可能丢关键
- **结构化传递**：定义清晰的传递 schema（如 task_goal + constraints + accumulated_findings）

#### 终止条件
- 显式：Agent 调用 `terminate` 工具
- 隐式：步数上限、目标达成（自评）、人工介入

### 1.7 Human-in-the-Loop（HITL）
- **何处插入**：关键决策点（如"调用支付工具前"）
- **形式**：
  - 阻塞式：必须等人确认
  - 旁路式：异步告警，默认继续
  - 监督式：人可随时打断
- **实现**：LangGraph 的 `interrupt` 机制、AutoGen 的 human input mode

---

## 二、主流框架对比

### 2.1 LangGraph（LangChain 出品）

**核心抽象**：
- **StateGraph**：图编排，节点 + 边 + 条件边
- **State**：TypedDict 定义，节点函数读 / 写 state
- **Reducer**：状态合并函数（如 `add_messages`）
- **Checkpointer**：持久化（内存 / SQLite / Postgres / Redis）
- **Thread**：每个 thread_id 一条历史
- **Streaming**：节点输出可流式
- **HITL**：`interrupt` 中断 + 恢复

**优势**：
- 图编排表达力强
- 支持循环、条件分支、并行
- 与 LangChain 生态深度整合
- 生产级特性最全（checkpoint、流式、HITL）

**劣势**：
- 学习曲线较陡
- 抽象多（state / reducer / channel）

**典型用法**：
```python
graph = StateGraph(State)
graph.add_node("planner", planner_fn)
graph.add_node("executor", executor_fn)
graph.add_node("critic", critic_fn)
graph.add_edge("planner", "executor")
graph.add_conditional_edges("executor", route_fn, {"critic":"critic", "end":END})
graph.add_edge("critic", "planner")  # 循环
app = graph.compile(checkpointer=checkpointer)
```

### 2.2 AutoGen（Microsoft）

**核心抽象**：
- **Agent**：基础单元，可对话、可调用工具
- **GroupChat**：多 Agent 在一个"群聊"中
- **GroupChatManager**：管理发言顺序
- **ConversableAgent**：可对话 Agent 基类
- **UserProxyAgent**：代理人类用户（也可执行代码）

**特点**：
- 对话驱动 — 一切都是 message
- 灵活但默认无约束（容易跑飞）
- 0.2 → 0.4 大改：新版用 Actor 模型

**优势**：
- 对话范式直观
- 适合"模拟讨论"类场景

**劣势**：
- 控制流不如 LangGraph 显式
- 容易陷入无意义讨论

### 2.3 CrewAI

**核心抽象**：
- **Agent**：role + goal + backstory + tools
- **Task**：description + expected_output + agent
- **Crew**：Agents + Tasks + Process
- **Process**：sequential / hierarchical

**特点**：
- 角色扮演风格（人设丰富）
- 任务驱动（不是消息驱动）
- 上手最快

**优势**：
- API 极简，适合快速搭建
- 角色定义清晰

**劣势**：
- 复杂逻辑不好表达
- 不够生产化

### 2.4 OpenAI Swarm

**核心抽象**：
- **Agent**：instructions + functions
- **handoff**：通过 function 返回新 Agent 切换
- 上下文随 handoff 自动传递

**特点**：
- 极简（< 1000 行代码）
- 教育性质，OpenAI 官方说"experimental"
- 已被新版的 Agents SDK 替代

### 2.5 OpenAI Agents SDK
- 2025 年发布
- 包含：Agent、Handoff、Guardrails、Tracing
- 强调可观测和安全
- 是 Swarm 的生产级升级

### 2.6 Anthropic 的方案
- 不推自己的多 Agent 框架
- 推 MCP 作为工具层
- 在 *Building Effective Agents* 中给出参考模式（不是框架）

### 2.7 框架选型矩阵

| 维度 | LangGraph | AutoGen | CrewAI | OpenAI Agents SDK |
|------|-----------|---------|--------|-------------------|
| 控制流 | 显式图 | 对话 | 任务 | Handoff |
| 学习曲线 | 中高 | 中 | 低 | 低 |
| 生产化 | 强 | 中 | 弱 | 中 |
| 调试 | 好（trace） | 中 | 弱 | 好 |
| 灵活性 | 极高 | 高 | 中 | 中 |
| 适合 | 复杂工作流 | 模拟讨论 | 快速原型 | OpenAI 栈 |

---

## 三、高频面试题（含答案）

### Q1：什么时候用多 Agent 比单 Agent 好？反之呢？

**答**：

**多 Agent 优势场景**：

1. **角色边界清晰**：写 vs 审、生成 vs 评估（GAN 思路）
2. **上下文隔离能避免污染**：研究 Agent 不该看到无关代码细节
3. **可并行子任务**：分头查 5 个网站
4. **不同模型组合**：Planner 用 Opus、Executor 用 Haiku
5. **角色专业化**：通过不同 prompt 让"同模型"扮演不同专家

**单 Agent 优势场景**（Cognition 主张）：

1. **任务高度耦合**：每步都依赖完整上下文
2. **长 context 模型够用**：Claude 200k / Gemini 2M 单 Agent 也能装下
3. **降低系统复杂度**：少一个 Agent 少一处 bug
4. **避免上下文割裂**：子 Agent 摘要传递必丢信息

**面试加分**：
- 引用 Cognition 反对 multi-agent 的观点
- "Anthropic 在 Building Effective Agents 中也建议先从单 Agent 起步"
- 提出**演进路径**：单 Agent 验证 → 单 Agent 长 context 优化 → 必要时拆 Agent

**判断框架**：
> 当**单 Agent 的瓶颈**真的是"context 装不下"或"角色边界混乱"时再拆，不要为了"看起来高级"而拆。

---

### Q2：LangGraph 的 StateGraph 相比 LangChain AgentExecutor 解决了什么？

**答**：

**AgentExecutor 的局限**：
- 黑盒：内部循环不可见
- 流程固定：ReAct 风格的线性循环
- 状态难持久化
- 难做条件分支、并行
- 难插入 HITL

**LangGraph 的核心改进**：

1. **显式图编排**：节点 + 边明确写出来，每一步可见可控

2. **任意控制流**：
   - 条件边（基于 state 路由）
   - 循环（A → B → A 可达）
   - 并行（fan-out / fan-in）

3. **状态管理**：
   - TypedDict 定义 schema
   - Reducer 控制合并语义
   - 可序列化 → 可持久化

4. **Checkpointer**：
   - 自动持久化每步 state
   - 支持中断恢复
   - 支持"时间旅行"调试（回到任意 step）

5. **HITL 原生支持**：
   - `interrupt()` 暂停执行
   - 用户提供输入 → resume

6. **流式输出**：
   - 节点输出可流式（token-level / message-level）
   - 状态变化可订阅

**心智模型**：
- AgentExecutor：runtime（黑盒、固定循环）
- LangGraph：DSL（你画图，框架执行）

**实战价值**：
- 复杂 Agent（多步、多分支、需持久化）—— LangGraph
- 简单 ReAct Agent —— AgentExecutor 也够（甚至原生 SDK）

---

### Q3：多 Agent 系统的上下文怎么共享？全共享 vs 隔离的取舍？

**答**：

**三种共享模式**：

**1. 全共享（Shared State）**
- LangGraph 默认：所有节点读写同一 state
- 优点：信息透明，每个 Agent 看全貌
- 缺点：context 膨胀、互相污染、并发冲突

**2. 显式传递（Message Passing）**
- AutoGen：Agent 间通过 message 沟通
- Handoff：上下文随转接传给下一个
- 优点：松耦合
- 缺点：传递时易丢信息，需要"翻译"

**3. 完全隔离**
- 每个子 Agent 拿独立 prompt
- 主 Agent 只看子结果摘要
- 优点：context 不爆
- 缺点：子 Agent 缺全局意图，可能跑偏

**实战取舍**：

- **小规模、紧耦合任务** → 全共享（信息完整最重要）
- **大规模、松耦合任务** → 隔离（避免污染）
- **生产实战常用混合**：
  - 主 Agent 维护全局 state
  - 子 Agent 拿"任务 + 必要上下文"
  - 子结果回传时结构化（不是原始 trace）

**典型结构化传递格式**：
```python
class SubTaskSpec:
    goal: str               # 子任务目标
    context_summary: str    # 必要上下文摘要
    constraints: list[str]  # 必须遵守的约束
    expected_output: str    # 期望输出格式
```

**Cognition 建议**：传递时**用主 Agent 的视角**重写子任务描述，确保子 Agent"懂"为什么做这事。

---

### Q4：怎么避免多 Agent 陷入无意义讨论 / 无限循环？

**答**：

**问题表现**：
- 两 Agent 反复"再考虑一下" — "好我再想想"
- 评估 - 修改 - 评估循环不收敛
- 群聊式讨论开 100 轮还没结论

**治理策略**：

**1. 硬约束**
- 最大轮数（如 max_rounds=10）
- 最大 token（成本兜底）
- 最大墙钟时间

**2. 终止条件显式化**
- 给 Agent 一个 `terminate` 工具
- Prompt 明确"达到 X 标准就终止"
- 用 Critic 给评分，>= 阈值终止

**3. 强 Supervisor**
- 中心调度而非自由群聊
- Supervisor 严格控制每轮谁说、说什么主题

**4. 防重复检测**
- 检测同一 Agent 连续输出相似内容
- 检测全局重复模式

**5. 阶段性 commit**
- 每达成一个里程碑，把结论固化进 state，禁止回滚讨论
- 避免无止境推翻重来

**6. 反对 GroupChat-style**
- Cognition 的观点：开放群聊容易跑飞
- 改用显式 DAG / 状态机

**Prompt 层面**：
```
You are in a multi-agent system. 
- If you have a concrete answer with >70% confidence, finalize it.
- Do NOT ask "should I continue?" — make a decision.
- If you've revised more than 3 times, the answer is good enough; ship it.
```

**监控**：
- 平均讨论轮数
- 收敛率（达到终止条件的比例）
- 异常长讨论告警

---

### Q5：CrewAI / AutoGen / LangGraph 怎么选？

**答**：

**简单决策树**：

**1. 快速原型 / 角色扮演场景 → CrewAI**
- 例：模拟一个市场调研团队
- API 极简，几行代码搭起来
- 不适合：需要复杂控制流、生产化

**2. 模拟讨论 / 多专家辩论 → AutoGen**
- 例：技术评审、医疗会诊
- 对话范式直观
- 不适合：固定流程任务

**3. 生产级复杂工作流 → LangGraph**
- 例：客服 Agent、Coding Agent、研究 Agent
- 显式控制流、HITL、持久化、流式
- 不适合：极简场景（杀鸡用牛刀）

**4. OpenAI 全栈 + 简单 → OpenAI Agents SDK**
- 优势：与 OpenAI 生态深度整合
- 限制：跨厂商弱

**5. 大厂 / 自研深度需求 → 直接用 SDK**
- LangGraph 仍是工程脚手架
- 但有时候直接基于 Anthropic / OpenAI SDK 写更可控

**面试加分回答**：
> 框架选型本质是**控制流抽象**的选择 —— 对话驱动（AutoGen）、任务驱动（CrewAI）、状态机驱动（LangGraph）。我会根据业务的本质形态选框架，而不是反过来用框架定义业务。

---

### Q6：LangGraph 的 Checkpointer 怎么用？解决什么问题？

**答**：

**Checkpointer 解决的问题**：

1. **长任务可中断恢复**：Agent 跑到一半挂了，从最后 checkpoint 继续
2. **HITL**：暂停等用户输入，恢复时从暂停点继续
3. **多轮对话持久化**：每轮的 state 自动存储，下次对话加载
4. **时间旅行调试**：回到任意历史 state，修改后重新运行
5. **A/B 比较**：同一 state 跑两条分支对比

**用法**：

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
app = graph.compile(checkpointer=checkpointer)

# 每次调用指定 thread_id
config = {"configurable": {"thread_id": "user_123"}}
result = app.invoke({"messages": [...]}, config=config)

# 中断后恢复（不需要传初始 state，从 checkpoint 加载）
app.invoke(None, config=config)

# 时间旅行：回到某个 checkpoint
history = app.get_state_history(config)
checkpoint = history[5]  # 5 步之前
app.invoke(None, {"configurable": {"thread_id": "user_123", "checkpoint_id": checkpoint.config["checkpoint_id"]}})
```

**Checkpointer 实现**：
- `MemorySaver`：内存（开发用）
- `SqliteSaver`：本地 SQLite
- `PostgresSaver`：Postgres（生产推荐）
- `RedisSaver`：Redis（高并发）

**关键设计**：
- 每个节点执行后自动 checkpoint
- 粒度细：node-level，不是整 graph 跑完才存
- State 必须可序列化（JSON / pickle）

**性能考虑**：
- 每步存 → 写入开销
- 优化：批量写、异步写、压缩

---

### Q7：怎么设计一个能"自我改进"的多 Agent 系统？

**答**：

**目标**：Agent 在使用中学习，提升后续表现，**不需要权重微调**。

**核心机制**：

**1. Reflexion 风格反思**
- 任务失败 → 生成 verbal reflection
- 反思存入 episodic memory
- 下次类似任务时召回 → 注入 prompt

**2. Trajectory 学习**
- 成功 trajectory 存入 success memory
- 失败 trajectory 存入 failure memory
- 新任务时用 RAG 召回相似过去案例做 few-shot

**3. Procedural Memory（工作流学习）**
- 高频工作流抽象为 SOP（标准流程）
- 存入 procedural memory
- 新任务匹配到 SOP 时直接用

**4. Critic 自动评估**
- LLM-as-Judge 评估每次输出
- 低分案例自动入失败池
- 高分案例自动入成功池

**5. 数据飞轮**
- 用户反馈（thumbs up/down）→ 标注信号
- 标注数据用于：
  - prompt 优化（A/B 测试新 prompt）
  - 工具描述改进
  - 微调 reranker / embedding

**6. Agent 自我编辑**
- 让 Agent 反思后修改自己的 prompt / 工具描述
- 类似 DSPy 的 auto-prompt 优化
- 高风险，需要 sandboxed test

**架构示例**：
```
[任务] → [Agent 执行] → [Trace 入库]
                          ↓
                     [Critic 评估]
                          ↓
              ┌───────────┴──────────┐
         [Success Pool]         [Failure Pool]
              ↓                       ↓
       [Few-shot 召回]       [Reflection 生成]
              ↓                       ↓
              └───────────┬──────────┘
                          ↓
                   [下次任务时注入]
```

**注意点**：
- 反思 / 经验本身可能错 → 加质量过滤
- Memory 膨胀治理（衰减、合并）
- 离线评估：自我改进真的更好吗？要回归测试

---

## 四、场景设计题（含答案）

### 场景 1：自动化研究 Agent

**题目**：设计一个 Deep Research Agent：用户给主题 → Agent 自动搜索、阅读、综合，最终输出研究报告。

**答案**：

**任务特性**：
- 开放探索（不知道要查多少轮）
- 多源信息（web、PDF、视频）
- 需要长输出（报告 5000+ 字）
- 上下文可能很长（要管理）

**架构**（混合：Supervisor + 子 Agent）：

```
[Lead Researcher Agent]  ← Supervisor
   │
   ├── Plan：把主题拆为 N 个子问题
   │
   ├── 对每个子问题，派出 Sub-Agent（可并行）
   │      ↓
   │   [Sub-Researcher]
   │      ├── search_web / search_papers / read_pdf
   │      ├── 多轮 ReAct 收集信息
   │      └── 汇总该子问题的 findings
   │
   ├── 收集所有子 findings
   ├── Critic：评估覆盖完整性、识别空白
   ├── 如有空白，派遣 Sub-Agent 补查
   │
   └── Writer Agent：基于所有 findings 写报告
         ↓
       [Report]
```

**关键设计**：

1. **拆分 Sub-Agent 的理由**：
   - 每个 sub 主题独立，并行加速
   - 每个 sub 自己的 context，不污染主流程
   - 子 Agent 只看子问题相关信息

2. **Sub-Agent 通信**：
   - 输入：子问题 + 高层背景（避免割裂）
   - 输出：结构化 findings（key claims + sources）
   - **不返回完整 trace**（成本爆炸）

3. **工具集**：
   - `web_search`（Tavily / Serper）
   - `fetch_url`
   - `read_pdf`
   - `arxiv_search`
   - `take_notes`（中间存储）

4. **上下文管理**：
   - Sub-Agent context 上限严控
   - 主 Agent 只汇总，不存原始 trace

5. **质量控制**：
   - Critic 检查：是否每个子问题都有可靠 source？
   - 引用必须给原文链接

6. **成本控制**：
   - Sub-Agent 用 Sonnet（够用）
   - Lead + Critic + Writer 用 Opus（决策准）
   - 工具调用并行化

7. **HITL**：
   - 用户可在 Plan 阶段修改子问题
   - 可中途打断、补充指令

**生产实践案例**：OpenAI Deep Research、Anthropic Research、Perplexity Pro 都是这个范式。

---

### 场景 2：代码 Agent（类似 Cursor / Claude Code）

**题目**：设计一个能在大型代码库中"做 PR 级修改"的 Agent。

**答案**：

**任务特性**：
- 代码库大（10k+ 文件）
- 任务长（30+ 步）
- 工具多（编辑、运行、grep、git）
- 容错性低（破坏性操作要谨慎）

**Cognition 的选择**：**单 Agent**（不拆多 Agent，因为代码任务高度耦合）

**Anthropic / Cursor 实际架构**：单 Agent 长 context + 强工具 + 子 Agent only for 隔离搜索

**核心架构**：

```
[Main Agent]  - 长 context（100k+），单线程主循环
  │
  ├── Tools
  │     ├── Read / Edit / Write
  │     ├── Grep / Find
  │     ├── Bash (sandboxed)
  │     ├── Run Tests
  │     └── (可选) Spawn Search Sub-agent
  │
  ├── Plan Mode：先规划再行动（可由用户审批）
  │
  ├── Context Management
  │     ├── 文件去重（同文件多次读保留最新）
  │     ├── 工具结果摘要
  │     └── 阶段 checkpoint
  │
  └── Safety
        ├── 破坏性操作 HITL（如 rm、git push）
        ├── Edit 前必读
        └── Test 失败时回滚
```

**关键设计**：

1. **为什么单 Agent**：代码修改高度耦合，子 Agent 缺全局视角易做错决策

2. **何时用 Sub-Agent**：
   - 大规模搜索（"找所有用到 X 的地方"）— 用搜索子 Agent 跑完只返回结论
   - 隔离的子任务（生成测试 fixture）

3. **上下文管理**：
   - 文件按 path 去重（多版本只留最新）
   - Bash 输出截断
   - 测试结果摘要（不存全部 stdout）

4. **工具设计**：
   - **必须先 Read 才能 Edit**（避免盲改）
   - Edit 用 diff 形式（小改）
   - Write 用于全文件覆盖（大改）
   - Bash 沙箱（白名单 / 黑名单命令）

5. **安全 HITL**：
   - 破坏性命令（rm -rf、git push --force）必须确认
   - 涉及外部副作用（部署、删数据库）必须确认

6. **失败处理**：
   - 测试失败 → 自动分析 + 修复重试
   - 重复失败 → 升级到用户

7. **可观测**：
   - 每步 trace 完整记录
   - 用户可"回退"到任意步骤
   - LangGraph Checkpointer 持久化

**面试加分**：
- 引用 Cognition 关于"不拆多 Agent"的理由
- 解释为什么 Cursor / Claude Code 选单 Agent
- 提到 Anthropic Computer Use 也是单 Agent

---

## 五、自测清单

- [ ] 5 种协作拓扑（Supervisor / Hierarchical / Network / Swarm / Pipeline）
- [ ] 7 种角色范式
- [ ] 3 种通信机制
- [ ] 多 Agent 拆分的信号 vs 反信号
- [ ] LangGraph 的 5 大核心特性（State/Reducer/Checkpointer/HITL/Streaming）
- [ ] LangGraph / AutoGen / CrewAI 的本质区别
- [ ] Cognition 反对多 Agent 的论据
- [ ] Self-improving Agent 的核心机制

---

## 六、延伸阅读

- Cognition — *Don't Build Multi-Agents*
- Anthropic — *Building Effective Agents*
- Anthropic — *How we built our multi-agent research system*
- LangGraph 官方文档
- AutoGen v0.4 文档
- Wu et al. — *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation*
