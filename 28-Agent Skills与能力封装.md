# Agent Skills 与能力封装专题

> 目标：理解 Agent 的第三种扩展方式——**能力封装（Skill）**。工具（Tool）给 Agent「能做什么动作」，MCP 给「从哪接入这些动作」，而 Skill 给的是「面对某类任务时，应该怎么做、按什么流程做、用哪些脚本做」。Skill 通过**渐进式披露（progressive disclosure）**把大量专业知识和流程装进 Agent，却几乎不占用常驻上下文预算。

---

## 本文职责边界

| 本文负责 | 本文不展开 |
|---|---|
| Skill 的定义、渐进式披露三层加载、SKILL.md 结构、Skill vs Tool/MCP/Prompt/Subagent 的区分、设计原则、主流实现（Anthropic Agent Skills / Claude Code / Agent SDK）、能力封装的治理 | Function Calling 基础见 [03-工具调用.md](./03-工具调用.md)；MCP 协议见 [03.1-MCP.md](./03.1-MCP.md)；工具平台治理见 [23-Tool Gateway与工具平台专题.md](./23-Tool%20Gateway与工具平台专题.md)；单次上下文组装见 [04.2-Agent上下文工程.md](./04.2-Agent上下文工程.md)；AI Coding 的 CLAUDE.md/AGENTS.md 见 [15-AI Coding Harness最佳实践.md](./15-AI%20Coding%20Harness最佳实践.md) |

---

## 一、一句话定义

**Skill 是一个可被模型按需加载的能力单元：一段「怎么做」的指令，外加可选的脚本和资源文件，打包成一个文件夹，靠一句 `description` 决定何时被激活。**

最小心智模型：

```text
skills/
  pdf-form-filling/
    SKILL.md          ← 必需：frontmatter(name, description) + 正文指令
    reference.md      ← 可选：详细规范，正文里按需 link
    fill_form.py      ← 可选：确定性步骤用脚本，而非让模型逐 token 生成
    templates/        ← 可选：示例、模板、schema
```

一句话区分三种扩展方式：

```text
Tool   = 一个可调用的动作      （search、issue_refund）
MCP    = 一批工具的接入协议     （把外部系统的工具/资源标准化接进来）
Skill  = 面对某类任务的做法包   （何时做、按什么流程、用哪些脚本和知识）
```

**核心判断**：工具扩展 Agent 的「手」，Skill 扩展 Agent 的「专业知识和工作方式」。

---

## 二、为什么需要 Skill

Agent 能力增长和上下文预算之间有一个根本矛盾。

### 2.1 三种旧办法都会撞墙

| 办法 | 做法 | 撞墙点 |
|---|---|---|
| 全塞进 system prompt | 把所有流程、规范、few-shot 写进常驻 prompt | 能力越多，常驻 token 越多；[Lost in the Middle](./17-上下文窗口的模型原理.md) 让长 prompt 反而更差；改一处要动全局 |
| 全做成工具 | 每个专业动作都做成 function | 工具描述也占 token；工具只暴露「接口签名」，装不下「怎么用、什么顺序、什么坑」这类流程知识 |
| 全交给 RAG | 把知识丢进向量库现查 | RAG 擅长「查事实」，不擅长「装可执行的流程和脚本」；检索到的片段缺乏结构和确定性 |

真实任务里有大量这样的知识：「填这类报销单要先校验金额上限，再查审批链，PDF 用附带的 `fill_form.py` 而不是自己拼字节」。这既不是一个「动作」，也不是一句「事实」，而是一套**做法**——这正是 Skill 的位置。

### 2.2 Skill 的解法：把知识分层，按需加载

Skill 的核心不是「多写文档」，而是**渐进式披露**：绝大部分内容平时不进上下文，只有相关时才逐层展开。这样即使装了几百个 skill，常驻成本也只是每个几十 token 的 `description`。

**核心判断**：Skill 让「Agent 会的东西」和「Agent 当前上下文里装的东西」解耦。

---

## 三、渐进式披露：三层加载模型

这是理解 Skill 的关键。一个 skill 的内容不是一次性注入，而是分三层按需加载：

```text
Level 1  metadata（name + description）
         → 常驻 system prompt，每个 skill 只花几十 token
         → 作用：让模型「知道有这个 skill、大概什么时候用」

Level 2  SKILL.md 正文
         → 模型判断「这个任务需要它」时才加载全文
         → 作用：给出完整流程、规则、注意事项

Level 3  链接的资源与脚本（reference.md / *.py / templates/）
         → 正文里用到时才 read 文件或 execute 脚本
         → 作用：装无限量的细节和确定性代码，完全不占常驻预算
```

