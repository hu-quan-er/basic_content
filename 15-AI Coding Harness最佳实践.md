# AI Coding Harness 最佳实践

> 目标：系统掌握如何为 AI Coding / Coding Agent 搭建可复用的工程脚手架，让 AI 少猜、多验证、可恢复、可审查。本文聚焦“如何更好地使用 AI Coding”，不是介绍模型原理。

---

## 一、什么是 Harness Coding

Harness Coding 可以理解为：给 AI Coding Agent 准备一套“可执行工作环境”和“工程约束系统”，让它在明确边界内完成开发任务。

它不是单纯写 prompt，而是把以下内容工程化：

- 项目规则：架构、代码风格、禁区、依赖策略。
- 上下文入口：哪些文档、规则、目录是必须看的。
- 任务包：一次任务的目标、边界、验收标准。
- 验证脚本：如何 lint、typecheck、test、smoke。
- 进度记录：长任务做到哪、什么已验证、什么未完成。
- 权限控制：哪些命令能自动跑，哪些必须确认。
- 恢复机制：上下文压缩、会话中断、后台任务失败后如何继续。
- 审查机制：最终 diff、测试证据、风险说明。

**一句话**：Harness Coding 的目标不是让 AI 更自由，而是让 AI 在更好的工程轨道里工作。

---

## 二、为什么 AI Coding 特别需要 Harness

AI Coding 和普通问答不同，它会影响真实代码库，有明显副作用：

| 风险 | 典型表现 | Harness 的作用 |
|------|----------|----------------|
| 上下文不足 | 改错文件、误解架构 | 提供规则文件、架构索引、任务包 |
| 运行方式不明 | 不知道如何测试、如何启动项目 | 提供统一脚本和命令说明 |
| 大 diff 不可审 | 一次改几十个文件 | 约束小步提交、小任务闭环 |
| 幻觉 API | 调用不存在的函数或库 | 强制 typecheck/test |
| 长任务断片 | 上下文压缩后忘记进度 | progress / feature list |
| 破坏性操作 | 删除文件、改配置、推送分支 | permissions / hooks / HITL |
| 错误完成 | 未验证就说完成 | 验证清单和证据格式 |

**面试金句**：AI Coding 的生产力上限不只取决于模型，而取决于代码库有没有为 AI 提供可发现的上下文和可执行的验证路径。

---

## 三、主流项目和产品的 Harness 实践

### 3.1 OpenAI Codex：`AGENTS.md` 作为项目级操作手册

Codex 的核心 harness 入口是 `AGENTS.md`。它用于告诉 coding agent 项目结构、命令、测试方式、代码约定和注意事项。官方文档强调它可以放在仓库根目录，也可以放在子目录，离当前工作目录更近的文件会覆盖更上层的指令。

适合沉淀：

- 项目概览。
- 构建、测试、lint 命令。
- 目录结构。
- 代码风格。
- PR / 提交要求。
- 禁止修改的文件。
- 验证要求。

典型 harness 价值：

- 多 agent / 多会话共享同一套项目知识。
- 减少每次任务开头重复解释。
- 子目录可以有领域规则，比如 `apps/web/AGENTS.md`、`services/api/AGENTS.md`。

参考：OpenAI Codex `AGENTS.md` 文档。

### 3.2 Claude Code：`CLAUDE.md`、Memory、Permissions、Hooks

Claude Code 的 harness 比较完整，常见组合是：

- `CLAUDE.md`：项目记忆和长期规则。
- Memory：跨会话保留项目背景、常用命令、偏好。
- Permissions：控制哪些工具/命令可自动执行。
- Hooks：在工具调用前后执行确定性脚本，例如格式化、检查、拦截危险命令。
- Subagents / Skills：把特定任务能力封装为可复用流程。

适合沉淀：

