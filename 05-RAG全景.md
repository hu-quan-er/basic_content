# RAG 全景

> 目标：从朴素 RAG 到 Advanced / Modular / Agentic RAG 的完整图景，能针对场景做架构决策。

---

## 一、核心概念

### 1.1 为什么需要 RAG
- **知识截止**：LLM 训练数据有时间边界
- **私有知识**：企业内部数据不在公开训练集
- **可解释**：能给出 citation
- **更新便宜**：改文档比改模型权重便宜几个数量级
- **降低 hallucination**：答案 grounded 在真实文档

### 1.2 RAG 的三阶段
```
[Indexing 索引阶段]
  文档 → 切分 → embedding → 存入向量库

[Retrieval 检索阶段]
  查询 → embedding → 召回 top-k → 重排 → 过滤

[Generation 生成阶段]
  组装 prompt（查询 + 上下文）→ LLM 生成 → 后处理（引用、校验）
```

### 1.3 RAG 演进：Naive → Advanced → Modular → Agentic

#### Naive RAG（朴素）
- 固定切分 + 单次检索 + 直接生成
- 问题：召回质量差、上下文塞太多噪声

#### Advanced RAG（进阶）
对 Naive RAG 每个环节做优化：
- **Pre-retrieval**：query 改写、HyDE、multi-query
- **Retrieval**：hybrid 检索（dense + sparse）、metadata 过滤
- **Post-retrieval**：rerank、compression、重排序

#### Modular RAG（模块化）
- 把 RAG 拆成可组合的模块（搜索、记忆、融合、路由）
- 支持非线性流程（条件分支、循环）
- 是 Advanced 的工程化抽象

#### Agentic RAG（智能化）
- **Agent 主导**检索决策
- 决定：要不要检索？查什么？查几次？什么时候停？
- 用工具调用形式发起检索
- 适合：复杂推理 + 多跳查询

### 1.4 切分（Chunking）策略
| 策略 | 思路 | 适用 |
|------|------|------|
| **Fixed** | 固定 token 数（512） | 通用、简单 |
| **Recursive** | 递归按 `\n\n` → `\n` → ` ` 切 | 半结构化文档 |
| **Semantic** | 按语义相似度切（相邻句相似度低则切） | 长形论文 / 报告 |
| **Document-aware** | 按文档结构切（Markdown header、code function） | 代码 / Markdown |
| **Parent-Child** | 小块检索、大块返回 | 精度 + 上下文兼顾 |
| **Sentence Window** | 单句索引 + 邻近句作上下文 | 精度优先 |
| **Summary Index** | 给每个 chunk 生成摘要，摘要索引 → 全文返回 | 长文档 |

**实战经验**：
- 起步用 Recursive 500~1000 token + 100 token overlap
- 代码 / 表格 / 公式要 document-aware
- Chunk 太大 → 召回精度低；太小 → 上下文不全
- 没有银弹，要 A/B

### 1.5 Embedding
**关键决策**：
- **维度**：768 / 1024 / 1536 / 3072 — 维度越高一般越好但成本高
- **多语言**：bge-m3、multilingual-e5、voyage-multilingual
- **领域适配**：通用 embedding 在法律、医疗等专业领域可能差，需要微调
- **API vs 自部署**：API 简单但贵且数据出去；自部署可控但要 GPU

**评估**：用 BEIR、MTEB benchmark 横向对比；自己数据上建小测试集做最终选择。

### 1.6 检索策略

#### Dense Retrieval（向量检索）
- 语义匹配，处理同义、改写
- 弱：精确匹配（数字、特定术语、罕见词）

#### Sparse Retrieval（稀疏检索）
- **BM25**：基于 TF-IDF 的经典算法
- **SPLADE**：神经 sparse retrieval
- 强：精确匹配
- 弱：语义改写

#### Hybrid Retrieval（混合）
- Dense + Sparse 各召一批，融合排序
- **融合方法**：
  - RRF（Reciprocal Rank Fusion）— 简单稳健
  - Weighted Sum — 需要分数归一化
