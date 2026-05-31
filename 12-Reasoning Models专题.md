# Reasoning Models 专题

> 目标：搞懂 o1 / o3 / DeepSeek R1 / Claude Extended Thinking 这一代"推理模型"的训练原理、推理机制、工程使用，以及在 Agent 中的角色。这是 2024 Q4 ~ 2025 LLM 领域最大变化。

---

## 一、核心概念

### 1.1 什么是 Reasoning Model
**狭义定义**：通过强化学习训练得到的、在输出最终答案前会**自发产生长思维链**的 LLM。

关键特征：
1. **内置长 CoT**：不需要 "let's think step by step" prompt，模型自己就会推理
2. **Self-correction**：会在推理中"等等让我重新想想"
3. **可控的思考预算**：能让它思考更多 / 更少（reasoning_effort）
4. **Test-time compute**：花更多推理 token 换更高准确率

### 1.2 与传统 CoT 的本质区别

| 维度 | 传统 CoT | Reasoning Model |
|------|----------|-----------------|
| 触发 | Prompt 工程（"step by step"） | 训练时学会，自发产生 |
| 推理长度 | 几百 token | 数千到数万 token |
| 训练阶段 | SFT 教 demos | RL 直接奖励推理过程 |
| Self-correction | 弱 | 强 |
| Test-time compute | 难 scale | 天然 scale |
| 价格 | 普通 LLM 价 | 通常更贵 |

**Sam Altman 总结**：从"快思考"（System 1）到"慢思考"（System 2）。

### 1.3 主流模型谱系（截至 2025 Q2）

#### OpenAI 系
- **o1-preview / o1**（2024.09）：首发，开启范式
- **o1-mini**：便宜版
- **o3 / o3-mini**（2024.12 ~ 2025.01）：能力升级，o3 在 ARC-AGI 上突破
- **o4-mini**（2025）：成本更优

#### Anthropic 系
- **Claude 3.7 Sonnet Extended Thinking**（2025.02）：首次推出 thinking 模式
- **Claude 4 Opus / Sonnet Thinking**：thinking 是可控的 budget
- 特点：thinking trace 对用户**可见**（vs OpenAI 隐藏）

#### DeepSeek 系
- **DeepSeek R1-Zero**（2025.01）：纯 RL 训练（无 SFT）证明可行
- **DeepSeek R1**：R1-Zero + 冷启动数据 + 多阶段训练
- 完全开源 + 论文公开 → 引爆复现潮
- **DeepSeek R1-Distill**：把 R1 的能力蒸馏到 Qwen / Llama 小模型

#### Google
- **Gemini 2.0 Flash Thinking**（2024.12）
- **Gemini 2.5 Pro / Flash Thinking**（2025）

#### 国内开源
- **Qwen QwQ-32B-Preview**（阿里）
- **Qwen3** 系列（2025 推出 thinking 模式）
- **Kimi K1.5**（月之暗面）
- **GLM-Zero-Preview**（智谱）

### 1.4 训练原理：从 SFT 到 RLVR

#### 传统 LLM 训练
```
预训练 → SFT（指令微调） → RLHF（人类偏好对齐）
```
- RLHF 用 Reward Model（人类标注偏好训出）做 PPO

#### Reasoning Model 训练（DeepSeek R1 范式）
```
预训练
  ↓
（可选）Cold-start SFT（少量高质量 reasoning data）
  ↓
RLVR（核心）
  ↓
（可选）拒绝采样 SFT + 多领域 RL
```

**核心：RLVR — Reinforcement Learning with Verifiable Rewards**

### 1.5 RLVR 详解

**核心思想**：不用人类标注偏好，用**可验证的奖励信号**直接 RL。

**Verifiable Reward 来源**：
- **数学**：最终数值是否正确（用计算验证）
- **代码**：单元测试是否通过（执行验证）
- **形式逻辑**：定理证明器验证
- **多项选择题**：答案是否匹配

**关键洞察**：
- 不需要 reward model（避免 reward model 被 hack）
- 数学 / 代码天然有 ground truth
- 模型可以**自由探索**推理路径，只要最后答对就给奖励

**典型算法**：
- **PPO**（OpenAI 早期 o 系列推测使用）
- **GRPO（Group Relative Policy Optimization）**（DeepSeek 提出，去掉 critic 模型）

