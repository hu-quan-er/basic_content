# Agent Loop 专题：从单次迭代到生产级控制循环

> 目标：把 Agent 的"心脏"——agent loop——彻底讲透。覆盖单次迭代解剖、终止条件、上下文管理、规划范式对 loop 的改造、工具调用机制、错误与循环检测、控制流变体、主流框架的 loop 实现差异，以及性能/可观测视角。

---

## 一、为什么要单独深挖 Agent Loop

前面 《LLM基础与Agent本质》~《AI Coding Harness最佳实践》 把范式、工具、记忆、RAG、多 Agent、评估、安全、可靠执行都覆盖了，但有一个被反复提到、却从没单独拆开的东西：**agent loop（智能体循环 / agentic loop）**。

它是 Agent 区别于"一次性 LLM 调用"的本质所在。几乎所有 Agent 框架（LangChain AgentExecutor、LangGraph、OpenAI Agents SDK、Claude 的 tool-use 循环、CrewAI、AutoGen）核心都是同一个循环的不同封装。

**核心判断**：Agent loop 不是一个 `while True`，而是一个带有"上下文组装 → 模型推理 → 动作解析 → 工具执行 → 观察回填 → 终止判断"六个阶段的受控循环，每个阶段都有自己的失败模式和工程对策。理解"怎么实现一个 agent"，本质就是能把这个循环讲清楚。

需要重点搞清楚的问题：
- 一个 agent loop 内部到底发生了什么？
- loop 什么时候停？怎么防止它停不下来？
- 每轮历史都在涨，上下文爆了怎么办？
- ReAct / Plan-Execute / Reflexion 对这个 loop 各做了什么改造？
- LangGraph 的 loop 和 LangChain AgentExecutor 的 loop 有什么区别？

---

## 二、最小心智模型

### 2.1 一句话定义

Agent loop 是"让 LLM 通过反复观察外部反馈来逐步逼近目标"的控制循环。和单次 prompting 的根本区别：**步数不确定、依赖外部观察、需要在循环中维护状态**。

### 2.2 最小伪代码

```python
def agent_loop(goal, tools, max_steps=20):
    history = [system_prompt(tools), user(goal)]
    for step in range(max_steps):
        # 1. 上下文组装 + 2. 模型推理
        resp = llm(history, tools=tools)

        # 3. 动作解析：模型要么给最终答案，要么要调工具
        if resp.is_final():
            return resp.content                 # 6. 终止：拿到答案

        # 4. 工具执行
        results = [run_tool(c) for c in resp.tool_calls]

        # 5. 观察回填
        history.append(resp)                    # assistant 的工具调用
        history.extend(tool_messages(results))  # tool 的返回

    return finalize_on_budget_exhausted(history)  # 6. 终止：预算耗尽
```

这 20 行就是几乎所有 Agent 框架的内核。后面所有内容都是在给这个循环的每一行"加工程"。