- **实战**：通常比单独任一种高 5~15% 准确率

### 1.7 Rerank（重排）
**为什么需要**：召回（recall-oriented）和生成需要的 precision-oriented 不一致。
- 召回：top 100 大约对的
- 生成：top 5 必须真的对

**典型 Reranker**：
- **Cross-encoder**：query + doc 拼接进模型，给精确相关度分（慢但准）
- **Cohere Rerank**：API 服务，多语言强
- **BGE-Reranker**：开源
- **Jina Reranker**：开源

**架构**：召回 top-100（快） → rerank top-5（准） → 进 LLM

### 1.8 Query 侧优化

#### Query Rewriting
- 用 LLM 改写 query 以提升召回
- 例：用户问"AI 怎么写代码" → 改成"large language model code generation techniques"

#### HyDE（Hypothetical Document Embedding）
- 让 LLM 先**生成一个假想答案**
- 用假想答案做检索（而非原始 query）
- 思路：假想答案语言风格更接近真实文档
- 限制：会引入 hallucination 偏差

#### Multi-Query
- 让 LLM 生成 query 的多个变体
- 多个变体分别检索，结果合并
- 提升 recall

#### Step-back Prompting
- 让 LLM 先抽象出"更高层的问题"
- 例：用户问"我 2020 年捐了 X 是否能抵税" → step back 为"个税抵扣规则是什么"
- 用 step-back 检索更通用知识

### 1.9 后处理

#### Contextual Compression
- 对召回的 doc，用 LLM 抽取与 query 相关的部分
- 砍掉不相关内容，节省 token

#### Filtering
- 基于 metadata 过滤（时间、作者、来源）
- 基于相关度阈值过滤（score < 0.6 丢弃）

### 1.10 Agentic RAG
**核心思想**：让 Agent 自主决定检索行为。

**决策维度**：
- **是否检索**：简单问题不需要检索
- **检索什么**：基于推理拆解出多个子查询
- **检索几次**：multi-hop 问题需要迭代
- **何时停止**：信息够了再生成

**典型实现**：
- ReAct + 检索工具
- Self-RAG：模型自我评估检索结果质量
- CRAG（Corrective RAG）：检索结果差则触发 web search 兜底
- Adaptive RAG：根据 query 难度路由到不同策略

### 1.11 GraphRAG
- 知识不再以"片段"组织，而是**知识图谱**（实体 + 关系）
- 微软 2024 推出，适合：需要全局视角的问题（"这本书的核心人物关系"）
- 流程：
  1. 抽取实体 + 关系（LLM）
  2. 社区检测（图算法）
  3. 每个社区生成摘要
  4. 查询时多层级检索（社区 → 实体 → 关系）
- 代价：构建成本高，索引时大量 LLM 调用

### 1.12 评估指标
| 维度 | 指标 | 说明 |
|------|------|------|
| **检索** | Recall@K | 真相关文档在 top-K 的比例 |
| | Precision@K | top-K 中真相关的比例 |
| | MRR | 第一个相关文档的倒数排名 |
| | NDCG | 考虑排序质量 |
| **生成** | Faithfulness | 答案是否 grounded 在 context 中 |
| | Answer Relevance | 答案是否切题 |
| | Context Precision | context 中有用信息比例 |
| | Context Recall | 真答案所需信息的覆盖率 |

---

## 二、主流实现要点

### 2.1 向量库选型
| 工具 | 特点 | 适用 |
|------|------|------|
| **pgvector** | Postgres 扩展 | 中小规模、工程化首选 |
| **Pinecone** | 托管 SaaS | 快速上线 |
| **Weaviate** | 开源，schema 友好 | 复杂 metadata |
| **Qdrant** | 开源，性能强 | 高 QPS |
| **Milvus / Zilliz** | 大规模 | 亿级向量 |
| **Chroma** | 嵌入式 | 本地开发 / 小项目 |
| **ES + dense_vector** | 既有 ES 栈复用 | hybrid 检索方便 |