#### GRPO 简述
```
对一个 query，采样 G 条回答 {o1, ..., oG}
计算每条的 reward r_i
group-relative advantage:  A_i = (r_i - mean(r)) / std(r)
用 advantage 更新 policy
```
- 比 PPO 简单：不需要 value/critic 网络
- 更省显存（critic 模型不小）
- DeepSeek R1 用 GRPO 训出来

### 1.6 R1 训练 pipeline（DeepSeek 论文）

**R1-Zero**（纯 RL，无 SFT）：
```
DeepSeek-V3-Base
  ↓ GRPO + Verifiable Reward
DeepSeek-R1-Zero
```
- 惊人的发现：纯 RL 也能涌现长 CoT
- 但有问题：可读性差（语言混杂）、不安全

**R1**（多阶段）：
```
1. Cold-start：少量高质量长 CoT 数据 SFT
2. Reasoning RL：用 RLVR 训练数学 / 代码
3. Rejection Sampling + SFT：用 R1 生成大量数据，过滤后 SFT
4. All-scenarios RL：通用任务 + 安全对齐
```

**关键启示**：
- 纯 RL 可以涌现推理（不需要 SFT）
- 但工程上 cold-start + 多阶段更稳

### 1.7 蒸馏到小模型

**做法**：用 R1 / o1 生成大量高质量推理 trace，作为 SFT 数据训小模型。

**DeepSeek 蒸馏结果**：
- R1-Distill-Qwen-7B 在数学题上超过 GPT-4o
- 蒸馏的 7B 模型超过自己 RL 训练的 7B
- → 强模型生成的推理数据 > 小模型自己探索

**工程意义**：开源社区能廉价获得"推理小模型"。

### 1.8 Test-Time Compute Scaling

**核心思想**：花更多推理算力 → 更高质量答案。

**Inference Scaling Laws**（OpenAI o1 论文）：
- 训练算力 + 测试算力 = 总能力
- 这是 LLM 第二个 scaling 维度

**Scaling Test-time 的方法**：

**1. 长 CoT（reasoning model 默认）**
- 让模型自己产生更长思考
- 长度 ~ 算力

**2. Best-of-N / Self-Consistency**
- 采样 N 条独立答案，投票 / reward model 选最优
- 简单但有效

**3. Tree Search**
- ToT / GoT 风格
- 在每个节点用 reward 评估、剪枝、扩展
- 配合 process reward model

**4. Iterative Refinement**
- 自我反思 → 修正 → 再反思
- Self-Refine、Reflexion

**5. Multi-agent Debate**
- 多 Agent 辩论、批评

**关键资源约束**：
- 上下文长度（思考太长会超）
- 延迟（thinking 时间 ~ token 数）
- 成本

### 1.9 Process Reward Model vs Outcome Reward Model

**ORM（Outcome Reward Model）**：
- 只看最终结果对不对
- 信号稀疏，但鲁棒
- RLVR 默认这种

**PRM（Process Reward Model）**：
- 评估每一步推理是否正确
- 信号密集，可指导中间步骤
- 训练成本高（需要 step-level 标注）
- 易被 reward hack（模型学会"看起来对"而非真对）

**实战**：
- 大多数 reasoning model（R1、o1）主要用 ORM 类 reward
- PRM 用于 search-based 推理（在 inference 时评估每步）

### 1.10 Hidden vs Visible Reasoning

**OpenAI o 系列**：reasoning trace **隐藏**
- 计费但用户看不到
- 原因（OpenAI 官方）：
  - 保护推理过程不被对手蒸馏
  - 允许模型"不安全地思考"但只输出安全答案
- 用户看到的是 reasoning_tokens（数量）+ final answer

**Claude Extended Thinking**：thinking **可见**
- 模型在 `<thinking>...</thinking>` 块里思考
- API 返回完整 trace
- 可调试性更强

**DeepSeek R1**：完全可见（`<think>...</think>`）
- 开源 + 透明

**工程含义**：
- 选 Claude/DeepSeek 调试更容易
- 选 OpenAI 时无法看推理细节
- 隐藏 trace 可能导致用户难以信任

### 1.11 控制思考预算

