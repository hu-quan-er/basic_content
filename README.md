# Agent 核心知识 · 学习计划

> 面向 Agent 方向的系统学习，覆盖：基础概念 + 主流框架/工具/SDK + 场景设计。
> 每个主题包含「核心概念 → 主流实现 → 关键问题（含解答）→ 场景设计（含解答）」。

---

## 知识体系总览

```
┌─ 基础层：LLM 原理 + Prompt 工程
├─ 范式层：ReAct / Plan-Execute / Reflexion / Multi-Agent
├─ 能力层：工具使用 / Tool Gateway / 记忆 / 检索 / 上下文工程 / 结构化输出
├─ 框架层：LangChain / LangGraph / AutoGen / CrewAI / MCP
└─ 工程层：评估 / Eval Harness / 可观测 / 安全 / 性能 / 成本 / 推理加速 / Agent Runtime / Browser Agent / 可靠执行 / AI Coding Harness
```

---

## 主题清单

| # | 主题 | 重点 | 文件 |
|---|------|------|------|
| 0 | 内容职责与迁移清单 | 全局文件职责边界、重复内容收敛规则、主题簇主责文件、后续写作规则 | [00-内容职责与迁移清单.md](./00-内容职责与迁移清单.md) |
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
| 13.1 | └ 多 Agent 状态管理专题 | 状态模型、A2A handoff、框架实现、生产场景、端到端示例 | [13.1-多Agent状态管理专题](./13.1-多Agent状态管理专题.md) |
| 14 | Agent 工程细节与可靠执行（进阶） | 结构化计划、Executor 状态机、子 Agent 完成保障、异常兜底、幂等恢复 | [14-Agent工程细节与可靠执行.md](./14-Agent工程细节与可靠执行.md) |
| 15 | AI Coding Harness 最佳实践（进阶） | AGENTS.md/CLAUDE.md、任务包、验证脚本、进度文件、权限与 hooks | [15-AI Coding Harness最佳实践.md](./15-AI%20Coding%20Harness最佳实践.md) |
| 16 | Agent Loop 专题（进阶） | 单次迭代解剖、停止条件、上下文管理、人在回路、框架 loop 对比 | [16-Agent Loop专题](./16-Agent%20Loop专题.md) |
| 17 | 上下文窗口的模型原理（进阶） | 自注意力 O(n²)、KV Cache、位置编码与外推、Lost in the Middle、长上下文架构方向 | [17-上下文窗口的模型原理.md](./17-上下文窗口的模型原理.md) |
| 18 | 模型固有局限与工程兜底（进阶） | 19 类原理性局限的全景表、七种通用兜底模式、模型缺陷与系统设计的对应 | [18-模型固有局限与工程兜底.md](./18-模型固有局限与工程兜底.md) |
| 19 | 推理加速底层系统（进阶） | prefill/decode、Roofline、KV Cache、PagedAttention、RadixAttention、FlashAttention、continuous batching、speculative decoding、量化、P/D disaggregation | [19-推理加速底层系统.md](./19-推理加速底层系统.md) |
| 19.1 | └ Agent 推理加速落地（子文档） | Agent 延迟拆解、少调用少 token、工具并行、模型分层、上下文压缩、多层缓存、结构化输出、可观测优化闭环 | [19.1-Agent推理加速落地.md](./19.1-Agent推理加速落地.md) |
| 20 | Agent Runtime 专题（进阶） | Run 生命周期、调度器、状态/检查点、HITL、handoff、完整实现、主流实现对比 | [20-Agent Runtime专题](./20-Agent%20Runtime专题.md) |
| 21 | Computer Use 与 Browser Agent 专题（进阶） | screenshot/DOM/accessibility tree、动作空间、locator、等待验证、HITL、安全边界、WebArena/OSWorld 评估 | [21-Computer Use与Browser Agent专题.md](./21-Computer%20Use与Browser%20Agent专题.md) |
| 22 | 结构化输出与约束解码专题（进阶） | JSON mode、JSON Schema、tool args schema、CFG/FSM grammar、validator、repair loop、schema versioning、性能成本 | [22-结构化输出与约束解码专题.md](./22-结构化输出与约束解码专题.md) |
| 23 | Tool Gateway 与工具平台专题（进阶） | 工具注册、Tool Retrieval、OpenAPI/MCP 接入、权限过滤、幂等、错误码、沙箱、审计、工具测试 | [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md) |
| 24 | Agent Eval Harness 专题（进阶） | golden set、failure pool、trace replay、rule evaluator、LLM judge 校准、CI gate、线上采样、eval report | [24-Agent Eval Harness专题.md](./24-Agent%20Eval%20Harness专题.md) |
| 25 | Buddy 型工作台智能体专题（进阶） | WorkBuddy、CodeBuddy、Qoder 类产品谱系、架构分层、上下文工程、工具集成、安全治理、评估体系 | [25-Buddy型工作台智能体专题](./25-Buddy型工作台智能体专题.md) |

