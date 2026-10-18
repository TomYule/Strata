# 超长文本分片、会话压缩与 Strata 上游贡献调研

调研日期：2026-10-17。依据公开源码、GitHub issue/PR 及本地 Git 状态；本轮没有创建分支、提交、推送或发布 issue/PR。

## 1. 结论

1. **先提交小范围的 Claude/clawgod 超窗错误兼容修复，值得做。** 上游已有 Pi 兼容修复，但不能据此推定 Claude CLI 也能识别相同400文案。现有维护者讨论明确欢迎补充其他 harness 的匹配情况。
2. **分片处理值得做，但应拆开两个用途：超长文档摘要与工具会话压缩。** 两者都不是“推理模型直接接受无限输入”。
3. **不建议默认让 Strata 的 `/v1/messages` 收到超长请求后偷偷摘要再执行。** 会改变请求语义、延迟、工具关系和可复现性，而且客户端下一轮可能再次上传原始历史。
4. 文档处理优先采用显式的分块摘要/检索工具；会话压缩优先使用客户端原生机制。若开发 Strata 兜底压缩，应是单独、默认关闭、可取消且可观察的功能提案。

## 2. 你的 fork 与 `me` 的实际状态

本地 Git 仓库位于：

```text
D:/Programs/strata-windows-x64-cuda12/Strata
```

上一级发行包目录不是 Git 仓库，但 `Strata` 子目录是。

检查结果：

```text
当前本地分支：main
remote origin：git@github.com:Niko1221/Strata.git
remote me：    git@github.com:TomYule/Strata.git
```

**`me` 是 remote，不是 branch。** GitHub fork 确认存在，parent 为 `Niko1221/Strata`；查询 `/branches/me` 返回404，公开分支列表仅有 `main`。本轮查询时 fork/main 与 upstream/main 均指向 `296b59d2f73c8f04a805df29c2fa97655adace78`。

本地工作区有多类修改：BAT、frontend/server、测试、客户端脚本、机器配置文档，还有未跟踪的崩溃转储。提交时必须挑选超窗修复本身，**不能 `git add .`**。

特别排除：

- `strata-stall-10068.dmp`：可能包含内存数据，不能上传。
- 个人绝对路径、配置备份、会话标识和故障文档中的机器信息。
- 本地客户端启动器、OpenCode watchdog、工具名清洗等无关修改。

## 3. 五类开源实现的实际做法

### 3.1 Pi：识别超窗错误，再压缩会话

源码：