不同厂商提供不同的预算控制：

**OpenAI**：
- `reasoning_effort`: "low" / "medium" / "high"
- 没有精确 token 控制

**Anthropic**：
- `max_thinking_tokens`：精确上限
- 可设很高（如 32k）或关掉（0）

**DeepSeek**：
- 自动（基于难度）

**实战经验**：
- 简单任务用 low / 关掉，避免无谓延迟
- 复杂任务用 high
- 不要总是 high（边际收益递减 + 成本暴涨）

### 1.12 何时该用 Reasoning Model

#### ✅ 适合
- **数学 / 代码 / 逻辑**：天然受益
- **复杂规划 / 多步推理**：明显比直答好
- **形式推理 / 证明**：科学问题
- **复杂 Agent 决策**：planning 阶段
- **难解的 corner case**：直答错的可能性高

#### ❌ 不适合
- **简单对话 / 闲聊**：浪费成本和延迟
- **快速 lookup**：信息检索任务
- **创意 / 写作**：reasoning model 在创意上 *不一定* 更强
- **实时 / 低延迟场景**：thinking 时间太长
- **简单分类 / 抽取**：传统 LLM 已经很好

**判断启发**：
- 这个问题如果让人类想 5 分钟会比想 5 秒更好吗？→ 是 → 用 reasoning model
- 否 → 普通 LLM 性价比更高

### 1.13 Reasoning Model 在 Agent 中的角色

**Agent 流程中谁应该用 reasoning model？**

**Planner 阶段**：✅ 强烈推荐
- 拆解复杂任务、确定步骤序列
- 错一步全错，思考一次定基调

**Executor 阶段**：⚠️ 看情况
- 简单工具调用 → 普通 LLM
- 复杂工具组合 → reasoning model

**Critic / Reviewer**：✅ 推荐
- 评估前序步骤、识别错误

**对话层**：❌ 通常不用
- 用户体验要快、要自然

**典型架构**：
```
[Planner: o1/R1]  ← 一次性深度思考
   ↓
[Executor: Sonnet/Haiku]  ← 多次快速调用
   ↓
[Critic: o1/R1]  ← 终审
```

---

## 二、主流实现与 API

### 2.1 OpenAI o 系列

**API 用法**：
```python
response = client.chat.completions.create(
    model="o3-mini",
    messages=[...],
    reasoning_effort="medium",  # low / medium / high
)

# 响应中
response.choices[0].message.content  # 最终答案
response.usage.completion_tokens_details.reasoning_tokens  # 思考 token 数（计费）
```

**注意**：
- 不支持 system message（o1 不支持，o3 部分支持）
- 不支持 streaming（o1，o3-mini 支持）
- Function calling 在 o1 早期不支持，后续逐步加上
- Temperature 等参数被忽略（设了也没用）

### 2.2 Anthropic Extended Thinking

```python
response = client.messages.create(
    model="claude-opus-4-7",
    thinking={
        "type": "enabled",
        "budget_tokens": 16000,  # 最大思考 token
    },
    messages=[...],
)

# 响应中包含 thinking block
for block in response.content:
    if block.type == "thinking":
        print("Thinking:", block.thinking)
    elif block.type == "text":
        print("Answer:", block.text)
```

**特点**：
- thinking 与正常输出在同一响应
- 可精确控制 budget
- 完整支持 tool use、streaming
- Thinking 不会进入下一轮历史（除非显式保留）

### 2.3 DeepSeek R1

```python
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[...],
)

response.choices[0].message.reasoning_content  # 思考
response.choices[0].message.content  # 答案
```

**特点**：
- 价格便宜（input $0.55/1M、output $2.19/1M）
- 思考完全可见
- 不支持 function calling（截至 2025 中）

### 2.4 自部署 reasoning model

**开源选项**：
- **DeepSeek R1** 全权重开源（~671B MoE）
- **R1-Distill-Qwen / Llama** 系列（7B、14B、32B、70B）
- **QwQ-32B**（阿里）
- **Marco-o1**（阿里达摩院）

**部署**：
- vLLM 支持
- 关键：长上下文（thinking 通常占很多 token）

### 2.5 框架支持

