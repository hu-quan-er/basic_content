# Voice / Realtime Agent

> 目标：掌握实时语音 Agent 的核心架构、延迟治理、双工对话、与主流实时 API 的工程细节。这是 2024~2025 最热的 Agent 方向之一。

---

## 一、核心概念

### 1.1 为什么 Voice Agent 难
和文本 Agent 相比，独立挑战：
- **延迟敏感**：人对话延迟容忍 ~500ms，超过 800ms 体验断崖
- **双工对话**：边说边听（barge-in）
- **流式一切**：音频流入、文本流出、合成流出全部并行
- **多模态融合**：声学特征（情绪、口音）+ 语义
- **错误传播**：ASR 错 → LLM 错 → TTS 错，链路长
- **真实世界**：背景噪声、口音、网络抖动

### 1.2 两大架构范式

#### Pipeline（级联式 / Cascade）
```
[音频流] → [VAD] → [ASR] → [LLM] → [TTS] → [音频流]
```
- **优点**：每段可独立选最佳模型、可观测、易调试、便宜
- **缺点**：延迟累积、声学信息丢失（情绪、口音）
- **代表**：LiveKit Agents、Pipecat、Vocode、Vapi

#### End-to-End（端到端 / 语音原生模型）
```
[音频流] → [Speech-to-Speech 模型] → [音频流]
```
- **优点**：低延迟、保留声学信息、自然
- **缺点**：贵、能力边界紧（function calling 较弱）、可控性低
- **代表**：GPT-4o Realtime、Gemini Live、Moshi（开源）

### 1.3 经典 Pipeline 各组件

#### VAD（Voice Activity Detection）
- **作用**：判断是不是人在说话（区分语音 / 静音 / 噪声）
- **关键参数**：speech threshold、silence duration（多长静音算结束）
- **工具**：Silero VAD（最常用）、WebRTC VAD、PyAnnote
- **延迟**：< 30ms，几乎可忽略

#### ASR（自动语音识别）
- **作用**：音频 → 文本
- **关键指标**：
  - **WER**（Word Error Rate）— 词错误率
  - **TTFT**（首字延迟）
  - **流式 vs 批量**
- **工具**：
  - **Deepgram**：最快、最便宜、流式好（~200ms TTFT）
  - **AssemblyAI**：英文准确率高
  - **OpenAI Whisper**：离线 / 自部署、慢、非流式（v3）
  - **GroqAI Whisper**：超快批量
  - **Azure Speech**：企业级、多语言
  - **国内**：火山引擎、阿里、讯飞
- **流式 ASR 的关键**：**partial transcript**（边说边出文本）

#### LLM
- **选型考虑**：低延迟优先（TTFT < 300ms）
- **常选**：GPT-4o / Haiku / Gemini Flash
- **关键**：流式输出 + Prompt Caching
- **特殊设计**：
  - 输出要"口语化"，不要 markdown / bullet points
  - 短句优先，便于 TTS 提早合成
  - 控制长度（max_tokens 限制，免得说一大段）

#### TTS（文本转语音）
- **作用**：文本 → 音频
- **关键指标**：
  - **TTFB**（Time to First Byte，音频首字节延迟）
  - **自然度**（MOS 评分）
  - **情绪 / 风格控制**
- **工具**：
  - **ElevenLabs**：自然度顶级，可克隆音色
  - **Cartesia Sonic**：超低延迟（~70ms TTFB），实时优选
  - **OpenAI TTS**：质量好，延迟中等
  - **Deepgram Aura**：低延迟、便宜
  - **PlayHT**：质量高、Streaming 支持
- **核心技术**：流式合成（边接受文本边输出音频）

### 1.4 双工与 Turn-Taking

#### 半双工（Half-duplex）
- 经典电话机式：你说完我说
- 简单：VAD 检测说话结束 → 触发 LLM
- 缺点：响应慢、不自然

#### 全双工（Full-duplex / Barge-in）
- 模型说话时用户可以打断
- 用户开始说 → 立即停止 TTS 输出
- 关键：**barge-in 检测延迟 < 200ms**
- 实现：VAD 持续监听，命中则中断 audio playback + 清空 LLM 上下文