- “先读哪些文档”。
- “改代码前必须确认现状”。
- “改 TS 后跑 typecheck”。
- “禁止直接改迁移文件或 `.env`”。
- “某些 Bash 命令必须先问用户”。

Claude Code 的经验特别适合长期任务：让 agent 读 progress 文件、看 git history、运行项目自检，再继续未完成任务。

参考：Claude Code Memory、Settings、Hooks、Permissions 文档，以及 Anthropic *Effective harnesses for long-running agents*。

### 3.3 GitHub Copilot：Repository Instructions 和 Prompt Files

GitHub Copilot 支持仓库级 instructions，常见文件是：

```text
.github/copilot-instructions.md
```

它适合放：

- 项目编码规范。
- 测试命令。
- 架构说明。
- 命名约定。
- 不要做的事。

Copilot 还支持 prompt files，用于把常见任务模板化，例如：

- 生成 API endpoint。
- 写测试。
- 做代码审查。
- 迁移组件。

这类 harness 的核心是：把团队反复说给 AI 的话，变成仓库可版本化的规则和模板。

参考：GitHub Copilot custom instructions / prompt files 文档。

### 3.4 Cursor：Rules、Modes、Background Agent

Cursor 的 harness 重点是 rules：

- User rules：个人级偏好。
- Project rules：仓库级规则，通常放在 `.cursor/rules`。
- 不同模式：Ask / Manual / Agent / Background Agent。
- Background Agent：适合异步执行较独立的任务。

适合沉淀：

- UI 风格和组件规范。
- 目录边界。
- 测试命令。
- “何时先问、何时直接改”。
- Background Agent 的任务边界和验收格式。

Cursor 的规则要短而明确。过长的 rules 会让模型抓不住重点。

参考：Cursor Rules、Agent、Background Agent 文档。

### 3.5 Windsurf / Cascade：Rules、Memories、Workflows

Windsurf 的 harness 常见抽象：

- Rules：全局或工作区规则。
- Memories：长期记忆，比如项目偏好、团队约定。
- Workflows：把常见流程固定下来，例如“实现功能并运行测试”。
- Planning mode：先计划再执行。

适合沉淀：

- 固定开发流程。
- 项目启动和验证命令。
- UI / API / 测试约定。
- 任务完成后的总结格式。

它和 Cursor 类似，偏 IDE 内协作；规则和 workflow 越接近真实工程流程，效果越稳定。

参考：Windsurf Rules、Memories、Workflows 文档。

### 3.6 Aider：`CONVENTIONS.md`、Repo Map、Lint/Test Command

Aider 是命令行 pair programming 工具，它的 harness 思路很工程化：

- 用 repo map 帮模型理解代码结构。
- 支持 lint / test command，让模型修改后运行验证。
- 可用 conventions 文件沉淀项目约定。
- 支持不同 edit format 和 architect/editor 分工。

它的实践说明一个关键点：AI Coding 不需要总是靠 IDE，命令行 + 明确测试闭环也能形成强 harness。

适合学习：

- 小步修改。
- 测试失败后自动修复。
- 通过 repo map 控制上下文。
- 用 convention 文件降低重复说明成本。

参考：Aider docs。

### 3.7 Google Jules：Plan-first 的异步任务模式

Jules 是异步 coding agent，常见交互是：

1. 用户把 GitHub repo / issue 交给 Jules。
2. Jules 先分析并生成 plan。
3. 用户确认 plan。
4. Jules 在云环境里改代码。
5. 产出 branch / diff / PR。

这类 harness 的重点不是即时补全，而是“后台任务可控执行”：

- 任务必须足够独立。
- plan 要可审查。
- 环境要能安装依赖和跑测试。
- 输出要能通过 PR review。

参考：Google Jules docs。

### 3.8 Cline / Roo Code：Memory Bank 和规则文件

Cline / Roo Code 社区常用 Memory Bank：

- `projectbrief.md`
- `productContext.md`
- `activeContext.md`
- `progress.md`
- `systemPatterns.md`
- `techContext.md`

