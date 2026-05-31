# Agent 核心知识 · 学习计划

> 面向 Agent 方向的系统学习，覆盖：基础概念 + 主流框架/工具/SDK + 场景设计。
> 每个主题包含「核心概念 → 主流实现 → 关键问题（含解答）→ 场景设计（含解答）」。

---

## 知识体系总览

```
┌─ 基础层：LLM 原理 + Prompt 工程
├─ 范式层：ReAct / Plan-Execute / Reflexion / Multi-Agent
├─ 能力层：工具使用 / 记忆 / 检索 / 上下文工程
├─ 框架层：LangChain / LangGraph / AutoGen / CrewAI / MCP
└─ 工程层：评估 / 可观测 / 安全 / 性能 / 成本 / 可靠执行 / AI Coding Harness
```

---

## 主题清单

| # | 主题 | 重点 | 文件 |
|---|------|------|------|
| 1 | LLM 基础与 Agent 本质 | Transformer、采样、训练阶段、Agent 定义、Workflow vs Agent | [01-LLM基础与Agent本质.md](./01-LLM基础与Agent本质.md) |
| 2 | Prompt 工程与推理范式 | CoT、ReAct、Plan-Execute、Reflexion、ToT、结构化输出 | [02-Prompt工程与推理范式.md](./02-Prompt工程与推理范式.md) |
| 3 | 工具使用与 MCP | Function Calling、工具 Schema、Tool RAG、MCP 协议 | [03-工具使用与MCP.md](./03-工具使用与MCP.md) |
| 4 | 记忆与上下文工程 | 短/长期记忆、MemGPT、Context Engineering、Lost in Middle | [04-记忆与上下文工程.md](./04-记忆与上下文工程.md) |
| 5 | RAG 全景 | 朴素/进阶/Agentic RAG、Hybrid 检索、Rerank、GraphRAG | [05-RAG全景.md](./05-RAG全景.md) |
| 6 | 多 Agent 协作 | 拓扑、角色范式、LangGraph、AutoGen、CrewAI | [06-多Agent协作.md](./06-多Agent协作.md) |
| 7 | 评估与可观测性 | 三层评估、LLM-as-Judge、Ragas、LangSmith、数据飞轮 | [07-评估与可观测性.md](./07-评估与可观测性.md) |
| 8 | 工程化：性能、成本、可靠性 | 延迟、Prompt Caching、模型路由、限流、降级 | [08-工程化性能成本可靠性.md](./08-工程化性能成本可靠性.md) |
| 9 | 安全与对齐 | Prompt Injection、Jailbreak、HITL、权限隔离、Guardrails | [09-安全与对齐.md](./09-安全与对齐.md) |
| 10 | 综合系统设计 | Code Agent / Deep Research / GUI Agent / 企业知识问答 | [10-综合系统设计.md](./10-综合系统设计.md) |
| 11 | Voice / Realtime Agent（进阶） | Pipeline vs E2E、延迟治理、Barge-in、电话客服、英语口语 | [11-Voice与Realtime Agent.md](./11-Voice与Realtime%20Agent.md) |
| 12 | Reasoning Models 专题（进阶） | o1/R1/Claude Thinking、RLVR、GRPO、test-time compute、Agent 中的角色 | [12-Reasoning Models专题.md](./12-Reasoning%20Models专题.md) |
| 13 | A2A 与 Agent 互操作协议（进阶） | A2A/MCP/ACP、Agent Card、Task 生命周期、跨组织协作 | [13-A2A与Agent互操作协议.md](./13-A2A与Agent互操作协议.md) |
| 14 | Agent 工程细节与可靠执行（进阶） | 结构化计划、Executor 状态机、子 Agent 完成保障、异常兜底、幂等恢复 | [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md) |
| 15 | AI Coding Harness 最佳实践（进阶） | AGENTS.md/CLAUDE.md、任务包、验证脚本、进度文件、权限与 hooks | [15-AI Coding Harness最佳实践.md](./15-AI%20Coding%20Harness最佳实践.md) |
| 16 | Agent Loop 专题（进阶） | 单次迭代解剖、终止条件、上下文压缩、范式对 loop 的改造、死循环检测、框架 loop 对比（含 Go/eino 实现） | [16-Agent Loop专题.md](./16-Agent%20Loop专题.md) |
| 16.1 | └ Agent Loop 停止条件设计（子文档） | 五个停止维度、完成信号陷阱、死循环检测、主流产品停止机制对照、收尾策略（Python + Go/eino） | [16.1-Agent Loop停止条件设计.md](./16.1-Agent%20Loop停止条件设计.md) |
| 17 | 上下文窗口的模型原理（进阶） | 自注意力 O(n²)、KV Cache、位置编码与外推、Lost in the Middle、长上下文架构方向 | [17-上下文窗口的模型原理.md](./17-上下文窗口的模型原理.md) |
| 18 | 模型固有局限与工程兜底（进阶） | 19 类原理性局限的全景表、七种通用兜底模式、模型缺陷与系统设计的对应 | [18-模型固有局限与工程兜底.md](./18-模型固有局限与工程兜底.md) |