### 1.5 延迟拆解（最重要的工程问题）

**目标**：用户停止说话到听到回复 < 800ms（理想 < 500ms）

```
用户停止说话
   ↓ VAD 检测 endpoint  (~200~500ms 取决于 silence threshold)
ASR 完成 final transcript  (累计 ~300~700ms)
   ↓
LLM TTFT  (~200~500ms)
   ↓ LLM 第一个完整短句生成  (~300~700ms)
TTS TTFB  (~70~300ms)
   ↓
用户耳朵听到第一个音  (~50ms 网络抖动)
```

**关键延迟杀手**：
1. **VAD endpoint 时间太长**（设 800ms 静音才算结束，单这就 800ms）
2. **ASR 等 final**（用 partial 可以提前 200~400ms）
3. **LLM 等完整 sentence**（用流式 + 分句提前 TTS）
4. **TTS 等整段**（流式 TTS 分块合成）

**优化关键 = 流式 + 并行 + 提前触发**

### 1.6 流水线并行（关键技术）

朴素串行的延迟是各段相加。流水线让阶段重叠：

```
时间轴 →
ASR:   ████████████
LLM:        ████████████   ← LLM 看到 partial transcript 就开始
TTS:            ████████████   ← TTS 看到 LLM 第一句就开始
```

**优化点**：
- **Predictive triggering**：根据语义判断"用户大概说完了"，不等 VAD 超时
- **Speculative LLM**：ASR partial → LLM 提前思考（被打断就丢弃）
- **Sentence-level TTS**：LLM 输出第一个 sentence → TTS 立即合成
- **Chunked TTS**：TTS 分块输出，边合成边播放

### 1.7 端到端语音模型（Speech-to-Speech）

#### GPT-4o Realtime API
- **架构**：音频 token 直接进模型，模型输出音频 token
- **特点**：
  - TTFT 极低（~200ms）
  - 保留声学信息（情绪、笑声）
  - 同模型支持 function calling
- **协议**：WebSocket / WebRTC
- **限制**：贵（input $5/1M、output $20/1M 音频）、可控性低

#### Gemini Live
- Google 的对应方案
- 多模态原生：音频 + 视频 + 文本
- 双向流

#### Moshi（开源）
- Kyutai Labs 出品
- 全双工语音模型（同时听 + 说）
- 200ms 端到端延迟
- 适合研究 / 自部署

#### 何时选 E2E vs Pipeline？

| 维度 | Pipeline | E2E |
|------|----------|-----|
| 延迟 | 较高（700~1500ms） | 极低（200~500ms） |
| 成本 | 低（可调便宜模型） | 高 |
| 可观测 | 强（每段可看） | 弱（黑盒） |
| 可控性 | 强（prompt 易调） | 弱 |
| 自然度 | 受限（声学信息丢） | 高（保留情绪） |
| Function calling | 强（成熟 LLM） | 较弱 |
| 多语言 | 灵活 | 受模型限制 |
| 推荐场景 | 客服、企业应用、需精确控制 | 陪伴、消费级、强情绪 |

### 1.8 网络与传输

#### WebRTC
- 浏览器 / 移动端实时音频的标准
- 内置 jitter buffer、NACK、Opus 编码
- 适合 P2P 或客户端 ↔ 服务器
- 配套 SFU（Selective Forwarding Unit）做多方

#### WebSocket
- 简单、跨平台、广泛支持
- 自己处理 jitter、丢包
- 适合服务器端推流（如 OpenAI Realtime）

#### gRPC streaming
- 服务间通信常用
- 不适合直接面客户端

### 1.9 Function Calling 在 Voice 场景

**特殊挑战**：
- **延迟**：调工具会插入额外延迟，破坏对话节奏
- **填充语**：模型应说"稍等查一下" 让用户感知工作中
- **打断**：调工具时被打断怎么办？
- **结构化数据 → 口语化**：工具返回 JSON，要转成自然语言