- **LangChain / LangGraph**：自然支持，把 reasoning_tokens 作为额外字段
- **OpenAI Agents SDK**：原生支持
- 自研：注意 thinking content 处理 + cost 计算（reasoning_tokens 也计费）

---

## 三、高频面试题（含答案）

### Q1：Reasoning Model 和传统 CoT 的本质区别？

**答**：

**表层差异**：
- 传统 CoT：靠 prompt 触发（"think step by step"）
- Reasoning Model：靠训练学会，自发产生

**本质差异**：

**1. 训练范式不同**
- CoT：SFT 阶段塞入推理样本，模型模仿
- Reasoning Model：RL 阶段直接奖励"先思考再答对"，模型自己探索推理策略

**2. 推理长度量级不同**
- CoT：几百 token，线性推理
- Reasoning Model：数千到数万 token，含自我修正、试错、回溯

**3. Self-correction 能力**
- CoT：基本没有，错了就错
- Reasoning Model：会出现 "wait, let me reconsider"、"actually no"

**4. Test-time compute 不同**
- CoT：再多 step by step 也撑不开
- Reasoning Model：天然 scale，思考越久越准（有上限）

**5. 涌现的"反思"行为**
- DeepSeek R1 论文展示了"Aha moment"：模型自己学会反思
- 这不是 prompt 工程能造出的

**面试加分**：
- 提到 RLVR 是核心新东西
- 提到 inference scaling laws
- 引用 R1-Zero 证明"纯 RL 也能涌现推理"

---

### Q2：RLVR 是什么？比 RLHF 强在哪？

**答**：

**RLHF**：Reinforcement Learning from Human Feedback
- 人类标注偏好对
- 训 Reward Model
- 用 RM 信号 RL 模型
- **问题**：RM 可能被 hack、人类偏好不稳定、贵

**RLVR**：Reinforcement Learning with Verifiable Rewards
- 用**可程序化验证**的奖励代替 RM
- 数学：算结果对不对
- 代码：跑测试通不通过
- 形式推理：定理证明器验证

**RLVR 的优势**：

1. **奖励信号干净** — 不会被模型 hack（数学题答对就是答对）
2. **不需要 RM** — 省训练成本和工程复杂度
3. **可大规模** — verifiable 任务可批量生成（生成数学题 + 自动验证）
4. **避免人类偏好的不一致**
5. **能涌现"超越人类范式"的推理** — 不被人类标注限制

**RLVR 的局限**：
- 只在**有 verifier 的领域**有效（数学、代码、逻辑）
- 创意 / 写作 / 主观任务仍需 RLHF
- 实际工程：reasoning model 通常 **RLVR + RLHF 组合**

**面试加分**：
- 提到 DeepSeek R1 / R1-Zero 是 RLVR 代表
- 提到 GRPO 算法（DeepSeek 提出）
- 区分 ORM vs PRM

---

### Q3：DeepSeek R1 的训练 pipeline 是什么？

**答**：

**R1-Zero（先证明可行性）**：
- DeepSeek-V3-Base 模型
- 直接用 GRPO + RLVR
- **不用 SFT、不用 cold start**
- 验证：纯 RL 也能涌现长 CoT 和反思能力
- 问题：输出可读性差、语言混杂

**R1（生产版，多阶段）**：

**Stage 1：Cold-start SFT**
- 收集少量（数千）高质量长 CoT 数据
- 来源：R1-Zero 生成 + 人工筛选
- SFT V3-Base 一遍，让模型有"语言习惯"

**Stage 2：Reasoning-focused RL**
- 用 GRPO + 可验证奖励（数学、代码）
- 加入语言一致性奖励（防混杂）
- 训练到收敛

**Stage 3：Rejection Sampling + SFT**
- 用 Stage 2 模型生成大量样本
- 过滤掉错的、不通顺的
- 加入非推理数据（写作、QA、翻译）
- SFT 一遍 → 通用能力

**Stage 4：All-scenarios RL**
- 二次 RL：推理任务 + 通用任务 + 安全对齐
- 让模型在所有场景都好

**关键洞察**：
1. **冷启动数据小但关键**：解决 R1-Zero 的可读性问题
2. **拒绝采样自蒸馏**：模型自己生成高质量数据自己学
3. **多阶段交替 SFT + RL**：稳健 + 通用