### 2.2 框架
- **LangChain**：组件丰富，RAG 工具链最全
- **LlamaIndex**：专注 RAG，索引能力强
- **Haystack**：模块化 pipeline
- **DSPy**：声明式 + 自动优化

### 2.3 评估框架
- **Ragas**：RAG 专属，四大指标
- **TruLens**：开源，可视化
- **DeepEval**：单元测试风格
- **LangSmith Eval**：与 trace 一体

### 2.4 文档解析
- 复杂 PDF：Unstructured、LlamaParse、PyMuPDF
- 表格：Camelot、Tabula、pdfplumber
- 扫描件 OCR：PaddleOCR、Tesseract、Azure DI
- 现代选择：用 VLM（如 GPT-4V）直接读 PDF 截图

### 2.5 常见架构
```
[文档源]
   ↓ 解析（unstructured）
[原文档]
   ↓ 切分（recursive + metadata）
[Chunks]
   ↓ embedding（voyage-3）
[Vector Store + BM25 index]

[Query]
   ↓ 改写（multi-query）
[Multiple queries]
   ↓ 检索（hybrid: dense + bm25）
[Top 100]
   ↓ Rerank（cohere-rerank-3）
[Top 5]
   ↓ Compression（LLM extract relevant）
[Compressed context]
   ↓ Prompt 组装
[LLM]
   ↓
[Answer + Citations]
```

---

## 三、高频面试题（含答案）

### Q1：检索召回了正确文档但答案还是错，怎么排查？

**答**：

**问题定位流程**：

**Step 1：确认检索是真的对**
- 看 trace：召回的 doc 里**确实有**正确答案吗？
- 还是只是"主题相关"但没答案？
- 工具：LangSmith / Langfuse 看完整 context

**Step 2：检查 context 组装**
- 文档是否被截断？关键句被砍掉？
- 排序是否合理？答案是否在 Lost-in-the-Middle 位置？
- 噪声文档是否太多稀释 attention？

**Step 3：分析生成**
- 模型是不是"不信任"上下文，回到自身知识？
  - 现象：答案与 context 矛盾但与常识符合
  - 处方：强化 grounding prompt（"Only answer based on the provided context. If not found, say 'I don't know'."）
- 模型是不是误解了 context？
  - 现象：context 里有但模型抽取错
  - 处方：context 加结构标记、关键信息高亮
- 模型上下文长度是否处理得动？
  - 现象：context 太长，关键被忽略
  - 处方：压缩 / rerank 减少塞入量

**Step 4：评估 chunk 设计**
- 答案是否被切到两个 chunk？
- 解法：增加 overlap、改用 parent-child 检索

**Step 5：模型能力问题**
- 用更强模型测试
- 如果换成 GPT-4 / Claude Opus 就对了 → 是模型瓶颈
- 还是错 → 是检索 / context 问题

**面试加分回答**：建立"检索准确率"和"生成准确率"两个独立指标分别归因，工具化测试集自动跑回归。

---

### Q2：Hybrid 检索的 BM25 和 Dense 怎么融合？权重怎么定？

**答**：

**两种融合方式**：

**1. RRF（Reciprocal Rank Fusion）— 推荐**
```
score(d) = Σ 1 / (k + rank_i(d))
```
- k 通常取 60
- 只用排名，不用原始分数（避免分数尺度问题）
- 简单、稳健、不需调参
- **首选方案**

**2. Weighted Score**
```
final = α * dense_score + (1-α) * bm25_score
```
- 需要分数归一化（min-max 或 z-score）
- α 需要调参
- 灵活但调参成本高

**权重选择经验**：
- 默认 α = 0.5 起步
- 用户 query 偏专业术语 / 数字 → BM25 权重 ↑
- 用户 query 偏口语 / 改写 → Dense 权重 ↑
- 用 grid search 在验证集上找最优

**评估方法**：
- 建测试集（query + 期望文档）
- 跑不同权重的 Recall@10、NDCG@10
- 选最高的

**工程实践**：
- 起步：RRF，零调参
- 进阶：基于 query 类型动态权重（多 router）
- 经验：Hybrid 比单一通常提升 5~15%，但**比不上 Rerank 的提升**（10~20%）

