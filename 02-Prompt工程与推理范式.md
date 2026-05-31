# Prompt 工程与推理范式

> 目标：掌握主流推理范式（CoT、ReAct、Plan-Execute、Reflexion、ToT）的原理、差异与选型。

---

## 一、核心概念

### 1.1 Prompt 工程基础
- **Zero-shot**：直接问，靠模型预训练知识
- **Few-shot / In-Context Learning**：给几个示例，模型模仿
- **Instruction Following**：明确角色、任务、输出格式
- **Prompt 分层结构**：角色（Role） + 任务（Task） + 约束（Constraints） + 示例（Examples） + 输出格式（Format）

### 1.2 推理范式总览

| 范式 | 一句话定义 | 核心思想 |
|------|------------|----------|
| CoT | Chain-of-Thought | "让我们一步步思考"，写出中间推理过程 |
| Self-Consistency | 多次采样投票 | 采样多条 CoT 路径，多数答案投票 |
| ToT | Tree of Thoughts | 把推理建模为树搜索（BFS/DFS） |
| GoT | Graph of Thoughts | 把推理建模为图，节点可合并复用 |
| ReAct | Reason + Act | Thought → Action → Observation 交错循环 |
| Plan-and-Execute | 先规划后执行 | 先生成完整计划，再依次执行（ReWOO 类似） |
| Reflexion | 反思修正 | 失败后生成自然语言反思，作为下一次尝试的额外输入 |
| Self-Refine | 自我打磨 | 生成 → 自我批评 → 改进，迭代多轮 |
| Debate | 多模型辩论 | 多个 LLM 互相辩论，提升答案质量 |

### 1.3 CoT 深入
- **触发方式**：
  - 显式："Let's think step by step"
  - Few-shot CoT：给带推理过程的示例
  - 训练驱动：o1 / R1 / Claude 3.7 thinking — 模型在 RL 阶段被训练成长思维链
- **涌现性**：CoT 在小模型（<10B）上几乎无效甚至负向；规模到 60B+ 才显著（Wei et al. 2022）
- **失效场景**：算术题中替换数字 → 准确率掉（GSM-Symbolic）

### 1.4 ReAct 深入
**核心循环**：
```
Thought: 我需要查询天气
Action: search_weather("北京")
Observation: 北京今天 25 度，晴
Thought: 用户问的是周末，需要查后天
Action: search_weather("北京", date="2026-05-20")
Observation: ...
Thought: 已收集到信息
Answer: 周末北京晴朗，气温 24~27 度
```

**优势**：动态决策、可与环境交互、错误可恢复

**失败模式**：
1. **无限循环**：反复调用同一工具
2. **错误累积**：早期错误的 Observation 误导后续 Thought
3. **幻觉行动**：调用不存在的工具或参数
4. **token 浪费**：每轮都重发完整历史

### 1.5 Plan-and-Execute / ReWOO
**思想**：先一次性生成完整计划（避免每步都让大模型决策），再让小模型 / 工具执行。

```
Step 1 [Planner LLM]: 
  Plan = [
    "搜索 LangGraph 文档",
    "搜索 AutoGen 文档", 
    "对比两者状态管理",
    "生成对比表"
  ]

Step 2 [Executor]: 
  循环执行 plan 中每一步，使用工具

Step 3 [Solver LLM]: 
  汇总所有 observations 生成最终答案
```

**优势**：
- 减少 LLM 调用次数（不用每步都让大模型 think）
- 计划可审查、可缓存
- 适合任务可预先分解的场景

**劣势**：
- 缺乏中途调整能力（如果 step 2 失败，整个计划可能崩）
- 不适合探索性任务

### 1.6 Reflexion 深入
**三件套**：
- **Actor**：执行任务的 Agent
- **Evaluator**：评分（来自环境 / LLM judge / 单元测试）
- **Self-Reflection LLM**：根据失败案例生成 verbal feedback

**关键点**：反思以**自然语言**形式存入 episodic memory，而不是更新权重 — 这让它能在不微调的情况下"学习"。

### 1.7 ToT / GoT
**ToT**（Tree of Thoughts）：
- 每个节点是一个部分解（partial solution）
- 用 BFS / DFS / Beam Search 搜索
- 每个节点用 LLM 评估"是否值得继续"
- 适合：数学题、24 点、字谜

