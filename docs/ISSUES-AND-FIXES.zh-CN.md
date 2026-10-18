# 本地模型 / OpenCode 问题清单与修复记录

更新时间：2026-10-17（已补充Surfingkeys停用后的浏览器与搜索复测）。状态定义：**配置已修复**不等于**运行时已验证**；重启、真实长会话或根因验证未做时单独标明。

## 问题总表

| ID | 问题 / 证据 | 处理 | 当前状态 |
|---|---|---|---|
| OC-01 | `opencli doctor` 已输出诊断且原 PID 15220 已退出，但 OpenCode bash 仍 running；timeout=60000 也没有完成 | 确认模型已空闲；提供 Esc/退出后恢复及隔离对照流程，不篡改 DB 状态 | **未修复根因，待恢复/复现** |
| OC-02 | 用户要求工具超过10分钟先查状态，不直接取消 | 安装生命周期监控：10分钟首次查询，未完成每2分钟复查；暂停人工等待，查询失败也不杀任务 | **已安装，16项测试和独立OpenCode服务烟测通过；用户窗口需重启**。这是检查/告警，不保证修复OC-01；见 `TOOL-WATCHDOG.zh-CN.md` |
| BR-01 | 截图显示 Browser Bridge 未连接 | 独立重新运行 doctor，0.67 秒 exit=0，extension v1.0.24 已连接 | **当前连接已恢复、验证通过**；不是本次主动安装/重启修复 |
| BR-02 | OpenCLI导航已创建HTTPS标签，但debugger attach报其他扩展URL不可访问 | 用户临时停用Surfingkeys；新会话复测open与state均exit0，doctor正常 | **当前浏览器操作恢复、验证通过**；前后对照强烈支持Surfingkeys为本机触发因素，未做重新启用反向验证；见 `OPENCLI-ATTACH-INVESTIGATION.zh-CN.md` |
| SEARCH-01 | DuckDuckGo适配器返回exit66/EMPTY_RESULT，实际快照是人机验证页面 | 停止自动重试，不修改适配器绕过验证；等待用户在同一Chrome profile手动完成验证 | **待人工验证后复测**；不能记为真实零结果或搜索已恢复 |
| SEARCH-03 | 用户要求Google等多平台搜索，避免依赖当前被挑战的DuckDuckGo | 实测OpenCLI Google与Brave各返回3条真实结果、exit0；本地客户端规则更新为Google优先、Brave可选 | **替代搜索路径已验证**；Google链接为跳转地址，Brave提供原始URL；不保证以后免验证码、不改变内置WebSearch能力 |
| WEB-01 | context-mode抓取报Cannot find module turndown；Node解析失败而Bun缓存有依赖 | 从已有本地缓存恢复turndown、GFM和domino；真实MCP抓取/索引测试通过 | **已修复并验证**；旧进程若缓存失败需重连；见 `WEB-TOOLS-REPAIR.zh-CN.md` |
| SEARCH-02 | claude-s内置WebSearch空返回；实际走Strata8080，不是报告所称15721 | Strata对不支持的Anthropic hosted web_search类型明确报错；普通自定义搜索函数仍允许 | **代码和17项相关回归验证通过，需重启服务生效**；未增加搜索后端，不能与SEARCH-01混为一项 |
| GPU-01 | Strata 请求开始时 free VRAM=0 MiB，decode 7.6–9 tok/s | IQ4_XS JSON 增加 `--vram-reserve-mib 2048`，保持128K/int8/32K KV驻留 | **配置已修复，待重启及压测**；吞吐提升未测 |
| CFG-01 | 普通 opencode 没有本地 launcher 的工具输出限制/精简压缩提示 | 合并全局 tool_output、compaction、简短规则文件和压缩提示；不改 provider/默认模型/权限/插件 | **已写入并静态验证，待客户端重启** |
| CTX-01 | 旧 OpenCode 同会话39次压缩、重复大结果累计约209万字符 | 96K保守预算、约64K压缩阈值；工具预览200行/12000字节；旧输出裁剪、摘要避免复制 | **缓解配置已完成，长会话改善待验证** |
| VER-01 | opencode-s 原为1.3.2，普通 opencode 为1.19.0 | 本地入口改用同一1.19.0 | **已修复，版本命令通过** |
| MODEL-01 | 客户端名称与后端加载模型可能不同；CC Switch 不会自动换GGUF | 四模型列表、本地入口health核对，不匹配拒绝启动 | **本地入口已验证**；普通 /models 仍需人工匹配后端 |
| CTX-02 | clawgod 历史32K/64K窗口的11条真实超窗错误，启动器和settings参数分叉 | 动态配置统一预算与模型；保留resume/continue | **配置与离线验证通过**；不能据旧记录说当前128K仍超窗 |
| CTX-03 | Strata原HTTP400超窗文案未命中已检查的Claude CLI恢复分类分支 | 区分prompt过长/输出预算过大，反馈实际token、窗口、安全余量、超出量与可用输出 | **代码已修复，55项测试54通过1跳过；待重启Strata及真实客户端恢复验证**；见 `CONTEXT-OVERFLOW-RECOVERY.zh-CN.md` |
| SKILL-01 | 活跃日志尾部大量 duplicate skill name，多处 skills 目录重复注册 | 记录，暂不删除用户技能；与此次工具未完成无直接因果证据 | **待评估，不盲目清理** |
| PLUGIN-01 | 全局8个包插件及本地rtk/ponytail文件可能影响流程 | 保留不动，提供隔离入口对照；未发现能直接证明本次卡死的插件异常 | **待对照，不指认责任插件** |