---

### Q3：Embedding 模型怎么选？什么时候需要微调？

**答**：

**选型四维度**：

1. **质量**：看 MTEB / BEIR / CMTEB（中文）
2. **维度**：1024 一般够用，3072 边际收益递减
3. **多语言**：处理多语数据用 multilingual 模型
4. **领域**：通用 vs 专业（法律、医疗、代码）

**主流选择**：
- **闭源 API**：OpenAI text-embedding-3、Voyage-3、Cohere embed-v3
- **开源**：BGE-M3、E5-large、Jina
- **代码专用**：Voyage-code、jina-embeddings-v2-code

**什么时候微调**：

✅ **需要微调**：
- 领域强专业，开源/通用模型在你数据上 Recall < 70%
- 数据有特殊格式（如电商 SKU 编码）
- 公司有 ≥ 10000 标注 pair（query-doc 对）
- 评估发现"标准库换了也提不上"

❌ **不需要微调**：
- 用 BGE-M3 / Voyage-3 已经 Recall > 90%
- 标注数据少
- 想快速迭代

**微调方法**：
- **Contrastive Learning**：positive pair（相关）+ negative pair（不相关）
- **数据来源**：用户点击日志、人工标注、LLM 生成
- **框架**：sentence-transformers、FlagEmbedding

**替代方案**（比微调便宜）：
- 用 reranker 修正（cohere-rerank-3、bge-reranker）— 通常比 finetune embedding 性价比高
- 用 query rewriting 适配 embedding 分布

---

### Q4：什么时候用 Agentic RAG 而非传统 RAG？

**答**：

**传统 RAG**：单次检索 + 一次生成
- 适合：直接问答（"X 是什么？")、简单查找

**Agentic RAG**：模型自主决策检索
- 适合：复杂、多跳、需要推理的问题

**用 Agentic RAG 的信号**：

1. **多跳问题**
   - "我们公司去年卖得最好的产品的供应商是谁？"
   - 需要先查"卖得最好的产品" → 再查"该产品的供应商"

2. **不确定是否要检索**
   - "1+1 等于几" → 不需要检索
   - "我们公司销售政策是什么" → 需要检索
   - Agentic RAG 让模型自己判断

3. **需要迭代精化**
   - 第一次召回不够 → 改写 query 再检索
   - 类似人类研究行为

4. **多源融合**
   - 部分信息在知识库，部分需要 web search
   - 模型选择数据源

5. **置信度自评估**
   - Self-RAG：模型评估每段 retrieval 是否真相关
   - CRAG：评估差则触发兜底

**代价**：
- LLM 调用次数 ≥ 3x 传统 RAG
- 延迟 ≥ 2x
- 流量大、简单任务多 → 慎用

**实战路线**：
- 80% 简单问题用传统 RAG（便宜快）
- 20% 复杂问题用 Agentic RAG
- 路由层根据 query 复杂度分流（Adaptive RAG）

---

### Q5：长文档 RAG 怎么设计？

**答**：

**核心挑战**：
- 单个 chunk 容易丢上下文
- 跨章节关联难捕捉
- 表格 / 图表 / 公式

**多策略组合**：

**1. 多层级索引**
```
Doc → Sections → Paragraphs → Sentences
```
每级都建索引，检索时按问题粒度选层级。

**2. Parent-Child Retrieval**
- 小 chunk 用于精确召回
- 召回后返回其父 chunk（大上下文）
- 实现：每个小 chunk metadata 存 parent_id

**3. Hierarchical Summarization**
- 每章生成摘要 → 摘要也入库
- 检索先在摘要层定位，再钻入细节

**4. Document-aware Chunking**
- 按 Markdown header / PDF 章节切
- 保留 section title 作为 metadata（注入 chunk 时带上）

**5. Metadata 丰富化**
- 每 chunk 标注：文档标题、章节、页码、时间
- 检索时可按 metadata 过滤

**6. 表格 / 图表特殊处理**
- 表格用 markdown 格式存储 + 单独 metadata
- 图表用 VLM 描述生成 alt text
- 公式保留 LaTeX

