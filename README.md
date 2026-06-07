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
└─ 工程层：评估 / 可观测 / 安全 / 性能 / 成本 / 推理加速 / Agent Runtime / 可靠执行 / AI Coding Harness
```

---

## 主题清单

| # | 主题 | 重点 | 文件 |
|---|------|------|------|
| 1 | LLM 基础与 Agent 本质 | Token、采样、训练阶段、Function Calling、Agent 定义、Workflow vs Agent | [01-LLM基础与Agent本质.md](./01-LLM基础与Agent本质.md) |
| 1.1 | └ Transformer 架构与模型原理（子文档） | Transformer block、Q/K/V、encoder/decoder 分叉、decoder-only、Scaling Laws、MoE、SSM/Mamba、架构演进 | [01.1-Transformer架构与模型原理.md](./01.1-Transformer架构与模型原理.md) |
| 2 | Prompt 工程与推理范式 | CoT、ReAct、Plan-Execute、Reflexion、ToT、结构化输出 | [02-Prompt工程与推理范式.md](./02-Prompt工程与推理范式.md) |
| 3 | 工具调用 | Function Calling、工具 Schema、并行与依赖、FC vs 代码 workflow、Tool RAG、沙箱 | [03-工具调用.md](./03-工具调用.md) |
| 3.1 | └ MCP 协议详解 | 动机、Host/Client/Server、三原语、传输、vs function calling、安全 | [03.1-MCP.md](./03.1-MCP.md) |
| 4 | 记忆与上下文工程 | 记忆 vs 上下文、State/Memory/Artifact 区分、阅读路径、核心术语 | [04-记忆与上下文工程.md](./04-记忆与上下文工程.md) |
| 4.1 | └ 生产级 Agent 记忆工程（子文档） | 记忆提取、验证、存储、召回、显式注入 vs 按需检索、更新/遗忘、隐私治理、评估指标 | [04.1-生产级Agent记忆工程.md](./04.1-生产级Agent记忆工程.md) |
| 4.2 | └ Agent 上下文工程（子文档） | Prompt 拼接、上下文分层、token 预算、压缩、引用化、Lost in the Middle、防污染、Context Manifest | [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md) |
| 5 | RAG 全景 | 朴素/进阶/Agentic RAG、Hybrid 检索、Rerank、GraphRAG | [05-RAG全景.md](./05-RAG全景.md) |
| 6 | 多 Agent 协作 | 拓扑、角色范式、LangGraph、AutoGen、CrewAI | [06-多Agent协作.md](./06-多Agent协作.md) |
| 7 | 评估与可观测性 | 三层评估、LLM-as-Judge、Ragas、LangSmith、数据飞轮 | [07-评估与可观测性.md](./07-评估与可观测性.md) |
| 8 | 工程化：性能、成本、可靠性 | 延迟、Prompt Caching、模型路由、限流、降级 | [08-工程化性能成本可靠性.md](./08-工程化性能成本可靠性.md) |
| 8.1 | └ 生产级 Agent 应用工程（子文档） | 业务边界、架构分层、状态机、工具网关、安全治理、HITL、评估、可观测、发布运维、成熟度模型 | [08.1-生产级Agent应用工程.md](./08.1-生产级Agent应用工程.md) |
| 9 | 安全与对齐 | Prompt Injection、Jailbreak、HITL、权限隔离、Guardrails | [09-安全与对齐.md](./09-安全与对齐.md) |
| 10 | 综合系统设计 | Code Agent / Deep Research / GUI Agent / 企业知识问答 | [10-综合系统设计.md](./10-综合系统设计.md) |
| 11 | Voice / Realtime Agent（进阶） | Pipeline vs E2E、延迟治理、Barge-in、电话客服、英语口语 | [11-Voice与Realtime Agent.md](./11-Voice与Realtime%20Agent.md) |
| 12 | Reasoning Models 专题（进阶） | o1/R1/Claude Thinking、RLVR、GRPO、test-time compute、Agent 中的角色 | [12-Reasoning Models专题.md](./12-Reasoning%20Models专题.md) |
| 13 | A2A 与 Agent 互操作协议（进阶） | A2A/MCP/ACP、Agent Card、Task 生命周期、跨组织协作 | [13-A2A与Agent互操作协议.md](./13-A2A与Agent互操作协议.md) |
| 13.1 | └ 多 Agent 状态管理与上下文同步（专题入口） | 阅读路径、核心概念、A2A 边界、框架选型、术语索引 | [13.1-多Agent状态管理与上下文同步.md](./13.1-多Agent状态管理与上下文同步.md) |
| 13.1.1 | └ 状态模型与读写契约 | State Catalog、Context View、State Patch、字段级权限、一致性、Reducer、存储边界 | [13.1.1-多Agent状态模型与读写契约.md](./13.1.1-多Agent状态模型与读写契约.md) |
| 13.1.2 | └ A2A 上下文同步与 Handoff 设计 | A2A Context Envelope、Task 映射、多轮同步、Handoff Contract、跨组织边界 | [13.1.2-A2A上下文同步与Handoff设计.md](./13.1.2-A2A上下文同步与Handoff设计.md) |
| 13.1.3 | └ 主流多 Agent 框架状态管理实现 | A2A、LangGraph、AutoGen、CrewAI、OpenAI Agents SDK、Google ADK、LlamaIndex、Semantic Kernel、MCP | [13.1.3-主流多Agent框架状态管理实现.md](./13.1.3-主流多Agent框架状态管理实现.md) |
| 13.1.4 | └ 多 Agent 生产场景与治理清单 | 企业入职、Deep Research、代码 Agent、客服、供应商尽调、可观测、安全、反模式 | [13.1.4-多Agent生产场景与治理清单.md](./13.1.4-多Agent生产场景与治理清单.md) |
| 13.1.5 | └ 多 Agent 状态同步端到端代码示例 | 可运行 Python 示例、StateStore、Context View、Patch 校验、Artifact、Event Log、A2A input-required、远程结果导入 | [13.1.5-多Agent状态同步端到端代码示例.md](./13.1.5-多Agent状态同步端到端代码示例.md) |
| 14 | Agent 工程细节与可靠执行（进阶） | 结构化计划、Executor 状态机、子 Agent 完成保障、异常兜底、幂等恢复 | [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md) |
| 15 | AI Coding Harness 最佳实践（进阶） | AGENTS.md/CLAUDE.md、任务包、验证脚本、进度文件、权限与 hooks | [15-AI Coding Harness最佳实践.md](./15-AI%20Coding%20Harness最佳实践.md) |
| 16 | Agent Loop 专题（进阶） | 单次迭代解剖、终止条件、上下文压缩、范式对 loop 的改造、死循环检测、框架 loop 对比（含 Go/eino 实现） | [16-Agent Loop专题.md](./16-Agent%20Loop专题.md) |
| 16.1 | └ Agent Loop 停止条件设计（子文档） | 五个停止维度、完成信号陷阱、死循环检测、主流产品停止机制对照、收尾策略（Python + Go/eino） | [16.1-Agent Loop停止条件设计.md](./16.1-Agent%20Loop停止条件设计.md) |
| 16.2 | └ Agent Loop 上下文管理（子文档） | 五种控制策略详解、组合 pipeline、LangChain/LangGraph/LlamaIndex/Claude/OpenAI/MemGPT/Mem0 对比分析 | [16.2-Agent Loop上下文管理.md](./16.2-Agent%20Loop上下文管理.md) |
| 16.3 | └ Agent Loop 人在回路（子文档） | HITL 六种模式、自治光谱、触发策略、暂停-持久化-恢复、LangGraph/Claude/AutoGen/CrewAI/HumanLayer/Temporal 对比 | [16.3-Agent Loop人在回路.md](./16.3-Agent%20Loop人在回路.md) |
| 17 | 上下文窗口的模型原理（进阶） | 自注意力 O(n²)、KV Cache、位置编码与外推、Lost in the Middle、长上下文架构方向 | [17-上下文窗口的模型原理.md](./17-上下文窗口的模型原理.md) |
| 18 | 模型固有局限与工程兜底（进阶） | 19 类原理性局限的全景表、七种通用兜底模式、模型缺陷与系统设计的对应 | [18-模型固有局限与工程兜底.md](./18-模型固有局限与工程兜底.md) |
| 19 | 推理加速底层系统（进阶） | prefill/decode、Roofline、KV Cache、PagedAttention、RadixAttention、FlashAttention、continuous batching、speculative decoding、量化、P/D disaggregation | [19-推理加速底层系统.md](./19-推理加速底层系统.md) |
| 19.1 | └ Agent 推理加速落地（子文档） | Agent 延迟拆解、少调用少 token、工具并行、模型分层、上下文压缩、多层缓存、结构化输出、可观测优化闭环 | [19.1-Agent推理加速落地.md](./19.1-Agent推理加速落地.md) |
| 20 | Agent Runtime 专题（进阶） | Run 生命周期、Agent Loop、调度器、状态/检查点、工具网关、HITL、handoff、可观测、durable execution | [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md) |
| 20.1 | └ Agent Runtime 完整实现（子文档） | 可运行 Python runtime、RunState、ToolGateway、Policy/HITL、Checkpoint、Resume、Event Log | [20.1-Agent Runtime完整实现.md](./20.1-Agent%20Runtime完整实现.md) |
| 20.2 | └ 主流 Agent Runtime 实现对比（子文档） | LangGraph、OpenAI Agents SDK、Google ADK、AutoGen、CrewAI、LlamaIndex、Semantic Kernel、Letta、Temporal | [20.2-主流Agent Runtime实现对比.md](./20.2-主流Agent%20Runtime实现对比.md) |

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
| 基础 | Token/采样/训练阶段；Agent 定义；Workflow vs Agent；Function Calling 底层 |
| Transformer 架构 | Attention/FFN/residual；encoder-only vs decoder-only；RoPE/ALiBi；MoE；SSM/Mamba；Scaling Laws |
| 推理 | ReAct vs Plan-Execute；CoT 涌现；Reflexion |
| 工具调用 | 工具描述设计；并行与依赖；FC vs 代码 workflow；多工具治理 |
| MCP | 碎片化→标准化；三原语；vs function calling；工具投毒安全 |
| 记忆 | Core Memory；Session Memory；Archival Memory；提取/验证/存储/召回/注入；显式注入 vs 按需检索；记忆治理 |
| 上下文工程 | Prompt 拼接；上下文分层；token 预算；压缩；artifact 引用化；Context Manifest；Lost in the Middle；防污染 |
| RAG | 召回错排查；Hybrid 权重；Rerank；Agentic RAG |
| 多 Agent | 拓扑选型；LangGraph 核心；单 vs 多 |
| 多 Agent 状态 | State Catalog；Context View；State Patch；Artifact-first；Handoff Contract；A2A Context Envelope；Reducer；Conflict Policy；Framework State |
| 多 Agent 代码示例 | `examples/multi_agent_state_demo.py`；StateStore；FieldRule；PatchOperation；A2A input-required；Remote Result Import；Event Log |
| 评估 | LLM-as-Judge 偏差；Trace 评估；数据飞轮 |
| 工程 | 缓存策略；延迟优化；成本治理 |
| 生产级 Agent | 任务合同；自治等级；Orchestrator；Run State；Tool Gateway；Guardrails；HITL；Eval；Trace；灰度回滚 |
| 安全 | Prompt Injection；HITL；权限隔离 |
| 可靠执行 | 结构化 Plan；子 Agent 完成保障；重试幂等；Checkpoint |
| AI Coding | Harness；任务包；验证闭环；长任务恢复 |
| Agent Loop | 一轮六阶段；终止双闸；死循环检测；上下文压缩；ReAct vs Plan-Execute；LangGraph vs AgentExecutor |
| 上下文窗口原理 | 自注意力 O(n²)；KV Cache 显存；RoPE/ALiBi 外推；Lost in the Middle；FlashAttention/GQA/SSM |
| 局限与兜底 | 幻觉/时效/数学→外接真相源；格式→约束生成；注入→信任边界；七类局限对七种兜底模式 |
| 推理加速底层 | prefill vs decode；TTFT/TPOT；Roofline；KV Cache；PagedAttention vs FlashAttention；RadixAttention；continuous batching；speculative decoding；量化；P/D 分离 |
| Agent 推理加速 | 串行 LLM hop；prefill tax；工具并行；模型路由；reasoning budget；prefix/tool/semantic cache；结构化输出；trace 优化闭环 |
| Agent Runtime | Run；Step；Scheduler；RunState；Context Builder；Tool Gateway；Policy/HITL；Checkpoint；Resume；Handoff；Event Log；Trace；Durable Execution |

---

## 进度跟踪

- [ ] LLM 基础与 Agent 本质
- [ ] Transformer 架构与模型原理
- [ ] Prompt 工程与推理范式
- [ ] 工具调用
- [ ] MCP 协议详解
- [ ] 记忆与上下文工程
- [ ] 生产级 Agent 记忆工程
- [ ] Agent 上下文工程
- [ ] RAG 全景
- [ ] 多 Agent 协作
- [ ] 评估与可观测性
- [ ] 工程化：性能、成本、可靠性
- [ ] 生产级 Agent 应用工程
- [ ] 安全与对齐
- [ ] 综合系统设计
- [ ] Voice / Realtime Agent（进阶专题）
- [ ] Reasoning Models（进阶专题）
- [ ] A2A 与 Agent 互操作协议（进阶专题）
- [ ] 多 Agent 状态管理与上下文同步（进阶专题）
- [ ] 多 Agent 状态模型与读写契约
- [ ] A2A 上下文同步与 Handoff 设计
- [ ] 主流多 Agent 框架状态管理实现
- [ ] 多 Agent 生产场景与治理清单
- [ ] 多 Agent 状态同步端到端代码示例
- [ ] Agent 工程细节与可靠执行（进阶专题）
- [ ] AI Coding Harness 最佳实践（进阶专题）
- [ ] Agent Loop 专题（进阶专题）
- [ ] 上下文窗口的模型原理（进阶专题）
- [ ] 模型固有局限与工程兜底（进阶专题）
- [ ] 推理加速底层系统（进阶专题）
- [ ] Agent 推理加速落地（进阶专题）
- [ ] Agent Runtime 专题（进阶专题）
- [ ] Agent Runtime 完整实现（进阶专题）
- [ ] 主流 Agent Runtime 实现对比（进阶专题）

---

## 如何继续生成 / 回顾

- 单篇精读：直接打开对应主题的 `.md` 文件
- 想继续生成 / 扩充某一篇：让 AI 基于该 md 文件继续展开（例如"把工具部分再加 5 个知识点"）
- 想做综合自测：让 AI 从所有主题抽取问题组成自测题集
