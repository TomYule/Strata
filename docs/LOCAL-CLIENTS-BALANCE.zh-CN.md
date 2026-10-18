# clawgod-s / OpenCode 本地上下文排障与统一方案

日期：2026-10-17。此文件是实施与恢复说明，不是已完成长会话性能验证的声明。

## 1. 查到的事实

### OpenCode 确实存在版本分叉

- 普通 `opencode`：`C:\ProgramData\chocolatey\bin\opencode.exe`，实测 **1.19.0**。
- 旧 `opencode-s.cmd`：固定 npm 的 `opencode.exe`，实测 **1.3.2**。
- 旧本地 profile 是独立 XDG 配置，CC Switch 改全局 OpenCode 不会同步进去。
- 全局有 8 个插件；隔离入口不是另一种模型，它主要改变配置/插件来源。但旧入口同时选中了旧二进制，确有行为差异。

### clawgod-s 有配置分叉，没有查到相同的双版本入口问题

- 普通 clawgod 和 clawgod-s 最终调用同一 `.clawgod/cli.cjs`。
- 安装记录：clawgod 2.1.0，底层 CLI 2.1.296。
- 旧 CMD 写 32768 context / 2048 output，专用 settings 又写 61440 / 8192 / 50% compact。
- 专用 settings 覆盖环境后，CMD 注释和实际预算不一致。
- `_NAME` 仍标旧 Orca；当前服务器实际是 UD-IQ4_XS。

### 真实错误与反复压缩不是同一问题

从已保存 transcript 的真实 API error 事件中找到 **11 条明确的 Strata 超窗**，均为 2026-10-12：

- 10 条对 32768 服务窗口。
- 1 条对 65536 服务窗口。
- 例：33108 输入 + 2048 输出 > 32768；65619 输入已超过 65536。
- 这不能证明 10 月 17 日的 131072 服务仍然频繁报超窗。

OpenCode 数据库中的 Strata 记录共 295 条消息；主会话 `ses_ec677f123ffeafp91qrD5i99tQ`：

- 39 次 compaction，记录为 `auto=true, overflow=false`。
- 压缩输入有约 20K 到 81K tokens，部分摘要增长到 4K–5K，至少一次输出到 8192 后以 `length` 停止。
- 433 次工具调用，其中 read 290 次。
- 大于 20000 字符的工具输出累计约 **2,088,768 字符**，不是 tokens。
- 同一个 29973 字符结果重复 15 次、40187 字符重复 14 次、50256 字符重复 11 次。
- 数据库中本地 provider 错误主要为两条连接失败与一条用户/操作中止；未查到该会话保存的 Strata ContextOverflow 错误。

**最有证据的解释是：历史小窗口确实超限；OpenCode 长会话还出现了重复读取→摘要→重新读取的循环。升级二进制值得做，但没有 A/B 证据证明它单独能治好循环。**

## 2. 平衡点

暂时不提高后端 128K。96 GB RAM 并不消除 2080 Ti 上的显存压力；之前日志有只剩 51 MiB 的验证窗口瞬时余量。

| 项目 | 本地起始档 |
|---|---:|
| Strata 当前实际窗口 | 131072，保持不动 |
| 客户端保守 context 声明 | 98304 |
| 输出上限 | 8192 |
| 提前压缩目标 | 约 65536 |
| OpenCode 单次工具预览 | 200 行 / 12000 bytes，超出保留磁盘副本 |
| 压缩保留的近期 token | 8192，最多 2 个近期用户轮次 |
| 模型并发 | 不同时加载多个大模型，不增加 batch |

为服务器留下余量应对工具 schema、tokenizer 差异、压缩请求和突然变大的工具结果。客户端 context 是保守预算，不是声称模型只有 96K 原生能力。

### OpenCode 的实际公式已核对

本机 1.19.0 中，设置 `limit.input` 时：

```text
压缩触发 = limit.input - compaction.reserved
```

不设置 input 时，主要走 `context - maxOutputTokens`，只填 reserved 不足以按预期调整。