---

## 目录组织规则

当前所有 Markdown 学习文档都打平放在根目录，不再使用专题子文件夹。

| 类型 | 命名方式 | 说明 |
|------|----------|------|
| 元文档 | `00-主题.md` | 全局目录、职责边界、迁移清单和写作规则 |
| 主线文档 | `NN-主题.md` | 按学习顺序阅读的核心主题 |
| 主线子文档 | `NN.x-主题.md` | 紧贴主线主题的补充内容 |
| 专题入口 | `NN-主题专题.md` | 一个专题的总览和阅读路径 |
| 专题子文档 | `NN.x-子主题.md` | 专题内部按小数编号排序 |

写作和整理优先级：

1. 先查 [00-内容职责与迁移清单.md](./00-内容职责与迁移清单.md)，确认新增内容的主负责文件。
2. 如果概念已经有主负责文件，其他文件只保留摘要和链接。
3. 专题入口负责阅读路径和问题地图，不重复子文档长篇细节。
4. 代码示例、产品案例、资料引用如果服务于不同目标，可以保留局部重复，但要说明用途。
5. 文档定位为系统学习资料，不使用招聘或应试化语境。

例如：

| 专题入口 | 子文档 |
|----------|--------|
| [13.1-多Agent状态管理专题.md](./13.1-多Agent状态管理专题.md) | `13.1.1` 到 `13.1.5` |
| [16-Agent Loop专题.md](./16-Agent%20Loop专题.md) | `16.1` 到 `16.3` |
| [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md) | `20.1` 到 `20.2` |
| [25-Buddy型工作台智能体专题.md](./25-Buddy型工作台智能体专题.md) | `25.1` 到 `25.6` |

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
| 内容职责 | 一个概念一个主负责文件；非主责文件保留摘要和链接；迁移记录见 `00` |
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
| Computer Use / Browser Agent | Screenshot；DOM；Accessibility Tree；Locator；Action Schema；Auto-wait；Verifier；Evidence-based Done；WebArena；OSWorld |
| 结构化输出 | JSON Mode；JSON Schema；Tool Args Schema；Final Output Schema；Constrained Decoding；Validator；Repair Loop；Schema Version |
| Tool Gateway | Tool Registry；Tool Retrieval；Permission Filter；Policy Engine；Risk Scoring；Idempotency；Sandbox；Audit；Tool Eval |
| Agent Eval Harness | Golden Set；Regression Set；Trace Replay；Rule Evaluator；LLM Judge Calibration；CI Gate；Failure Pool；Shadow Eval |
| Buddy 工作台智能体 | WorkBuddy；CodeBuddy；Qoder；Task Contract；Context Manifest；Agent Runtime；Tool Gateway；HITL；Office Agent；Coding Agent；任务成功率 |

---

## 进度跟踪

- [ ] 内容职责与迁移清单
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
- [ ] 多 Agent 状态管理专题（进阶专题）
- [ ] Agent 工程细节与可靠执行（进阶专题）
- [ ] AI Coding Harness 最佳实践（进阶专题）
- [ ] Agent Loop 专题（进阶专题）
- [ ] 上下文窗口的模型原理（进阶专题）
- [ ] 模型固有局限与工程兜底（进阶专题）
- [ ] 推理加速底层系统（进阶专题）
- [ ] Agent 推理加速落地（进阶专题）
- [ ] Agent Runtime 专题（进阶专题）
- [ ] Computer Use 与 Browser Agent（进阶专题）
- [ ] 结构化输出与约束解码（进阶专题）
- [ ] Tool Gateway 与工具平台（进阶专题）
- [ ] Agent Eval Harness（进阶专题）
- [ ] Buddy 型工作台智能体（进阶专题）

---

## 如何继续生成 / 回顾

- 单篇精读：直接打开对应主题的 `.md` 文件
- 想继续生成 / 扩充某一篇：让 AI 基于该 md 文件继续展开（例如"把工具部分再加 5 个知识点"）
- 想做综合自测：让 AI 从所有主题抽取问题组成自测题集