- [overflow.ts](https://github.com/earendil-works/pi/blob/8efd314fa3d3232ce197d8d7a6a5660530b9d83e/packages/ai/src/utils/overflow.ts)
- [compaction.ts](https://github.com/earendil-works/pi/blob/8efd314fa3d3232ce197d8d7a6a5660530b9d83e/packages/coding-agent/src/core/compaction/compaction.ts)

观察：

- 使用已知服务商错误模式识别context overflow。
- 压缩配置明确区分 `reserveTokens` 与 `keepRecentTokens`；所查版本默认分别为16384和20000。这是Pi默认值，不是本机推荐值。
- 寻找合法切分点，不在tool result位置随意切断；工具结果必须与对应调用保持关系。
- 会话历史序列化后用于摘要；保留近期消息及文件操作信息。

借鉴点：**错误分类必须正确，压缩边界必须理解工具协议。** 这正是本地Strata修复有价值的原因。

### 3.2 OpenCode：客户端维护摘要和近期上下文

当前开发分支源码：

- [packages/core/src/session/compaction.ts](https://github.com/anomalyco/opencode/blob/1cb7bcadb1653d069ffd22e2d8b696719abbbffe/packages/core/src/session/compaction.ts)

观察：

- 区分auto、overflow、manual触发。
- 摘要结果与近期原文分开管理。
- 摘要指令明确要求只生成摘要、不继续执行任务或调用工具。
- 当前开发分支结构已迁移；不能直接把它的所有配置项当成本机安装的1.19.0支持项。本机之前使用的字段是通过安装包schema单独核对的。

借鉴点：压缩应成为客户端可见的会话状态，不是服务端每轮临时改写请求。

限制：本机曾出现39次压缩和反复读取，说明“具备压缩功能”并不等于“长任务能稳定推进”。需要控制工具输出、摘要膨胀及重复探索。

### 3.3 Aider：压缩旧历史，保留最近部分，再递归检查

源码：

- [aider/history.py](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/history.py)

观察：

- 先计算消息token总量。
- 给近期历史保留预算，旧部分交给摘要。
- 摘要与tail合并后再数token；仍然太大则继续处理。
- 有深度控制及回退逻辑，不是无限简单递归。

借鉴点：每次摘要后必须重新计数，摘要不一定足够短；旧摘要也会增长。

限制：不是专门处理任意大单个文档的通用分片系统，不能直接照抄便承诺每个超长输入都能成功。

### 3.4 LangChain：长文档 Map–Reduce 与会话摘要中间件是两条路线

源码：

- [MapReduceDocumentsChain（classic）](https://github.com/langchain-ai/langchain/blob/bd5b134d876ef47858beef27bd29c81eeda03293/libs/langchain/langchain_classic/chains/combine_documents/map_reduce.py)
- [ReduceDocumentsChain（classic）](https://github.com/langchain-ai/langchain/blob/bd5b134d876ef47858beef27bd29c81eeda03293/libs/langchain/langchain_classic/chains/combine_documents/reduce.py)
- [SummarizationMiddleware](https://github.com/langchain-ai/langchain/blob/bd5b134d876ef47858beef27bd29c81eeda03293/libs/langchain_v1/langchain/agents/middleware/summarization.py)
- [短期记忆文档](https://docs.langchain.com/oss/python/langchain/short-term-memory)

文档路线：

```text
切文档 → 各块摘要（map）→ 分组压缩（collapse）→ 合并结果（reduce）
```

源码中的reduce按token_max分组，超过预算继续collapse，并支持collapse_max_retries。值得注意：**单个Document超过上限时仍会报错**，调用者必须先把巨大文档切开，不能以为“启用map-reduce就自动处理一切”。

**classic MapReduceDocumentsChain 已标为deprecated。** 适合借鉴算法，不建议把旧链作为新工程核心依赖；新实现应采用现代中间件/图工作流/显式检索工具。

会话路线：SummarizationMiddleware提供trigger/keep策略，并调整切分点，保证AI工具调用与ToolMessage配对。

借鉴点：

- 长文档处理要先切到单块安全范围。
- 概括任务可做分层摘要；定点问答通常更适合检索相关块。
- 设置有限collapse轮数；“摘要没有变短”应报告失败，不能循环烧推理时间。

### 3.5 llama.cpp：明确窗口错误 / context shift，不等于语义摘要

参考：

- [server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [server-context.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-context.cpp)

观察：

- 超窗错误路径有专用类型及 `n_prompt_tokens` / `n_ctx` 信息。
- `--context-shift` 用于生成过程中的上下文移动；所查README标为默认disabled。
- context shift、KV缓存优化不是“旧信息被正确总结并保留”，不能当成无损无限上下文。

借鉴点：推理服务负责准确限制、明确反馈；是否丢弃、摘要或检索由上层策略决定。

## 4. Strata 上游已有内容：不要重复造issue

### #1615：已处理Pi识别，维护者欢迎其他harness反馈

[Issue #1615](https://github.com/Niko1221/Strata/issues/1615) 的例子就是150722输入 / 131072窗口，要求harness识别后能自己compact-and-retry。

维护者评论：v0.1.42通过#1623加入 `request exceeds the context window:`；若其他harness匹配不同短语，请告知以便核查。Pi报告者随后确认其匹配器可识别。

这意味着我们的提交应说明：

> Pi场景已修，但Claude Code / clawgod所用的400分类分支还需要相应前缀；同时返回精确预算差额。

不要声称“Strata完全没有超窗识别支持”。

### #1623 / #1675：已有错误文案PR

- [PR #1623](https://github.com/Niko1221/Strata/pull/1623)：文案修复及CPU-only HTTP回归测试。API查询时仍显示open、merged=false，但维护者评论称已通过该工作在0.1.42提供，且当前main源码确有对应前缀；不要只用GitHub的merged字段推断功能缺失。
- [PR #1675](https://github.com/Niko1221/Strata/pull/1675)：另一份文案提案，closed、merged=false。

最有利的补充：链接#1615，展示**特定Claude分类器**对当前/修复文案的结果，而不是再泛泛请求“支持超窗”。

### #1507：已有Web聊天界面压缩提案

[PR #1507](https://github.com/Niko1221/Strata/pull/1507) 目前open。描述是在Web客户端做压缩、保留最近约5K tokens、原始消息继续保留可查看，且“No server change”。

不要把Web UI压缩和API服务端隐式摘要混成同一个PR。

### #2508：KV提案，不是文本分片摘要

[Issue #2508](https://github.com/Niko1221/Strata/issues/2508) 讨论KV片段去重/恢复及未来RAG引导的KV会话。作者明确区分已有工作与尚未实现/测量的设想。

KV恢复可以降低重复prefill，但不会自动解决语义历史变长或摘要丢信息。

## 5. 针对本机的实现建议

### A. claude-s / clawgod-s：优先压缩会话，不默认服务端摘要

保留已有路径：

```text
正常请求 → Strata核算窗口
超窗 → 精确400错误 → 客户端识别 → 压缩旧历史/调整输出 → 再发送
```

优点：客户端掌握真实会话结构、工具调用关系、文件状态；压缩后后续请求也能复用压缩后的历史。

需要补充验证：

- 精确区分输入本身超长 vs max_tokens超大。
- 运行已安装版本的真实分类器测试，而不只搜索二进制字符串。
- 真实会话被拒后是否发起compaction、下一次输入是否减少。
- 如果系统提示/工具定义本身超长，应明确报告“历史压缩不足以解决”，不能原样重试。

### B. 单个超长文档：显式分块工具

建议先做独立本地工具或客户端插件，保持Strata推理API简单：

1. 文档按章节/段落/代码符号切分，并用实际tokenizer校验；没有自然边界时再按token切。
2. 每块携带文件路径、章节、行号或偏移，避免摘要失去出处。
3. 保留原始文件，摘要只作派生缓存。
4. 摘要任务逐块map再reduce；定点问答优先检索相关块，不先概括整本资料。
5. 每次加入摘要指令、输入块和输出预留后都重新计数。
6. 大摘要再归并；最多2–3层，检测未变短并停止。

本机128K服务的实验起始值：

| 参数 | 起始建议（未基准验证） |
|---|---:|
| 单块正文 | 16K–24K tokens |
| 每块摘要上限 | 1K–2K |
| 最终摘要 | 4K–8K |
| 近期完整会话 | 16K–24K，按工具关系调整 |
| 并发 | 1 |
| 最大归并层数 | 3 |
| 任务等待策略 | 可取消，有进度，不无限自旋重试 |

这些不是生产默认。特别是代码审查/逐字比对不能只靠有损摘要：必须能够回查原文。

### C. 如果以后做Strata服务端兜底

建议先提RFC，不直接塞进`Service.prepare`：

- 默认关闭，通过显式请求/配置开启。
- 最好返回可复用的压缩结果/引用，而不是偷偷换掉messages。
- 保持原始请求；保护系统指令、当前问题、未完成工具调用及调用结果配对。
- 缓存键包括模型、tokenizer/template、系统指令、工具schema和历史前缀；会话隔离。
- 限制接收字节数、分块数、归并深度、任务时间和磁盘占用。
- 摘要期间不得触发真实工具；源文档按不可信数据处理，不能提升成系统指令。
- 单GPU下摘要和正常请求会争抢同一引擎，必须设计排队、公平性和取消；不要持有正常生成锁再递归HTTP请求自己，避免死锁。
- 公布compressed-from/to、耗时、是否丢失原文细节，准确记录最终模型实际usage，不把原始请求token冒充实际推理token。
- 客户端下一轮若仍发原始历史，要命中稳定缓存而不是每轮重做摘要。

## 6. 是否提交更新：建议分成两个工作项

### PR 1：推荐现在准备

建议标题：

```text
fix(serve): expose Claude-compatible context overflow errors with exact token budgets
```

最小范围：

- `serve/server.py` 的错误构造与两种超窗分支。
- `serve/test_context_overflow.py` 的数值/分类/恢复边界测试。
- 少量通用文档，不带本机路径或用户日志正文。

提交前审查：

1. 先把本地patch与upstream/main逐块比较，仅携带本次改动；server.py已有其他本机补丁。
2. 尽量保持原有HTTP状态、error envelope、admission规则和fit行为不变。
3. 当前本地实现将room<1的判断提到前面，属于分支重排；上游版应确认必要性，或改成仅文案变更以缩小风险。
4. `prompt is too long: N tokens > M` 中M为保留最少输出/安全余量后的输入上限，必须同时给出真实窗口及完整预算，避免把有效输入上限混同于模型context。
5. 不把所有400标成overflow，不为相同请求设置误导性的Retry-After。
6. 附本地测试结果：此前55项，54通过1跳过；明确这是MockEngine HTTP测试，尚非真实Claude自动压缩端到端成功。
7. 最好补真实分类器用例和一组受控客户端compact/retry证据，再请求合并。

PR应是#1615的兼容性补充，可先在该issue反馈，或新issue链接旧讨论。发布前需用户确认公开内容。

### RFC 2：分片压缩，先讨论后实现

建议主题：

```text
Opt-in document summarization / context compaction with bounded chunking
```

明确选择层次：Web UI、客户端工具、独立辅助服务、还是Strata核心。引用#1507，说明与KV提案#2508的区别。建议先完成客户端文档分块原型及本机质量/延迟测量，不与错误兼容PR捆绑。

## 7. Git操作建议（本轮未执行）

你的`me` remote已存在，可在用户要求提交时：

1. 在当前仓库创建独立主题分支，例如 `fix/claude-context-overflow`，不要在main直接commit。
2. 保留全部现有工作区改动，不reset/覆盖其他补丁。
3. 只暂存/提交本次超窗修复的精确代码块和测试；有个人补丁混在同一文件时要逐块处理。
4. 推送主题分支到`me`，随后向`Niko1221/Strata:main`提PR。
5. 遵循仓库AGENTS.md：检索已有issue/PR、一项改动一个PR、报告未测部分。仅Python服务修改无需假装做过CUDA/HIP性能验证。

不建议为完成这个小PR安装全新依赖或覆盖正在运行的发行目录。若需要独立克隆，放到新的干净开发目录，与模型数据/服务配置分离。

## 8. 调研限制

通用WebSearch工具本轮被环境许可分类器暂时阻止；通过GitHub公开API检索相关issue/PR，并实际读取上述项目官方源码/文档完成调研。部分旧路径404后通过仓库tree定位了新路径，没有把失效地址当证据。

源码读取和比较不等于已经在本机跑过各项目算法。没有实测分片摘要的准确率、耗时或缓存收益，也没有声称任一框架可无损处理无限上下文。

## Sources

- [Strata fork](https://github.com/TomYule/Strata)
- [Strata #1615（含维护者回复）](https://github.com/Niko1221/Strata/issues/1615)
- [Strata #1623](https://github.com/Niko1221/Strata/pull/1623)
- [Strata #1675](https://github.com/Niko1221/Strata/pull/1675)
- [Strata #1507 Web compaction](https://github.com/Niko1221/Strata/pull/1507)
- [Strata #2508 KV proposals](https://github.com/Niko1221/Strata/issues/2508)
- [Pi compaction](https://github.com/earendil-works/pi/blob/8efd314fa3d3232ce197d8d7a6a5660530b9d83e/packages/coding-agent/src/core/compaction/compaction.ts)
- [Aider history](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/history.py)
- [OpenCode compaction](https://github.com/anomalyco/opencode/blob/1cb7bcadb1653d069ffd22e2d8b696719abbbffe/packages/core/src/session/compaction.ts)
- [LangChain SummarizationMiddleware](https://github.com/langchain-ai/langchain/blob/bd5b134d876ef47858beef27bd29c81eeda03293/libs/langchain_v1/langchain/agents/middleware/summarization.py)
- [LangChain reduce](https://github.com/langchain-ai/langchain/blob/bd5b134d876ef47858beef27bd29c81eeda03293/libs/langchain/langchain_classic/chains/combine_documents/reduce.py)
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