## 最新待办：浏览器与搜索

- [x] 复现OpenCLI attach_failed并保存trace。
- [x] 用户停用Surfingkeys后，用新会话验证open/state恢复。
- [x] 复测DuckDuckGo并确认EMPTY_RESULT实际来自人机验证。
- [x] 测试Google与Brave，均返回真实搜索结果；更新claude-s/clawgod-s/OpenCode读取的搜索指引。
- [ ] 可选：用户手动完成DuckDuckGo验证后再恢复该平台；当前不作为自动调用路径。
- [ ] 如需Surfingkeys与OpenCLI共存，另做独立Chrome profile或兼容性对照；不自动永久禁用其他扩展。
- [ ] 重启Strata后验证不支持的托管WebSearch明确报错，而非假空结果。

证据：`OPENCLI-ATTACH-INVESTIGATION.zh-CN.md`；DuckDuckGo trace目录`20261017111458-5ca03d35`，其中`state/0001.json`显示challenge-form。浏览器attach恢复不等于原OpenCode工具running卡死根因已修复，OC-01保持开放。

## 1. 当前卡住会话的精确证据

- 项目：`F:/项目/03中转站/new-api`。
- Session：`ses_eb830d3b5ffehqzEHSwLc4hXV7`。
- Message：`msg_147d33c00001VTmBqF6QmlyL86`。
- 工具：bash，参数 `{"command":"opencli doctor","timeout":60000}`。
- 开始：2026-10-17 11:06:48（日志 UTC 为 03:06:48）。
- 截至本次验证，数据库工具状态仍 running，没有 end；原 doctor 进程已不在。
- 后台 daemon PID15868 存在属于正常常驻设计，不因父进程退出就判定为泄漏。
- `/status`：busy=false，queued=0，phase="tool call complete"，prompt_tokens=70624。
- 当前后端上下文131072，最后请求未超窗；模型已完成，但这本身不足以证明客户端 SSE、工具清理、插件每个环节都正常。
- 独立新 doctor：exit0，0.67秒，扩展已连接，Connectivity OK。

**结论边界：** 故障定位在客户端工具/完成生命周期；确切根因未验证，可能涉及进程收尾、流处理或其他客户端状态。不能把独立 doctor 成功当成原会话已解锁，也不能把它归因于上下文。

## 2. 已实施修改

### 2.1 普通 OpenCode 也启用上下文保护

文件：`C:/Users/Administrator/.config/opencode/opencode.json`。

```json
{
  "tool_output": {"max_lines": 200, "max_bytes": 12000},
  "compaction": {
    "auto": true,
    "prune": true,
    "tail_turns": 2,
    "preserve_recent_tokens": 8192
  }
}
```

另增加：

- `instructions` 引用 `Strata/docs/OPENCODE-CONTEXT-RULES.md`。
- `agent.compaction.prompt`：要求简洁交接、保留精确路径/结论/下一步，避免复制旧摘要和完整日志。

作用域说明：这些输出/摘要设置作用于普通 OpenCode 的本地和远程模型；provider、远程模型上限、凭据和默认模型均不变。不设置全局 reserved，避免改变远程模型窗口公式。Strata provider 的 input73728 / output8192 在当前默认公式下约64K触发；本地launcher以81920−16384达到相同目标。

新规则为行为引导，不是保证模型不会循环。工具输出上限也不保证截断每一种技能/系统注入；本次技能内容约29645字符仍是额外上下文来源。