**面试加分**：
- 能说出 R1-Zero 的意义（证明纯 RL 可行）
- 能区分 R1 与 R1-Zero
- 提到这是开源社区 reasoning model 工程的标准范式

---

### Q4：Test-time Compute Scaling 是什么？

**答**：

**核心论点**（OpenAI o1 论文）：
> LLM 能力 = f(训练算力, 测试算力)
> 历史上只 scale 训练算力，现在发现 scale 测试算力也有效

**Scaling Test-time 的方法**：

**1. Long CoT**（reasoning model 默认）
- 模型生成更长思考
- 思考 token 数 ↑ → 准确率 ↑（log scale）

**2. Best-of-N**
- 采样 N 个回答
- 用 reward model 或多数投票选最优
- N 越大越好（但成本线性增长）

**3. Tree Search**
- 在推理树上搜索
- 配合 process reward model 评估每步
- 高效但实现复杂

**4. Multi-pass refinement**
- 生成 → 评估 → 修改 → 再评估
- Reflexion / Self-Refine

**5. Multi-agent debate**
- 多 Agent 互相辩论批评

**两类 scaling 的关系**：
- 小模型 + 大 inference compute ≈ 大模型 + 小 inference compute
- 工程上，小模型 + 长 reasoning 可能更划算（模型部署便宜）

**实际数据**：
- AIME 2024：o1 思考越久准确率越高（30% → 80%+）
- 但有边际递减
- 上限：模型能力本身的边界

**面试加分**：
- 提到这是 LLM scaling 的"第二维度"
- 提到 trade-off（更高准确率 vs 延迟 / 成本）
- 提到 reasoning model 的核心创新就是把 test-time scaling 内化到模型本身

---

### Q5：什么时候该用 / 不该用 Reasoning Model？

**答**：

**该用的场景**：

1. **数学 / 代码 / 逻辑**：天然受益
2. **复杂规划**：Agent 的 planner 阶段
3. **多步推理 / 多约束求解**
4. **难解 corner case**：普通 LLM 容易错
5. **科学问题 / 论文级理解**

**不该用的场景**：

1. **简单对话 / 闲聊**：浪费
2. **快 lookup**：检索类任务
3. **实时 / 低延迟**：thinking 太慢
4. **创意写作**：reasoning model **不一定**更好
5. **简单分类 / 抽取**：传统 LLM 够用

**成本 / 延迟代价**：
- 思考 token 也计费（OpenAI 等同 output 价）
- 延迟可能 5x ~ 10x 普通 LLM
- 一个 o1 调用可能 30+ 秒

**架构最佳实践**：
- **混合架构**：Planner / Critic 用 reasoning，Executor / 对话用普通 LLM
- **动态路由**：query 复杂度判断 → 选模型
- **预算控制**：Anthropic 的 `max_thinking_tokens` 精确控制

**判断启发**：
> "这个问题给人类多 5 分钟会显著更好吗？"
> 是 → 用 reasoning model
> 否 → 普通 LLM 更经济

**面试加分**：
- 不要把 reasoning model 当万灵药
- 强调架构中的角色分工
- 提到延迟问题（用户体验）

---

### Q6：Reasoning trace 该 hidden 还是 visible？

**答**：

**两派做法**：

**Hidden（OpenAI o 系列）**：
- 计费但用户看不到
- 官方解释：
  - 防止推理过程被对手蒸馏（保护模型 IP）
  - 允许模型在思考中"不安全地探索"但只输出安全答案
- 用户只看到 `reasoning_tokens` 数量

**Visible（Anthropic、DeepSeek）**：
- 完整展示思考过程
- 可调试、可解释、用户信任度高
- 风险：被竞争对手蒸馏

**工程取舍**：

| 维度 | Hidden | Visible |
|------|--------|---------|
| 可调试 | 差 | 好 |
| 用户信任 | 差 | 好 |
| 模型保护 | 强 | 弱 |
| Agent debug | 难 | 易 |
| 监管 / 合规 | 难证明 | 易证明 |

**实战建议**：
- 生产中如果用 OpenAI o 系列，要建立**外部观察**手段（如评估 final answer 与 prompt 的语义连贯性）
- 用 Claude / DeepSeek 时，thinking 可作为额外信息（如检测幻觉）
- Thinking 不应直接展示给最终用户（除非是开发者工具），可能引起困惑

