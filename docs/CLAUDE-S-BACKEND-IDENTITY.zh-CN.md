# claude-s 错报 LM Studio：来源与修复

日期：2026-10-17。

## 已确认的链路

本次回答来自：

```text
claude-s -> claude.orig.exe -> http://127.0.0.1:8080 -> Strata
模型：qwen3.8-flash-next-unsloth-ud-iq4_xs
```

证据：

- 11:58 创建的 `~/.local/strata-clients/run-vrjokyn6/settings.json` 指向8080，模型名与上面一致。
- 会话 `~/.claude/projects/C--Users-Administrator/1e97cd60-d3cb-4a13-99f6-403eaacbd7a5.jsonl` 第27行的assistant消息元数据模型一致。
- `/health` 返回 `service=strata`、上述模型、131072上下文。

因此“通过 LM Studio 跑”是回答中的环境判断错误，不是本次后端路由变成8000。

## 过时/范围不当的输入

同一会话第16行 instructions 实际注入用户主目录的 `memory/MEMORY.md`，其中索引写：

> Claude Code runs on LOCAL qwen3.8-27b via LM Studio 127.0.0.1:8000 ...

这条把旧 LM 专用入口的情况泛化成所有 Claude Code 会话，且48GB/模型名称等也是旧状态。`local-qwen-lmstudio-stack.md` 有同样过宽的表述。

第6–8行的 claude-mem SessionStart 附件又注入了旧 LM Studio / Claude-LM 历史记录。它们是历史资料，不能用于判定当前网络路由。

另一个 `strata-clawgod-s.md` 仍写旧 Orca 模型、旧工具/权限和思考状态；这些也需要按实际启动配置核对。

## 已实施修复

`Strata/scripts/local-client.py` 新增每次启动生成的 `runtime-context.md`，通过现有 `--append-system-prompt-file` 传给原生 Claude / clawgod，内容包括：

- 客户端应用是 `claude.orig.exe` 或 clawgod，不等于推理模型身份。
- 本次核验的推理服务是 Strata，不是 LM Studio。
- 端点8080、health模型名、实际服务窗口与客户端预算。
- LM Studio / Claude-LM / 8000历史不代表本次启动。
- 服务更换后应重新检查health，技能只列当前会话真实可用项。
- 继续包含原有上下文控制说明。

此变更不影响权限模式、不改LM Studio配置、不删claude-mem历史，也不关闭记忆功能。

## 状态与验证

- 10项local-client测试通过，包括四模型的动态环境内容。
- 尚未重新发起真实身份问答，不能保证本地模型一定遵守环境说明。
- 对用户主目录旧记忆文件的直接修订被执行环境的许可分类器“暂时不可用”阻止；**旧记忆原文尚未修改**。不要把本报告当成已完成全部记忆清理。
- 生效方式：退出旧claude-s，重新运行claude-s，建议新会话；旧会话历史仍包含错误回答与旧注入。

## 慢响应另行分析

这次问候请求元数据显示输入31557 tokens，即使用户只输入一句问候，系统说明、技能和记忆仍占输入。界面的“Thought for 4m13s”不能单独用于判定一直在推理，需分开队列、预填充、生成及客户端开销。本次不擅自关闭记忆/插件、改变thinking模式来掩盖路由自述问题。