对照上下文预算：

| 层级 | 何时进上下文 | 典型成本 | 类比 |
|---|---|---|---|
| L1 metadata | 始终 | 每 skill 约 20–50 token | 书的目录 |
| L2 SKILL.md | 命中该 skill 时 | 数百 ~ 一两千 token | 翻到那一章 |
| L3 资源/脚本 | 用到具体细节时 | 按需，可外置执行 | 查附录 / 跑工具 |

一个直观结论：**装 100 个 skill 的 Agent，空闲时的上下文开销 ≈ 100 行目录**；只有真正用到某个 skill 时，才为它付全额 token。这就是 Skill 相对「全塞 prompt」的根本优势。

`description` 因此是整个机制里最关键的一句话——它是**路由信号**。写得好，模型在对的时候激活；写得含糊，skill 要么永不触发，要么到处误触发。

---

## 四、SKILL.md 的结构

一个 skill 是一个文件夹，入口是 `SKILL.md`：

```markdown
---
name: pdf-form-filling
description: 当用户需要填写、批量生成或校验 PDF 表单时使用。处理字段映射、
             金额与审批规则校验，并用附带脚本生成最终 PDF。
---

# PDF 表单填写

## 何时用
- 用户提供 PDF 模板 + 一批数据，要求生成填好的表单。

## 流程
1. 读取模板字段：运行 `python inspect_fields.py <pdf>`。
2. 校验数据：金额上限与审批规则见 [reference.md](./reference.md)。
3. 生成 PDF：用 `python fill_form.py --data data.json --out result.pdf`，
   不要自己拼 PDF 字节。
4. 校验产物：确认所有必填字段非空。

## 注意
- 金额超过 5000 需要走 HITL 审批，不要直接生成。
```

要点：

| 部分 | 作用 | 设计要求 |
|---|---|---|
| `name` | 唯一标识 | 稳定、kebab-case，不随内容小改而变 |
| `description` | L1 路由信号 | 说清「什么触发」+「大概做什么」，用第三人称、含触发词 |
| 正文「何时用」 | 强化触发判断 | 列正例/反例，降低误触发 |
| 正文「流程」 | 核心价值 | 把确定性步骤指向脚本，把判断性步骤留给模型 |
| 链接文件 | L3 细节 | 用相对链接，按需展开，不在正文堆砌 |
| 脚本 | 确定性执行 | 数据处理、格式转换等不应让模型逐 token 生成 |

**脚本 vs 指令的分界线**：确定性的、有正确答案的、可验证的步骤 → 写成脚本（省 token 又不出错）；需要判断、需要结合上下文变通的步骤 → 留成自然语言指令。这条线和 [22-结构化输出](./22-结构化输出与约束解码专题.md) 里「能验证就别只靠模型自觉」是同一个工程哲学。

---

## 五、Skill vs Tool / MCP / Prompt / Subagent

这是最容易混的地方，用一张表钉死：

| 维度 | Prompt / 系统指令 | Tool（Function） | MCP | Skill | Subagent |
|---|---|---|---|---|---|
| 提供什么 | 全局人格与规则 | 一个可执行动作 | 一批工具的接入协议 | 一套「怎么做」的流程包 | 一个独立上下文的执行者 |
| 是否占常驻上下文 | 全额常驻 | 描述常驻 | 工具描述常驻 | **仅 metadata 常驻** | 主线只留句柄 |
| 谁触发 | 始终生效 | 模型每步选择 | 模型选择其中的工具 | 模型按 description 激活 | 主 Agent 派发 |
| 装得下流程/脚本吗 | 装得下但占预算 | 只有接口 | 只有接口 | **专门装这个** | 装在子 Agent 自己的 skill/prompt 里 |
| 典型规模 | 1 份 | 几十个 | 若干 server | 可上百个 | 少量 |

关键关系,而不是互斥：

- **Skill 会用 Tool 和 MCP**。skill 正文可以说「用 `issue_refund` 工具」或「调这个 MCP server」——skill 是指令层，工具是动作层,两者叠加。
- **Skill 里的脚本需要代码执行环境**。L3 的 `*.py` 要能被执行,依赖一个 code execution / 容器环境;没有它,skill 就退化成「纯指令包」。
- **Skill 和 Subagent 互补**。给一个专职 subagent 配上专属 skill,是常见组合:subagent 解决「隔离的上下文」,skill 解决「它该怎么做」。见 [06-多Agent协作](./06-多Agent协作.md)。
- **Skill 不取代 Tool Gateway**。skill 说「该调哪个工具、什么顺序」;要不要真的放行、权限、幂等、审计,仍由 [23-Tool Gateway](./23-Tool%20Gateway与工具平台专题.md) 决定。skill 是「攻略」,Gateway 是「门禁」。