**典型范式**：
```
用户："帮我订明天去上海的机票"
Agent：→ TTS "好的，我来查一下航班..."（填充语，立即播放）
       → 并行调用 search_flights 工具
       → 工具返回
       → TTS "查到了，明天有 8:00 和 14:00 的..."
```

### 1.10 Memory 与上下文

#### 短期
- 当前会话的多轮对话
- VAD 切的每个 utterance 一条 message
- ASR 错误会污染历史（错字累积）

#### 长期
- 跨会话用户偏好（"我是会员、我之前问过...")
- 关键：在新会话第一句话之前**预加载**，免得首句延迟

#### 上下文压缩
- 长对话超阈值摘要
- 但语音对话通常单次时长有限（10~30 min）

---

## 二、主流框架与工具

### 2.1 实时编排框架

#### LiveKit Agents
- 基于 WebRTC 的实时 Agent 框架
- 内置 VAD / ASR / TTS 各 provider 适配
- 抽象 Agent class、自动 turn-taking
- 生产级、跨语言（Python / Node）
- **2025 主流选择**

#### Pipecat
- Daily.co 出品
- Pipeline DSL 风格
- 适合复杂自定义编排
- Python 优先

#### Vocode
- 早期方案，逐渐被取代

#### Vapi
- SaaS 化方案
- 适合快速搭建电话客服

### 2.2 一站式 Voice Platform

- **Retell AI**：电话客服优化
- **Bland AI**：电话外呼
- **Synthflow**：低代码
- **Hume AI**：情绪理解专长

### 2.3 ASR 选型矩阵

| 工具 | 延迟 | 准确率 | 价格 | 流式 | 多语言 |
|------|------|--------|------|------|--------|
| Deepgram Nova-2 | 极低 | 高 | 便宜 | ✅ | 中等 |
| AssemblyAI | 中 | 极高 | 中 | ✅ | 强 |
| Whisper（OpenAI） | 高 | 高 | 便宜 | ❌（v3） | 极强 |
| Whisper（Groq） | 低 | 高 | 便宜 | ❌ | 极强 |
| Azure Speech | 中 | 高 | 中 | ✅ | 极强 |
| 火山 / 阿里 / 讯飞 | 低 | 高（中文） | 中 | ✅ | 中文优 |

### 2.4 TTS 选型矩阵

| 工具 | TTFB | 自然度 | 价格 | 流式 | 克隆 |
|------|------|--------|------|------|------|
| Cartesia Sonic | ~70ms | 高 | 中 | ✅ | ✅ |
| ElevenLabs | ~300ms | 极高 | 贵 | ✅ | ✅ |
| Deepgram Aura | ~200ms | 中 | 便宜 | ✅ | ❌ |
| OpenAI TTS | ~400ms | 高 | 便宜 | ✅ | ❌ |
| PlayHT | ~250ms | 高 | 中 | ✅ | ✅ |
| Azure TTS | ~300ms | 中 | 便宜 | ✅ | ✅（限） |

---

## 三、高频面试题（含答案）

### Q1：Voice Agent 的端到端延迟怎么拆解？怎么优化到 800ms 以内？

**答**：

**延迟来源**（朴素 pipeline）：

```
1. VAD 端点检测       200~500ms（取决于 silence threshold）
2. ASR 出 final       100~400ms（流式则 ~100ms）
3. LLM TTFT          200~500ms
4. LLM 出第一个 sentence  200~500ms
5. TTS TTFB          70~400ms
6. 音频传输           50~100ms
─────────────────────────
朴素串行：1000~2000ms
```

**优化策略**：

**1. 缩短 VAD endpoint**
- 默认 800ms silence 改为 300~500ms
- 但太短会误切断（用户思考停顿）
- 平衡：使用语义 endpointing — 用模型判断"句子是否完整"
- LiveKit Agents、Cartesia 都有 turn-taking model

**2. ASR 用 partial transcript**
- 不等 final，partial 就给 LLM
- LLM speculative 跑，最终被 final 修正
- 节省 200~400ms

**3. 流水线重叠**
```
ASR:  ████████████
LLM:        ████████████  ← partial 就启动
TTS:            ████████████  ← LLM 第一句就启动
```

