# claude-s / clawgod-s 上下文错误兼容修复

日期：2026-10-17。修改 `serve/server.py`，不修改客户端二进制，不增加盲目重试，不截断输入。

## 修复内容

使用服务端完成聊天模板/工具/图像处理后的实际 token 数，检查：

```text
实际输入 + 请求输出额度 + 8 个安全 token <= 服务窗口
```

统一反馈以下字段（位于 HTTP JSON 的 `error.message`，不增加 SDK 不认识的 envelope 字段）：

- `input_tokens`：实际编码后的输入长度，不是字符估算。
- `requested_output_tokens`：调用方请求的输出额度；省略或非正值走自动预算时为 `auto`。
- `required_output_tokens`：错误计算所用的输出预留；自动预算无空间时按最少1 token计算，不把它冒充请求值。
- `safety_tokens=8`。
- `required_total_tokens`：本次需要的总容量。
- `context_limit_tokens`：服务端窗口。
- `excess_tokens`：相对窗口超出的数量。
- `available_output_tokens`：保持输入不变时还可分配的输出额度，不小于0。

### 输入本身放不下

错误前缀：

```text
prompt is too long: 150722 tokens > 131063 maximum input tokens with 1 output token and 8 safety tokens reserved.
```

此处131063是保留最少1个输出token后的可用输入上限，不是把131072窗口写错。后文仍明确列出完整窗口。

例如同时请求8192输出：

```text
input_tokens=150722
requested_output_tokens=8192
required_output_tokens=8192
safety_tokens=8
required_total_tokens=158922
context_limit_tokens=131072
excess_tokens=27850
available_output_tokens=0
```

指示压缩历史或减少输入再试。`fit_max_tokens` 无法解决这种情况。

### 输入能放下，只是输出预算太大

错误前缀：

```text
input length and `max_tokens` exceed context limit:
```

例如输入125000、输出8192、窗口131072：

```text
required_total_tokens=133200
excess_tokens=2128
available_output_tokens=6064
```

明确提示可改为 `max_tokens <= 6064`，或压缩历史以保留8192输出。

## 为什么这样能帮助自动恢复

核对了本机clawgod底层CLI的HTTP400分类逻辑：它识别 `prompt is too long` 和 `input length and \`max_tokens\` exceed context limit`，分别进入输入超长和输出预算超限分类。原来Strata只有 `request exceeds the context window`，不命中所检查的400分类分支。

原生 `claude.orig.exe` 也包含上述识别文本和reactive-compaction逻辑标记。修复保留旧的 `exceeds the context window` 文案，使其他客户端仍可识别；HTTP400/invalid_request_error不变。Responses API仍返回context_length_exceeded/input。

**这让客户端能够正确分类并使用已有恢复机制，不保证每种会话一定自动恢复。** 2026-10-17已完成真实native/clawgod对模拟HTTP服务的双轮实验：两种新文案均触发compact_boundary、摘要交接和后续请求；旧文案也有兼容重发，但没有观察到压缩。输出预算分支在实验中仍保留8192而选择压缩，不能宣称已验证自动降低max_tokens。单轮对话明确报告无法压缩。模拟服务使用合成计数与固定摘要，不是实际超长模型质量验证。详见 `contributions/context-overflow-verification.md`。

## 保持不变

- 不把所有400错误都改成上下文错误。
- 不自动原样重试。
- 不静默删除消息/工具结果，不分片摘要。
- 不修改 `fit_max_tokens` 默认配置；仍为false时用户能收到真实拒绝与可用额度。
- 已配置fit_max_tokens=true的服务仍仅在输入放得下时缩减输出。
- 保留128K窗口、显存预留及其他引擎参数。

## 验证

执行：

```text
python -m unittest serve.test_context_overflow serve.test_responses serve.test_request_accounting
```

结果：原套件55项，54通过、1跳过；扩大到MaxTokens/FitMaxTokens/请求加固后共76项，75通过、1跳过；均无失败。

覆盖三种HTTP API、流式/非流式请求开始前拒绝、精确超出数量、1-token边界、fit开关、非上下文错误不误标，以及“被拒→缩减预算/缩短输入→200成功”。使用MockEngine，不占用当前GPU模型；不是对客户端自动重试的端到端证明。

## 生效与观察

**修改后必须重启Strata的Python服务。当前运行进程不会热加载server.py。**

1. 等当前任务结束，关闭Strata服务窗口。
2. 重新启动对应模型BAT（例如run-unsloth-ud-iq4_xs.bat）。
3. 再使用claude-s或clawgod-s，观察超窗时是否出现压缩/调整预算后恢复。
4. 若仍拒绝，保留完整错误，重点看input_tokens、excess_tokens和available_output_tokens，不重复发送同一请求。

升级Strata可能覆盖本地源码修改，升级后需复查测试和错误格式。
