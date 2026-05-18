# Day 4 — 记忆与上下文工程

> 目标：理解 Agent 的短期 / 长期记忆架构、上下文管理策略、以及 Context Engineering 的核心方法论。

---

## 一、核心概念

### 1.1 为什么 Agent 需要"记忆"
LLM 本身是**无状态的**：每次推理只看当前 prompt。Agent 要在多轮 / 跨会话保持连贯，必须由宿主程序管理状态 — 这就是"记忆"。

### 1.2 记忆分类（认知科学借鉴）
| 类型 | 含义 | Agent 中的对应 |
|------|------|----------------|
| **工作记忆** | 当前思考用的临时缓存 | 当前 prompt 中的内容 |
| **Episodic 情景记忆** | 具体发生的事件 | 历史对话、工具调用轨迹 |
| **Semantic 语义记忆** | 抽象事实知识 | 用户偏好、领域知识库 |
| **Procedural 程序记忆** | 流程技能（"怎么做"） | 习得的工作流、prompt 模板 |

### 1.3 短期记忆（Short-term Memory）
**定义**：单次会话内的对话历史和中间状态。

**典型实现**：
- **Buffer**：直接累积所有 messages（最简单但会爆）
- **Window**：只保留最近 N 轮（丢失早期信息）
- **Token Buffer**：保留最近 token 数 ≤ M 的内容
- **Summary**：把旧对话压缩成摘要 + 保留最近 N 轮
- **Summary Buffer**：动态摘要（超过阈值就摘要一次）

### 1.4 长期记忆（Long-term Memory）
**定义**：跨会话持久存储，可在新会话中被检索使用。

**典型实现**：
- **Vector Store**：把记忆条目向量化存储，按相似度检索
- **Knowledge Graph**：实体 + 关系结构化存储
- **结构化 DB**：用户偏好等强结构数据用 SQL/NoSQL
- **混合存储**：vector + graph + structured 协同

**写入策略**：
- 每轮结束后由 LLM 提取重要信息（"用户提到了她叫小红，喜欢猫")
- 提取出的事实存入长期记忆
- 下次会话开始时按用户问题检索 top-k 注入

### 1.5 上下文工程（Context Engineering）
**定义**：管理塞进 LLM context window 内容的工程实践。

**核心动作**：
1. **Write（写入）** — 决定哪些信息写入记忆
2. **Select（选择）** — 哪些记忆 / 文档应该被本次 prompt 用到
3. **Compress（压缩）** — 长内容摘要、精简
4. **Isolate（隔离）** — 分隔不同来源（system / user / tool / memory）

> 这是 LangChain CEO Harrison Chase 推广的 framework。Andrej Karpathy 也用过 "context engineering > prompt engineering" 的说法。

### 1.6 Lost in the Middle 问题
**现象**（Liu et al. 2023）：在长上下文中，**开头和结尾**信息利用率高，**中间**显著被忽略。

**实验**：把答案放在 30 条文档的不同位置，10 文档时模型表现稳定，20 条以上时中段位置的准确率明显下降。

**应对**：
- 关键信息放最前或最后
- 检索结果按相关度排序后**重排**（最相关的放两端）
- 控制 context 长度，不要盲目堆

### 1.7 上下文污染（Context Pollution）
**含义**：错误 / 无关信息进入 context，影响后续推理。

**典型场景**：
- 工具返回大量噪声数据（如 1MB JSON）
- 早期 Hallucination 进入历史，后续被强化
- 错误的 Reflection 误导后续

**应对**：
- 工具结果摘要后再回填
- 关键决策点 self-check
- Reflection 加质量过滤

### 1.8 MemGPT / Letta 思想
**核心**：把 LLM 当作 OS，**分页式管理上下文**。

```
┌─────────────────────────┐
│ Main Context (in-window) │  ← 当前推理用
│  - System Instructions   │
│  - Working Memory        │
│  - Recent Messages       │
├─────────────────────────┤
│ External Storage         │  ← 不在 window，需要时调用工具读
│  - Archival Memory       │  ← 长期向量库
│  - Recall Memory         │  ← 完整历史
└─────────────────────────┘
```

**机制**：LLM 自己用工具管理记忆：
- `core_memory_append`：写入工作记忆
- `archival_memory_insert`：存入长期
- `archival_memory_search`：检索长期
- `recall_search`：搜索完整历史

**意义**：把"如何管理上下文"也交给 LLM 自主决策，类似虚拟内存。