这套结构特别适合长任务和上下文恢复。它把“项目背景、当前目标、技术约束、已完成事项”拆成多个稳定文件，避免一个巨长规则文件变得不可读。

适合沉淀：

- 当前任务状态。
- 产品目标。
- 技术栈说明。
- 系统模式。
- 待办和阻塞。

参考：Cline Memory Bank / `.clinerules`，Roo Code rules / memory bank 文档。

### 3.9 Cognition / Devin：不要盲目多 Agent，重视上下文连续性

Cognition 在 *Don't Build Multi-Agents* 中强调，代码任务里多 Agent 很容易造成上下文割裂：子 Agent 只看到局部摘要，主 Agent 又看不到完整推理过程，最终导致错误决策。

对 harness 的启发：

- 代码任务优先单主 Agent，保持完整上下文。
- 子 Agent 只用于只读搜索、并行调查、审查等边界清晰任务。
- 子 Agent 输出必须结构化，带证据，不要只给一句总结。

参考：Cognition *Don't Build Multi-Agents*。

### 3.10 Anthropic：Long-running Agent Harness

Anthropic 的 *Effective harnesses for long-running agents* 是 harness coding 里非常值得读的分享。核心思想包括：

- 给 agent 持久化进度文件。
- 用 feature list 管理任务完成状态。
- 让 agent 从 git history 和已有 artifacts 里恢复上下文。
- 通过测试和检查来确认是否真的完成。
- 避免把所有进度只存在聊天上下文里。

这套方法适合复杂功能开发、长周期修 bug、持续跑 benchmark 的场景。

---

## 四、抽象出来的 10 个最佳实践

### 4.1 Repo Instruction：项目级规则文件

至少准备一个：

| 工具 | 常见文件 |
|------|----------|
| Codex | `AGENTS.md` |
| Claude Code | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor | `.cursor/rules/*.mdc` 或 `.cursor/rules` |
| Windsurf | workspace rules |
| Cline / Roo | `.clinerules`、memory bank |
| Aider | `CONVENTIONS.md` |

推荐内容：

