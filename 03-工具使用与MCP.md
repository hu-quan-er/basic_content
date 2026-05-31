# 工具使用与 MCP

> 目标：掌握 Function Calling 的工程细节、工具治理方案、以及 MCP 协议的设计动机。

---

## 一、核心概念

### 1.1 工具（Tool）的本质
- **Tool = LLM 的"手"**：模型只产出意图（JSON），实际执行由宿主程序完成
- **三层契约**：
  - **Schema**（机器接口）：name、description、parameters JSON Schema
  - **描述**（给 LLM 看的接口）：自然语言指引模型何时如何调用
  - **实现**（实际执行）：宿主代码 / API / RPC

### 1.2 工具调用的完整生命周期
```
1. Schema 注入   → 把所有可用工具的 schema 加入 system prompt
2. 模型决策      → LLM 输出 tool_call(name, arguments)
3. 调用解析      → 宿主程序解析 JSON、校验 schema
4. 实际执行      → 调用真实函数 / API
5. 结果回填      → 把结果作为 tool_result message 传回
6. 继续推理      → LLM 基于结果继续生成（可能再调工具，或最终回答）
```

### 1.3 工具描述的最佳实践（重点）
- **name**：动词开头、snake_case、唯一明确（`search_orders` 而非 `query`）
- **description**：
  - 第一句讲清楚"做什么"
  - 第二句讲清楚"何时调用"（边界）
  - 列出反例（"不要用此工具查 X"）
- **参数**：
  - 类型严格（Enum 优于 string）
  - description 字段必填，给出格式示例
  - 必填 vs 可选要明确
- **示例**：
```json
{
  "name": "search_orders",
  "description": "Search user orders by date range. Use this when user asks about purchase history, refunds, or shipping status. Do NOT use for product inventory queries (use search_products instead).",
  "parameters": {
    "user_id": {"type": "string", "description": "User UUID, e.g., 'usr_abc123'"},
    "start_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
    "status": {"type": "string", "enum": ["pending", "shipped", "delivered", "cancelled"]}
  }
}
```

### 1.4 工具选择的三大失败模式
1. **描述模糊**：两个工具描述重合 → 模型选错
2. **参数歧义**：模型猜参数（如把"昨天"猜成 `date="yesterday"` 字符串）
3. **工具过多**：超过 20+ 工具，模型 attention 稀释，选择质量明显下降

### 1.5 并行工具调用（Parallel Tool Calling）
- **能力**：一次输出多个 tool_call（OpenAI / Claude 都支持）
- **使用场景**：独立查询（"查北京和上海的天气"）
- **限制**：
  - 模型未必每次都用并行（依赖训练）
  - 有依赖的调用不能并行（结果 A 才能确定调用 B）
- **工程实现**：宿主代码用 `asyncio.gather` / `Promise.all` 并发执行

### 1.6 工具结果处理
- **成功**：直接回填 JSON 结果
- **失败**：
  - **可重试错误**（网络、超时）→ 宿主层重试，模型不感知
  - **业务错误**（参数错误、资源不存在）→ 把错误信息回填，让模型自主修正
  - **致命错误**（权限、配额） → 直接返回错误给上层，不让 Agent 继续
- **大结果**：截断 + 摘要（不要把 10MB 的查询结果原样喂给 LLM）

### 1.7 Tool Retrieval（工具检索 / Tool RAG）
**问题**：工具数 > 30 时，全量注入 prompt 导致：
- Token 浪费
- 选择准确率下降
- Lost in the Middle 影响

**解法**：把工具描述 embedding 化，按用户问题召回 top-k 工具，只把这 k 个注入 prompt。

**实现要点**：
- 每个工具一条 embedding（基于 name + description）
- 召回数量：通常 top 5~10
- 召回 → 二次确认（让小模型 / 规则判断）→ 再注入大模型
- 适合工具数百以上的场景（企业内部接入大量 API）

### 1.8 MCP（Model Context Protocol）

#### 1.8.1 设计动机
**问题**：每个 LLM 应用都自己实现工具集成，导致：
- 重复造轮子
- 工具无法跨应用复用
- 生态碎片化

**MCP 类比 USB-C**：标准化 LLM 应用与外部资源/工具/上下文的连接协议。