### 1.9 Prompt Caching 与记忆
- Prompt Caching 是**机制**（前缀重用），不是记忆
- 但它让"保留长 system prompt + 工具 schema"在 Agent 多轮中成本可接受
- 是"工程上让长 context 可行"的关键支撑

---

## 二、主流实现要点

### 2.1 LangChain 短期记忆类型
- `ConversationBufferMemory` — 全量
- `ConversationBufferWindowMemory(k=N)` — 滑窗
- `ConversationSummaryMemory` — 全摘要
- `ConversationSummaryBufferMemory(max_tokens=...)` — 摘要 + 最近窗口
- `ConversationTokenBufferMemory(max_tokens=...)` — 按 token 控制

### 2.2 LangGraph 状态管理
- **State**：用 TypedDict 定义图状态（messages、scratchpad、用户信息等）
- **Reducer**：定义状态合并逻辑（如 `add_messages` 自动追加）
- **Checkpointer**：状态持久化（内存 / SQLite / Postgres / Redis）
- **Thread**：每个 thread_id 对应一条会话历史
- **Cross-thread Memory**：通过 `Store` 接口跨 thread 共享（如用户偏好）

### 2.3 长期记忆专用服务
- **Mem0**：开源记忆层，自动从对话提取事实
- **Zep**：知识图谱 + 向量混合
- **Letta**（前 MemGPT）：完整 MemGPT 实现
- **LangMem**：LangChain 的记忆套件

### 2.4 向量库选型（用于长期记忆）
| 工具 | 特点 |
|------|------|
| **pgvector** | Postgres 扩展，工程化首选 |
| **Pinecone** | 托管服务，开箱即用 |
| **Weaviate** | 开源，schema 友好 |
| **Qdrant** | 开源，性能优秀 |
| **Milvus** | 大规模 |
| **Chroma** | 本地开发友好 |

### 2.5 Embedding 模型
- **OpenAI**：text-embedding-3-large / small
- **Voyage**：voyage-3，目前评测领先
- **Cohere**：embed-english-v3 / multilingual
- **开源**：BGE-M3、E5、Jina
- **国产**：阿里 GTE、智源 BGE

### 2.6 Anthropic Prompt Caching 实战
- 标记缓存点：`cache_control={"type": "ephemeral"}`
- 最多 4 个缓存断点
- TTL：5 min / 1 hour（1h 是 beta）
- 计费：写入 1.25x 单价、读取 0.1x
- 收益门槛：缓存内容 ≥ 1024 tokens（Sonnet）/ 2048 tokens（Haiku）

---

## 三、高频面试题（含答案）

### Q1：Agent 跑了 30 轮，上下文爆了，怎么办？

**答**：

**根因优先级排查**：

1. **是否有不必要的内容？**
   - 工具返回的大 JSON 应该摘要后才回填
   - System prompt 是否过长？砍掉低价值示例
   - 历史中已被解决的子任务能否清掉？

2. **是否有压缩空间？**
   - 摘要早期对话（保留要点，丢细节）
   - 工具调用历史用结构化记录（不保留完整原文）

3. **架构改造**：
   - **Summary Buffer**：超过阈值自动摘要，保留最近 N 轮原文
   - **MemGPT 模式**：分主上下文 + 外部存储，模型按需读取
   - **多 Agent 拆分**：把任务拆给子 Agent，每个子 Agent 用独立 context
   - **Plan-and-Execute**：用计划压缩上下文（不需要每步都看完整历史）

**工程实现示例**：
```python
def compress_history(messages, threshold=20000):
    if total_tokens(messages) < threshold:
        return messages
    
    # 保留最近 5 轮原文 + 旧历史摘要
    recent = messages[-10:]
    old = messages[:-10]
    summary = llm.summarize(old, focus="key decisions, user preferences, unfinished tasks")
    return [SystemMessage(f"Earlier conversation summary: {summary}")] + recent
```

**监控**：
- 实时 token 计数
- 告警阈值（如 80% context 时压缩）
- 离线分析：哪些场景容易爆？是否能从源头优化？

---

### Q2：用户上次说他叫小红，下次对话怎么自动调用？

**答**：

需要**长期记忆系统**，三步：

**1. 提取**（每轮结束后异步执行）
```python
extraction_prompt = """
From the conversation, extract durable facts about the user:
- Identity (name, role, demographics)
- Preferences (likes, dislikes)
- Goals
- Important events

Return JSON, only what's confidently stated, no inference.
"""
facts = llm.extract(conversation, prompt=extraction_prompt)
# {"user_name": "小红", "pet_preference": "猫"}
```

