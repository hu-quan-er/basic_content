# Agent 工程师面试 · 14 天复习计划

> 面向 Agent 工程师面试的系统复习，覆盖：基础概念 + 主流框架/工具/SDK + 场景设计。
> 每天一个主题，每个主题包含「核心概念 → 主流实现 → 高频面试题（含答案）→ 场景设计题（含答案）」。

---

## 知识体系总览

```
┌─ 基础层：LLM 原理 + Prompt 工程
├─ 范式层：ReAct / Plan-Execute / Reflexion / Multi-Agent
├─ 能力层：工具使用 / 记忆 / 检索 / 上下文工程
├─ 框架层：LangChain / LangGraph / AutoGen / CrewAI / MCP
└─ 工程层：评估 / 可观测 / 安全 / 性能 / 成本 / 可靠执行
```

---

## 14 天学习计划

| Day | 主题 | 重点 | 文件 |
|-----|------|------|------|
| Day 1 | LLM 基础与 Agent 本质 | Transformer、采样、训练阶段、Agent 定义、Workflow vs Agent | [Day01-LLM基础与Agent本质.md](./Day01-LLM基础与Agent本质.md) |
| Day 2 | Prompt 工程与推理范式 | CoT、ReAct、Plan-Execute、Reflexion、ToT、结构化输出 | [Day02-Prompt工程与推理范式.md](./Day02-Prompt工程与推理范式.md) |
| Day 3 | 工具使用与 MCP | Function Calling、工具 Schema、Tool RAG、MCP 协议 | [Day03-工具使用与MCP.md](./Day03-工具使用与MCP.md) |
| Day 4 | 记忆与上下文工程 | 短/长期记忆、MemGPT、Context Engineering、Lost in Middle | [Day04-记忆与上下文工程.md](./Day04-记忆与上下文工程.md) |
| Day 5 | RAG 全景 | 朴素/进阶/Agentic RAG、Hybrid 检索、Rerank、GraphRAG | [Day05-RAG全景.md](./Day05-RAG全景.md) |
| Day 6 | 多 Agent 协作 | 拓扑、角色范式、LangGraph、AutoGen、CrewAI | [Day06-多Agent协作.md](./Day06-多Agent协作.md) |
| Day 7 | 评估与可观测性 | 三层评估、LLM-as-Judge、Ragas、LangSmith、数据飞轮 | [Day07-评估与可观测性.md](./Day07-评估与可观测性.md) |
| Day 8 | 工程化：性能、成本、可靠性 | 延迟、Prompt Caching、模型路由、限流、降级 | [Day08-工程化性能成本可靠性.md](./Day08-工程化性能成本可靠性.md) |
| Day 9 | 安全与对齐 | Prompt Injection、Jailbreak、HITL、权限隔离、Guardrails | [Day09-安全与对齐.md](./Day09-安全与对齐.md) |
| Day 10 | 综合系统设计 | Code Agent / Deep Research / GUI Agent / 企业知识问答 | [Day10-综合系统设计.md](./Day10-综合系统设计.md) |
| Day 11 | Voice / Realtime Agent（进阶） | Pipeline vs E2E、延迟治理、Barge-in、电话客服、英语口语 | [Day11-Voice与Realtime Agent.md](./Day11-Voice与Realtime%20Agent.md) |
| Day 12 | Reasoning Models 专题（进阶） | o1/R1/Claude Thinking、RLVR、GRPO、test-time compute、Agent 中的角色 | [Day12-Reasoning Models专题.md](./Day12-Reasoning%20Models专题.md) |
| Day 13 | A2A 与 Agent 互操作协议（进阶） | A2A/MCP/ACP、Agent Card、Task 生命周期、跨组织协作 | [Day13-A2A与Agent互操作协议.md](./Day13-A2A与Agent互操作协议.md) |
| Day 14 | Agent 工程细节与可靠执行（进阶） | 结构化计划、Executor 状态机、子 Agent 完成保障、异常兜底、幂等恢复 | [Day14-Agent工程细节与可靠执行.md](./Day14-Agent工程细节与可靠执行.md) |

---

## 每天的学习节奏

| 时段 | 时长 | 内容 |
|------|------|------|
| 概念精读 | 60 min | 看当天文档"核心概念" + "主流实现要点" |
| 动手实验 | 60 min | 用框架写一个最小 demo 验证概念 |
| 高频题口述 | 30 min | 看题目自己讲，再对答案 |
| 场景题写作 | 30 min | 写出完整方案再对答案 |

---

## 面试答题方法论

### 概念题答题框架（30s ~ 2min）
1. **一句话定义** — 用最朴素的话讲清楚
2. **为什么需要** — 解决了什么问题
3. **关键机制** — 怎么实现的
4. **优劣与适用场景** — 何时用何时不用
5. **典型实现** — 一个具体例子（框架/产品）

### 系统设计题答题框架（10~20min）
1. **澄清需求** — 功能 / 非功能（延迟、成本、准确率、合规）
2. **数据与流程** — 数据来源、处理链路
3. **核心架构** — 单/多 Agent、工具设计、记忆设计
4. **关键技术决策** — 模型选型、检索策略、评估方法
5. **工程化** — 监控、A/B、灰度、回滚
6. **风险与对策** — 失败模式枚举 + 兜底

### 反问环节准备
- 团队规模 / Agent 在产品中的定位
- 当前最大的技术挑战
- 评估体系 / 数据飞轮成熟度

---

## 高频面试题速查

| 主题 | 必背题 |
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

---

## 进度跟踪

- [ ] Day 1 — LLM 基础与 Agent 本质
- [ ] Day 2 — Prompt 工程与推理范式
- [ ] Day 3 — 工具使用与 MCP
- [ ] Day 4 — 记忆与上下文工程
- [ ] Day 5 — RAG 全景
- [ ] Day 6 — 多 Agent 协作
- [ ] Day 7 — 评估与可观测性
- [ ] Day 8 — 工程化：性能、成本、可靠性
- [ ] Day 9 — 安全与对齐
- [ ] Day 10 — 综合系统设计
- [ ] Day 11 — Voice / Realtime Agent（进阶专题）
- [ ] Day 12 — Reasoning Models（进阶专题）
- [ ] Day 13 — A2A 与 Agent 互操作协议（进阶专题）
- [ ] Day 14 — Agent 工程细节与可靠执行（进阶专题）

---

## 如何继续生成 / 回顾

- 单天精读：直接打开对应 `DayXX-*.md`
- 想继续生成 / 扩充某一天：让 AI 基于该 md 文件继续展开（例如"把 Day3 的工具部分再加 5 道真题"）
- 想做诊断测试：让 AI 从所有 Day 抽题组卷