同一套循环用 **Go + [eino](https://github.com/cloudwego/eino)**（CloudWeGo 的 LLM 应用框架）手写如下——`ToolCallingChatModel` 负责推理，循环与终止完全在自己手里：

```go
// 手写 agent loop：对应上面的 Python agent_loop
func agentLoop(ctx context.Context, cm model.ToolCallingChatModel,
	tools map[string]tool.InvokableTool, toolInfos []*schema.ToolInfo,
	goal string, maxSteps int) (string, error) {

	chat, err := cm.WithTools(toolInfos) // 绑定工具，返回带 tools 的新实例
	if err != nil {
		return "", err
	}
	history := []*schema.Message{
		schema.SystemMessage("你是一个会使用工具的助手"),
		schema.UserMessage(goal),
	}

	for step := 0; step < maxSteps; step++ {
		// ① 上下文组装 + ② 模型推理
		resp, err := chat.Generate(ctx, history)
		if err != nil {
			return "", err
		}
		history = append(history, resp) // ⑤ 回填 assistant 消息

		// ③ 动作解析：没有 tool_call 即视为最终答案 → ⑥ 终止
		if len(resp.ToolCalls) == 0 {
			return resp.Content, nil
		}

		// ④ 工具执行 + ⑤ 观察回填
		for _, call := range resp.ToolCalls {
			out, err := tools[call.Function.Name].InvokableRun(ctx, call.Function.Arguments)
			if err != nil {
				out = "ERROR: " + err.Error()
			}
			history = append(history, schema.ToolMessage(out, call.ID))
		}
	}
	return "", errors.New("reached max steps without final answer") // ⑥ 预算耗尽
}
```

如果不想自己写循环，eino 内置的 ReAct agent（`flow/agent/react`）就是这同一个 loop 的封装，`MaxStep` 即硬预算上限：

```go
agent, _ := react.NewAgent(ctx, &react.AgentConfig{
	ToolCallingModel: cm,
	ToolsConfig:      compose.ToolsNodeConfig{Tools: []tool.BaseTool{searchTool, finishTool}},
	MaxStep:          20, // 硬上限，等价于 Python 版的 max_steps（默认 12）
})
out, _ := agent.Generate(ctx, []*schema.Message{schema.UserMessage(goal)})
```

### 2.3 ReAct：经典的 loop 形态

ReAct（Reasoning + Acting）把每轮拆成三段交替：

```
Thought: 我需要先查一下汇率
Action: currency_api(from="USD", to="CNY")
Observation: 1 USD = 7.24 CNY
Thought: 现在可以算了
Action: finish(answer="724 元")
```

**Thought → Action → Observation** 的循环就是 agent loop 的"文本可读版"。现代 function-calling 把 Thought 隐式化、把 Action 变成结构化 tool_call，但循环骨架没变。

**核心结论**：function calling 时代的 agent loop，本质还是 ReAct，只是把 Action 从"模型吐文本再解析"换成了"模型直接吐结构化 tool_call"，把解析的脆弱性交给了模型供应商。

---

## 三、单次迭代解剖（最该讲细的部分）

把一轮 iteration 拆成六个阶段，每个阶段单独看输入输出和失败模式。

```
        ┌─────────────────────────────────────────────┐
        │              一轮 Iteration                   │
        │                                               │
  ① 上下文组装 → ② 模型推理 → ③ 动作解析 → ④ 工具执行 │
        ↑                                          │     │
        │              ⑤ 观察回填  ←───────────────┘     │
        │                   │                            │
        └──────── 否 ── ⑥ 终止判断 ── 是 ──→ 输出最终结果 │
        └─────────────────────────────────────────────┘
```

### 3.1 阶段①：上下文组装（Context Assembly）

每轮喂给模型的 context 通常包括：

| 组成 | 说明 | 是否每轮变化 |
|------|------|--------------|
| System prompt | 角色、约束、工具说明、输出格式 | 否（可缓存） |
| 工具 schema | 可用工具定义 | 否（可缓存） |
| 静态知识 / few-shot | 检索到的资料、示例 | 视情况 |
| 历史消息 | 之前的 thought/action/observation | 是（单调增长） |
| 当前状态 / scratchpad | 已知变量、中间结论 | 是 |

**失败模式**：把所有历史无脑拼接 → 上下文爆炸、Lost in the Middle、成本飙升。
**对策**：稳定前缀（system + tools）放最前面利于 prompt caching；历史按需压缩（见第五节）。

### 3.2 阶段②：模型推理（Inference）

模型在这一步决定"下一步做什么"：继续思考、调哪个工具、还是给最终答案。

关键工程点：
- **温度**：agent loop 通常用低温（0~0.3），保证动作稳定可复现。
- **是否开 thinking / reasoning**：复杂规划开 reasoning 模型（见 《Reasoning Models专题》），简单工具编排用普通模型省钱。
- **是否强制工具**：`tool_choice=required` 可强制本轮必须调工具，防止过早 finish。

### 3.3 阶段③：动作解析（Action Parsing）

从模型输出里提取"要执行什么"。两种范式：

| 范式 | 解析方式 | 脆弱性 |
|------|----------|--------|
| 文本 ReAct | 正则/解析 `Action: xxx` | 高，模型格式不稳就崩 |
| Function Calling | 直接读结构化 `tool_calls` | 低，供应商保证 schema |

**失败模式**：幻觉工具（调了不存在的工具）、参数 schema 不合法、该 finish 时还在调工具。
**对策**：解析后做白名单校验 + 参数 schema 校验，非法就把错误回填让模型自纠（见第七节）。

### 3.4 阶段④：工具执行（Tool Execution）

- **并行 vs 串行**：本轮多个无依赖 tool_call 应并行执行（降延迟）；有依赖的拆到不同轮。
- **超时 / 重试 / 幂等**：写操作要带 idempotency_key（详见 《Agent工程细节与可靠执行》）。
- **结果裁剪**：超大返回（如 10MB JSON）不能原样回填，要摘要或截断 + 存引用。

### 3.5 阶段⑤：观察回填（Observation Integration）

把工具结果作为 `tool` 角色消息加回 history，进入下一轮。

**关键决策**：回填多少？
- 全量回填：信息完整但吃 token。
- 摘要回填：省 token 但可能丢关键信息。
- 引用回填：只回填一个 handle/id，需要时再取（适合大数据）。

### 3.6 阶段⑥：终止判断（Termination Check）

见第四节，单独展开——这是最容易被忽略却最容易出事故的地方。

**核心结论**：真正理解 agent loop 的标志，是能讲清"一轮 iteration 的六个阶段各自的失败模式和对策"，而不只是知道怎么调 API。

---

## 四、终止条件（loop 怎么停）— 概览

停不下来的 agent = 烧钱 + 卡死；停太早 = 任务没做完就收尾。终止逻辑必须**显式、多重**，是 agent loop 最容易出事故的一环。

### 4.1 五类终止条件

| 类型 | 触发 | 处理 |
|------|------|------|
| 正常完成 | 模型给出 final answer / 调用 `finish` 工具 | 返回结果 |
| 预算耗尽 | 超过 max_steps / max_tokens / max_cost / max_wall_time | 强制收尾，返回"尽力而为"结果 + 标注未完成 |
| 死循环检测 | 检测到重复动作 | 中断或换策略 |
| 死路 / 不可恢复错误 | 工具反复失败、无可用动作 | 升级到人工或降级返回 |
| 外部中断 | 用户取消 / 超 deadline / 改需求 | 优雅取消，保存 checkpoint |

### 4.2 两道必备闸

最低配置：**显式 finish 动作**（正常终止）+ **硬预算上限**（强制终止），再叠加死循环检测、错误升级、外部中断三类软检测。

**核心结论**：生产级 agent 一定要有显式终止动作 + 硬预算上限两道闸，不能只靠模型"自觉"说完成。

> 📖 **本节是 agent loop 的核心难点，完整展开（五个设计维度、完成信号陷阱、死循环检测算法、收尾 finalize 策略，以及 LangChain / LangGraph / OpenAI Agents SDK / Claude / AutoGen / CrewAI 等主流产品的真实停止机制与 Python+Go/eino 代码）单独拆到子文档：**
>
> **《[16.1-Agent Loop 停止条件设计](./16.1-Agent%20Loop停止条件设计.md)》**

---

## 五、上下文管理（loop 的核心难点）

历史随轮次**单调增长**，迟早撞上 context window。这是 agent loop 最难、也最能区分工程水平的地方。

> 📖 为什么会有窗口上限、为什么窗口没满也会退化（自注意力 O(n²)、KV Cache、Lost in the Middle），从模型原理层的解释见《[17-上下文窗口的模型原理](./17-上下文窗口的模型原理.md)》。

### 5.1 增长来源

每轮新增：assistant 的 thought + tool_call + 每个 tool 的返回。工具返回往往是大头（网页、日志、JSON）。

### 5.2 五种控制策略

| 策略 | 做法 | 代价 |
|------|------|------|
| 截断（Truncation） | 丢最早的消息，保留近 N 轮 | 丢失早期关键信息 |
| 摘要（Summarization / Compaction） | 把旧历史压成摘要再续 | 摘要丢细节、需额外 LLM 调用 |
| 外置记忆（Scratchpad / Memory） | 关键结论写到外部 store，context 只留指针 | 检索可能漏 |
| 分层（Working / Episodic / Long-term） | 仿 MemGPT 分层调度 | 实现复杂 |
| 工具结果引用化 | 大结果存 artifact，context 只放 id | 需要二次取数 |

### 5.3 Compaction（压缩）的工程要点

- **触发时机**：context 用量达阈值（如 70%）触发，而非等到爆。
- **压缩对象**：压缩旧的 observation，保留 plan、关键结论、未完成事项。
- **保护区**：system prompt、当前目标、最近一轮永不压缩。
- **不可逆风险**：压缩会丢信息，重要事实应在压缩前固化到结构化 state（见 《Agent工程细节与可靠执行》 的 run state）。

**核心结论**：上下文管理的目标不是"塞更多"，而是"每轮只给模型决策这一步所必需的最小充分信息"——这就是 Context Engineering 在 loop 里的落地（见 《记忆与上下文工程》）。

### 5.4 Scratchpad vs 长期记忆

- **Scratchpad（短期/工作记忆）**：本次 run 内的中间变量、已知事实，随 loop 推进累积，run 结束即弃。
- **长期记忆**：跨 run 的知识/偏好，存向量库/数据库，按需检索进 context。

agent loop 主要靠 scratchpad；长期记忆是"按需注入 context 组装阶段"的外部源。

---

## 六、规划范式对 Loop 的改造

同一个循环骨架，不同推理范式改造的是"模型每轮怎么想、loop 怎么调度"。（范式本身见 《Prompt工程与推理范式》，这里只讲它们对 loop 的改造点。）

| 范式 | 对 loop 的改造 | 适用 |
|------|----------------|------|
| **ReAct** | 边想边做，每轮 think→act→observe；动态、灵活 | 步数不确定、需即时反馈 |
| **Plan-and-Execute** | 先一次性出完整 plan，再按 plan 逐 step 执行；loop 变成"执行器遍历 DAG" | 步骤可预先规划、要可控可恢复 |
| **ReWOO** | 先规划好所有工具调用（不看中间结果），一次性/批量执行，最后汇总；减少 LLM 往返 | 步骤间依赖弱、想省 token |
| **Reflexion** | 在 loop 外套一层"执行→评估→反思→重试"的外循环 | 有可验证反馈、允许多次尝试 |
| **Tree of Thoughts** | 把单线 loop 变成多分支搜索 + 回溯 | 解空间大、需探索 |

### 6.1 ReAct vs Plan-Execute 的 loop 差异

```
ReAct（内循环驱动）:
  每轮都问模型"下一步做什么" → 灵活但步步要钱、可能跑偏

Plan-Execute（外部计划驱动）:
  问一次模型出全 plan → 执行器照着跑 → 可控、可恢复，但应变差
  → 常配 Replan：执行失败/偏差大时回去重规划（混合模式）
```

**核心结论**：ReAct 是"模型每轮当方向盘"，Plan-Execute 是"模型先画地图、执行器照图走"。生产里多用混合：plan 给骨架，执行中允许局部 replan。

### 6.2 Reflexion：loop 之上的 loop

```
外循环（reflect）:
  for attempt in range(K):
      result = agent_loop(task)        # 内循环：正常 agent loop
      score, feedback = evaluate(result)
      if score >= threshold: break
      task = task + reflect(feedback)   # 把反思加进下一次尝试
```

本质是把"评估反馈"变成下一次 loop 的输入，适合代码、解题这类有客观验证信号的任务。

---

## 七、错误处理与鲁棒性（在 loop 里）

（错误分类、重试预算、幂等的完整版见 《Agent工程细节与可靠执行》，这里聚焦"loop 里如何处理"。）

### 7.1 错误回填让模型自纠

工具失败/参数非法时，不要直接崩，把结构化错误作为 observation 回填，给模型一轮自我修正机会：

```json
{
  "role": "tool",
  "tool_call_id": "call_3",
  "content": {
    "status": "error",
    "error_code": "INVALID_ARGUMENT",
    "message": "date 必须是 YYYY-MM-DD，收到 '昨天'",
    "hint": "请用 2026-05-30 这样的绝对日期重试"
  }
}
```

但要**限制自纠轮数**：同一 step 连续失败 N 次就放弃，避免在错误里打转烧钱。

### 7.2 loop 里的鲁棒性清单

- 每轮校验 tool_call 合法性（白名单 + schema），非法即回填纠错。
- 死循环检测（算法见子文档《16.1-Agent Loop 停止条件设计》）。
- 每轮检查预算（steps / tokens / cost / time）。
- 工具超时 + 重试 + 幂等。
- 异常不可恢复时升级人工（HITL），而非硬撑。

---

## 八、控制流变体（架构视角）

同一个 loop，可以组合成不同拓扑。

### 8.1 单 Agent Loop
最基础：一个模型 + 一组工具 + 一个循环。

### 8.2 Orchestrator-Worker / 多 Agent
主 loop（orchestrator）把子任务派给子 agent，每个子 agent 有自己的内层 loop。

```
Orchestrator Loop
   ├── 调 sub_agent_A(loop)
   ├── 调 sub_agent_B(loop)
   └── 汇总
```
（多 Agent 拓扑详见 《多Agent协作》；子 Agent 完成保障见 《Agent工程细节与可靠执行》。）

### 8.3 Human-in-the-Loop（中断 / 审批）
在 loop 的某些动作前插入审批闸：高风险动作（转账、删库、发邮件）暂停 loop，等人确认再继续。要求 loop 能**暂停—持久化—恢复**（见 LangGraph 的 interrupt）。

### 8.4 嵌套 / 委派
工具本身可以是另一个 agent（agent-as-tool）。一个 loop 的一次"工具调用"展开成另一个完整 loop。

---

## 九、主流框架的 Loop 实现对比

| 框架 | loop 抽象 | 暴露程度 | 特点 |
|------|-----------|----------|------|
| **LangChain AgentExecutor** | 封装好的 while 循环（取 action→执行→回填） | 低（黑盒） | 上手快，定制控制流难 |
| **LangGraph** | 把 loop 显式建成**状态图**：节点=步骤，边=控制流，循环=图里的环 | 高（完全可控） | 支持条件分支、中断恢复、checkpoint、人审；生产首选 |
| **OpenAI Agents SDK** | Runner 驱动的 agent loop，内置 handoff / guardrail | 中 | 轻量、官方、tool/handoff 一等公民 |
| **Claude tool-use 循环** | 你自己写 while：`stop_reason == "tool_use"` 就执行工具再回灌 | 高（自己写） | 最透明，loop 完全在你手里 |
| **CrewAI** | 以"角色/任务"为单位的协作循环 | 中 | 偏多 agent 协作编排 |
| **AutoGen** | 以"会话/消息"驱动的多 agent 对话循环 | 中 | 对话式多 agent、可嵌套 |

### 9.1 LangGraph 为什么把 loop 显式化

把 agent loop 画成图后：
- 循环 = 图里从某节点回到上游的**环**。
- 终止 = 走到 END 节点的条件边。
- 中断/恢复 = 在节点间持久化 state。
- 这让"加一个审批节点""失败走另一条边""断点续跑"都变成改图，而不是改一坨 while 里的 if。

**核心结论**：LangChain 的 AgentExecutor 帮你把 loop 藏起来、好上手但难定制；LangGraph 把 loop 摊开成状态机、让控制流、循环、中断、恢复全部可显式编程——这就是从"能跑的 demo"到"可控的生产系统"的分界。

### 9.2 Claude / 裸 API 手写 loop

```python
messages = [{"role": "user", "content": goal}]
while True:
    resp = client.messages.create(model=..., tools=tools, messages=messages)
    messages.append({"role": "assistant", "content": resp.content})
    if resp.stop_reason != "tool_use":
        break                                  # 终止：没有要调的工具
    tool_results = run_tools(resp.content)      # 执行 tool_use 块
    messages.append({"role": "user", "content": tool_results})  # 回填
```

eino（Go）里没有直接暴露 `stop_reason`，但判据等价：`resp.ToolCalls` 为空就相当于 `stop_reason != "tool_use"`，循环结束：

```go
history := []*schema.Message{schema.UserMessage(goal)}
for {
	resp, err := chat.Generate(ctx, history) // chat 已 WithTools
	if err != nil {
		return "", err
	}
	history = append(history, resp)
	if len(resp.ToolCalls) == 0 { // 等价于 stop_reason != "tool_use" → 终止
		return resp.Content, nil
	}
	for _, call := range resp.ToolCalls { // 执行工具并回填
		out, _ := tools[call.Function.Name].InvokableRun(ctx, call.Function.Arguments)
		history = append(history, schema.ToolMessage(out, call.ID))
	}
}
```

最透明，适合理解 loop 本质，也适合需要完全自定义控制流的场景。

---

## 十、性能、成本与可观测性

### 10.1 loop 的成本结构
- 每轮一次 LLM 调用；历史单调增长 → **后面的轮越来越贵**。
- N 轮的总成本 ≈ Σ(每轮 context 长度)，近似随轮数**平方级**增长（因为历史累积）。

优化手段：
- **Prompt caching**：把稳定前缀（system + tools + 早期历史）缓存，命中后只为增量付费。loop 场景收益极大。
- **减少轮数**：并行工具调用、Plan-Execute 一次规划、ReWOO 减往返。
- **模型分级**：规划用强模型、执行/格式化用便宜模型。
- **上下文压缩**：见第五节，直接砍每轮 token。

### 10.2 延迟
延迟随轮数线性累积（每轮一次模型往返 + 工具耗时）。降延迟：并行工具、流式输出、推测/预取、减少不必要轮次。

### 10.3 可观测性（每轮都要可追踪）
对每轮记录：输入 context 摘要、模型输出、tool_call、工具结果、耗时、token、cost、状态。

```
trace
 └── run_id
      └── step_i
           ├── prompt_tokens / completion_tokens / cost
           ├── thought / tool_call(name, args)
           ├── tool_result(status, latency)
           └── decision: continue | finish | error
```

调试"卡死的 loop""跑偏的 agent"全靠这层逐轮 trace（详见 《评估与可观测性》）。

**核心结论**：没有逐轮 trace 的 agent loop 是不可调试的黑盒；上线前必须保证每一轮的输入、决策、动作、结果都能回放。

---

## 十一、经典细化场景

### 场景 1：agent 在两个工具间无限横跳
**现象**：search→calc→search→calc 循环不收敛。
**处理**：动作指纹检测短周期循环（见子文档 6.1 节）；命中后注入"你在重复，请基于已有信息直接给出答案或说明缺什么"；仍不行则强制 finalize。

### 场景 2：第 15 轮 context 快满了，agent 草率收尾
**处理**：在 70% 阈值就触发 compaction，而不是撑到爆；压缩前把关键结论固化到结构化 state；给模型预留 finalize 预算。

### 场景 3：模型该 finish 了却一直在"思考"不调 finish
**处理**：用显式 finish 工具 + `tool_choice` 引导；设 max_steps 兜底；超预算自动 finalize 并标注"未完全完成"。

### 场景 4：工具返回 8MB 日志，直接回填把 context 撑爆
**处理**：工具结果引用化——存成 artifact 返回 id + 摘要；模型要细节时再用 `fetch(id, query)` 取片段。

### 场景 5：每轮都重新检索同样资料，浪费钱
**处理**：把检索结果写进 scratchpad/state，loop 里先查 state 再决定是否重新检索；对相同 query 做缓存。

### 场景 6：用户在 loop 跑到一半改了需求
**处理**：loop 支持外部中断信号；收到后保存 checkpoint，把新需求合并进 context，决定是续跑还是 replan（见 《Agent工程细节与可靠执行》 场景 9）。

### 场景 7：高风险动作（转账）夹在 loop 中间
**处理**：HITL 审批闸——执行到该动作时暂停 loop、持久化 state、等人确认；确认后从断点恢复继续。

### 场景 8：reasoning 模型在 loop 里每轮都重思考，太慢太贵
**处理**：规划阶段用 reasoning，执行/格式化阶段降级到普通模型；或只在卡住时才升级到 reasoning（见 《Reasoning Models专题》 test-time compute 调度）。

---

## 十二、可控 Agent Loop 编排伪代码

```python
def controlled_agent_loop(goal, tools, budget):
    state = init_state(goal)                  # 结构化 run state，不只是 message 列表
    history = assemble_initial_context(goal, tools)
    action_fingerprints = deque(maxlen=6)

    for step in range(budget.max_steps):
        # 预算闸
        if budget.exceeded(state):
            return finalize(state, reason="budget")

        # 上下文管理
        if context_usage(history) > 0.7:
            history = compact(history, protect=[system, goal, recent(2)])

        # 推理
        resp = llm(history, tools=tools, temperature=0.2)

        # 终止：显式完成
        if resp.calls("finish"):
            return finalize(state, resp.answer)

        # 动作解析 + 校验
        valid, errors = validate(resp.tool_calls, tools)
        if not valid:
            history += error_feedback(errors)     # 回填让模型自纠
            continue

        # 死循环检测
        fp = fingerprint(resp.tool_calls)
        action_fingerprints.append(fp)
        if is_looping(action_fingerprints):
            history += nudge("你在重复，请换思路或直接收尾")
            continue

        # 工具执行（并行 + 超时 + 幂等）
        results = run_tools_parallel(resp.tool_calls, budget.deadline)

        # 观察回填 + 状态更新
        history += assistant(resp) + tool_msgs(results)
        update_state(state, resp, results)
        trace(step, resp, results)                # 逐轮可观测

    return finalize(state, reason="max_steps")
```

这段把前面所有要点串起来：预算闸、压缩、显式终止、动作校验、死循环检测、并行执行、状态更新、逐轮 trace。

对应的 eino（Go）实现，同样把这些工程闸装到手写 loop 里：

```go
func controlledAgentLoop(ctx context.Context, cm model.ToolCallingChatModel,
	tools map[string]tool.InvokableTool, toolInfos []*schema.ToolInfo,
	goal string, b Budget) (string, error) {

	chat, _ := cm.WithTools(toolInfos)
	st := initState(goal)
	history := assembleInitialContext(goal)
	fps := make([]string, 0, 6) // 动作指纹环形窗口

	for step := 0; step < b.MaxSteps; step++ {
		// 预算闸
		if b.Exceeded(ctx, st) {
			return finalize(st, "budget"), nil
		}
		// 上下文管理：达阈值触发压缩
		if contextUsage(history) > 0.7 {
			history = compact(history)
		}

		resp, err := chat.Generate(ctx, history)
		if err != nil {
			return "", err
		}

		// 终止：显式 finish
		if call, ok := findCall(resp, "finish"); ok {
			return finalize(st, call.Function.Arguments), nil
		}
		// 动作解析 + 校验
		if errs := validate(resp.ToolCalls, toolInfos); len(errs) > 0 {
			history = append(history, resp)
			history = append(history, errorFeedback(errs)...) // 回填让模型自纠
			continue
		}
		// 死循环检测
		fps = pushFingerprint(fps, fingerprint(resp.ToolCalls))
		if isLooping(fps) {
			history = append(history, resp, nudge("你在重复，请换思路或直接收尾"))
			continue
		}

		// 工具执行（并行）+ 回填 + 状态更新 + 逐轮 trace
		history = append(history, resp)
		results := runToolsParallel(ctx, tools, resp.ToolCalls, b.Deadline)
		for _, r := range results {
			history = append(history, schema.ToolMessage(r.Output, r.CallID))
		}
		updateState(st, resp, results)
		trace(step, resp, results)
	}
	return finalize(st, "max_steps"), nil // ⑥ 预算耗尽兜底
}
```

> 其中 `validate / isLooping / fingerprint / finalize` 等闸的设计细节，统一放在子文档《[16.1-Agent Loop 停止条件设计](./16.1-Agent%20Loop停止条件设计.md)》里展开。

---

## 十三、复习思考题（含解答）

> 用于自我检验对本篇知识的掌握，先自己讲一遍再对照解答。

### Q1：一个 agent loop 内部一轮发生了什么？
六个阶段：①上下文组装（system+tools+历史+state）②模型推理（决定下一步）③动作解析（提取 tool_call，校验白名单/schema）④工具执行（并行/超时/幂等）⑤观察回填（结果作为 tool 消息加回 history）⑥终止判断（完成/预算/死循环/错误）。每个阶段都有失败模式：组装→上下文爆炸，解析→幻觉工具，执行→超时副作用，终止→停不下来。

### Q2：agent loop 怎么保证一定会停？
两道硬闸 + 三类软检测。硬闸：显式 finish 工具触发正常终止 + max_steps/tokens/cost/time 预算上限强制终止。软检测：死循环检测（动作指纹重复）、死路检测（工具反复失败升级人工）、外部中断（取消/改需求）。不能只靠模型自觉说"完成"。

### Q3：每轮历史都在涨，context 爆了怎么办？
分层处理：稳定前缀（system+tools）放前面做 prompt caching；达阈值（如 70%）触发 compaction，压缩旧 observation、保留 plan/关键结论/未完成项、保护最近一轮；大工具结果引用化（存 artifact 返回 id）；关键事实在压缩前固化到结构化 state 防丢失。目标是"每轮只给决策这步所需的最小充分信息"。

### Q4：ReAct 和 Plan-and-Execute 的 loop 有什么区别？
ReAct 是内循环驱动——每轮都问模型"下一步做什么"，灵活但步步花钱、易跑偏。Plan-Execute 是外部计划驱动——先问一次出完整 plan，执行器照 plan 遍历，可控可恢复但应变差。生产常用混合：plan 给骨架，执行中允许局部 replan。ReWOO 是 Plan 的变体，提前规划所有工具调用减少 LLM 往返。

### Q5：怎么检测和打破 agent 的死循环？
对 (tool_name, normalized_args) 做指纹，维护近 N 轮指纹集合：检测完全重复、短周期 A-B-A-B、高重复率。命中后干预——注入提示让模型换思路或直接收尾；强制进入 finalize；或换更强模型/换策略。配合 max_steps 兜底。

### Q6：LangGraph 和 LangChain AgentExecutor 在 loop 上的本质区别？
AgentExecutor 把 loop 封装成黑盒 while，上手快但定制控制流难。LangGraph 把 loop 显式建成状态图：节点=步骤、边=控制流、循环=图里的环、终止=到 END 的条件边、中断恢复=节点间持久化 state。结果是分支、循环、人审、断点续跑全部变成"改图"而非改一坨 if，是从 demo 到生产系统的分界。

### Q7：function calling 出现后，agent loop 还是 ReAct 吗？
本质还是。ReAct 的 Thought→Action→Observation 骨架没变，只是把 Action 从"模型吐文本再正则解析"换成"模型直接吐结构化 tool_call"，把解析脆弱性交给了供应商；Thought 被隐式化（或放进 reasoning/thinking）。循环结构、终止逻辑、观察回填都一样。

### Q8：agent loop 的成本为什么容易失控，怎么治理？
因为历史单调增长，第 N 轮要把前 N-1 轮都带上，总成本近似随轮数平方增长。治理：prompt caching 缓存稳定前缀（loop 场景收益最大）、并行工具/Plan-Execute/ReWOO 减少轮数、模型分级（规划用强模型执行用便宜的）、上下文压缩砍每轮 token、设 cost 预算上限硬兜底。

### Q9：怎么调试一个"跑偏"或"卡死"的 agent loop？
靠逐轮 trace。对每轮记录：输入 context、模型输出（thought+tool_call）、工具结果、耗时、token、cost、决策（continue/finish/error）。回放时看：哪轮开始重复（死循环）、哪轮动作和目标无关（跑偏）、哪轮 context 突然膨胀（结果回填过大）、哪轮工具反复失败。没有这层 trace 的 loop 是不可调试的黑盒。

---

## 十四、自测清单

- [ ] 能 20 行手写出一个最小 agent loop
- [ ] 能说清一轮 iteration 的六个阶段 + 各自失败模式
- [ ] 能列出五类终止条件并设计显式 finish + 预算双闸
- [ ] 能写出死循环检测逻辑
- [ ] 能讲清 context 压缩的触发时机、对象、保护区、风险
- [ ] 能区分 scratchpad 和长期记忆在 loop 里的角色
- [ ] 能对比 ReAct / Plan-Execute / ReWOO / Reflexion 对 loop 的改造
- [ ] 能讲清 LangGraph 显式状态图 vs AgentExecutor 黑盒 while 的区别
- [ ] 能裸 API 手写 Claude/OpenAI 的 tool-use 循环
- [ ] 能解释 loop 成本为何近似平方增长及 prompt caching 的价值
- [ ] 能设计逐轮 trace 用于调试卡死/跑偏

---

## 十五、关键术语 Cheat Sheet

| 术语 | 一句话 |
|------|--------|
| Agent Loop | 通过反复观察外部反馈逐步逼近目标的受控循环 |
| Iteration | 一轮：组装→推理→解析→执行→回填→判断 |
| ReAct | Thought→Action→Observation 交替的 loop 形态 |
| Termination | 终止：finish 动作 / 预算 / 死循环 / 死路 / 中断 |
| Loop Detection | 用动作指纹检测并打破重复循环 |
| Context Compaction | 达阈值时压缩旧历史，保护关键信息 |
| Scratchpad | 本次 run 内的工作记忆，loop 结束即弃 |
| Plan-and-Execute | 先规划全 plan，执行器照 DAG 遍历 |
| ReWOO | 提前规划所有工具调用，减少 LLM 往返 |
| Reflexion | loop 外套"执行-评估-反思-重试"外循环 |
| HITL Interrupt | 高风险动作前暂停 loop 等人审，可恢复 |
| Stop Reason | 模型停止原因（tool_use=继续，其他=终止） |
| Prompt Caching | 缓存稳定前缀，loop 场景大幅省成本 |
| Step Budget | max_steps/tokens/cost/time 的硬上限 |

---

## 十六、延伸阅读

- ReAct: Synergizing Reasoning and Acting in Language Models（ReAct 原论文）
- Reflexion: Language Agents with Verbal Reinforcement Learning
- ReWOO: Decoupling Reasoning from Observations
- Anthropic《Building effective agents》（loop / workflow vs agent 的工程观点）
- LangGraph 官方文档：state machine、cycles、interrupt、checkpoint
- OpenAI Agents SDK：Runner / Agent loop / handoff
- 子文档：《[16.1-Agent Loop 停止条件设计](./16.1-Agent%20Loop停止条件设计.md)》（停止条件的详细展开 + 主流产品实现 + Go/eino 代码）
- 本仓库关联：《Prompt工程与推理范式》（推理范式）、《记忆与上下文工程》（记忆与上下文工程）、《多Agent协作》（多 Agent）、《评估与可观测性》（评估与可观测）、《Reasoning Models专题》（Reasoning Models）、《Agent工程细节与可靠执行》（可靠执行）

---

## 十七、核心要点速记

1. agent loop 不是 `while True`，是带六个阶段的受控循环，每阶段都有失败模式和对策。
2. function calling 时代的 loop 本质还是 ReAct，只是把 Action 换成了结构化 tool_call。
3. 生产级 agent 必须有显式终止动作 + 硬预算上限两道闸，不能只靠模型自觉。
4. 上下文管理不是"塞更多"，是"每轮只给决策这步所需的最小充分信息"。
5. ReAct 是模型每轮当方向盘，Plan-Execute 是先画地图照图走。
6. LangChain 把 loop 藏起来好上手，LangGraph 把 loop 摊成状态机才好生产。
7. loop 成本随轮数近似平方增长，prompt caching 在这里收益最大。
8. 没有逐轮 trace 的 agent loop 是不可调试的黑盒。