**4. LLM 选低 TTFT 模型**
- Haiku / GPT-4o-mini / Flash
- Prompt Caching 命中（system prompt + 工具 schema）
- 短上下文，砍冗余

**5. TTS 分句流式**
- LLM 每输出一个完整 sentence → 立即送 TTS
- 用 Cartesia 这类低 TTFB
- 流式播放（不等全部合成）

**6. Prompt 引导短回复**
- "Reply in 1~2 sentences, conversational tone"
- 避免长 markdown / bullet points
- 减少 LLM output 时间

**7. 网络优化**
- WebRTC（自带 jitter buffer、Opus codec）
- 服务器就近部署
- HTTP/2 长连接

**8. E2E 模型**
- 如果可控性要求不极致，用 GPT-4o Realtime
- 跳过 ASR + LLM + TTS 串联

**理想优化后**（pipeline）：
- VAD: 300ms
- ASR partial: 100ms（与 LLM 并行）
- LLM TTFT + 第一句: 400ms
- TTS TTFB: 100ms
- 总: ~700~800ms

---

### Q2：Pipeline 范式 vs E2E 语音模型怎么选？

**答**：

**简单决策树**：

| 需求 | 选 |
|------|-----|
| 需要精细控制 prompt / 工具 | Pipeline |
| 需要复杂 function calling | Pipeline |
| 极致低延迟 / 自然度 | E2E |
| 需要保留情绪 / 笑声 | E2E |
| 企业场景 / 合规审计 | Pipeline |
| 消费级陪伴 / 娱乐 | E2E |
| 多语言切换 | Pipeline |
| 预算紧 | Pipeline |
| 离线 / 自部署 | Pipeline（用开源组件） |

**详细对比**：

**Pipeline 优势**：
1. **可观测**：能看 ASR 错在哪、LLM 想什么
2. **可调试**：每段独立替换 / 优化
3. **可控**：Prompt 调整、工具完整
4. **便宜**：能用 Haiku + Deepgram + 国内 TTS，单分钟成本极低
5. **多语言**：换 ASR / TTS 即支持新语言

**E2E 优势**：
1. **延迟**：理论极限低（~200ms）
2. **声学保留**：能感知情绪、口音
3. **更自然**：tone、emphasis、笑声
4. **简单**：单 API 调用解决

**E2E 劣势（容易被忽视）**：
1. **可控性差**：调 prompt 不如 LLM 那么精确
2. **Function calling 较弱**：成熟度不如纯 LLM
3. **贵**：当前定价远高于 pipeline
4. **黑盒**：模型 hallucinate 时难定位
5. **多模态融合**：复杂任务（边说边看屏幕）支持不一

**实战选型**：
- 大多数生产应用：Pipeline（尤其客服、企业）
- 强情绪 / 陪伴产品：E2E（AI 朋友、AI 女友）
- 不少应用：**Hybrid** — 简单对话走 E2E、复杂任务回退 pipeline

---

### Q3：Barge-in（用户打断）怎么实现？

**答**：

**核心要求**：用户开始说话 → 立即停止 AI 输出 → 延迟 < 200ms

**实现步骤**：

**1. 持续 VAD**
- AI 说话时**不停止 VAD**
- 监听用户麦克风的 audio stream
- 用 Silero VAD 等流式 VAD

**2. 触发条件**
- 检测到 voice（不只是噪声）
- 持续 N 帧（如 200ms）避免误触发
- 注意区分 backchannel（"嗯""啊"）

**3. 中断动作**
- **立即停止 TTS audio playback**（最关键）
- 取消 LLM 流式输出（cancel current generation）
- 取消未播完的 TTS 请求
- 清空 audio buffer

**4. 上下文修正**
- AI 被打断时，已说了一部分，已说部分要记入 history
- 例：模型本来要说 5 句，说了 2 句被打断 → history 里只记 2 句
- 否则下次模型会假定用户听到了 5 句

**5. 用户输入处理**
- 用户开始说的内容进 ASR
- 等 endpoint → 触发新的 LLM 调用

**6. 反向：背景音的误打断**
- 用户的咳嗽、笑声、邻居声音不该触发打断
- 需要区分：是有意"接话"还是背景