- CC Switch provider 默认 `input=73728`、output=8192，默认 reserved 取 8192，目标为 65536。
- `opencode-s` 进程 overlay 使用 `input=81920`、reserved=16384，仍为 65536，但明确保留压缩缓冲。
- 1.19.0 的旧工具裁剪默认描述为 false，因此本地 overlay 显式开启 prune。

clawgod 使用 context=98304、auto compact window=81920、pct=80，计算目标约 65536。程序可能有额外预计算/压缩阶段，实际触发仍应看日志。

## 3. 模型选择的边界

四个选项：

| key | 真实模型 |
|---|---|
| `iq3_s` | `qwen3.8-flash-next-iq3_s` |
| `unsloth-ud-iq4_xs` | `qwen3.8-flash-next-unsloth-ud-iq4_xs` |
| `iq2_xs` | `qwen3.8-flash-next-iq2_xs` |
| `orca-iq2_xxs` | `orcarouter-qwen3.8-flash-next-uncensored-iq2_xxs` |

**Strata 8080 只运行一个模型。客户端 `/models` 或 `/model` 的名字切换不能直接换 GGUF 权重。**

新启动辅助程序先检查 `/health`：

- 选择与已加载模型相同：允许启动客户端。
- 不同/未加载：退出并显示对应 BAT，要求先停止旧服务、启动目标，再重试。
- 不强杀进程，不自动重打包，不加载第二个大模型。
- IQ3_S 目前只有 GGUF、没有运行配置，其首次启动仍需本地 setup。
- 核对是**启动时检查**，不是每次请求的动态路由器；会话内不要随便换成其他真实模型，后端切换后重启本地 launcher。

## 4. CC Switch 与全局配置

安装器注册 `providers(app_type='opencode', id='strata')`，保存四模型 raw provider block，直连 `http://127.0.0.1:8080/v1`。

同时合入 `~/.config/opencode/opencode.json` 的 provider 列表：

- 保留已有远程 provider、默认 model、small_model、插件和 instructions。
- 不启用额外 HTTP 代理，不改 LM Studio 8000。
- 不修改普通 clawgod 的全局 provider。
- 不执行 CC Switch CLI 的 `set-current`：本地该 CLI 对 raw OpenCode payload 的支持与现有数据库结构不一致，可能只改标记却不正确同步。

CC Switch 桌面当前可能缓存 provider 列表，安装后重启或刷新桌面。新增项名称：**Strata local (4 models)**。桌面的启用/停用同步仍应以全局 `provider.strata` 是否存在为准。

`opencode-s` 从全局配置读取 Strata provider；若 CC Switch 停用并移除该块，启动器拒绝启动，**不会偷偷重新启用**。但普通 OpenCode 或已启动进程可能缓存旧配置，启停后应重新启动客户端。

## 5. 启动器行为

安装后：

```text
opencode-s
clawgod-s
clawgod-ss
```

交互运行显示四模型菜单，回车选当前后端。

```text
opencode-s --local-list
opencode-s --local-check
opencode-s --local-model unsloth-ud-iq4_xs
clawgod-s --local-model iq2_xs
clawgod-s --local-model unsloth-ud-iq4_xs --resume <session-id>
```

- `--local-check` 只验证 health、配置和预算，不发推理。
- 其余参数传给原客户端；不要再用 `--model` / `--settings` 覆盖受管理的本地选择。
- 不添加固定新 session-id，原生 resume/continue 行为保留。
- 当前工作目录保持不变。
- `opencode-s` 统一用 Chocolatey 1.19.0，加载 CC Switch 全局配置，因此全局插件仍会生效。
- `opencode-s-isolated` 用同一个新版程序，但隔离全局/项目配置，便于排查插件问题；provider 仍以 CC Switch live config 为来源。
- `clawgod-s` 保留原本跳过权限模式，`clawgod-ss` 保留原本较安全入口及已有 Bash allow；本次没有扩大权限。
- clawgod 的 per-process 临时 settings 继承专用设置、hooks 和 permissions，只统一本地模型与预算，不改原始 settings 文件。

辅助文件 `LOCAL-CLIENT-CONTEXT-RULES.md` 引导小范围读取与摘要；这是行为建议而不是强制钩子。OpenCode 另有工具输出截断机制。若模型无视建议仍然循环，应停止会话，用简短交接摘要开新会话，不能承诺靠提示词彻底解决。

