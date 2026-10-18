# TODO：Strata 超窗恢复贡献与分片压缩提案

创建日期：2026-10-17。目标：让 Claude Code / clawgod 正确识别 Strata 的上下文超限，获得真实预算信息并使用已有恢复机制；分片压缩独立规划。

## 边界

- 本轮执行本地准备与测试，不自动push、commit或发布issue/PR。
- 保留已有BAT、frontend工具清洗、客户端配置等工作，不reset、不整体覆盖。
- 不上传个人路径、密钥、会话正文、模型或 `.dmp`。
- 使用独立模拟HTTP服务验证客户端，不向真实模型发送巨量测试输入，不重启正在运行的Strata。

## TODO

- [x] 调研Pi/OpenCode/Aider/LangChain/llama.cpp与Strata已有issue/PR。
- [x] 确认`me`是fork remote，当前分支为main。
- [x] 创建主题分支 `fix/claude-context-overflow`，审查并隔离超窗修复diff；其他本机修改原样保留。
- [x] 为当前/修复错误构造受控测试，运行原生Claude及clawgod单轮/双轮实验。
- [x] 服务端76项测试：75通过、1跳过；新文案双轮实验观察到压缩边界与后续请求；单轮无法压缩如实报告。
- [x] 生成仅含server错误构造及对应测试的独立patch，clean apply通过；英文PR草稿已写入。
- [x] 编写独立分片压缩RFC，明确职责、资源限制及测试标准。
- [x] 更新本清单、修复报告、提交前检查和后续操作。
- [ ] 待用户确认后commit/push及发布PR（本轮不执行）。
- [ ] 分片处理原型实现和质量/延迟基准（独立后续任务，不混入兼容修复）。

## 关联文档

- `CONTEXT-COMPACTION-OSS-RESEARCH.zh-CN.md`
- `CONTEXT-OVERFLOW-RECOVERY.zh-CN.md`
- `ISSUES-AND-FIXES.zh-CN.md`

## 执行产物

- `contributions/context-overflow.patch`：两个文件的最小patch，不含本机工具清洗/启动器修改。
- `contributions/context-overflow-verification.md`：真实客户端模拟实验矩阵、测试结果和限制。
- `contributions/context-overflow-pr-draft.md`：英文PR草稿，未发布。
- `contributions/chunked-compaction-rfc.zh-CN.md`：独立分片工具RFC，未实现。
- `../scripts/probe_context_recovery.py`：本地CLI恢复实验。
- `../scripts/export_context_patch.py`：可重复导出patch并验证admission AST不变。

关键结论：新文案让两个客户端在受控双轮实验中执行压缩后继续；旧文案也会兼容重发，不能说它完全不重试。模拟响应不是实际模型摘要质量证据。当前分支有其他未提交工作，不要整体暂存；没有commit/push。

## 验收标准

1. prompt过长与输出预算过大可区分，实际数量包含8-token安全余量。
2. 无静默截断、无无限重发，非上下文400不误标。
3. 测试覆盖Messages/OpenAI/Responses与边界；客户端实验不读真实用户项目/会话。
4. patch只涉及server错误构造及对应测试；不含其他本机修改。
5. 说明是否实际观察到客户端压缩/重试，不把字符串匹配等同于端到端恢复。
