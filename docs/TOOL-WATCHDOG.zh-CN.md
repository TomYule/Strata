# OpenCode 工具生命周期监控：10分钟检查，继续等待

## 当前行为（按用户最后要求）

**10分钟不是强制终止上限，而是第一次检查点。**

1. 工具出现 pending/running 事件，或进入执行前钩子时开始计时。
2. 持续显示输出不会推迟首次检查。
3. 完成/错误事件到达，或查询确认工具已经完成：停止监控。
4. 到10分钟仍未完成：查询该工具所在消息的最新状态、输出变化和会话状态。
5. 有输出/状态进展：继续等待，2分钟后再次检查。
6. 只有 running 标签、没有可确认进展：记录 `running-unverified`，继续等；不能把 running 当成进程存活证明。
7. 查询失败/无结果：记录 unknown/probe_failed，继续等，不误杀。
8. 等待人工权限确认/回答时暂停计时；question 工具本身不设置强制结束时间。
9. 每2分钟检查一次、每约10分钟提示一次，使用定时器，不忙循环占CPU。

**不自动取消，不自动重试，不自动杀进程，不修改session数据库。** 用户可随时按Esc。没有额外30秒宽限：原先的“120秒+30秒”方案已经被600秒检查方案替换。

命令原有的timeout仍然有效。例如bash自己的60秒超时仍可结束命令；本监控不把它强行加长。若命令未能结束或收尾卡住，600秒检查点负责发现并报告状态。

## 覆盖与边界

- 监控从可观察的工具pending/执行前开始，直到terminal事件；不是仅监控子进程执行时间，也不在tool.execute.after过早解除。
- 覆盖普通OpenCode及opencode-s；隔离入口也安装同一插件。
- 不作用于clawgod-s，它不是OpenCode。
- 不监控工具调用产生之前的模型思考/排队。
- 不会自动接管插件加载之前已经卡住的旧调用；先退出旧窗口再启动。
- SDK没有为所有工具公开可信的子进程PID/心跳；目前检查的是OpenCode消息/输出/会话状态，不伪称已确认操作系统进程存活。
- 即使输出在变化，也不能保证业务任务正确推进。
- 若OpenCode主事件循环完全阻塞，进程内定时器也可能无法执行；这不是外部进程级强制watchdog。
- “确认已经完成但客户端仍忙”的情况下这里只结束监控、记录事实，不改写UI/数据库来伪造成功。
- 原doctor卡死根因仍未确定，这个监控是可观察性和等待策略，不是已验证的根因修复。

## 文件

实际实现：

```text
Strata/scripts/opencode-watchdog/core.mjs
Strata/scripts/opencode-watchdog/probe.mjs
Strata/scripts/opencode-watchdog/plugin.mjs
```

两个加载入口：

```text
C:/Users/Administrator/.config/opencode/plugins/00-tool-watchdog.ts
C:/Users/Administrator/.local/opencode-strata/opencode/plugins/00-tool-watchdog.ts
```

日志：

```text
C:/Users/Administrator/.local/state/opencode/tool-watchdog.jsonl
```

日志只记时间、目录、session/call/tool标识、状态与检查结果，不保存命令参数、提示词、输出正文或凭据。约2MiB轮转保留一份旧日志；多进程并发轮转可能产生写日志警告，不作为审计级持久保证。

关键事件：`loaded`、`started`、`checkpoint`、`status_checked`、`extended`、`finished`、`probe_failed`。

`loaded` 当前应含：

```json
{"firstCheckMs":600000,"recheckMs":120000,"policy":"check-and-extend"}
```

之前短暂开发版本可能留下 `timeoutMs` / `abort_acknowledged` 的测试日志。当前代码不再调用session.abort。

## 如何生效

完整退出并重新启动OpenCode。无需重启Strata，无需修改CC Switch provider，也不改原有权限。

```text
opencode
```

或：

```text
opencode-s
opencode-s-isolated
```

重新运行一个小工具后，日志应出现当前policy的loaded以及started/finished。旧窗口不一定热加载插件，必须重启。

## 验证

- 16项自动测试通过：10分钟时点、输出不重置、2分钟续等、权限/问题暂停、多会话隔离、完成清理、状态查询失败续等、遗漏完成事件的补查、日志不含命令正文。
- 启动一个独立临时OpenCode1.19.0服务器，运行`echo WATCHDOG_SMOKE_OK`，观察真实loaded/started/finished事件。
- 真实message状态API返回completed、session状态返回idle；没有调用模型，没有中断用户会话。
- 首次独立服务烟测在初始化时20秒超时；将测试启动请求等待窗口调到60秒后通过，最终检查/续等版本再次通过且无服务器错误。
- 没有在真实用户任务上等待10分钟验证长任务，也没有证明doctor旧卡点已修复；时间推进逻辑使用虚拟时钟覆盖。

复测命令（CMD）：

```bat
"C:/nvm4w/nodejs/node.exe" --test "D:/Programs/strata-windows-x64-cuda12/Strata/scripts/opencode-watchdog/core.test.mjs" "D:/Programs/strata-windows-x64-cuda12/Strata/scripts/opencode-watchdog/probe.test.mjs"
```

独立服务器烟测：

```bat
"D:/Programs/strata-windows-x64-cuda12/Strata/.venv/Scripts/python.exe" -I "D:/Programs/strata-windows-x64-cuda12/Strata/scripts/test_watchdog_live.py"
```

烟测会创建标有`Watchdog plugin smoke test (no LLM)`的测试会话，不删除用户会话。

## 禁用/回滚

退出OpenCode，把两个`00-tool-watchdog.ts`入口改成非`.ts/.js`后缀（例如`.disabled`），再启动。无需删除实现文件、修改数据库或删除会话。