**核心判断**：不要问「这个能力该做成 Tool 还是 Skill」,而要问「用户要的是一个原子动作,还是一套做法」。动作 → Tool;做法 → Skill(内部再引用若干 Tool)。

---

## 六、主流实现

### 6.1 Anthropic Agent Skills

Anthropic 在 2025 年把 Skill 作为一等公民推出,同一套 skill 文件夹可跨多个载体复用:

| 载体 | 用法 |
|---|---|
| Claude 应用(claude.ai / 桌面端) | 上传/启用 skill,对话中自动按需激活 |
| Claude Code | 项目或用户级 skill,CLI Agent 在编码任务中调用 |
| Agent SDK / API | 通过代码执行环境挂载 skill 目录,构建自定义 Agent |

统一约定:一个文件夹 + `SKILL.md`(YAML frontmatter `name`/`description` + markdown 正文)+ 可选脚本资源;模型自主决定何时加载,支持多个 skill 组合。脚本部分依赖 code execution 工具/容器。

### 6.2 与已有机制的落地映射

| 机制 | 关系 |
|---|---|
| CLAUDE.md / AGENTS.md（[15](./15-AI%20Coding%20Harness最佳实践.md)） | 是「始终生效」的项目级指令,相当于全局 L 常驻;Skill 是「按需生效」的能力包。两者互补:全局约定放 AGENTS.md,专项做法拆成 skill |
| MCP（[03.1](./03.1-MCP.md)） | 提供工具/资源的接入;Skill 提供使用它们的流程 |
| Tool Gateway（[23](./23-Tool%20Gateway与工具平台专题.md)） | skill 里引用的工具,执行时仍过 Gateway 的权限/幂等/审计 |
| 上下文工程（[04.2](./04.2-Agent上下文工程.md)） | 渐进式披露本质是一种上下文供应策略:按需注入 L2/L3,是 context manifest 的一个来源 |
| Runtime（[20](./20-Agent%20Runtime专题.md)） | Runtime 负责在每步把命中的 skill 内容拼进上下文、执行脚本、回填结果 |

### 6.3 自建 Skill 机制的最小要素

如果不用现成平台,自己在 Agent 里实现「skill」需要四件事:

```text
1. 注册表：扫描 skills/ 目录，抽取每个 SKILL.md 的 name+description → 组成 L1 目录
2. 路由：把 L1 目录放进 system prompt，或用一个轻量检索/分类器挑候选 skill
3. 加载：命中时 read SKILL.md 全文注入（L2）；正文引用文件时再 read（L3）
4. 执行：提供 code execution 环境跑 skill 附带的脚本，结果回填上下文
```

这几乎就是 [23-Tool Gateway](./23-Tool%20Gateway与工具平台专题.md) 里 Tool Retrieval + [04.2 上下文工程](./04.2-Agent上下文工程.md) 的组合复用,不需要全新基础设施。

---

## 七、设计原则

1. **description 决定成败**。它是唯一常驻的路由信号。写触发条件(「当…时使用」)+ 能力概述,含用户会用的关键词;避免只写「一个很有用的工具」。
2. **一个 skill 一件事**。职责单一才好触发、好复用、好组合。把「报销」和「排班」塞进一个 skill,description 无法精准路由。
3. **确定性下沉到脚本**。凡是有唯一正确答案的步骤(格式转换、字段抽取、校验计算)写成脚本;让模型做判断,不让模型做算术。
4. **正文分层,别堆砌**。SKILL.md 正文控制在「一屏能读完的流程」,细节规范拆到 L3 文件用 link 指过去,保护 L2 预算。
5. **可组合优于大而全**。多个小 skill 能被模型同时激活组合,好过一个巨型 skill。
6. **把 skill 当代码治理**。version、review、测试、权限——skill 里可以有可执行代码和敏感流程,属于供应链的一部分,见第九节。

**反模式**:把 skill 写成「第二份 system prompt」(全塞正文,失去渐进披露);description 含糊导致永不触发或到处误触发;确定性步骤仍让模型手搓;skill 里硬编码密钥或越过 Tool Gateway 直连高危系统。