## 6. 安装与当前状态

实现文件：

- `Strata/scripts/local-client.py`：四模型菜单、health 核对、按服务窗口计算预算、客户端进程隔离。
- `Strata/scripts/install-local-clients.py`：备份、注册 CC Switch provider、保留全局设置并更新四个启动入口。
- `Strata/scripts/test_local_client.py`：无 GPU / 无网络推理的逻辑测试。

**2026-10-17 10:35 安装已完成。** 先前被阻止的安装已成功执行；误换行进入 Python 交互模式的后台任务已停止。CC Switch 数据库、全局 OpenCode provider 和四个启动入口已更新，远程默认模型及已有插件保持不变。备份目录：`C:\Users\Administrator\.cc-switch\backups\strata-clients-20261017-103552-799921`。下方命令留作安装记录，当前无需重复运行。

在 Claude Code 输入：

```text
! "D:/Programs/strata-windows-x64-cuda12/Strata/.venv/Scripts/python.exe" -I "D:/Programs/strata-windows-x64-cuda12/Strata/scripts/install-local-clients.py"
```

或在 PowerShell：

```powershell
& 'D:\Programs\strata-windows-x64-cuda12\Strata\.venv\Scripts\python.exe' -I 'D:\Programs\strata-windows-x64-cuda12\Strata\scripts\install-local-clients.py'
```

安装器生成时间戳备份目录：

```text
C:\Users\Administrator\.cc-switch\backups\strata-clients-<timestamp>\
```

其中有 SQLite 一致性备份、原始 JSON/CMD 以及 restore-map。若已存在不同内容的 `strata` provider，安装器停止而不是直接覆盖。

安装后执行：

```text
opencode-s --version
opencode-s --local-list
opencode-s --local-check
clawgod-s --local-check
```

然后先新开一个小任务会话，确认模型名、工具调用和压缩行为；再处理旧会话。不要把几十万字符旧日志整段粘到新会话。

## 7. 验证结果与尚未验证

已通过：

- 7 项离线测试：参数传递、非法模型、不同服务窗口预算、匹配/不匹配、clawgod hooks/permissions 保留、OpenCode provider 拷贝及停用时拒绝。
- 辅助程序对当前 128K UD-IQ4_XS 的 clawgod dry-run 通过。
- 选择 IQ2_XS 而后端为 IQ4_XS 时返回退出码 3，无进程被停止。
- 四个候选模型列出正确。
- 安装完成后 `opencode-s --version` 返回 1.19.0。
- `opencode-s --local-check` 和 `clawgod-s --local-check` 均通过：当前 UD-IQ4_XS，服务窗口 131072、客户端预算 98304、输出 8192、压缩目标约 65536。
- CC Switch DB 中的四模型 provider 与全局 live config 一致；远程默认模型保留。

未完成：
- CC Switch UI 启停往返验证。
- 新 OpenCode 真实 TUI 加载及全局插件兼容性验证。
- 39 次压缩问题的长会话 A/B 与真实吞吐改善验证。
- IQ3_S 打包或任意后端切换；本次没有进行。

## 8. 回滚

先退出相关客户端及 CC Switch。按 backup/restore-map 恢复原 CMD 和两个 OpenCode JSON。只在明确要恢复整个 CC Switch 状态、且期间没有其他新增改动时恢复整份 DB；否则从当前 DB 删除本次 `strata/opencode` 记录并恢复对应 live provider，避免抹掉后续配置。不要删除用户会话、模型或日志。

## 9. LM-config 记录哪些可借鉴

参考：`D:\Programs\CC Switch\LM-config\claude-lm长期运行注意事项与最佳平衡.md` 及其日志排障手册。

继续采用：单请求、有限输出/思考、提前压缩、避免全量日志、显存留余量、不要用无限超时掩盖卡死、按最小请求→工具→长任务顺序验证。

不照搬：旧 27B 模型的 GPU offload=60、batch=256、关闭 speculation、48 GB 内存假设。这次是 96 GB RAM + MoE Strata，已有 MTP、KV streaming，不是同一引擎参数体系。