**2. 存储**
- 向量库：每条 fact 单独 embedding
- 结构化 KV：高频字段（user_name）直接表字段
- 写入策略：
  - 新增：相似度 < 0.9 的视为新事实
  - 更新：相似但有冲突的标记为"事实变更"，旧事实标 deprecated
  - 去重：相似度 > 0.95 视为重复

**3. 检索 + 注入**（新会话开始时）
```python
def build_system_prompt(user_id, current_query):
    # 高频字段直接读
    user_profile = db.get_user_profile(user_id)
    
    # 向量召回相关 facts
    related_facts = vector_store.search(
        query=current_query, 
        filter={"user_id": user_id}, 
        top_k=10
    )
    
    return f"""
    User context:
    - Name: {user_profile.name}
    - Known facts: {format(related_facts)}
    
    Use this context naturally in your response.
    """
```

**关键工程点**：
- **隐私**：用户能查看 / 删除自己的记忆（GDPR）
- **新鲜度**：旧记忆带时间戳，过期的降权
- **冲突解决**：用户改名怎么办？最新优先
- **可解释**：能展示"基于哪些记忆给的回答"

**开源方案**：Mem0、Letta、LangMem 都开箱即用。

---

### Q3：怎么应对 Lost in the Middle？

**答**：

**Lost in the Middle**：长 context 中段信息被忽略。

**应对策略**：

**1. 控制 context 长度**
- 别盲目塞 50 个文档，10~15 通常够用
- RAG 后用 rerank 拉精度而非堆数量

**2. 重排序（最重要）**
- 检索召回后按相关度排序
- 把最相关的放**两端**（开头 + 结尾），相关度低的放中间
- LangChain `LongContextReorder` 直接做这事

**3. 结构化呈现**
- 不要平铺文本，用标记分隔（XML、Markdown）
- 让模型更容易"定位"到关键片段
```xml
<important_context>...关键信息...</important_context>
<reference_material>...次要信息...</reference_material>
```

**4. 显式指令**
- "Pay close attention to documents marked as PRIMARY"
- 引导模型显式关注关键部分

**5. 分阶段处理**
- 让模型先"读完所有文档列要点"
- 再基于要点回答
- 用两次调用换准确率

**6. 长 context 模型不一定救你**
- Claude 200k、Gemini 2M 不代表中段问题解决
- 该重排还得重排

**评估**：构造"needle in haystack"测试集，验证不同位置的检索准确率。

---

### Q4：MemGPT 和 RAG 的区别？

**答**：

**RAG**：被动检索
- 系统决定"什么时候检索、检索什么"
- 通常每轮开始按用户问题召回
- 检索结果一次性塞入 prompt
- 模型只能看到本次召回的内容

**MemGPT**：主动管理
- 模型自主决定"何时翻档案、何时存档案"
- 通过工具调用读写外部存储
- 像 OS 的虚拟内存：主上下文是 RAM，外部是磁盘
- 模型决定哪些信息装载 / 换出

**对比**：

| 维度 | RAG | MemGPT |
|------|-----|--------|
| 控制权 | 系统 | 模型 |
| 调用次数 | 单次检索 | 多次读写 |
| 适合 | 知识问答 | 长期个人助理 |
| 复杂度 | 低 | 高 |
| 成本 | 低 | 高（多次工具调用） |
| 灵活性 | 低 | 高 |

**实战**：
- 80% 场景 RAG 够用
- 长期 personal agent / 跨会话连贯性强需求 → MemGPT
- 也可结合：MemGPT 的存储后端用向量库

---

### Q5：怎么避免上下文污染？

**答**：

**典型污染源 + 应对**：

**1. 工具结果污染**
- **场景**：工具返回 10 万 token JSON，全塞 context
- **应对**：工具层做摘要 / 抽样
```python
def tool_post_process(raw_result):
    if len(raw_result) > 5000:
        return summarize(raw_result, focus="key fields")
    return raw_result
```

**2. 早期 hallucination 自我强化**
- **场景**：模型早期编造"用户叫张三"，后续基于此推理
- **应对**：
  - 关键事实有 source（来自用户 / 来自工具）
  - 定期 self-check（"以下推理基于哪些已确认事实？"）

**3. 错误的 Reflection**
- **场景**：Reflexion 生成的反思本身是错的，污染下次尝试
- **应对**：Reflection 加质量评估，分数低的丢弃