**7. Backchannel 处理**
- 用户的"嗯""对""然后呢"不应打断
- 可用语义模型判断（is_backchannel）
- 或简单：很短的语音不算打断（< 500ms）

**框架支持**：
- LiveKit Agents 内置 barge-in 处理
- 关键参数：`interrupt_speech_duration`、`min_interrupt_duration`

**精细化**：
- Anthropic / OpenAI 在他们的 Voice 工程博客中提到 **smart turn-taking** — 训练专门的 turn-taking model 判断"用户是真要说还是只是 hesitation"

---

### Q4：流式 TTS 怎么避免"卡顿"？

**答**：

**问题**：TTS 分块合成，块之间可能有 gap → 听起来不连贯

**根因**：
- LLM 输出不连续（生成一段、思考一段）
- TTS 合成跟不上播放速度（buffer 耗尽）
- 网络抖动

**解决方案**：

**1. 文本缓冲策略**
- 不要 token-level 送 TTS（太碎）
- 累积到 sentence 或 clause 再送
- 平衡：buffer 太大延迟高，太小卡顿

**2. 智能切句**
- 在标点、长停顿位置切（", "、"."、"...")
- 避免在词中间切
- 用 sentence tokenizer（spacy 等）

**3. Audio buffer**
- 客户端维护 audio buffer（如 200ms）
- 持续接收 chunks 填充
- 永远不让 buffer 完全清空（一旦清空就 gap）

**4. Streaming TTS 提前合成**
- 当前句播放时，下一句已经在合成
- 用 producer-consumer 模式：合成线程往 queue 推、播放线程从 queue 拉

**5. 选低 TTFB TTS**
- Cartesia Sonic 等低延迟 TTS
- 块间衔接好

**6. 预合成填充语**
- "嗯"、"好的"、"让我看看"提前合成缓存
- 等 LLM 想的同时播放填充语，避免静默

**7. 自适应播放速度**
- 接收太慢时略提高播放速率（用户感知差异小）
- 接收太快时降低播放速率
- 避免 buffer 溢出 / 耗尽

**8. 网络层**
- WebRTC（自带 jitter buffer）
- TCP 用 long connection（避免重连）
- 服务器靠近用户

**评估**：
- 测听感（人工 MOS）
- 量化：buffer underflow 次数 / 分钟、gap 总时长

---

### Q5：电话客服 Voice Agent 怎么设计？

**答**：

**特点 / 约束**：
- 电话音质差（8kHz / 16kHz、噪声）
- 用户分布广（口音、年龄）
- 高峰并发高
- 合规：录音保留、PII 保护
- 接听 / 转人工流程

**架构**：

```
[PSTN/SIP] → [Telephony Gateway]（Twilio / Plivo / Asterisk）
                ↓
            [Audio Stream]
                ↓
            [LiveKit Agents]
              ├─ Silero VAD
              ├─ Deepgram ASR（电话域优化模型）
              ├─ GPT-4o-mini LLM
              │   ├─ Function Calling（CRM / 知识库）
              │   └─ Memory（短期）
              └─ Cartesia TTS
                ↓
            [Audio out → PSTN]
```

**关键设计**：

**1. 电话域适配**
- ASR 选电话优化模型（Deepgram phonecall model）
- 8kHz → 16kHz 上采样
- 噪声抑制（RNNoise / Krisp）

**2. 开场白**
- 首次接通：预合成 audio 立即播放（避免首句延迟）
- "您好，这里是 XX 客服，请问有什么可以帮您？"

**3. ASR 错误处理**
- 关键字段（订单号、手机号）多次确认
- "我听到您说订单号是 12345，对吗？"
- 数字识别强化（数字模式）

**4. 转人工**
- 检测情绪激动（关键词 / 声学情绪模型）
- 用户明确要求
- AI 无法处理（多次失败）
- 转人工时同步对话历史给客服

**5. HITL / 合规**
- 通话开始播 "本次通话将被录音"
- 关键操作（退款）必须人工确认
- 录音存合规存储（加密）

