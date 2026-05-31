# LLM 基础与 Agent 本质

> 目标：建立从 Token 到 Agent 的完整心智模型，能讲清楚 Agent 与 Workflow / Chatbot 的本质区别。

---

## 一、核心概念

### 1.1 Transformer / Decoder-only
- **自注意力（Self-Attention）**：每个 token 通过 Q/K/V 计算与所有其他 token 的关联度
- **Decoder-only 架构**：GPT 系列、Claude、Llama 都采用；因果掩码（Causal Mask）保证只能看到前文
- **位置编码**：绝对位置（Sinusoidal）→ 相对位置（RoPE / ALiBi），RoPE 主导现代 LLM 因为外推性好

### 1.2 Token 与上下文窗口
- **Tokenization**：BPE（Byte-Pair Encoding）、SentencePiece；中文一般 1.5~2 字符/token，英文约 4 字符/token
- **上下文窗口**：模型一次能处理的 token 上限（GPT-4o：128k，Claude 4：200k，Gemini 1.5 Pro：2M）
- **窗口 ≠ 有效利用**：长上下文存在 Lost in the Middle 问题

### 1.3 采样策略
- **Greedy**：每步选最高概率，最确定但易重复
- **Temperature**：缩放 logits，T→0 接近 greedy，T→∞ 接近均匀分布
- **Top-k**：保留概率最高的 k 个 token
- **Top-p（Nucleus）**：保留累积概率达 p 的最小集合，比 top-k 更自适应
- **Frequency / Presence Penalty**：抑制重复
- **重要陷阱**：temperature=0 ≠ 完全确定性！MoE 路由、并行计算的浮点非确定性、batch 顺序都会引入不一致

### 1.4 训练阶段
- **Pretraining（预训练）**：海量文本上做 next-token prediction，习得语言能力与世界知识
- **SFT（监督微调）**：用 instruction-response 对调整为"会听指令"
- **RLHF（人类反馈强化学习）**：训练奖励模型 → PPO 优化策略
- **DPO（Direct Preference Optimization）**：跳过奖励模型，直接用偏好对优化，训练更稳
- **Constitutional AI**：用一套原则让模型自我批评、自我改进（Anthropic）

### 1.5 Function Calling 的本质
- **不是新能力，是 SFT 出来的格式遵循**：训练时塞入大量 `<tool_call>{...}</tool_call>` 样本
- **解码端可加约束**：JSON Schema 约束 + 结构化解码（如 outlines、xgrammar）
- **关键点**：模型本身不"执行"工具，它只产出 **工具调用意图**，执行由宿主程序完成

### 1.6 Agent 的定义
最被广泛接受的定义（Anthropic / OpenAI 共识）：

> **Agent = LLM 在循环中自主决策、调用工具、维护状态，直到任务完成**

四要素：
1. **Planning（规划）** — 拆解目标、安排步骤
2. **Tools（工具）** — 与外界交互的接口
3. **Memory（记忆）** — 跨步骤 / 跨会话保持信息
4. **Loop（循环）** — 多轮 Thought-Action-Observation

### 1.7 Agent vs Workflow vs Chatbot（Anthropic 经典分类）

| 维度 | Chatbot | Workflow | Agent |
|------|---------|----------|-------|
| 决策权 | 无（被动回答） | 开发者预定义路径 | LLM 自主决策路径 |
| 控制流 | 单次推理 | 固定 DAG | 动态循环 |
| 可预测性 | 高 | 高 | 低 |
| 适用 | 问答 | 流程化任务（如审批） | 开放性任务（如 Deep Research） |
| 成本 | 低 | 可预估 | 不确定（可能爆炸） |

**关键判据**：如果你能画出确定流程图，就用 Workflow；只有当问题本身是开放探索，才用 Agent。

---

## 二、主流实现要点

### 2.1 Function Calling 协议对比
- **OpenAI**：`tools=[{"type":"function","function":{"name":"...","parameters":{...}}}]`，并行调用默认开
- **Anthropic**：`tools=[{"name":"...","input_schema":{...}}]`，强制 JSON Schema
- **Gemini**：`tools=[{"function_declarations":[...]}]`，支持 automatic function calling
- **统一抽象**：LangChain `@tool` 装饰器、LiteLLM 统一 API

### 2.2 结构化输出三种路线
1. **Prompt 约束**：写明 "output JSON only"（不可靠）
2. **JSON Mode**：模型保证语法合法，但不保证 schema 正确
3. **Structured Output / Constrained Decoding**：解码时强制符合 Schema（OpenAI Structured Output、xgrammar、outlines），最可靠