---

## 八、核心问题（含解答）

### Q1：Skill、Tool、MCP、RAG 到底怎么分工？

一句话:**RAG 查事实,Tool 做动作,MCP 接系统,Skill 教做法**。

- 用户问「Q3 营收多少」→ 事实检索,RAG。
- 用户说「给这张订单退款」→ 原子动作,Tool(经 Gateway)。
- 「把公司 Jira 接进来」→ 接入协议,MCP。
- 「按公司规范生成一份季度合规报告」→ 一套多步流程 + 校验 + 模板,Skill(内部会用到 RAG 查数据、Tool 写文件)。

判断口诀:**要一个答案用 RAG,要一个动作用 Tool,要一整套怎么做用 Skill。**

### Q2：渐进式披露为什么能省这么多 token？

因为**成本和数量解耦**。传统「全塞 prompt」下,能力数 N 直接乘进常驻 token,N 大了既贵又触发 Lost in the Middle。渐进式披露把常驻成本压到「N × 一句 description」(L1),只有命中的少数 skill 才付 L2/L3 全额。于是 Agent 可以「会几百件事」,而每轮上下文只为「当前这件事」付费。这是把上下文从「装满所有可能」改成「按需装当前需要」,和 [04.2 上下文工程](./04.2-Agent上下文工程.md) 的按需注入是同一思路。

### Q3：skill 里的脚本和普通工具有什么区别？

工具是**预先注册、有 schema、走 Tool Gateway 治理**的一等动作;skill 脚本是**随 skill 附带、在代码执行环境里跑的实现细节**。区别在治理面和意图:

- 工具面向「模型每一步都可能选它」,所以要 schema、权限、幂等、审计。
- skill 脚本面向「这个流程内部的确定性步骤」,模型不是在「选择调用它」,而是在「执行这个流程时用到它」。

实践里两者会协作:skill 脚本负责本地确定性处理(解析 PDF),真正对外的高危动作(发起支付)仍应封成工具走 Gateway。**不要用 skill 脚本绕过 Gateway 直连生产系统。**

### Q4：怎么防止 skill 之间冲突或误触发？

三招:
1. **description 精准 + 加反例**。正文「何时用/何时不用」直接降低误触发。
2. **职责单一 + 命名不重叠**。避免两个 skill 的触发域交叉。
3. **可观测**。记录每轮激活了哪些 skill(见 [07 可观测](./07-评估与可观测性.md)),把「该触发没触发 / 不该触发却触发」纳入 [24-Eval Harness](./24-Agent%20Eval%20Harness专题.md) 的回归集,像评估工具选择一样评估 skill 路由准确率。

### Q5：Skill 会不会带来新的安全面?

会,而且是**能力封装特有的供应链风险**。skill 可携带可执行脚本和「怎么做」的指令,一个被投毒的 skill 相当于往 Agent 里注入了既有指令又有代码的载荷——比工具投毒更强。控制点:

- skill 来源可信、经 review、version 锁定(类比依赖治理)。
- 脚本在沙箱里跑,遵守 [23](./23-Tool%20Gateway与工具平台专题.md) 的文件/网络/命令边界。
- skill 内容纳入 [27-Agent安全生命周期](./27-Agent安全生命周期专题.md) 的威胁建模:把「第三方 skill」当作不可信输入的一种。
- 敏感动作始终经 Tool Gateway + HITL,skill 无权绕过。

---

## 九、场景设计题（含答案）

### 场景 1：企业内部「合规报告生成」Agent

**题目**：财务团队要一个 Agent,能按公司规范生成月度合规报告——取数、按固定模板排版、跑几项合规校验、超阈值走审批。规范文档很长且季度更新,报告格式严格。怎么用 Skill 设计?

**思路**：
1. **不塞 prompt**:整套规范和模板太长,塞进常驻 prompt 既贵又难维护。做成一个 `compliance-report` skill。
2. **分层**:
   - L1 description:「当需要生成月度/季度合规报告时使用,负责取数、按公司模板排版并跑合规校验」。
   - L2 SKILL.md:主流程(取数 → 校验 → 排版 → 复核 → 超阈值 HITL)。
   - L3:`rules.md`(长规范,季度更新只改这个文件)、`template.docx`、`validate.py`(确定性合规校验)、`render.py`(确定性排版)。