**GoT**（Graph of Thoughts）：
- 节点可以**合并**（merge），允许复用
- 比 ToT 更灵活，更贴近人类思维

**实战代价**：ToT/GoT token 消耗巨大，工业落地少，更多用于研究。

### 1.8 结构化输出三种路线
1. **Prompt 约束**："output JSON only" — 不可靠，10~30% 会偏离
2. **JSON Mode**：模型保证语法合法，但 schema 不保证
3. **Structured Output / Constrained Decoding**：
   - 解码时按 grammar 强制采样
   - OpenAI Structured Output（基于 schema）、Outlines、XGrammar
   - 100% 符合 schema，但可能影响生成质量（被强制选了次优 token）

---

## 二、主流实现要点

### 2.1 LangChain Prompt 模板
- `PromptTemplate` / `ChatPromptTemplate`
- 变量插值、Few-shot 模板、Output Parser
- LangSmith Hub：共享 prompt 仓库

### 2.2 Anthropic XML 风格
Claude 训练时对 XML 标签敏感，推荐结构化用 XML：
```xml
<task>分析这段代码的安全漏洞</task>
<code>{{user_code}}</code>
<output_format>
  <vulnerabilities>...</vulnerabilities>
  <severity>high|medium|low</severity>
</output_format>
```

### 2.3 Prompt Caching
- **Anthropic**：缓存命中节省 90% 输入 token 成本，但 5 分钟 TTL
- **OpenAI**：自动缓存（无需声明），节省 50%
- **使用条件**：长且稳定的前缀（系统提示 + few-shot），变量放最后
- **Agent 场景价值**：tool schemas + system prompt 几乎每轮都重发，缓存命中率极高

### 2.4 推理模型（Reasoning Models）
- **OpenAI o1 / o3**：内置长 CoT，输出前有 hidden reasoning
- **DeepSeek R1**：开源版本，公开 reasoning trace
- **Claude 3.7 Sonnet (Thinking) / Claude 4 Opus (Thinking)**：可控的"extended thinking"模式
- **使用建议**：复杂推理用 reasoning 模型，但成本高、延迟大，简单任务不要用

### 2.5 Prompt 工程框架
- **Anthropic Prompt Improver**：自动改写 prompt
- **DSPy**：声明式编程 prompt，自动优化（基于 metric 反向调整 demos）
- **TextGrad**：把 prompt 当变量做梯度下降优化

---

## 三、高频面试题（含答案）

### Q1：ReAct 和 Plan-and-Execute 有什么区别？什么场景选哪个？

**答**：

**核心区别**：
- **ReAct**：每一步都让 LLM 决策下一步动作（thought + action 交错）
- **Plan-and-Execute**：先一次性产出完整计划，再按计划执行

**对比**：

| 维度 | ReAct | Plan-and-Execute |
|------|-------|------------------|
| LLM 调用次数 | 多（每步） | 少（计划 + 总结） |
| 成本 | 高 | 低 |
| 灵活性 | 高（可中途调整） | 低（计划生成后较难改） |
| 适合 | 探索性、环境多变 | 任务可预先分解 |
| 失败模式 | 循环、错误累积 | 计划本身错就全错 |

**选型判据**：
- **任务路径不可预见**（如调试一个 bug、Deep Research） → ReAct
- **任务路径可大致预见但需要执行**（如"搜索 5 个网站做对比"） → Plan-and-Execute
- **复杂场景**：混合 — 用 Plan 产出骨架，每步内部用 ReAct 处理细节（LangGraph 的常见模式）

---

### Q2：CoT 为什么对小模型无效？

**答**：

实验观察（Wei et al. 2022）：在 GSM8K 等数学题上，模型规模 <60B 时加 CoT 几乎无提升，规模到 ~100B 后才显著提升 — 这是经典的**涌现现象**。

**可能的解释**：
1. **能力门槛**：多步推理需要每步都接近正确，小模型每步错误率高，链越长越糟（错误累积）
2. **指令理解**：小模型可能根本"理解不到"step by step 是什么意思
3. **数据稀疏性**：高质量推理数据在预训练中占比小，小模型权重不足以编码这种能力

**工程含义**：
- 小模型上别盲目加 CoT，可能增加成本却无收益
- 小模型上可以用 **distillation CoT**：用大模型生成推理过程，作为小模型 SFT 数据（如 Orca、Phi 系列）
- 或者：小模型只做执行，大模型做规划

---