**安全维度**：
- Visible thinking 能让用户发现模型的 "anti-pattern"（例：辱骂用户但最终礼貌输出）
- 这是 Anthropic 选 visible 的一个动机

**面试加分**：
- 知道两派的取舍
- 提到 Anthropic 的 alignment 角度
- 提到工程上 thinking trace 别污染下轮 context

---

### Q7：Reasoning Model 在 Agent 系统中怎么放？

**答**：

**核心原则**：让 reasoning 用在"思考密度高、单点出错代价大"的地方。

**典型角色**：

**1. Planner（强烈推荐）**
- Agent 启动时分解任务
- 一次思考定基调，错了后面都白做
- 用 o1 / R1 / Claude Thinking 一次性深度规划

**2. Critic / Reviewer（推荐）**
- 评估前序输出
- 识别 subtle 错误
- 终审 / 关键 checkpoint

**3. Executor（看情况）**
- 简单工具调用 → 普通 LLM
- 复杂工具组合（多步推理决定调谁） → reasoning model
- 但要考虑延迟（每步都慢）

**4. 对话层（一般不用）**
- 用户期待快、自然
- thinking 太慢破坏体验
- 除非是研究 / 教育产品

**架构 pattern**：

```
[User Query]
    ↓
[Planner: o1/R1]         ← 深度思考一次
    ↓ (plan)
[Executor: Haiku/4o-mini]   ← 多次轻量调用
    ├─ tool calls
    ├─ context gather
    └─ ...
    ↓
[Critic: o1/R1]          ← 终审一次
    ↓
[Final Answer]
```

**注意**：

**1. Thinking 不进下轮 context**
- Claude thinking 默认不进 history
- 否则 context 爆炸

**2. Function calling 的成熟度**
- o1 早期不支持
- 现在 o3 / Claude thinking 支持
- DeepSeek R1 截至 2025.05 还不稳

**3. 流式输出**
- Reasoning 阶段没有可流式的内容
- 用户体验：先显示"AI 正在思考..."进度
- thinking 完才有 final answer 流式

**4. 成本控制**
- Reasoning token = output 单价
- 一次 thinking 可能 5000+ token = 几分钱~几毛
- 不要每个简单 query 都触发

**5. Hybrid 路由**
- Query 难度分类器决定走 reasoning 或普通
- 复杂 → reasoning，简单 → 普通

---

### Q8：Reasoning Model 失败模式有哪些？

**答**：

**1. 过度思考（Overthinking）**
- 简单问题想很久还是答对
- 浪费成本和延迟
- **应对**：reasoning_effort 调低、设 max budget

**2. Reasoning Hallucination**
- 思考过程看起来很合理，但中间步骤其实是错的
- 最终答案错但理由"自洽"
- **应对**：用 verifier 校验（数学题用计算器、代码跑测试）

**3. 思考与答案不一致**
- 思考时说"答案是 5"，最终输出"答案是 7"
- 罕见但存在
- **应对**：可见 thinking 模型可以检测

**4. Stuck in loops**
- "Let me reconsider" → "Actually no" → "Wait" 反复
- 不收敛
- **应对**：max budget 强制截断

**5. Format breakage**
- 推理时插入 markdown / 特殊符号
- 干扰下游 parser
- **应对**：明确 prompt 输出格式

**6. Reward hacking 遗留**
- 训练时模型学到"看起来在思考"而不是真思考
- 现象：思考很长但最终错
- **应对**：选择训练充分的模型、加 verifier

**7. 创意任务退化**
- Reasoning model 在创意上可能不如普通 LLM
- 思考容易让创意"理性化"
- **应对**：创意任务用 GPT-4o / Claude 而非 o1

**8. Token 爆炸**
- 单次 thinking 几万 token
- 总 context 限制下挤掉对话历史
- **应对**：budget 控制、不保留 thinking 到下轮

**9. Function calling 不稳**
- 早期 reasoning model 工具调用质量差
- 现在改善但仍不如专门优化的非 reasoning 模型
- **应对**：复杂 tool use 用 Sonnet 而非 o1

