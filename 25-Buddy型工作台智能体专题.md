# Buddy 型工作台智能体专题

> 目标：把腾讯 WorkBuddy、腾讯 CodeBuddy、阿里 Qoder / QoderBuddy 这类产品放到同一个技术框架里分析，理解它们不是简单聊天机器人，而是围绕"工作台入口 + 上下文系统 + Agent Runtime + 工具执行 + 安全治理"构建的产品化 Agent。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Buddy 型工作台智能体的产品谱系、学习路径、产品架构映射和关键问题 | Agent Runtime 通用原理见 [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md)；上下文工程见 [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md)；Tool Gateway 见 [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)；Eval Harness 见 [24-Agent Eval Harness专题.md](./24-Agent%20Eval%20Harness专题.md) |

---

## 一、资料状态

截至 2026-06-14，本专题能稳定核到的公开官方资料包括：

| 产品 | 可核信息 | 证据等级 |
|---|---|---|
| Qoder | 官方站定位为 AI Coding Assistant / Autonomous Development Desktop / Agentic Coding Platform，支持代码补全、AI 对话编程、自动代码生成，并出现 JetBrains Plugin、CLI、Windows/macOS/Linux 等信息 | 高 |
| CodeBuddy | 官方站定位为 Tencent Cloud Code Assistant / AI Code Editor，提到代码补全、错误诊断、技术问答、性能优化、主流语言支持 | 高 |
| WorkBuddy | 公开检索中多见于媒体/百科转述，描述为 CodeBuddy 团队面向办公场景的全场景 AI 智能体；未在本次检索中稳定核到独立官方产品页 | 中低 |
| QoderBuddy | 未在 Qoder 官方页核到该正式产品名；本文按阿里系 Qoder / QoderBuddy 类产品分析 | 中低 |

---

## 二、一句话定义

**Buddy 型工作台智能体是把 LLM、上下文工程、工具调用、权限控制和执行反馈封装到一个具体工作入口里的 Agent 产品。**

它和普通 AI 助手的区别不在于"会聊天"，而在于能围绕一个真实任务持续执行：

```text
user intent
  -> task contract
  -> context collection
  -> plan / act / observe loop
  -> tool execution
  -> verification
  -> audit / memory / handoff
```

---

## 三、两条主线

| 主线 | 代表产品 | 核心任务 | 核心上下文 | 核心工具 |
|---|---|---|---|---|
| 办公执行 Buddy | WorkBuddy、OpenClaw/Manus 类产品 | 整理文件、处理表格、生成文案、跨应用办公、业务流程执行 | IM、文档、表格、文件、日程、企业知识库、业务系统 | 浏览器、桌面、文档 API、表格 API、IM bot、RPA、企业 API |
| 开发工作台 Buddy | Qoder、CodeBuddy、Cursor、Claude Code 类产品 | 读代码、改代码、生成测试、运行命令、修复错误、部署 | 代码仓库、依赖、测试、Git diff、issue、PR、终端状态 | IDE API、文件系统、grep、git、shell、测试框架、包管理器、部署工具 |

二者共享 Agent Runtime 和 Tool Gateway，但上下文、权限、验证方式和失败代价不同。

---

## 四、专题阅读路径

| 顺序 | 文件 | 解决的问题 |
|---|---|---|
| 1 | [25.1-Buddy产品谱系与案例.md](./25.1-Buddy产品谱系与案例.md) | 这类 Buddy 产品到底是什么，WorkBuddy 与 Qoder 的差异在哪里 |
| 2 | [25.2-Buddy架构分层与Agent运行时.md](./25.2-Buddy架构分层与Agent运行时.md) | 一个 Buddy 型产品应如何拆成入口、上下文、Runtime、工具、安全、评估 |
| 3 | [25.3-Buddy上下文工程与工具集成.md](./25.3-Buddy上下文工程与工具集成.md) | WorkBuddy / Qoder 分别需要什么上下文和工具系统 |
| 4 | [25.4-Buddy安全治理与评估体系.md](./25.4-Buddy安全治理与评估体系.md) | 如何控制副作用、权限、审计、人在回路和质量评估 |
| 5 | [25.5-Buddy系统学习路线与问题清单.md](./25.5-Buddy系统学习路线与问题清单.md) | 如何系统学习、复盘、做小型实验和系统设计自测 |
| 6 | [25.6-Buddy资料来源与证据等级.md](./25.6-Buddy资料来源与证据等级.md) | 本专题使用的公开资料和证据等级 |

---

## 五、核心架构速览

```text
Interaction Surface
  Web / Desktop / IDE / CLI / IM / Browser Extension
        |
Task Contract
  intent, scope, constraints, risk, success criteria
        |
Context Builder
  history, files, repo, docs, tables, enterprise knowledge, tool state
        |
Agent Runtime
  plan, act, observe, checkpoint, budget, stop condition, resume
        |
Tool Gateway
  registry, permission, schema validation, risk scoring, HITL, audit
        |
Execution Layer
  API / MCP / browser / desktop / shell / git / test / enterprise systems
        |
Verification & Eval
  state check, tests, side-effect check, trace replay, user acceptance
```

---

## 六、和现有主题的联读关系

| 已有主题 | 关联点 |
|---|---|
| [03-工具调用.md](./03-工具调用.md) | Buddy 产品的能力边界最终落在工具调用 |
| [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md) | 工作台智能体的上下文不是聊天历史，而是任务相关状态切片 |
| [15-AI Coding Harness最佳实践.md](./15-AI%20Coding%20Harness最佳实践.md) | Qoder / CodeBuddy 类产品的工程轨道 |
| [20-Agent Runtime专题.md](./20-Agent%20Runtime专题.md) | Buddy 产品可靠执行的底座 |
| [21-Computer Use与Browser Agent专题.md](./21-Computer%20Use与Browser%20Agent专题.md) | WorkBuddy 这类跨应用办公 Agent 的关键执行形态 |
| [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md) | 权限、审计、幂等、风险控制的核心层 |
| [24-Agent Eval Harness专题.md](./24-Agent%20Eval%20Harness专题.md) | 从 demo 走向产品化必须依赖评估闭环 |