#### 1.8.2 架构
```
[LLM App / Host]  ←→ [MCP Client]  ←→ [MCP Server]  ←→ [真实工具/数据]
  e.g., Claude Desktop                  e.g., GitHub MCP server
```
- **Host**：使用 LLM 的应用（Claude Desktop、Cursor、自研 Agent）
- **Client**：嵌在 Host 中，负责与 Server 通信（JSON-RPC over stdio / SSE / HTTP）
- **Server**：暴露资源、工具、提示，运行在本地或远程

#### 1.8.3 三种能力原语
| 原语 | 说明 | 例子 |
|------|------|------|
| **Tools** | 可被 LLM 调用执行的函数 | `create_issue`、`run_sql` |
| **Resources** | LLM 可读取的只读数据 | 文件、数据库表、API 响应 |
| **Prompts** | 预设的提示模板 | "code review prompt"、"bug triage prompt" |

#### 1.8.4 价值
- **工具复用**：写一次 MCP server，所有支持 MCP 的客户端都能用
- **生态分工**：服务方提供 MCP server，应用方专注 Agent 逻辑
- **权限可控**：用户可显式授权某个 server，避免应用任意调用

#### 1.8.5 局限
- 标准还在演进，2024 末才发布
- 仍需宿主端做工具发现、调度
- 不解决工具选择质量问题（模型层面的）

### 1.9 沙箱执行（Code Execution）
当 Agent 需要执行用户代码（如 Code Interpreter）：
- **隔离要求**：禁文件系统、禁网络、禁系统调用
- **常用方案**：
  - **Docker 容器**：传统但启动慢
  - **Firecracker microVM**：AWS Lambda 同款，秒级启动
  - **E2B / Modal / Daytona**：托管沙箱服务
  - **Pyodide / WASM**：浏览器侧执行
- **关键约束**：CPU/内存配额、执行超时、网络白名单

---

## 二、主流实现要点

### 2.1 各家工具调用 API 对比
| 厂商 | 协议特点 | 并行调用 | 强 Schema |
|------|----------|----------|-----------|
| OpenAI | `tools` + `tool_choice` | 默认开 | Structured Output |
| Anthropic | `tools` + `tool_use` block | 支持 | input_schema 强制 |
| Gemini | `function_declarations` | 支持 | 较弱 |
| 国产（DeepSeek、Qwen） | OpenAI 兼容格式 | 部分支持 | 不稳 |

### 2.2 LangChain @tool 装饰器
```python
from langchain_core.tools import tool

@tool
def search_orders(user_id: str, start_date: str) -> list:
    """Search user orders by date range."""
    ...
```
- 函数 docstring → tool description
- 参数 type hint + Pydantic → schema
- 跨多家 LLM 复用

### 2.3 MCP 生态
- **已有 server**（社区）：GitHub、GitLab、Slack、Postgres、SQLite、文件系统、Puppeteer、Brave Search
- **Host**：Claude Desktop（首发支持）、Cursor、Continue、Cline、Zed
- **SDK**：Python、TypeScript、Java、Kotlin

### 2.4 OpenAI Assistants API 内置工具
- **Code Interpreter**：Python 沙箱
- **File Search**：内置 RAG
- **Function Calling**：自定义工具
- 优点：开箱即用；缺点：黑盒、不可控、迁移困难

---

## 三、高频面试题（含答案）

### Q1：工具描述怎么写才能让模型准确调用？

**答**：

**结构上**：
1. **第一句讲做什么**：动词开头，明确动作
2. **第二句讲何时调用**：边界条件
3. **第三句讲何时不要调用**：反例（很重要）
4. **参数都要 description**：包括格式、单位、示例

**反面案例**：
```
search: 搜索数据
```
↓
**正面案例**：
```
search_orders: Search user orders by date range. 
Use when user asks about purchase history, refunds, or shipping. 
Do NOT use for product inventory (use search_products instead).
```

**进阶技巧**：
- 用 **few-shot**：在 system prompt 里给 1~2 个调用示例
- 用 **Enum** 收紧参数空间
- 测试时主动构造**歧义场景**（"我想看上次买的东西" — 是 search_orders 还是 search_products？）

