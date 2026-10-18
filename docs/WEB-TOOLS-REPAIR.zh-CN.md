# claude-s / clawgod-s 网页工具日志与修复

日期：2026-10-17。

## 1. 真实日志证据

用户报告的两次WebSearch空结果与turndown错误定位到：

```text
C:/Users/Administrator/.claude/projects/C--Users-Administrator/1e97cd60-d3cb-4a13-99f6-403eaacbd7a5.jsonl
```

- 第108行：WebSearch查询`LM Studio server status`，结果只有标题/提示，没有链接。
- 第131行：`mcp__context-mode__ctx_fetch_and_index`实际报缺少turndown。
- 第160行：WebSearch查询`Claude Code latest release notes`，同样没有结果条目。
- assistant模型元数据为`qwen3.8-flash-next-unsloth-ud-iq4_xs`。
- 活跃原生`claude.orig.exe`进程使用`run-vrjokyn6/settings.json`，其中endpoint为8080，不是15721。

本次没有定位到一份独立、带相同故障的活跃clawgod会话；claude-s/clawgod-s共用的context-mode插件路径与Strata链路受同样修复影响。不要把claude-s日志误称两个客户端都已分别复现。

全局settings.json确有15721，CC Switch数据库也启用15721代理，但**全局值不是这个claude-s进程的生效配置**。HTTP200也不能证明某次生成经过该端口。

## 2. turndown修复：已完成并验证

插件：`~/.claude/plugins/cache/context-mode/context-mode/1.0.169`。

根因证据：插件没有本地node_modules，Node createRequire解析turndown失败；Bun能从自己的全局缓存找到它。doctor全绿没有覆盖这条HTML转换依赖路径。

恢复了已在本机Bun缓存中的：

- turndown 7.2.4
- turndown-plugin-gfm 1.0.2
- @mixmark-io/domino 2.2.0

仅复制到插件node_modules，无网络安装、无包升级、无lifecycle scripts、无package.json变更，不碰SQLite依赖或已有数据库。

脚本：`scripts/repair_context_html_deps.py`。

验证：`scripts/test_context_html_mcp.py` 直接启动已安装MCP bundle，使用临时索引目录，通过MCP initialize/tools/list/tools/call调用真实fetch_and_index，成功抓取https://example.com并索引1节，无缺依赖错误。

如果旧MCP进程缓存了失败import，重连context-mode或重启客户端。插件升级后目录变化可能需要再次验证依赖。

## 3. WebSearch空结果：服务能力不匹配，不是已证实的代理故障

安装的Claude/clawgod WebSearch实现发送Anthropic托管工具：

```text
web_search_20250305
```

并读取服务端搜索结果块。本地Strata没有实现该托管搜索后端；原先普通工具格式转换可能让它看起来收到一个工具请求，但不会实际进行互联网搜索。

**修复：** `serve/server.py` 的Anthropic入口在加载模型前明确拒绝`type=web_search_*`的托管搜索请求，返回400/invalid_request_error：

```text
Strata does not provide Anthropic hosted web search (...).
No web search was performed.
Use a configured search MCP/CLI provider; fetching a URL is not a search.
```

- 不影响名为web_search的普通用户函数工具；其仍可由客户端真实执行。
- 不影响OpenAI工具调用或其他接口。
- 不伪造搜索结果、不把错误描述成“0条匹配”。
- 更新本地客户端上下文规则，禁止把空搜索结果当成真正检索的结论，禁止根据全局配置猜当前路由。

**状态：已修改代码，必须重启Strata服务才生效。** 这修复的是误导性成功/空结果，**没有新增互联网搜索引擎**。

## 4. 已测试的搜索备用路径仍有问题

本机OpenCLI注册了duckduckgo/google/brave等搜索adapter。尝试现有duckduckgo搜索时返回：

```text
attach failed: Cannot access a chrome-extension:// URL of different extension
```

所以不能宣称备用搜索已恢复。未关闭浏览器扩展、未修改浏览器安全配置、未登录外部服务，也未配置付费API。

后续要恢复真正的搜索能力，需要选择：

1. 修复现有OpenCLI的目标标签页/Browser Bridge附加问题；或
2. 用户提供/授权一个搜索MCP或搜索API，把它接到本地客户端。

通用URL抓取已恢复，但它不负责发现未知网址，不等于WebSearch。

## 5. 测试结果

```text
python -m unittest serve.test_hosted_search serve.test_context_overflow serve.test_request_hardening
```

17项全部通过。覆盖流式/非流式托管搜索拒绝、拒绝前不加载模型、普通同名函数工具仍正常，以及上下文/请求加固回归。

当前会话工具偶发被安全分类器阻止是另一问题，不代表fetch依赖修复失败。真实MCP验证绕开的是本会话工具调用入口的故障，使用的是同一已安装bundle，不改变权限设置。

## 6. 未执行/待完成

- 未重启用户正在运行的Strata/Claude/clawgod。
- 未修改CC Switch provider或全局代理。
- 未实现/配置真正的WebSearch服务。
- 未完成OpenCLI浏览器附加错误修复。
- 未清理历史会话/数据库/技能。

本次hosted-search补丁与超窗上游PR是不同事项，不要混入`context-overflow.patch`。