### 2.3 模型选型直觉
- **闭源**：Claude Opus / Sonnet、GPT-4o / o1、Gemini 1.5
- **开源**：Llama 3.x、Qwen 2.5、DeepSeek V3、Mistral
- **选型维度**：能力 / 上下文长度 / 工具调用质量 / 价格 / 延迟 / 私有化能力

---

## 三、高频面试题（含答案）

### Q1：Agent 和传统 Workflow 的本质区别？什么场景选哪个？

**答**：
本质区别在于**决策权归属**：
- Workflow 中开发者预先定义了所有路径，LLM 只是节点中的一环
- Agent 中 LLM 自主决策下一步做什么，包括是否调用工具、调用哪个

选型判据：
- 任务路径**可预先穷举** → Workflow（更可控、更便宜、更可测）
  - 例：发票审核（固定 5 步）、客服 FAQ 路由
- 任务路径**依赖中间结果且分支爆炸** → Agent
  - 例：Deep Research（不知道要查几轮）、代码修复（不知道是哪种 bug）

工程实践中**80% 的需求其实是 Workflow**，过度用 Agent 会导致：成本不可控、延迟高、难调试。Anthropic 在 *Building Effective Agents* 一文中明确建议："start with the simplest solution, only add agentic behavior when necessary"。

---

### Q2：LLM 的 Function Calling 底层是怎么实现的？

**答**：
分两层：

**模型层（训练）**：
- SFT 阶段插入大量"用户问 → 模型输出工具调用 JSON"的样本
- 让模型学到：看到工具描述时，要么直接回答，要么生成符合 schema 的调用结构
- 训练数据格式通常用特殊 token（如 `<tool_call>...</tool_call>`）包裹

**运行层（推理）**：
1. 客户端把 tools schema 注入 system prompt（每家厂商格式不同）
2. 模型自回归生成，可能输出"普通文本"或"工具调用 JSON"
3. 服务端解析输出：如果命中工具调用 token → 解析参数 → 返回 `tool_calls` 字段
4. 客户端实际执行函数 → 把结果作为 `tool_result` 消息塞回
5. 模型基于结果继续生成

**为什么有时调用失败**：训练样本覆盖不到的工具描述风格、参数命名歧义、复杂嵌套 schema 都会让模型混乱。

---

### Q3：temperature=0 真的是完全确定的吗？

**答**：
**不是**。原因有四：
1. **GPU 浮点非结合性**：`(a+b)+c ≠ a+(b+c)`，并行 reduce 顺序不同结果略不同
2. **Batch 影响**：同一 prompt 在不同 batch 中（不同的 padding、不同邻居）可能走不同 kernel
3. **MoE 路由**：Mixture-of-Experts 模型的路由可能因负载均衡漂移
4. **API 端的隐藏随机性**：例如 OpenAI 的 `seed` 参数也只承诺 "mostly deterministic"

实践中：如果一定要复现，用 seed 参数 + 固定 model snapshot + temperature=0；但仍不保证 100%。

---

### Q4：上下文窗口越大越好吗？

**答**：
**不一定**。三个角度：

1. **能力 ≠ 容量**：Lost in the Middle 现象（Liu et al. 2023）显示长上下文中段的信息利用率显著下降
2. **成本与延迟**：输入 token 计费 + 注意力 O(n²) 计算（虽然 FlashAttention 优化到接近线性，但延迟仍随长度增长）
3. **质量退化**：超过训练长度后，即使技术上能输入，模型可能输出质量明显下降

实践：
- 优先考虑**上下文工程**（压缩、摘要、检索）而非堆 token
- Anthropic 的 prompt caching 让重复长上下文成本降 90%，但延迟仍在
- 真正需要长上下文的场景（如分析整本书）才用大窗口模型

---

### Q5：闭源模型 vs 开源模型怎么选？

**答**：
按四个维度决策：

| 维度 | 闭源 | 开源 |
|------|------|------|
| 能力上限 | Claude Opus / GPT-4 / o1 仍领先 | 顶级开源接近 GPT-4 水平（DeepSeek V3、Llama 405B） |
| 成本 | 按 token 付费，规模化后贵 | 自部署后边际成本低，但需 GPU 资源 |
| 隐私 / 合规 | 数据出境受限 | 可完全私有化 |
| 工具生态 | Function Calling 成熟 | 部分开源模型工具调用质量不稳定 |

**典型选型决策树**：
- 探索期 / MVP → 闭源（快速验证）
- 高合规要求（金融、医疗、政企） → 开源私有化
- 高 QPS 通用场景 → 开源自部署 + 闭源兜底
- 顶级智能要求（如复杂推理） → 闭源（Opus / o1）

---