**评估方法**：建一个 "用户问题 → 期望调用" 的测试集，跑准确率，每次改 description 都回归。

---

### Q2：50+ 工具的 Agent，怎么治理？

**答**：

**单 Agent 全量注入是行不通的**，三种治理路线：

**路线 1：Tool Retrieval（推荐）**
- 把工具 description embedding 化
- 用户问题来时，先检索 top-10 工具
- 只把这 10 个注入 LLM
- 实现：用 BM25 + 向量混合检索，效果最好

**路线 2：分层 Agent**
- **Router Agent**：只决定走哪个子领域（订单、商品、售后）
- **子 Agent**：各自只看本领域的工具（5~10 个）
- 适合：工具天然按领域分组

**路线 3：组合命名空间 + 渐进披露**
- 工具按 namespace 组织（`orders.search`、`orders.refund`）
- 系统提示先给 namespaces 列表
- LLM 先选 namespace，再展开其下的工具
- MCP 的方向（每个 server 是一个 namespace）

**实战经验**：
- 工具数 < 20：全量注入即可
- 20~50：开始考虑 retrieval
- 50+：必须 retrieval / 分层
- 100+：分层 + retrieval 组合

---

### Q3：MCP 解决了什么问题？相比直接定义 tools 的价值？

**答**：

**MCP 解决的问题**：
**工具集成的碎片化**。在 MCP 之前，每个 LLM 应用都要自己实现：
- GitHub 工具
- Slack 工具
- 数据库工具
- 文件系统工具
- ...

应用之间不能共享，重复劳动。

**MCP 的核心价值**：
1. **协议标准化**：JSON-RPC + 三种原语（Tools / Resources / Prompts）
2. **生态分工**：工具提供方写 MCP server，应用方专注 Agent 逻辑
3. **进程隔离 + 安全**：MCP server 独立进程，权限可显式授权
4. **跨应用复用**：写一次，Claude Desktop / Cursor / Cline 都能用

**相比直接 tools 的差异**：
- 直接 tools：紧耦合，工具代码在应用内
- MCP：松耦合，工具代码在独立 server

**何时用 MCP**：
- 公司有多个 Agent 应用，复用同一批工具 → 用 MCP
- 单一 Agent 应用 + 工具是私有的 → 直接 tools 更简单

**MCP 的局限**：
- 协议年轻，工具质量参差
- 不解决"模型选错工具"的问题（那是模型 + prompt 的事）
- 性能略损（IPC 开销）

---

### Q4：工具调用失败如何兜底？

**答**：

**分三类错误，分别处理**：

**1. 临时性错误（网络、超时、429）**
- 宿主层指数退避重试（3 次）
- **模型不感知**：避免污染 reasoning
- 超过重试上限 → 转为业务错误回填

**2. 业务错误（参数错、404、422）**
- 把**结构化错误信息**回填给模型
```json
{"error": "Order not found", "code": "ORDER_404", "hint": "Check order_id format: order_xxx"}
```
- 让模型自主调整重试
- **重试上限**：同一工具同一参数失败 ≥ 2 次 → 强制跳出

**3. 致命错误（权限、配额、系统故障）**
- 立即终止 Agent
- 返回用户友好错误
- 触发告警

**整体策略**：
```
TOOL_RETRY_POLICY = {
  "max_total_calls": 20,       # 全程工具调用上限
  "max_same_tool": 5,          # 同一工具上限
  "max_same_args": 2,          # 同参数重试上限  
  "transient_retry": 3,        # 临时错误重试
  "timeout_per_call": 30,      # 单次调用超时
}
```

**降级**：所有兜底都失败 → 返回"暂时无法处理，已记录工单" + 人工接管。

---

### Q5：并行工具调用什么时候有用？什么时候有坑？

**答**：

**有用**：相互独立的查询
- "查北京和上海的天气" → 并行两次 `get_weather`
- "获取这 5 个仓库的 stars" → 并行 5 次 `get_repo_stats`
- 收益：延迟从 N×单次 降到 max(单次)

**有坑**：
1. **隐性依赖**：模型可能误判为可并行，但实际有依赖（B 需要 A 结果）
2. **副作用工具**：写操作并行可能导致竞态（如并发更新同一资源）
3. **资源限制**：API rate limit、数据库连接数
4. **错误处理复杂**：5 个并行，1 个失败，怎么处理？