**6. 长对话治理**
- 5 分钟超长触发摘要 + 转人工
- 静音超 30s 礼貌结束

**7. 高并发**
- LiveKit 集群部署
- 每路通话独立 Worker
- 监控：CPU、网络、ASR/TTS 配额

**8. 评估**
- 解决率 / 转人工率
- 平均通话时长
- 用户满意度（电话末 IVR 评分）
- WER（关键字段准确率）

---

### Q6：Voice Agent 的 function calling 与文本 Agent 有何不同？

**答**：

**核心差异**：**延迟可见**

文本 Agent 调工具：用户看到 "..." 等一会儿可接受。
Voice Agent 调工具：用户听到几秒静默 → 体验断崖。

**特殊设计**：

**1. 填充语（Filler Speech）**
- 模型应主动说"好的，我查一下"再调工具
- Prompt 引导：
```
When you need to call a tool, FIRST say a short acknowledgment
like "Let me check that for you" or "One moment".
THEN call the tool.
```

**2. 工具调用并行**
- LLM 边说填充语，工具调用在后台并行启动
- 而不是等填充语播完才调

**3. 工具超时治理**
- 单工具 < 3s 否则 abort
- 超时 → "对不起，查询花的时间比预期长，我换个方式"

**4. 结果口语化**
- 工具返回 JSON：`{"flights": [{"time": "08:00", "price": 1500}, ...]}`
- 不能直接念 JSON
- LLM 要转成自然话："查到 3 个航班，最早是早上 8 点的，1500 元"

**5. 多结果处理**
- 工具返回 50 个结果不能全念
- 摘要 + 让用户选："给您找到 50 多个，要按价格、时间还是航空公司排？"

**6. 中断时的工具调用**
- 用户打断时，工具是否还要执行？
- 安全的：取消（除非已经发起副作用）
- 有副作用的：继续完成，但 LLM 知道用户已打断（要重新策略）

**7. 用户输入歧义**
- 文本 Agent 用户能精确写参数（"订单 abc123"）
- Voice 用户："那个上次的订单"
- 工具需要 context-aware（默认用最近订单）

**8. 工具选择延迟**
- 50+ 工具时，模型选择本身慢
- Voice 场景压缩工具集（最常用 10 个）
- 复杂工具走 fallback（"请稍等转专业客服")

---

### Q7：Voice Agent 的评估怎么做？

**答**：

**多维评估**：

**1. 语音识别质量（ASR 层）**
- **WER（Word Error Rate）**：整体准确率
- **Entity WER**：关键实体（数字、名字、地址）准确率
- 不同噪声 / 口音 / 语速下的 WER

**2. 延迟（工程层）**
- **TTFA**（Time to First Audio）：用户停止说到听到第一个音
- **P50 / P95 / P99**
- 各组件分段延迟
- 网络 RTT

**3. 对话质量（LLM 层）**
- 与文本 Agent 类似：任务成功率、相关性、安全性
- **特殊**：口语化程度（不能输出 markdown）
- 简洁度（不啰嗦）

**4. TTS 质量**
- **MOS**（Mean Opinion Score）：人工 1~5 评分
- **WER 反推**：用 ASR 转回文本对比，看 TTS 清晰度
- 韵律 / 情感自然度

**5. 用户体验**
- **NPS** / CSAT
- **任务完成率**
- **转人工率**
- **打断频率**（用户打断 = 不满）
- **静默率**（用户长时间不响应 = 困惑）

**6. 商业指标**
- 通话时长（适宜的更短更好）
- 解决率
- 客单成本

**评估方法**：

**离线**
- 录制真实通话样本 → 标注 → 跑回归
- WER 算法自动
- 任务成功用 LLM-judge
- TTS 人工 MOS

**在线**
- 实时监控：延迟、错误率、用户挂断时长
- 抽样人工 review
- 用户反馈接入（电话末 IVR）

**特殊评估**：
- **Voice Bench / AudioBench**：公开 benchmark
- **真实场景测试集**：自建（电话 / 客厅 / 户外）

---

### Q8：背景噪声 / 多人说话怎么处理？

**答**：