**4. 多源信息混淆**
- **场景**：模型分不清"系统知识"和"用户输入"
- **应对**：用 role / 标记强分隔
```
<user_provided>...</user_provided>
<retrieved>...</retrieved>
<my_reasoning>...</my_reasoning>
```

**5. 长链 Agent 的中间噪声**
- **场景**：每步 Thought / Observation 都留着，到 step 20 已经一团乱
- **应对**：阶段性 checkpoint summary，丢弃细节

**架构性的根本应对**：
- **隔离**：Sub-agent 拿独立 context，主 Agent 只看子任务结果
- **结构化状态**：用 TypedDict / Pydantic 管理 Agent 状态，明确每字段来源
- **可观测**：trace 每个 context piece 的来源，便于排查

---

### Q6：Context Engineering 和 Prompt Engineering 的区别？

**答**：

**Prompt Engineering**（狭义）：
- 关注**单次调用**的 prompt 文本怎么写
- 技巧：role 设定、few-shot、CoT 触发、约束输出格式
- 优化目标：让单次 prompt 产生期望输出

**Context Engineering**（广义）：
- 关注**整个 context window 内容的工程化管理**
- 技巧：
  - **Write**：决定哪些信息写入记忆
  - **Select**：哪些记忆 / 文档应当出现
  - **Compress**：长内容压缩
  - **Isolate**：sub-agent 隔离
- 优化目标：让 Agent 在多轮、长任务、多工具场景下持续可用

**关系**：
- Prompt engineering 是 context engineering 的**子集**
- 在 Agent 时代，单次 prompt 优化收益递减，**怎么管理上下文流动**才是主战场

**类比**：
- Prompt engineering 像写一个完美的函数
- Context engineering 像设计一个分布式系统

**实战表现**：
- 单次问答系统 → prompt engineering 投入更多
- Agent 系统 → context engineering 投入更多

---

### Q7：长期记忆怎么避免"记忆膨胀"？

**答**：

**问题**：记忆条目越积越多，
- 召回质量下降（相关 + 不相关混在一起）
- 检索变慢
- 隐私 / 合规风险（持久存储敏感信息）

**治理策略**：

**1. 写入侧节流**
- 不是每句话都存，只存"durable facts"（持久事实）
- 用 LLM 判断"这条信息是否值得记忆"（重要性打分）
- 阈值过滤：只存 >= 0.7 的

**2. 去重与合并**
- 相似度 > 0.95 的条目视为重复，只保留最新
- 同主题多条记忆定期 LLM 合并（如 5 条关于偏好 → 1 条综合）

**3. 衰减机制**
- 记忆带 last_accessed_at
- 久未访问 → 降权 / 归档
- Ebbinghaus 曲线类的指数衰减

**4. 冲突检测**
- 新事实与旧事实冲突时（如"用户搬家了"），标旧的为 deprecated
- 不删除（审计需要），但召回时过滤

**5. 分层存储**
- Hot：最近 30 天 / 高频访问 → 高性能向量库
- Warm：3 个月内 → 普通存储
- Cold：归档（仍可访问但慢）

**6. 用户控制**
- 用户能查看 "what does the AI know about me"
- 提供删除按钮（合规必备）
- 提供"忘记此事"指令

**7. 评估**
- 离线指标：召回 P@K、记忆条目质量分布
- 监控：单用户记忆条目数告警

---

## 四、场景设计题（含答案）

### 场景 1：私人 AI 助手的记忆架构

**题目**：设计一个长期陪伴用户的 AI 助手（类似 Pi、Replika），要记住用户偏好、历史对话、待办事项。

**答案**：

**记忆分层**：

```
┌────────────────────────────────────┐
│ 工作记忆（当前会话 context）         │
│  - System Prompt + Persona         │
│  - 当前用户 Profile 摘要            │
│  - 最近 N 轮对话                    │
│  - 召回的相关长期记忆               │
├────────────────────────────────────┤
│ 短期记忆（会话级）                   │
│  - LangGraph State + Checkpointer  │
│  - 存储：Postgres                  │
├────────────────────────────────────┤
│ 长期记忆（跨会话）                   │
│  - 结构化 Profile（姓名、年龄、职业） │
│  - Episodic（重要事件、情绪节点）    │
│  - Semantic（偏好、兴趣、关系）      │
│  - Procedural（习得的对话风格）      │
│  - 存储：pgvector + Postgres        │
├────────────────────────────────────┤
│ 待办与提醒                          │
│  - 结构化 Task 表                   │
│  - 定时调度（Cron）                 │
└────────────────────────────────────┘
```