**工程实践**：
- 只读 / 幂等工具：标记为 `parallel_safe=True`，允许并行
- 写操作：默认串行，必要时显式标记
- 实现：宿主端按 schema 决定是 `asyncio.gather` 还是顺序执行
- 错误：单个失败用 `return_exceptions=True` 收集，部分成功也能继续

---

### Q6：怎么设计一个支持 100+ 内部 API 接入的工具层？

**答**：

**分层架构**：

```
┌──────────────────────────────────────┐
│ Layer 4: Agent 编排层（LangGraph）    │
├──────────────────────────────────────┤
│ Layer 3: 工具治理层                   │
│  - Tool Registry（统一注册中心）       │
│  - Tool Retrieval（RAG 召回）         │
│  - Permission（权限校验）              │
├──────────────────────────────────────┤
│ Layer 2: 协议适配层                   │
│  - OpenAPI → Tool Schema 自动转换     │
│  - MCP server 包装                    │
├──────────────────────────────────────┤
│ Layer 1: 真实 API                     │
└──────────────────────────────────────┘
```

**关键设计**：

1. **OpenAPI → Tool Schema 自动转换**
   - 内部 API 都有 OpenAPI / Protobuf 定义
   - 写转换器自动生成 tool description（基于 endpoint summary、param description）
   - **痛点**：自动生成的 description 模型友好度差，要人工润色一遍

2. **分领域 namespace**
   - `crm.*`、`order.*`、`finance.*`
   - 每个 namespace 对应一个 MCP server（或一组 tools）

3. **两阶段调用**
   - 第一阶段：LLM 选 namespace（基于元描述）
   - 第二阶段：LLM 在该 namespace 内选具体 tool

4. **权限模型**
   - 工具元数据标注 required_permissions
   - Agent 运行前根据当前用户 token 过滤可用工具集
   - 敏感工具（如转账）强制 HITL

5. **可观测性**
   - 每次调用记录：tool_name、args、user、latency、success
   - 离线分析：哪些工具被高频误调？哪些工具描述需要优化？

6. **评估**
   - 建"用户问题 → 期望工具序列"的回归集
   - 每次新增 / 修改工具描述后回归

---

### Q7：Code Interpreter 类工具的安全风险？怎么防？

**答**：

**风险点**：
1. **任意代码执行** — 用户输入直接跑
2. **逃逸到宿主** — 容器逃逸、内核漏洞
3. **数据泄露** — 读取宿主文件、敏感环境变量
4. **滥用资源** — 死循环、内存炸弹、加密货币挖矿
5. **网络滥用** — 内网扫描、外联 C2

**防御层**：

1. **隔离运行时**
   - Docker 容器（基础）
   - Firecracker / gVisor microVM（更强）
   - 一次性容器：每次执行新建，结束销毁

2. **配额限制**
   - CPU：cgroup 限 1 core
   - 内存：512MB
   - 时间：30s 超时
   - 磁盘：临时目录限 100MB，只读根

3. **网络策略**
   - 默认无网
   - 必要时白名单（pypi.org 安装包）
   - 内网禁止访问

4. **文件系统**
   - 只读根
   - 可写区限定 /tmp
   - 用户上传文件挂载只读

5. **包管理**
   - 预装常用包（numpy、pandas）
   - 禁止 pip install 任意包（或仅 PyPI 白名单）

6. **审计与监控**
   - 全量日志：源代码、stdout、stderr
   - 异常告警：高 CPU、内存接近上限、网络外联

7. **托管方案**：
   - **E2B**：专业沙箱，提供 SDK
   - **Modal**：函数即服务
   - **Daytona**：开发环境沙箱

---

## 四、场景设计题（含答案）

### 场景 1：企业接入 200+ 内部 API

**题目**：公司有 200+ 内部 API（CRM、ERP、HR、财务等），要让 Agent 能调用，给出完整方案。

**答案**：

**架构**：