**噪声类型**：
- 稳态：风扇、空调
- 非稳态：键盘、关门、车流
- 人声：电视、旁人对话（最难）

**应对策略**：

**1. 客户端降噪**
- **Krisp**：闭源、效果好
- **RNNoise**：开源、轻量
- WebRTC 内置 NS（弱）
- 移动端：iOS / Android 系统级

**2. ASR 模型选择**
- 选噪声 robust 的 ASR（电话域、声学多样训练）
- Whisper large 抗噪强

**3. 说话人验证 / 分离**
- **Speaker Diarization**：识别"谁在说"
- **Voice Verification**：只接受注册用户的声音
- 工具：PyAnnote、SpeechBrain

**4. VAD 加强**
- 用更鲁棒的 VAD（Silero v4 / WebRTC + RNNoise）
- 调高 threshold（牺牲灵敏度换准确）

**5. 多通道**
- 阵列麦克风（远场）
- Beamforming 锁定方向

**6. 语义层防御**
- 即使 ASR 误识别噪声为文本，LLM 应识别"不合理输入"
- 用 confidence 过滤：ASR confidence < 0.6 视为噪声
- "对不起，我没听清，能再说一次吗"

**7. 多人场景**
- 主动澄清："我刚听到几个声音，请问是您在跟我说话吗？"
- 或：第一个识别说话人后锁定（voice print）

**特殊：电话场景**
- 8kHz 信噪比天生差
- 用电话域专门优化的 ASR
- 客户端噪声抑制（Twilio 有此选项）

---

## 四、场景设计题（含答案）

### 场景 1：AI 英语口语陪练

**题目**：设计一个能陪用户练英语口语、纠正发音、评估流利度的 Agent。

**答案**：

**特殊需求**：
- 需要分析发音（不只是识别词）
- 需要长时间陪练（30 min+）
- 需要个性化教学（弱项追踪）
- 用户层面广（不同水平）

**架构选择**：**Hybrid Pipeline**
- 主流程：Pipeline 范式（需要精细控制教学逻辑）
- 关键时刻：端到端模型（情感反馈、自然对话）

**核心组件**：

**1. ASR + 发音分析**
- **Phonetic ASR**：不只是词，识别 phoneme（音素）
- 工具：Azure Pronunciation Assessment、SpeechAce、自训
- 输出：词级别 / 音素级别准确度评分

**2. LLM**
- 选择对话教学风格强的模型（Claude / GPT-4o）
- Prompt：
  - 适应用户水平（初级用简单词、高级用挑战）
  - 主动纠错 + 鼓励
  - 苏格拉底式引导

**3. TTS**
- 选自然、能调风格的（ElevenLabs）
- 不同教学场景调不同 voice（朋友 vs 老师）

**4. 用户档案**
- 词汇表：会的、不会的、刚学的
- 发音弱项：常错的音素
- 偏好话题
- 历史进度

**5. 课程编排**
- 基于档案选话题
- 难度梯度
- 间隔重复（spaced repetition）

**关键设计**：

**1. 反馈机制**
- 用户说错：温和指出 + 示范
- 不要打断式纠正（破坏 flow）
- 句末统一反馈

**2. 双语切换**
- 必要时切母语解释（"这个词的意思是..."）
- 默认全英文沉浸

**3. 长对话治理**
- 30 min 自动总结 + 推荐休息
- 关键内容存长期记忆

**4. 个性化**
- 进度追踪（流利度 / 词汇量 / 发音）
- 弱项主动推（"上次发音错的 word XX，今天再用一次"）

**评估**：
- 用户留存（核心）
- 单次对话时长
- 发音改进曲线
- 主观满意度

---

### 场景 2：医疗咨询 Voice Agent（高合规）

**题目**：设计一个能初步问诊、做症状评估、必要时转医生的语音 Agent。

**答案**：

**关键约束**：
- HIPAA / 医疗合规（严）
- 准确率红线（误诊责任）
- 用户可能紧急（实时识别）
- 不能"诊断"（法律限制）

**架构**：Pipeline（绝不能 E2E，可控性 + 可审计要求）

**核心组件**：