**7. 跨文档关联**
- 实体抽取 + 共现统计
- 类似 GraphRAG，建图谱

**8. 查询策略**
- Step-back：先问"这本书 / 文档讲了什么"再细问
- Multi-query：拆问题为多个子查询
- Outline-first：让 LLM 先看大纲再精读

---

### Q6：怎么处理 RAG 中的引用与归因？

**答**：

**为什么重要**：
- 合规（医疗、法律必须可追溯）
- 用户信任（"基于哪份文档说的"）
- 错误归因（哪个文档误导了模型）

**实现方式**：

**1. Prompt 级别**
```
For each statement, cite the source using [doc_id]. 
Only state facts from the provided context.
```
- 优点：简单
- 缺点：模型可能错引、漏引

**2. 结构化输出**
```json
{
  "answer": "...",
  "citations": [
    {"claim": "...", "source": "doc_3", "span": [100, 200]}
  ]
}
```

**3. Post-hoc Attribution**
- LLM 生成后，用单独模型 / NLI 检查每句话的支持文档
- 工具：Self-Citation、Attribute First then Generate

**4. Span-level Citation**
- 不只给文档，给文档内的具体 span
- 实现：返回 highlighted 段落

**5. 评估**
- Faithfulness（生成是否 grounded）
- Citation Precision（引的对不对）
- Citation Recall（该引的都引了吗）
- 工具：Ragas、TruLens

**前端展示**：
- Inline citation：[1], [2] 标记
- Hover 显示原文
- 链接跳转到原文档

---

### Q7：1000 万级文档的 RAG 系统怎么设计？

**答**：

**关键挑战**：
- 索引规模：1000 万 doc × N chunks/doc × 1024 dim = TB 级
- 检索延迟：暴力检索不行
- 索引构建时间
- 增量更新

**架构**：

**1. 向量库选型**
- Milvus / Zilliz / Qdrant Cluster
- 不要：Pinecone（贵）、pgvector（这个规模力不从心）

**2. 索引算法**
- **HNSW**（默认）：精度高、内存大
- **IVF-PQ**：内存友好，精度略低
- **DiskANN**：磁盘索引，超大规模
- 选择：先 HNSW，规模超内存上限再换 IVF-PQ

**3. 分片**
- 按业务域 / 时间 / 地理分片
- 每个分片独立索引
- 查询时多分片并发 + 合并

**4. 分层检索**
```
Layer 1: 粗排（BM25 / 小 embedding model）→ top 1000
Layer 2: 精排（大 embedding + ANN）→ top 100
Layer 3: Rerank（cross-encoder）→ top 5
```

**5. 索引构建**
- 离线 batch（Spark / Ray）
- 增量更新（Kafka → 实时索引）
- 双写或单写双读

**6. 缓存**
- Query 级缓存（相似 query 复用结果）
- 热门 doc 的 embedding 内存常驻

**7. 元数据过滤先行**
- 用户问题中能提取的过滤条件（时间、地区、产品）先用
- 把 1000 万缩小到 10 万再向量检索

**8. 监控**
- P99 检索延迟
- 召回 / 内存 / GPU 使用率
- 索引 staleness

**9. 评估**
- 抽样测试集，定期跑回归
- 用户反馈数据形成数据飞轮

---

## 四、场景设计题（含答案）

### 场景 1：法律咨询 RAG，准确率 ≥ 95%

**题目**：法律事务所要做内部 RAG 系统，回答律师关于条款、案例的问题，准确率 ≥ 95%。设计方案。

**答案**：

**关键约束**：
- 准确率要求极高
- 文档强结构（条款 / 案例 / 解释）
- 用词专业，普通 embedding 可能不够

**架构**：

**1. 数据准备**
- 法律条款：按"条 / 款 / 项"结构化解析
- 案例：判决书、案号、当事人、争议焦点、判决要点
- 元数据丰富：法律领域、适用地区、生效日期、法律层级（宪法 / 法律 / 法规 / 规章）