---

## 学习节奏建议

| 时段 | 时长 | 内容 |
|------|------|------|
| 概念精读 | 60 min | 看当天文档"核心概念" + "主流实现要点" |
| 动手实验 | 60 min | 用框架写一个最小 demo 验证概念 |
| 问题自测 | 30 min | 看思考题自己讲一遍，再对照解答 |
| 场景设计 | 30 min | 写出完整方案再对照解答 |

---

## 知识梳理方法论

### 概念梳理框架
1. **一句话定义** — 用最朴素的话讲清楚
2. **为什么需要** — 解决了什么问题
3. **关键机制** — 怎么实现的
4. **优劣与适用场景** — 何时用何时不用
5. **典型实现** — 一个具体例子（框架/产品）

### 系统设计思考框架
1. **澄清需求** — 功能 / 非功能（延迟、成本、准确率、合规）
2. **数据与流程** — 数据来源、处理链路
3. **核心架构** — 单/多 Agent、工具设计、记忆设计
4. **关键技术决策** — 模型选型、检索策略、评估方法
5. **工程化** — 监控、A/B、灰度、回滚
6. **风险与对策** — 失败模式枚举 + 兜底

---

## 核心知识点速查

| 主题 | 关键点 |
|------|--------|
| 基础 | Agent 定义；Workflow vs Agent；Function Calling 底层 |
| 推理 | ReAct vs Plan-Execute；CoT 涌现；Reflexion |
| 工具 | 工具描述设计；多工具治理；MCP 价值 |
| 记忆 | 短长期记忆架构；上下文爆炸；MemGPT |
| RAG | 召回错排查；Hybrid 权重；Rerank；Agentic RAG |
| 多 Agent | 拓扑选型；LangGraph 核心；单 vs 多 |
| 评估 | LLM-as-Judge 偏差；Trace 评估；数据飞轮 |
| 工程 | 缓存策略；延迟优化；成本治理 |
| 安全 | Prompt Injection；HITL；权限隔离 |
| 可靠执行 | 结构化 Plan；子 Agent 完成保障；重试幂等；Checkpoint |
| AI Coding | Harness；任务包；验证闭环；长任务恢复 |
| Agent Loop | 一轮六阶段；终止双闸；死循环检测；上下文压缩；ReAct vs Plan-Execute；LangGraph vs AgentExecutor |
| 上下文窗口原理 | 自注意力 O(n²)；KV Cache 显存；RoPE/ALiBi 外推；Lost in the Middle；FlashAttention/GQA/SSM |
| 局限与兜底 | 幻觉/时效/数学→外接真相源；格式→约束生成；注入→信任边界；七类局限对七种兜底模式 |

---

## 进度跟踪

- [ ] LLM 基础与 Agent 本质
- [ ] Prompt 工程与推理范式
- [ ] 工具使用与 MCP
- [ ] 记忆与上下文工程
- [ ] RAG 全景
- [ ] 多 Agent 协作
- [ ] 评估与可观测性
- [ ] 工程化：性能、成本、可靠性
- [ ] 安全与对齐
- [ ] 综合系统设计
- [ ] Voice / Realtime Agent（进阶专题）
- [ ] Reasoning Models（进阶专题）
- [ ] A2A 与 Agent 互操作协议（进阶专题）
- [ ] Agent 工程细节与可靠执行（进阶专题）
- [ ] AI Coding Harness 最佳实践（进阶专题）
- [ ] Agent Loop 专题（进阶专题）
- [ ] 上下文窗口的模型原理（进阶专题）
- [ ] 模型固有局限与工程兜底（进阶专题）

---

## 如何继续生成 / 回顾

- 单篇精读：直接打开对应主题的 `.md` 文件
- 想继续生成 / 扩充某一篇：让 AI 基于该 md 文件继续展开（例如"把工具部分再加 5 个知识点"）
- 想做综合自测：让 AI 从所有主题抽取问题组成自测题集