**1. ASR**
- 医疗领域适配（医学术语库）
- 多语言（移民人口）
- 高准确率优先于低延迟

**2. LLM**
- 自部署或 HIPAA 合规的 API（Anthropic / Azure OpenAI 有 BAA）
- Prompt：极保守，明确"我不是医生，不做诊断"

**3. 工具**
- 症状录入（结构化）
- 知识库查询（医疗文献）
- 紧急触发（拨 120 / 转护士）

**4. 安全 / 合规层**
- 全程录音（HIPAA 要求）
- PII 加密存储
- 数据驻留（医疗数据本地）

**关键设计**：

**1. 紧急识别**
- 关键词 + 语义模型识别紧急（"胸痛"、"喘不上气"）
- 立即触发：转人工 / 拨 120 / 提示就医
- 优先于其他逻辑

**2. 不诊断**
- Prompt 强制："Never give diagnoses. Always recommend consulting a doctor."
- 输出过滤：包含诊断性语言 → 重写

**3. 结构化收集**
- 症状（位置、性质、持续时间、强度）
- 既往史
- 当前用药
- 输出标准化报告给医生

**4. HITL**
- 任何用药建议必须医生审核
- 任何转诊必须医生确认
- 用户可随时转人工

**5. 多语言**
- 立即检测用户语言，匹配 ASR / TTS / LLM
- 关键内容双语对照

**6. 信任建立**
- 开场明确身份：" 我是 AI 助手，不能替代医生"
- 不确定时主动转医生

**评估**：
- 严重症状识别率（不能漏）
- 不必要转诊率（不能假阳性）
- 用户满意度
- 医生审核通过率（结构化报告质量）

**法律 / 风控**：
- 合规审计季度
- 法务 review 所有 prompt 变更
- 错答案例分析（防医疗事故）

---

## 五、自测清单

- [ ] Pipeline vs E2E 的取舍维度
- [ ] 经典 pipeline 6 段（VAD/ASR/LLM/TTS/网络/客户端）
- [ ] 延迟拆解和优化（流水线 + 提前触发）
- [ ] Barge-in 实现 4 步
- [ ] Function calling 在 voice 场景的 5 点特殊设计
- [ ] 流式 TTS 防卡顿 8 个手段
- [ ] Voice Agent 评估的 6 个维度
- [ ] 噪声 / 多人场景的 7 种应对
- [ ] LiveKit Agents / Pipecat 的定位

---

## 六、延伸阅读

- LiveKit — *Agents Documentation*
- Pipecat — Documentation + Tutorials
- OpenAI — *Realtime API* 文档
- Anthropic — *Voice AI engineering* 博客
- Kyutai Labs — *Moshi: A Speech-Text Foundation Model*
- Defossez et al. — *Moshi paper*
- Cartesia — *Sonic technical blog*
- Deepgram — *Building voice agents* 系列

---

## 七、关键术语 Cheat Sheet

| 术语 | 含义 |
|------|------|
| VAD | Voice Activity Detection — 检测说话开始 / 结束 |
| ASR | Automatic Speech Recognition — 语音转文本 |
| TTS | Text-to-Speech — 文本转语音 |
| WER | Word Error Rate — 词错误率 |
| TTFT | Time to First Token — 首 token 延迟 |
| TTFA | Time to First Audio — 首音频延迟 |
| TTFB | Time to First Byte — 首字节延迟 |
| MOS | Mean Opinion Score — 语音质量主观评分（1~5）|
| Barge-in | 用户在 AI 说话时打断 |
| Turn-taking | 对话轮次切换 |
| Endpointing | 检测用户说完话 |
| Backchannel | "嗯" "对" 等附和语 |
| Filler speech | 填充语，避免静默 |
| Speaker Diarization | 说话人分离 |
| Pipeline | 级联式架构（VAD→ASR→LLM→TTS）|
| E2E / S2S | Speech-to-Speech 端到端模型 |
| Full-duplex | 全双工，边听边说 |
| SIP / PSTN | 电话网络协议 |
| Opus codec | 实时音频编码标准 |
| Jitter buffer | 抖动缓冲，平滑网络抖动 |