### Q6：LLM 是真的在"推理"吗？

**答**：
这是个开放问题。两种主流观点：

**怀疑派**（Yann LeCun 等）：
- LLM 本质是大型 pattern matcher，"推理"是把训练时见过的模式重组
- 反例：稍微变换数字 / 名字，CoT 准确率显著下降（GSM-Symbolic 论文）

**支持派**：
- 涌现的多步骤泛化能力难以用纯查表解释
- o1 / R1 类推理模型在数学竞赛上的表现接近顶级人类

**实用主义答法**：
> "无论是不是真推理，从工程视角看，CoT、ReAct、Reflexion 这些技术能可测地提升任务成功率。我们用它，但同时通过测试集严格量化它的能力边界。"

这个问题面试时考察的是你的**认知深度**，不要简单回答"是"或"不是"。

---

## 四、场景设计题（含答案）

### 场景 1：自动报销审核 Agent

**题目**：设计一个员工报销自动审核系统，先判断它该是 Workflow 还是 Agent，给出方案。

**答案**：

**先判断**：报销审核流程**高度结构化**（识别发票 → 分类 → 校验金额上限 → 匹配项目 → 输出结论），这是典型的 **Workflow** 而非 Agent。如果按 Agent 来做，会引入不可控、不可审计、合规风险。

**架构**：
```
[报销单 + 票据] 
   → 节点1：OCR 识别（CV 模型，非 LLM）
   → 节点2：发票分类（LLM，分类任务）  
   → 节点3：规则校验（纯代码，金额上限、票据类型白名单）
   → 节点4：项目编码匹配（RAG，从项目库检索）
   → 节点5：异常 LLM 推理（仅在规则校验失败时进入，给出疑点）
   → 节点6：输出审核报告 + 路由（自动通过 / 人工复核）
```

**关键决策**：
- **大部分用纯代码，少量用 LLM**：合规和成本双优
- **人工复核兜底**：金额超阈值、规则歧义、LLM 不确定时
- **审计日志**：每一步的输入输出全留痕
- **评估**：用历史已审核单做回归集，准确率与人工一致率两个指标

**反向思考**：什么时候这套要升级成 Agent？当业务规则极度复杂（如跨国多税制、多版本政策动态生效），用 Agent 让 LLM 调用"政策检索工具 + 金额计算工具 + 项目匹配工具"动态决策，但仍需 HITL。

---

### 场景 2：技术调研 Agent

**题目**：用户问"对比 LangGraph 和 AutoGen，给出选型建议"，设计一个能自动回答的 Agent。

**答案**：

**判断**：这是开放探索任务，需要多轮搜索 + 综合判断，**适合 Agent**。

**架构**（Plan-and-Execute 范式）：
```
1. Planner（LLM）：把问题拆为子问题
   - LangGraph 核心特性？
   - AutoGen 核心特性？
   - 两者在状态管理上的差异？
   - 社区生态？
   - 典型用户案例？

2. Executor（循环）：对每个子问题
   - WebSearch 工具：搜官方文档 + 技术博客
   - FetchURL 工具：抓取详细页面
   - 写入中间笔记（短期记忆）

3. Synthesizer（LLM）：汇总笔记 → 生成对比表 + 推荐

4. Reflector（LLM，可选）：检查输出是否覆盖所有子问题，缺失则回到 Executor
```

**关键决策**：
- **为什么不用 ReAct**：开放问题需要先有结构化分解，纯 ReAct 容易跑偏
- **工具**：WebSearch（Tavily / Serper）、FetchURL、Note（写入临时存储）
- **成本控制**：限制最大 step 数（如 20）、设置 token budget
- **评估**：用一组事先准备好的对比题（如 "Pinecone vs Weaviate"）做回归

---

## 五、自测清单

口述以下问题，每题 30s~2min：

- [ ] 用一句话定义 Agent
- [ ] Function Calling 的两层实现（训练 + 运行）
- [ ] 列举 5 种采样参数及其作用
- [ ] CoT 为什么对小模型无效
- [ ] 解释 Anthropic 的 Workflow vs Agent 分类
- [ ] temperature=0 为什么不完全确定
- [ ] RLHF 和 DPO 的区别
- [ ] 闭源 vs 开源选型 4 个维度
- [ ] Lost in the Middle 是什么

---

## 六、延伸阅读

- Anthropic — *Building Effective Agents*（必读）
- OpenAI — *A practical guide to building agents*
- Lilian Weng — *LLM Powered Autonomous Agents*
- Liu et al. — *Lost in the Middle: How Language Models Use Long Contexts*
- GSM-Symbolic — Apple 关于 LLM 推理能力的怀疑性论文