### Q3：ReAct 的失败模式有哪些？怎么治理？

**答**：

**四大失败模式**：

1. **无限循环**：反复调用同一工具拿同样结果
   - 治理：步数上限（max_iterations=15）、检测重复 action 后强制总结

2. **错误累积**：早期 observation 错误污染后续 thought
   - 治理：每 N 步做一次 self-check（"基于当前信息能否回答？是否有矛盾？"）

3. **幻觉行动**：调用不存在的工具 / 错误参数
   - 治理：Function Calling + Schema 校验，校验失败立即反馈给模型重试

4. **Token 爆炸**：历史越积越长
   - 治理：滑动窗口、摘要压缩、Plan-Execute 改造

**防御性 prompt**：
```
You have at most 10 tool calls. 
If you find yourself calling the same tool twice with similar arguments, STOP and summarize what you know.
If a tool fails twice, try a different approach.
```

**工程上**：用 LangGraph / 自研编排器实现循环计数器、重复检测、超时熔断。

---

### Q4：如何让 LLM 严格输出 JSON？

**答**：

按可靠性从低到高三种方式：

**Level 1：Prompt 约束**
```
Output JSON only, no markdown, matching this schema:
{ "name": str, "age": int }
```
失败率：10~30%。问题：模型可能加 ```json 围栏、加注释、字段缺失。

**Level 2：JSON Mode**
- OpenAI `response_format={"type":"json_object"}`
- 模型保证输出合法 JSON，但**不保证符合特定 schema**
- 失败率：~5%（schema 不符）

**Level 3：Structured Output / Constrained Decoding**
- OpenAI `response_format={"type":"json_schema","json_schema":{...}}`
- Anthropic：tool use 强制 schema
- 开源：Outlines、XGrammar、lm-format-enforcer
- **原理**：解码每一步只在符合 grammar 的 token 中采样
- 失败率：~0%（语法上保证 100% 符合）

**工程实践**：
1. 用 **Pydantic 定义 schema** → 自动转 JSON Schema
2. 输出后再做一次 Pydantic 解析校验（双保险）
3. 失败时**重试一次**，把错误信息反馈给模型

**注意**：Constrained Decoding 偶尔会降低质量（被迫选次优 token），关键场景做 A/B 测试。

---

### Q5：什么是 Self-Consistency？它的局限？

**答**：

**做法**：对同一问题用 temperature>0 采样多条 CoT 路径（如 5~40 条），对最终答案做**多数投票**。

**为什么有效**：
- 正确答案是"吸引子"，不同推理路径会汇聚到同一答案
- 错误答案各有各的错，被分散投票稀释

**实验**：GSM8K 上从 ~58%（greedy CoT）提到 ~75%（40 samples）。

**局限**：
1. **只能用于有标准答案的任务**：开放生成（写文章）没法投票
2. **成本暴涨**：40 倍调用
3. **答案需可比较**：自由文本要靠 LLM judge 来判等价（又引入偏差）
4. **不解决根本错误**：如果模型对该题就是不会，再多采样也救不回来

**工程上常用低配版**：sample 3 条，如果都一致则信任，不一致则升级到更强模型。

---

### Q6：Reflexion 和单纯重试有什么不同？

**答**：

**单纯重试**：失败 → 再试一次，模型可能犯同样的错。

**Reflexion**：
1. 失败 → 用 LLM 生成 verbal reflection（"这次错在 X 上，下次应该 Y"）
2. 把 reflection 加入下一次尝试的 context
3. 模型基于"自己的反思"修正行为

**核心创新**：用**自然语言反思**代替梯度更新，是一种"in-context RL"。

**实验**（Shinn et al. 2023）：HumanEval 编程任务上从 80% 提到 91%。

**适用条件**：
- 必须有**可靠的失败信号**（单元测试、环境 reward、judge）
- 任务有**明确目标**（不是开放生成）

**工程实践**：
- 反思要存入 episodic memory，跨 trial 累积
- 反思条目数有上限（避免污染 context）
- 反思质量本身可评估，差的反思直接丢弃

---

### Q7：Prompt Caching 在 Agent 场景的价值？

**答**：

**Agent 场景的痛点**：每轮 LLM 调用都要重发：
- 长 system prompt（几千 token）
- Tool schemas（几千 token）
- Few-shot 示例
- 完整历史

一个 10 轮的 Agent 任务，重复内容会被算 10 次 token。

**Prompt Caching 解法**：
- 标记稳定前缀为可缓存
- 首次调用建立缓存（成本略高，~25%）
- 后续命中：**输入 token 节省 90%（Anthropic）/ 50%（OpenAI）**
- TTL：5 分钟（Anthropic 可延长到 1 小时）

**缓存放置规则**：
```
[可缓存] System Prompt
[可缓存] Tool Schemas  
[可缓存] Few-shot Examples
[可缓存] 静态 RAG 文档
─────── 缓存边界 ───────
[动态] 当前对话历史
[动态] 用户问题
```

**变量越靠后越好**：缓存命中必须是**前缀完全匹配**，中间插入变量会废掉后面所有缓存。

**实际收益**：复杂 Agent 总成本能降 50~70%、延迟降 30%。

---

## 四、场景设计题（含答案）

### 场景 1：客服 Agent 进入 ReAct 死循环

**题目**：线上客服 Agent 偶发性进入无限循环，反复调用 `search_order` 工具，最后超时返回错误。给三种解决思路并对比。

**答案**：

**根因分析**：可能是工具返回结果不符合 LLM 预期（如订单号格式不对），LLM 反复尝试不同参数。

**方案 1：硬性步数上限 + 强制总结**
- 实现：编排器记录 step 数，超过 N 步强制停下，让 LLM 基于已收集信息给最佳答复
- 优点：简单可靠
- 缺点：可能没拿到完整信息就返回，体验差

**方案 2：重复检测 + 行为引导**
- 实现：检测同一工具用相似参数调用 ≥3 次，向 LLM 注入 "You are calling the same tool repeatedly, try a different approach or summarize what you know" 
- 优点：让模型自主调整，体验好
- 缺点：实现复杂，"相似"的判定需要调

**方案 3：改造为 Plan-and-Execute**
- 实现：先让 LLM 出计划（"我要查订单 → 查物流 → 查售后政策"），再串行执行
- 优点：从根上避免循环
- 缺点：失去 ReAct 的灵活性，复杂客服问题计划可能错

**推荐组合**：方案 1（兜底）+ 方案 2（主治），方案 3 在简单工单场景上线。同时建监控告警，循环类失败日志聚合分析根因。

---

### 场景 2：金融问答的输出格式可靠性

**题目**：理财问答场景，LLM 要输出结构化建议（产品列表 + 评分 + 风险等级），上线后发现 5% 的输出格式错误导致前端解析失败。

**答案**：

**多层防御**：

1. **Schema 强约束**：用 Pydantic 定义
```python
class Recommendation(BaseModel):
    products: List[Product]
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
```

2. **Structured Output 路线**：
   - OpenAI：`response_format={"type":"json_schema",...}` 强制符合
   - 开源模型：Outlines + grammar

3. **解析层重试**：
```python
for attempt in range(3):
    raw = llm.generate(...)
    try:
        result = Recommendation.parse_raw(raw)
        break
    except ValidationError as e:
        feedback = f"Last output failed: {e}, please fix and retry"
        ...