**10. 安全 / 越狱**
- thinking 中模型可能"想"出违规内容（hidden trace 用户看不到，但仍生成了）
- **应对**：OpenAI 选 hide 是有道理的；Anthropic 在 thinking 中也做对齐

---

## 四、场景设计题（含答案）

### 场景 1：复杂数学应用题辅导 Agent

**题目**：设计一个能帮学生解高考数学应用题、给详细推理过程的 Agent。

**答案**：

**特殊需求**：
- 准确率要求极高（误导学生危害大）
- 推理过程要清晰、教学性强
- 题目可能涉及多种类型（代数、几何、概率、微积分）
- 要能识别学生的错误并解释

**架构**：

```
[学生提交题目（文字 + 可能图片）]
   ↓
[OCR / VLM]（识别公式 + 图）
   ↓
[Pre-processor]：题型分类（代数 / 几何...）
   ↓
[Solver: Reasoning Model]（核心）
   ├─ 用 o1/R1/Claude Thinking
   ├─ 长思考探索解法
   └─ 输出推理过程 + 最终答案
   ↓
[Verifier]
   ├─ 代数题：SymPy 验证
   ├─ 数值题：计算器验证
   └─ 几何题：人工 spot check
   ↓
[Teacher LLM]（普通 LLM）
   ├─ 把 reasoning 重写成教学语言
   ├─ 加入"为什么这一步"的解释
   └─ 适配学生水平
   ↓
[输出给学生]
```

**关键决策**：

**1. 用 reasoning model（核心）**
- 数学题本质需要长推理
- 复杂题（高考压轴）普通 LLM 经常错
- 用 Claude Thinking（可见 + 可控 budget + 工具调用）

**2. Verifier 层（必须）**
- Reasoning model 也会"思考很对但答错"
- 必须有独立验证
- SymPy / NumPy / 几何 solver

**3. 双 LLM 分工**
- Reasoning model 解题（求答）
- 普通 LLM 改写（教学）
- 教学时不要直接展示 raw thinking（学生看不懂）

**4. 学生水平适配**
- 历史交互判断水平
- 推理深度自适应（高中生 vs 初中生）

**5. 错误诊断**
- 学生提交错误解法 → reasoning model 分析
- "你在第 3 步用了错误的公式..."
- 这是教育产品差异点

**评估**：
- 答案准确率（必须 >99%，否则下架）
- 推理过程合理性（人工抽检）
- 学生满意度
- 学生提高度（A/B 对比有 vs 没 Agent）

**成本**：
- Reasoning model 一次 thinking $0.1~0.5
- 普通题快路径（不思考）便宜版
- 难题深思考版

---

### 场景 2：代码 Agent 中混合 Reasoning Model

**题目**：现有 Code Agent（Claude Code 风格）单 Agent + Sonnet。需要在复杂 bug fix 任务上提升表现。Reasoning Model 怎么集成？

**答案**：

**问题分析**：
- 简单任务（修小 bug、加注释）：Sonnet 已经够好
- 复杂任务（多文件重构、性能 debug、tricky 并发 bug）：需要更深推理

**集成方案**：

**方案 A：Reasoning Planner + Standard Executor（推荐）**

```
[用户任务]
   ↓
[Task Classifier]（小模型 / 规则）
   ├─ 简单任务 → 直接 Sonnet Agent
   └─ 复杂任务 → ↓
[Planning Phase: o1/R1/Claude Thinking]
   ├─ 读关键文件
   ├─ 深度思考方案
   └─ 输出 detailed plan
   ↓
[Execution Phase: Sonnet Agent]
   ├─ 按 plan 执行
   ├─ 工具调用（read/edit/test）
   └─ ReAct 风格快速迭代
   ↓
[Verification Phase: o1/R1]
   ├─ Review changes
   ├─ Identify risks
   └─ Suggest tests
```

**优点**：
- 复杂任务 planner 一次深度思考奠基调
- Executor 多步快速执行
- 终审捕获遗漏

**方案 B：仅在卡住时升级**

```
[Sonnet Agent 主循环]
   ↓
（如果 N 步内未完成 / 反复失败）
   ↓
[升级到 Reasoning Model]
   ├─ 把当前 context 喂进去
   └─ 让 reasoning model 跳出
   ↓
[结果反馈给 Sonnet 继续]
```