**2. 切分**
- 条款：每"条"为一个 chunk，保留条款编号、章节标题
- 案例：按段落切，保留案号、争议焦点为 metadata

**3. Embedding**
- 起步用 BGE-M3 中文版
- 收集 1 万+ 律师问题 → 期望条款的标注对，微调
- 或用 reranker（cohere-multilingual-rerank）补救

**4. 检索**
- Hybrid（BM25 + Dense） + Rerank
- BM25 权重高（法律术语精确匹配重要）
- Metadata 过滤：按法律领域、生效日期过滤

**5. 生成**
- 强 grounding prompt：每个论断必须引用条款 / 案例
- 输出格式：结构化（答案 + 引用列表）
- 不知道就说不知道（重要！）

**6. 验证**
- Post-hoc check：LLM 二次校验答案是否真在引用中
- 关键事实匹配：日期、条款号、案号要精确

**7. 评估**
- 律师标注的高质量测试集（500 题起步）
- 双盲：律师评估 AI 答案 vs 律师答案
- 指标：准确率、引用正确率、Faithfulness、用户满意度

**8. HITL**
- 高风险问题（诉讼策略）必须人工 review
- 答案标注置信度，低于阈值触发律师审核

**9. 持续优化**
- 用户标记的错答 → 入数据飞轮
- 月度回归测试

**关键决策**：
- 95% 准确率几乎必须 finetune embedding 或重 rerank
- 不要追求"自动给出最终答案"，定位为"律师助理"，给候选 + 引用
- 越严肃场景越要 HITL

---

### 场景 2：客服 FAQ RAG

**题目**：电商客服系统，问"什么时候发货""退货政策"这类高频问题，要快、准、便宜。

**答案**：

**特点分析**：
- Query 高度重复 → 缓存效率高
- 答案在固定 FAQ 文档中 → 数据稳定
- 高 QPS、低延迟、低成本

**架构**（追求性价比）：

**1. 知识库**
- 不超过 1000 条 FAQ
- 每条：问题 + 标准答案 + 同义问题（人工补充）

**2. 检索**
- **Semantic Cache** 优先：相似 query 直接返回缓存
- BM25 + Dense Hybrid
- 1000 量级，向量库可以是 SQLite + sqlite-vss 或内存

**3. 路由**
- LLM 路由：判断 query 是否在 FAQ 范围
- 不在范围 → 转人工或更广 RAG / web

**4. 生成**
- 简单场景：直接返回 FAQ 答案模板（不用 LLM）
- 复杂场景：小模型（GPT-4o-mini / Haiku）基于 FAQ 改写

**5. 个性化**
- 用户身份信息（VIP / 普通）通过 metadata 过滤定制答案
- 订单查询调工具，不走 RAG

**6. 监控**
- Top miss query：经常没匹配上的问题 → 补 FAQ
- Top fallback：转人工的问题 → 找规律

**关键决策**：
- 优先级：缓存 → 规则 → 小模型 RAG → 大模型 RAG → 人工
- 90% 流量应该被前两层吃掉
- 评估：客户解决率 + 转人工率 + 用户满意度

---

## 五、自测清单

- [ ] RAG 三阶段（Indexing / Retrieval / Generation）
- [ ] Naive → Advanced → Modular → Agentic 演进
- [ ] 6+ 种切分策略与适用
- [ ] Dense / Sparse / Hybrid 的差异
- [ ] RRF 融合公式
- [ ] Rerank 的角色（recall vs precision）
- [ ] HyDE / Multi-Query / Step-back 的思路
- [ ] Self-RAG / CRAG / Adaptive RAG
- [ ] GraphRAG 的核心思想
- [ ] 4 个 RAG 评估指标（Ragas）

---

## 六、延伸阅读

- Gao et al. — *Retrieval-Augmented Generation for Large Language Models: A Survey*
- Microsoft — *GraphRAG*
- Asai et al. — *Self-RAG*
- Yan et al. — *Corrective Retrieval Augmented Generation (CRAG)*
- Ragas — Evaluation Framework Documentation
- Anthropic — *Contextual Retrieval*（重要工程经验）