```md
# AI Coding Instructions

## Project Overview
- Monorepo using pnpm.
- Frontend: `apps/web`.
- Backend: `services/api`.
- Shared packages: `packages/*`.

## Common Commands
- Install: `pnpm install`
- Typecheck: `pnpm typecheck`
- Lint: `pnpm lint`
- Unit tests: `pnpm test`
- Web dev: `pnpm --filter web dev`

## Coding Rules
- Follow existing patterns before introducing new abstractions.
- Keep diffs small and focused.
- Do not add dependencies unless explicitly justified.
- Do not change public APIs unless requested.

## Verification
- After TypeScript changes, run `pnpm typecheck`.
- After business logic changes, run related tests.
- Before final response, summarize changed files and verification results.

## Safety
- Do not edit `.env`, secrets, migrations, or deployment config unless explicitly requested.
- Ask before destructive commands, git push, deploy, or database operations.
```

规则要短、具体、可执行。不要写“代码要优雅”这种无法验证的句子。

### 4.2 Hierarchical Instructions：分层规则

大型仓库不要只有一个超长规则文件。推荐：

```text
AGENTS.md
apps/web/AGENTS.md
services/api/AGENTS.md
packages/ui/AGENTS.md
```

根目录放全局规则，子目录放领域规则：

- 前端：组件规范、样式系统、状态管理、测试方式。
- 后端：API 风格、错误码、事务、鉴权。
- 数据层：迁移规则、索引规则、禁止事项。
- UI 库：可访问性、设计 token、storybook。

好处：

- Agent 在相关目录工作时获取更精确规则。
- 避免根规则过长。
- 团队可以按模块维护。

### 4.3 Task Packet：每次任务都给任务包

不要只说“帮我修一下”。给 AI 一个任务包：

```md
## Task
Fix duplicate refund bug.

## Background
Refund logic is in `services/api/refund`.
Order model is in `packages/domain/order`.

## Expected Behavior
- A refunded order cannot be refunded again.
- API returns 409 for repeated refund.
- Existing successful refund flow still works.

## Constraints
- Keep public API response shape unchanged.
- Do not add dependencies.
- Keep diff minimal.

## Verification
- Add regression test.
- Run refund-related tests.
- Run typecheck if TypeScript signatures change.

## Output
- Summarize files changed.
- Include verification commands and results.
- List remaining risks.
```

任务包越清楚，AI 越不容易做无关扩展。

### 4.4 Plan Gate：先计划，再执行

对非小修任务，要求：

```text
先阅读相关代码，不要修改。
输出：
1. 你发现的现状
2. 修改计划
3. 预计改哪些文件
4. 需要跑哪些测试
5. 风险和不确定点
等我确认后再改。
```

适合：

- 多文件修改。
- 数据库 / 权限 / 支付 / 业务核心链路。
- 没有明确测试的模块。
- 重构。
- UI 大改。

不一定每个小任务都要 plan gate，但高风险任务必须有。

### 4.5 Verification Scripts：统一验证脚本

AI 不该猜怎么验证。建议放：

```text
scripts/verify.sh
scripts/verify-unit.sh
scripts/verify-web.sh
scripts/smoke.sh
```

示例：

```bash
#!/usr/bin/env bash
set -euo pipefail

pnpm lint
pnpm typecheck
pnpm test
```

再在规则文件里写：

```md
For most code changes, run `scripts/verify.sh`.
If full verification is too slow, run the narrowest related test and explain why full verification was skipped.
```

关键不是脚本多，而是要让验证路径稳定、可发现、可重复。

### 4.6 Progress Ledger：长任务进度文件

长任务不要只存在聊天上下文里。建议：

```text
ai/progress.md
ai/feature-list.json
```

`ai/progress.md`：

```md
# AI Progress

## Current Goal
Implement refund flow.

## Done
- Added backend refund endpoint.
- Added ownership validation.
- Added regression test for duplicate refund.

## In Progress
- Frontend refund button state.

## Blocked
- Need product decision on refund reason enum.

## Last Verification
- `pnpm test services/api/refund.test.ts` passed.
- Full suite not run.
```

`ai/feature-list.json`：

```json
[
  {
    "feature": "duplicate refunds are rejected",
    "status": "passing",
    "evidence": "services/api/refund.test.ts"
  },
  {
    "feature": "refund button disabled after refund",
    "status": "pending",
    "evidence": null
  }
]
```

规则：

- 只有跑过相关验证，才能标 `passing`。
- 未验证只能标 `implemented_unverified` 或 `pending`。
- 每次上下文压缩或会话结束前更新。

### 4.7 Evidence-based Final：最终回答必须带证据

要求 AI 每次收尾用固定格式：

```md
## Changes
- `services/api/refund.ts`: added duplicate refund guard.
- `services/api/refund.test.ts`: added regression test.

## Verification
- Passed: `pnpm test services/api/refund.test.ts`
- Not run: full suite, because unrelated and slow.

## Risks
- Did not manually test UI refund button.
```

不要接受：

> 已完成，应该没问题。

没有验证命令、没有文件列表、没有风险说明，就不是完整交付。

### 4.8 Permissions and Hooks：权限和钩子

对 coding agent 来说，工具权限要分级：

| 操作 | 建议 |
|------|------|
| Read / rg / ls | 默认允许 |
| Edit project files | 允许，但要求 diff 可审 |
| Run tests / lint | 默认允许 |
| Install dependencies | 需要说明理由 |
| Modify lockfile | 需要确认 |
| Edit `.env` / secrets | 禁止或强确认 |
| DB migration | 高风险确认 |
| `rm`, `git reset`, `git push`, deploy | 必须人工确认 |

Hooks 可用于：

- 拦截危险命令。
- 自动格式化。
- 在写文件后跑局部 lint。
- 禁止修改敏感目录。
- 记录工具调用日志。

这类机制的核心是：安全不能只靠 prompt，必须有工具层硬约束。

### 4.9 Context Index：让 AI 快速找到上下文

准备短文档：

```text
docs/architecture.md
docs/testing.md
docs/api-conventions.md
docs/frontend-patterns.md
docs/database.md
docs/security.md
```

每个文档控制在可读范围内，写“该看哪里、怎么验证、不要做什么”。

示例：

```md
# Testing Guide

## Backend
- Unit tests live next to source as `*.test.ts`.
- Run a single test: `pnpm vitest path/to/file.test.ts`.

## Frontend
- Component tests use Testing Library.
- Avoid snapshot-only tests.

## Required
- Bug fixes need a regression test when feasible.
- If no test is added, explain why.
```

### 4.10 Small Batch Loop：小批量闭环

最佳循环：

```text
Read → Plan → Edit small diff → Run narrow test → Repair → Summarize
```

不要：

```text
Read entire repo → rewrite architecture → add dependencies → run no tests
```

AI Coding 最稳定的工作方式是小步、可验证、可回滚。

---

## 五、推荐的项目 Harness 目录

### 5.1 最小版

```text
.
├── AGENTS.md / CLAUDE.md
├── scripts/
│   ├── verify.sh
│   └── smoke.sh
└── docs/
    ├── architecture.md
    └── testing.md
```

适合个人项目或小团队。

### 5.2 标准版

```text
.
├── AGENTS.md
├── apps/
│   └── web/
│       └── AGENTS.md
├── services/
│   └── api/
│       └── AGENTS.md
├── ai/
│   ├── progress.md
│   ├── feature-list.json
│   └── task-template.md
├── docs/
│   ├── architecture.md
│   ├── testing.md
│   ├── api-conventions.md
│   ├── frontend-patterns.md
│   └── security.md
└── scripts/
    ├── verify.sh
    ├── verify-web.sh
    ├── verify-api.sh
    └── smoke.sh
```

适合中大型业务项目。

### 5.3 企业版

```text
.
├── AGENTS.md
├── .github/
│   ├── copilot-instructions.md
│   └── prompts/
├── .cursor/
│   └── rules/
├── ai/
│   ├── progress.md
│   ├── feature-list.json
│   ├── review-checklist.md
│   └── risk-register.md
├── docs/
│   ├── architecture.md
│   ├── testing.md
│   ├── security.md
│   ├── release.md
│   └── incident-playbook.md
├── scripts/
│   ├── verify.sh
│   ├── verify-ci-local.sh
│   ├── smoke.sh
│   └── secret-scan.sh
└── policy/
    ├── allowed-tools.md
    ├── data-handling.md
    └── ai-code-review.md
```

适合企业内部推广 AI Coding，需要安全、审计、合规和统一流程。

---

## 六、任务类型与 Harness 用法

### 6.1 代码理解

Prompt：

```text
请先阅读相关代码，不要修改。

目标：理解订单退款流程。

请输出：
1. 入口在哪里
2. 核心调用链
3. 涉及哪些文件
4. 数据如何流转
5. 风险点和测试入口
```

Harness：

- `docs/architecture.md`
- `docs/api-conventions.md`
- `rg` / repo map
- 不允许 edit

### 6.2 Bug 修复

Prompt：

```text
现象：重复退款没有被拦截。
期望：已退款订单再次退款返回 409。
复现：调用 POST /refund 两次。

请先定位根因，不要修改。
找到根因后给最小修改方案和回归测试计划。
```

Harness：

- 任务包。
- 单测命令。
- 回归测试要求。
- 小 diff。

### 6.3 新功能

Prompt：

```text
我要新增退款原因字段。

约束：
- 不破坏现有 API。
- 不新增依赖。
- 后端、前端、测试都要覆盖。

请先给计划，列出文件和测试。
```

Harness：

- Plan gate。
- feature list。
- verify scripts。
- progress ledger。

### 6.4 重构

Prompt：

```text
请做行为不变的重构。

目标：把 refund service 中的校验逻辑拆成独立函数。
要求：
- 不改变公开 API。
- 不改变错误码。
- 保持现有测试通过。
- 每次只改一个逻辑块。
```

Harness：

- 强制测试。
- diff 小。
- 输出行为等价说明。

### 6.5 长任务 / 后台 Agent

Prompt：

```text
这是一个长任务。请维护 `ai/progress.md` 和 `ai/feature-list.json`。

每完成一个可验证子项：
1. 更新 feature status。
2. 记录验证命令。
3. checkpoint 当前进度。

如果上下文不足，先读 progress 文件再继续。
```

Harness：

- progress ledger。
- feature list。
- git branch。
- checkpoint。
- 每阶段验证。

---

## 七、AI Coding Harness 模板库

### 7.1 `AGENTS.md` / `CLAUDE.md` 模板

```md
# AI Coding Instructions

## Read First
- Read this file before making changes.
- For long tasks, also read `ai/progress.md`.

## Project Overview
- Describe the product in 2-4 bullets.
- Mention key directories and ownership boundaries.

## Commands
- Install: `...`
- Lint: `...`
- Typecheck: `...`
- Test: `...`
- Smoke: `...`

## Development Rules
- Keep diffs focused.
- Prefer existing patterns.
- Do not introduce dependencies without approval.
- Do not change public APIs unless requested.

## Verification Rules
- Bug fixes should include regression tests when feasible.
- Run the narrowest relevant test first.
- Run broader verification before final handoff if practical.

## Safety Rules
- Never edit secrets.
- Ask before destructive commands.
- Ask before database migrations, deploys, or git push.

## Final Response Format
- Changes
- Verification
- Risks / Not run
```

### 7.2 `ai/task-template.md`

```md
# AI Task Packet

## Task

## Background

## Expected Behavior

## Constraints

## Files / Areas Likely Involved

## Verification

## Out of Scope

## Final Output Required
```

### 7.3 `ai/review-checklist.md`

```md
# AI Code Review Checklist

- [ ] Diff is focused on the requested task.
- [ ] Public APIs are unchanged unless requested.
- [ ] New behavior has tests or explicit manual verification.
- [ ] No secrets or env files changed.
- [ ] No unnecessary dependency added.
- [ ] Error handling and edge cases are covered.
- [ ] Migration / data changes are reviewed.
- [ ] Final response lists commands run and risks.
```

### 7.4 `scripts/verify.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

pnpm lint
pnpm typecheck
pnpm test
```

### 7.5 Final Response 模板

```md
## Changes
- ...

## Verification
- Passed: `...`
- Failed: `...`
- Not run: `...` because ...

## Risks
- ...

## Next Step
- ...
```

---

## 八、Harness 成熟度模型

### Level 0：裸用 AI

特征：

- 只有自然语言 prompt。
- 没有规则文件。
- 不跑测试。
- AI 改完直接相信。

风险：效率看似高，返工和隐藏 bug 多。

### Level 1：项目规则

特征：

- 有 `AGENTS.md` / `CLAUDE.md` / rules。
- 写了项目结构和基础命令。
- 要求小 diff。

收益：减少重复解释。

### Level 2：验证闭环

特征：

- 有统一 `scripts/verify.sh`。
- AI 每次交付要给验证证据。
- bug fix 要补回归测试。

收益：明显降低幻觉代码。

### Level 3：长任务恢复

特征：

- 有 progress ledger。
- 有 feature list。
- 后台任务可以中断恢复。
- 上下文压缩后能继续。

收益：能处理多小时、多阶段任务。

### Level 4：权限和审计

特征：

- 有工具权限策略。
- 有 hooks。
- 敏感操作 HITL。
- 有 AI 代码审查清单。

收益：适合团队和企业落地。

### Level 5：组织级 AI SDLC

特征：

- 规则模板统一。
- PR 流程纳入 AI 输出说明。
- 指标追踪：接受率、回滚率、测试失败率。
- 安全、合规、license 扫描接入。

收益：AI Coding 变成工程能力，而不是个人技巧。

---

## 九、常见反模式

| 反模式 | 问题 | 改法 |
|--------|------|------|
| 规则文件太长 | 模型抓不住重点 | 拆成根规则 + 子目录规则 |
| 只有原则没有命令 | AI 不知道如何验证 | 写清 `lint/test/typecheck` |
| 一次任务太大 | diff 不可审 | 拆成任务包 |
| 不要求先读代码 | 容易盲改 | 加 read-first 约束 |
| 不维护进度 | 长任务断片 | 用 `ai/progress.md` |
| 允许自由安装依赖 | 引入复杂度 | 新依赖必须解释并确认 |
| 忽略测试失败 | 修一个坏三个 | 测试失败必须继续分析 |
| 最终只说完成 | 无证据 | 强制 final response 模板 |
| 把 AI 当决策者 | 业务判断失控 | 人负责目标和验收 |
| 多 Agent 乱拆 | 上下文割裂 | 单主 Agent，子 Agent 只做边界清晰任务 |

---

## 十、面试题与回答

### Q1：什么是 AI Coding Harness？

**答**：

AI Coding Harness 是为 coding agent 准备的一套工程脚手架，包括项目规则、上下文索引、任务模板、验证脚本、权限控制、进度记录和审查流程。它的目标是让 AI 少猜、多验证、可恢复、可审查。

### Q2：为什么只写 prompt 不够？

**答**：

因为 coding agent 会产生真实副作用。单靠 prompt 无法保证它知道项目怎么跑、哪些文件不能改、如何验证、任务做到哪。Harness 把这些隐性知识变成仓库内可版本化、可执行、可复用的规则和脚本。

### Q3：`AGENTS.md` / `CLAUDE.md` 应该写什么？

**答**：

写项目概览、目录结构、常用命令、代码规则、测试规则、安全禁区和最终输出格式。不要写长篇理念，要写具体可执行指令，比如“改 TypeScript 后跑 `pnpm typecheck`”，“不要改 `.env`”，“新增依赖前先说明理由”。

### Q4：长任务怎么避免上下文断片？

**答**：

用 progress ledger 和 feature list。把当前目标、已完成项、未完成项、阻塞点、验证命令写入文件。上下文压缩或新会话开始时，agent 先读这些文件再继续。不要只依赖聊天历史。

### Q5：AI Coding 怎么做验证闭环？

**答**：

按优先级：单元测试、类型检查、lint、集成测试、smoke test、人工 review。规则文件要告诉 AI 何时跑哪些命令，最终回答必须列出通过、失败、未运行的验证项。

### Q6：什么时候需要 plan gate？

**答**：

多文件修改、核心业务链路、权限/支付/数据迁移、重构、没有明确测试的模块都需要。让 AI 先读代码、列文件、讲方案和风险，经确认后再改。

### Q7：团队推广 AI Coding 最重要的制度是什么？

**答**：

把 AI 使用约定纳入 repo，而不是停留在口头。统一规则文件、验证脚本、PR 输出模板、权限策略和审查清单。团队要评估 AI 代码的接受率、回滚率、测试失败率和安全问题。

### Q8：为什么代码任务不宜盲目多 Agent？

**答**：

代码修改通常高度耦合，需要完整上下文。多 Agent 会带来上下文割裂和摘要损失。更稳的方式是单主 Agent 保持全局上下文，子 Agent 只做只读搜索、并行调查、审查等边界清晰任务。

---

## 十一、自测清单

- [ ] 能解释 harness coding 和 prompt engineering 的区别
- [ ] 能设计一个项目级 `AGENTS.md` / `CLAUDE.md`
- [ ] 能说明为什么规则文件要短而具体
- [ ] 能设计任务包模板
- [ ] 能设计 progress ledger 和 feature list
- [ ] 能设计 `scripts/verify.sh`
- [ ] 能说明 plan gate 适用场景
- [ ] 能列出 AI Coding 权限分级
- [ ] 能解释 hooks 的作用
- [ ] 能处理长任务中断恢复
- [ ] 能区分个人级、项目级、企业级 harness
- [ ] 能说出 Codex、Claude Code、Copilot、Cursor、Aider 的 harness 差异
- [ ] 能设计最终交付格式
- [ ] 能列出 5 个 AI Coding 反模式

---

## 十二、术语 Cheat Sheet

| 术语 | 含义 |
|------|------|
| Harness Coding | 为 AI Coding 准备规则、脚本、上下文、验证和权限控制 |
| Repo Instruction | 仓库级 AI 指令文件 |
| Task Packet | 单次任务的结构化说明 |
| Plan Gate | 先计划并确认，再改代码 |
| Progress Ledger | 长任务进度文件 |
| Feature List | 可验证功能状态列表 |
| Verification Script | 统一验证脚本 |
| Hook | 工具调用前后的确定性脚本 |
| Memory Bank | 分文件维护的长期项目上下文 |
| Evidence-based Final | 带文件、命令、结果和风险的最终总结 |
| Background Agent | 后台异步 coding agent |
| Repo Map | 代码库结构索引，帮助模型选上下文 |

---

## 十三、延伸阅读

- OpenAI Codex — `AGENTS.md`: https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex — Cloud tasks: https://developers.openai.com/codex/cloud
- Claude Code — Memory: https://docs.anthropic.com/en/docs/claude-code/memory
- Claude Code — Settings: https://docs.anthropic.com/en/docs/claude-code/settings
- Claude Code — Hooks: https://docs.anthropic.com/en/docs/claude-code/hooks
- Claude Code — Permissions: https://docs.anthropic.com/en/docs/claude-code/iam
- Anthropic — Effective harnesses for long-running agents: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic — Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- GitHub Copilot — Repository custom instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- GitHub Copilot — Prompt files: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-prompt-files
- Cursor — Rules: https://docs.cursor.com/context/rules
- Cursor — Background Agent: https://docs.cursor.com/background-agent
- Windsurf — Cascade memories / rules / workflows: https://docs.windsurf.com/
- Aider — Docs: https://aider.chat/docs/
- Google Jules — Docs: https://jules.google/docs/
- Cline — Docs: https://docs.cline.bot/
- Roo Code — Docs: https://docs.roocode.com/
- Cognition — Don't Build Multi-Agents: https://cognition.ai/blog/dont-build-multi-agents
- SWE-bench: https://www.swebench.com/
- Terminal-Bench: https://www.tbench.ai/

---

## 十四、面试金句

- "AI Coding Harness 的核心是把隐性工程知识变成仓库内可执行的规则、脚本和检查点。"
- "好的 harness 让 AI 少猜项目怎么跑，多用测试证明它真的完成。"
- "不要把任务完成状态只放在聊天历史里，长任务要写 progress ledger。"
- "规则文件不是越长越好，越具体、越接近执行命令越有用。"
- "AI Coding 的交付物不是代码，而是 diff + 验证证据 + 风险说明。"
- "安全不能靠 prompt 自律，危险命令和敏感文件必须有权限层硬约束。"
- "Coding agent 适合单主 Agent 保持上下文，子 Agent 只做边界清晰的只读或审查任务。"
- "团队级 AI Coding 的关键不是每个人会不会 prompt，而是 repo 是否 AI-ready。"