3. **分工**:取数用现有 RAG/DB 工具;校验和排版用脚本(确定性);「哪些数字异常需要人看」的判断留给模型。
4. **治理**:金额/风险超阈值 → Tool Gateway + HITL;skill 版本随规范季度更新走 review;报告生成过程记 trace。
5. **收益**:平时这个 skill 只花几十 token 常驻;只有真做报告时才加载全套;规范更新只动 L3 一个文件,不碰 Agent 主体。

### 场景 2：给编码 Agent 配「项目专属做法」

**题目**：一个 Claude Code 风格的编码 Agent,在你的仓库里总是不按团队约定(用错测试框架、漏掉迁移脚本、PR 描述格式不对)。怎么治?

**思路**：
- **全局稳定约定 → AGENTS.md/CLAUDE.md**(始终生效):技术栈、目录约定、禁改文件。见 [15](./15-AI%20Coding%20Harness最佳实践.md)。
- **专项流程 → skill**(按需):
  - `db-migration` skill:改 schema 时的完整流程 + `gen_migration.py`。
  - `pr-checklist` skill:提 PR 前的验证脚本和描述模板。
- **为什么拆开**:把所有专项流程都塞 AGENTS.md 会让常驻指令臃肿且互相干扰;拆成 skill 后,只有「正在做迁移」时才加载迁移做法。
- **评估**:把「改了 schema 有没有触发 db-migration skill」做成 eval 用例,回归防退化。

**核心判断**:全局且始终成立的 → 常驻指令;局部且按任务成立的 → skill。

---

## 十、自测清单

- [ ] 用一句话分别说清 Prompt / Tool / MCP / Skill / Subagent 各提供什么。
- [ ] 讲清渐进式披露的三层,以及每层何时进上下文、成本量级。
- [ ] 解释为什么「装 100 个 skill」几乎不增加空闲上下文开销。
- [ ] 说明 description 为什么是整个机制里最关键的一句话。
- [ ] 给一个具体任务,判断该做成 Tool 还是 Skill,并说明理由。
- [ ] 说清 skill 脚本和注册工具在治理上的区别,以及为什么脚本不能绕过 Tool Gateway。
- [ ] 列出 skill 引入的供应链安全风险和三条控制点。
- [ ] 设计一个 skill 的目录结构:哪些内容放 L2 正文、哪些下沉到 L3 文件或脚本。

---

## 十一、关键术语 Cheat Sheet

| 术语 | 含义 |
|---|---|
| Skill | 可按需加载的能力单元:指令 + 可选脚本/资源,打包成文件夹 |
| Progressive Disclosure | 渐进式披露:metadata → 正文 → 资源脚本 三层按需加载 |
| SKILL.md | skill 入口文件:YAML frontmatter(name/description)+ markdown 流程正文 |
| description | L1 常驻的路由信号,决定 skill 何时被激活 |
| L1 / L2 / L3 | metadata 常驻 / 正文按命中加载 / 资源脚本按用到加载 |
| Skill 脚本 | 随 skill 附带、在代码执行环境跑的确定性实现 |
| Composability | 可组合:模型可同时激活多个 skill 协作完成任务 |
| Skill 供应链风险 | skill 携带指令+代码,被投毒相当于强注入,需 review/版本/沙箱治理 |

---

## 十二、延伸阅读

- Anthropic — Agent Skills 文档与工程博客(2025)
- Anthropic — Claude Code skills / subagents 文档
- 本库关联:[03 工具调用](./03-工具调用.md)、[03.1 MCP](./03.1-MCP.md)、[04.2 上下文工程](./04.2-Agent上下文工程.md)、[15 AI Coding Harness](./15-AI%20Coding%20Harness最佳实践.md)、[23 Tool Gateway](./23-Tool%20Gateway与工具平台专题.md)、[24 Eval Harness](./24-Agent%20Eval%20Harness专题.md)、[27 安全生命周期](./27-Agent安全生命周期专题.md)

---

## 十三、核心要点

1. **Skill 是能力封装的第三条路**:不是动作(Tool)、不是接入(MCP)、不是事实(RAG),而是「面对某类任务的做法包」。
2. **渐进式披露是它的灵魂**:三层按需加载,让常驻成本和能力数量解耦,Agent 得以「会几百件事」而每轮只为当前任务付费。
3. **description 是路由信号**:整个机制里唯一常驻、决定触发的一句话,写好它比写长正文更重要。
4. **确定性下沉到脚本,判断留给模型**:和「能验证就别只靠模型自觉」是同一工程哲学。
5. **Skill 不取代 Tool Gateway 和安全治理**:它是攻略不是门禁;携带代码的 skill 属于供应链,要按代码治理和威胁建模来管。