```
[用户]
   ↓
[Agent Orchestrator (LangGraph)]
   ↓
[Tool Gateway]
   ├─ Tool Registry（统一目录）
   ├─ Tool Retrieval（向量召回 top-15）
   ├─ Permission Filter（基于用户角色）
   ├─ Audit Logger
   └─ Rate Limiter
   ↓
[MCP Servers，按业务域分]
   ├─ crm-server  （20 tools）
   ├─ erp-server  （40 tools）
   ├─ hr-server   （30 tools）
   ├─ finance-server（50 tools）
   └─ ...
   ↓
[真实 API]
```

**关键决策**：

1. **工具描述**：
   - 用 OpenAPI 自动生成 → 人工润色 high-traffic API
   - 投入比例：top 20% API 占 80% 调用，重点优化

2. **召回机制**：
   - 用户问题向量化
   - 召回 top-15 工具（覆盖 95% 真实需求）
   - 注入 LLM 时按 namespace 分组展示

3. **权限**：
   - 每个 tool 元数据中标 `required_roles`
   - 用户 SSO 后获取角色集，过滤工具
   - 敏感操作（转账、删除）强制 HITL 二次确认

4. **可观测**：
   - 每次工具调用记录 trace
   - 离线指标：召回准确率、工具调用准确率、平均链长
   - 误调用 case 自动入库供 prompt 优化

5. **演进路径**：
   - Phase 1：高频 20 个 API 上线，验证模式
   - Phase 2：按域扩展到 100
   - Phase 3：全量 200，引入 Tool RAG
   - Phase 4：建立工具评分体系，持续优化

**风险**：
- LLM 可能调错工具 → 用单元测试 + LLM-as-Judge 持续评估
- API 变更 → CI 接入 OpenAPI 变更检测，自动重生成 schema

---

### 场景 2：金融数据分析 Agent

**题目**：要做一个能"查公司财报 → 计算指标 → 生成图表"的 Agent，怎么设计工具？

**答案**：

**工具集设计**：

1. **数据获取工具**
   - `get_company_financials(ticker, year, quarter)` — 财报 API
   - `get_stock_price(ticker, date_range)` — 行情 API
   - `get_news(ticker, days)` — 新闻 API

2. **计算工具**
   - `calculate_ratio(numerator, denominator, name)` — 通用比率
   - `compare_periods(metric, current, previous)` — 同比环比
   - **关键**：复杂计算用 **Code Interpreter** 而非穷举写工具

3. **可视化工具**
   - `generate_chart(type, data, title)` — 图表生成（背后是 matplotlib/echarts）

4. **辅助工具**
   - `web_search(query)` — 兜底搜索
   - `current_date()` — 当前时间（避免模型幻觉）

**关键决策**：

- **优先用 Code Interpreter**：复杂分析（多步骤计算、自定义指标）让 LLM 写 Python 跑，比为每个指标写一个工具灵活得多
- **数据格式统一**：所有数据工具返回 Pandas DataFrame 序列化 JSON，便于 Code Interpreter 直接用
- **缓存**：财务数据是确定性的，加缓存层（同一公司同一季度结果不变）
- **结果尺寸控制**：财报数据可能很大，工具内部摘要 / 抽样后返回

**安全**：
- Code Interpreter 沙箱（E2B）
- 只允许预装的数据科学包
- 输出图表存对象存储，返回 URL

**评估**：
- 建"问题 → 期望分析结果"测试集（如 "苹果 2024Q4 营收同比" → 精确答案）
- 数字准确率 + 推理过程评估

---

## 五、自测清单

- [ ] 工具描述的最佳实践（结构 4 要素）
- [ ] 工具选择的三大失败模式
- [ ] 50+ 工具的三种治理路线
- [ ] MCP 的三种能力原语（Tools / Resources / Prompts）
- [ ] MCP 解决的核心问题（碎片化）
- [ ] 工具调用错误的三分类处理策略
- [ ] 并行工具调用的适用与坑
- [ ] Code Interpreter 沙箱的 7 层防御

---

## 六、延伸阅读

- Anthropic — *Model Context Protocol Specification*
- OpenAI — *Function Calling Guide*
- Anthropic — *Tool Use with Claude*
- Schick et al. — *Toolformer: Language Models Can Teach Themselves to Use Tools*
- Patil et al. — *Gorilla: Large Language Model Connected with Massive APIs*