**关键流程**：

**A. 对话循环**
1. 用户发消息
2. 加载短期记忆（本会话历史）
3. 召回长期记忆（按消息内容 + 用户 ID 检索）
4. 组装 context
5. LLM 生成回复
6. 异步任务：抽取新 fact、更新 profile

**B. 长期记忆抽取（异步）**
```
每 N 轮结束后触发：
  facts = llm.extract(conversation)
  for fact in facts:
    if similarity_to_existing(fact) > 0.95: skip
    elif conflicts_with_existing(fact): mark old as deprecated
    else: insert new
```

**C. 提醒与待办**
- 用户提"明天提醒我开会" → 工具 `create_reminder(time, content)`
- 定时调度到时间触发，主动发消息

**关键技术决策**：

1. **Persona 一致性**：System prompt 固定人设，加入"你之前对用户说过 X"的引用
2. **情绪记忆**：检测情绪标记，重大情绪节点优先保留
3. **遗忘机制**：90 天未访问的记忆降权，1 年归档
4. **隐私**：端到端加密、本地优先存储、用户随时导出/删除

**评估**：
- 一致性：让评估员伪装老用户，看模型能否记住他
- 召回准确率：测试集 "用户提及 X" → 看是否能召回
- 用户满意度：NPS、留存

---

### 场景 2：长 Trace Coding Agent 的上下文管理

**题目**：一个写代码的 Agent（类似 Cursor / Claude Code），可能跑 30+ 步，每步都涉及读文件、改文件、跑测试，怎么管理上下文不爆？

**答案**：

**核心问题**：每读一个大文件、每次工具输出，都可能塞几千 token。30 步累积必爆。

**策略**：

**1. 工具输出主动压缩**
- `read_file` 长文件分块读，只回填关键段（基于查询 LLM 决定）
- `run_tests` 输出长 → 摘要：成功数、失败数、关键错误信息
- `grep` 结果过多 → 截断 + 提示用户细化

**2. 文件状态去重**
- 同一文件多次读取，只保留最新版本（旧版本 stale）
- 用 `<file path="..." version="3">` 标记

**3. 阶段性 checkpoint summary**
- 每 10 步触发：让 LLM 总结"目前完成了什么、还要做什么、关键约束"
- 把早期 thought / observation 替换为 summary
- 保留最近 5 步原文供细粒度推理

**4. 子任务隔离**
- 主 Agent 接收 "实现功能 X"
- 拆分为子任务：A) 写代码 B) 写测试 C) 调试
- 每个子任务用独立 context，主 Agent 只看子任务的结果摘要

**5. 工具结果分级回填**
```
[关键结果]   完整回填（如失败的 test trace）
[一般结果]   摘要回填（如 grep 命中数）
[低价值结果] 仅元信息（如 "file created"）
```

**6. 持久化与可恢复**
- LangGraph Checkpointer 持久状态
- 任务超长 → 切片保存，下次继续

**7. 模型选择**
- 主 Agent 用大模型（决策准）
- 子任务用中等模型（成本低）
- 摘要 / 提取用小模型

**监控**：
- 单任务 token 上限（如 50 万 token 强制终止）
- 每步 token 增量监控
- 离线分析：哪些工具贡献最多 token？哪类任务最容易爆？

---

## 五、自测清单

- [ ] 工作记忆 / Episodic / Semantic / Procedural 的差异
- [ ] 短期记忆的 5 种实现策略
- [ ] 长期记忆三段式（提取 → 存储 → 检索）
- [ ] Context Engineering 的 4 个核心动作（Write/Select/Compress/Isolate）
- [ ] Lost in the Middle 现象与 5 种应对
- [ ] MemGPT 的核心思想（LLM as OS）
- [ ] 上下文污染的 5 类来源
- [ ] 长期记忆膨胀的 7 种治理策略
- [ ] Prompt Caching 的工程价值

---

## 六、延伸阅读

- Liu et al. — *Lost in the Middle: How Language Models Use Long Contexts*
- Packer et al. — *MemGPT: Towards LLMs as Operating Systems*
- LangChain Blog — *Context Engineering*
- Mem0 — *Open-source Memory Layer for AI Agents*
- Anthropic — *Prompt Caching Documentation*