**优点**：成本最优，只在需要时升级
**缺点**：升级时机判断难

**方案 C：Reasoning Model 做 Code Review**

```
Sonnet 完成 change → Reasoning Model review → 标记问题
```

**实战取舍**：

**1. 何时用 Reasoning**
- 调试 race condition / 内存泄漏
- 跨多文件的逻辑追踪
- 性能优化（需要全局思考）
- 大型重构

**2. 何时**不**用**
- 简单 CRUD
- 格式化 / 注释
- 单元测试编写
- API 文档生成

**3. 工程注意**
- Reasoning model 的 function calling 不如 Sonnet 流畅 → 限制其工具集
- Thinking 不持久化到下轮（context 太大）
- Cost monitor：reasoning 调用 $1+ 一次，要警惕滥用

**4. 评估**
- SWE-Bench 类标准 benchmark
- 内部测试集分难度档
- A/B 对比：纯 Sonnet vs Hybrid
- 看 cost-quality 帕累托

**用户层产品决策**：
- 让用户选 "fast" / "deep thinking" 两挡（类似 Cursor 的 mode）
- 默认 fast，复杂任务自动 / 手动升级 deep

---

## 五、自测清单

- [ ] Reasoning Model 与传统 CoT 的 5 点本质区别
- [ ] RLVR 与 RLHF 的差异
- [ ] GRPO 算法核心思想
- [ ] DeepSeek R1 的 4 阶段训练 pipeline
- [ ] R1-Zero 的意义
- [ ] Inference Scaling Laws
- [ ] Test-time compute 的 5 种方法
- [ ] PRM vs ORM
- [ ] Hidden vs Visible thinking 的取舍
- [ ] Reasoning Model 该用 / 不该用的判据
- [ ] Reasoning Model 的 10 个失败模式
- [ ] 在 Agent 系统中的 3 个典型角色（Planner / Critic / Executor）

---

## 六、关键术语 Cheat Sheet

| 术语 | 含义 |
|------|------|
| Reasoning Model | 内置长 CoT 的 LLM |
| RLVR | RL with Verifiable Rewards |
| GRPO | DeepSeek 提出的 RL 算法，去掉 critic |
| PRM | Process Reward Model — 评估每步推理 |
| ORM | Outcome Reward Model — 只评估最终结果 |
| Test-time Compute | 推理时算力消耗 |
| Inference Scaling Laws | 推理算力 → 能力的规律 |
| Extended Thinking | Anthropic 的 reasoning 模式 |
| reasoning_effort | OpenAI 的思考深度控制 |
| Thinking Budget | Anthropic 精确控制思考 token |
| Best-of-N | 采样 N 个选最优 |
| Self-Consistency | CoT 多次采样投票 |
| Distillation | 蒸馏（用 reasoning model 教小模型） |
| Aha Moment | R1 论文术语，模型涌现反思能力的现象 |
| Hidden Reasoning | 思考过程对用户不可见（OpenAI o 系列） |
| Visible Reasoning | 思考过程可见（Claude / DeepSeek） |

---

## 七、延伸阅读

- OpenAI — *Learning to Reason with LLMs*（o1 介绍）
- DeepSeek-AI — *DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning*
- Anthropic — *Claude's extended thinking* 文档
- *Let's Verify Step by Step*（PRM 经典论文）
- *Scaling Inference-Time Compute*（OpenAI / 其他多篇）
- Lilian Weng — *Reasoning models* 博客（强烈推荐）
- Sebastian Raschka — *Understanding Reasoning LLMs*
- Apple — *GSM-Symbolic*（推理能力的怀疑性研究，重要 counterpoint）

---

## 八、面试金句

- "Reasoning model 把 test-time compute 内化到模型本身"
- "RLVR 跳过了 reward model 这一可被 hack 的环节"
- "DeepSeek R1-Zero 证明了纯 RL 也能涌现长 CoT"
- "Reasoning 不是万灵药，简单任务用它纯属浪费"
- "Agent 中我会把 reasoning model 放在 planner 和 critic 阶段"
- "GSM-Symbolic 提醒我们：reasoning model 也可能是 pattern matching 的放大版"