应用脚本：`Strata/scripts/fix-opencode-context.py`，可重复执行且不重复添加规则。

完整备份：

```text
C:\Users\Administrator\.config\opencode\opencode.json.bak-tool-stall-20261017-112443-980618
```

### 2.2 显存预留

文件：`Strata/strata-unsloth-ud-iq4_xs.json`。

仅增加：

```json
"--vram-reserve-mib", "2048"
```

已验证其他字段与备份语义一致，128K、int8、kv-resident32768不变。

语义等价的原配置备份（JSON排版不同）：

```text
Strata/strata-unsloth-ud-iq4_xs.json.bak-20261017-vram-fix
```

没有重启服务。显存预留会减少专家缓存，可能牺牲一部分正常吞吐以避免Windows显存换页；实际是否更快必须重测。

## 3. 当前恢复步骤

### A. 解锁旧工具状态

1. 在卡住的 OpenCode 中按一次 Esc。
2. 如果恢复，告知“doctor 已通过，继续原任务，不重复读取旧文件”。
3. 若 Esc 无效，退出这一个 OpenCode 窗口，不需要停止模型。
4. 从原项目目录恢复；不要同时开两个进程操作同一个会话。

隔离对照命令：

```text
opencode-s-isolated --local-model unsloth-ud-iq4_xs --session ses_eb830d3b5ffehqzEHSwLc4hXV7
```

隔离模式旨在排查全局/项目配置和插件影响，不承诺不再发现任何外部技能目录。若同一工具在隔离模式仍复现，则应优先收集OpenCode进程/流结束证据，不继续无依据禁插件。

**没有直接修改session数据库，也没有把running改成completed。** 此类修改只能掩盖故障，不能恢复内存中的执行流程。

### B. 让配置生效

- 完整退出并重新启动 OpenCode，使用普通 `opencode` 或 `opencode-s` 都会读到新增全局保护。
- 在用户方便时停止Strata窗口，再双击 `Strata/run-unsloth-ud-iq4_xs.bat`。
- 启动日志应出现reserve2048，保持max_context131072。
- 观察验证窗口期间显存余量与警告，不只看空闲时的nvidia-smi。

### C. 最小回归

1. 新会话执行一个只打印固定字符串的命令，确认完成时间和退出码出现。
2. 单独执行一次 `opencli doctor`，确认不是只显示输出而仍running。
3. 执行一次小范围读取，确认工具完成。
4. 最后才恢复登录页面/项目排查任务。
5. 若普通入口卡、隔离入口不卡，保留对照日志后逐个查插件，不一次删除全部插件。

## 4. 验证清单

已完成：

- [x] 原有7项local-client离线测试通过。
- [x] 新增2项context-fix回归测试通过：字段保留、摘要agent已有属性保留、幂等、输出限制。
- [x] 读取最终JSON校验成功。
- [x] provider、model、small_model、plugin、权限配置未改变。
- [x] Strata仅增加2048预留项，与备份做语义对比通过。
- [x] 安装的OpenCode二进制包含新增配置字段的schema定义。
- [x] 新doctor退出成功、连接正常。

待完成：

- [ ] 用户Esc/退出后原会话成功恢复。
- [ ] 重启OpenCode确认新配置运行时加载。
- [ ] 重启Strata确认2048预留生效。
- [ ] 同一小工具在普通/隔离模式A/B无卡死。
- [ ] 长会话不再重复压缩/读取；比较正确率和速度。
- [ ] Windows工具完成阶段的确切根因、可靠复现与真正代码修复。

## 5. 回滚

退出客户端后，用完整OpenCode备份恢复配置；如果期间增加过其他provider，应只回滚本次新增的instructions/tool_output/compaction/agent.compaction字段，不能覆盖后续改动。

停止Strata后，将其备份恢复为原JSON，再启动。不要在进程运行中直接认为文件回滚就已改变已加载参数。

## 6. 证据位置

- `C:/Users/Administrator/.local/share/opencode/log/opencode.log`
- `C:/Users/Administrator/.local/share/opencode/opencode.db`（仅只读查询）
- `Strata/strata-unsloth-ud-iq4_xs.log`
- `http://127.0.0.1:8080/status`、`/health`、`/metrics`
- OpenCLI `dist/src/browser/daemon-lifecycle.js`：daemon使用detached + stdio ignore，不能无证据断定它继承了stdout导致挂起。

本次没有升级OpenCode/OpenCLI、重启daemon、安装浏览器扩展、操作登录凭据、删除技能/插件、修改OpenCode二进制或杀用户客户端。