```

4. **降级策略**：3 次都失败 → 返回"暂时无法生成建议"模板 + 告警

5. **离线监控**：
   - Schema 合规率（应 >99.9%）
   - 字段缺失率
   - 异常值告警（如 confidence=0.999 频繁出现）

6. **数据回流**：失败 case 收集 → 离线分析 → 优化 prompt 或加入 few-shot

---

## 五、自测清单

- [ ] CoT、Self-Consistency、ToT、GoT 的关系
- [ ] ReAct 的完整循环 + 四种失败模式
- [ ] Plan-and-Execute 对比 ReAct 的成本与适用
- [ ] Reflexion 的三件套
- [ ] 让 LLM 输出 JSON 的三种路线 + 可靠性
- [ ] Prompt Caching 的缓存边界规则
- [ ] 推理模型（o1 / R1）跟普通 CoT 的差异

---

## 六、延伸阅读

- Wei et al. — *Chain-of-Thought Prompting Elicits Reasoning*
- Yao et al. — *ReAct: Synergizing Reasoning and Acting*
- Shinn et al. — *Reflexion: Language Agents with Verbal Reinforcement Learning*
- Yao et al. — *Tree of Thoughts*
- Khattab et al. — *DSPy: Compiling Declarative Language Model Calls*
- Anthropic — *Prompt Engineering Guide*
