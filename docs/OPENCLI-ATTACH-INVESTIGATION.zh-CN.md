# OpenCLI attach 故障：已确认事实与待验证假设

更新时间：2026-10-17。

## 已确认

- CLI v1.8.7可运行；提示有v1.8.8，但未验证该更新是否修复本问题，未升级。
- Browser Bridge扩展v1.0.24已连接，doctor全部通过，连接profile为sv9udwuu。
- `duckduckgo search`与独立浏览器会话打开example.com均出现：
  `attach failed: Cannot access a chrome-extension:// URL of different extension`。
- 独立测试会话的tab list确认URL为https://example.com/，不是选中了扩展顶层页面。
- `tab list`成功只证明标签管理路径可用；返回空数组只说明该会话无标签，不证明CDP附加成功。
- 网页导航已发生但debugger attach失败；未证明OpenCLI自身实现完全无问题，也未证明是其他调试器抢占。

## 冲突候选（尚未证实）

Surfingkeys 1.19.2在全部URL、all_frames、document_start注入，并创建指向自身扩展的frontend.html iframe，与错误类型吻合。

最后只读检查Chrome Secure Preferences时，Surfingkeys和OpenCLI的disable_reasons均为空。该磁盘状态不能替代浏览器实时状态，但没有看到Surfingkeys已停用的记录。

不能据此定性为“Surfingkeys就是根因”，也不能泛称所有翻译/广告扩展都冲突。Chrome/OpenCLI版本兼容性仍是待排除因素。

## 下一步（用户已同意临时停用对照）

1. 用户在Chrome打开 `chrome://extensions/?id=gfbliohnnapiefjpjlpjnehglfpaknnc`，关闭Surfingkeys开关，不卸载。
2. 保持OpenCLI启用。
3. 新建独立测试会话/标签，避免旧页面残留注入影响结果。
4. 验证open、state以及公开搜索，分别记录结果。
5. 只有停用恢复且重新启用后再次失败，才能增强冲突因果判断；重新启用也需使用新页面。

不修改Secure Preferences，不关闭用户标签，不擅自停用其他扩展，不绕过Chrome调试权限。

## profile说明

OpenCLI的 `--profile` 选择已经连接的Browser Bridge profile，不等于自动创建干净Chrome用户配置。独立Chrome profile需要另行建立并安装/启用OpenCLI扩展，待连接后再从 `opencli profile list` 选择。

## 后续复测与上游证据

- 新建会话`strata-check-1017b`的`open https://example.com`仍报attach_failed。
- 同一会话`tab new https://example.com`成功，`tab select`成功，但`state`在25秒测试窗口内未返回。创建/选择成功不等于调试附加已恢复。
- [上游#1341](https://github.com/jackwener/OpenCLI/issues/1341)存在相同错误。评论报告包括“其他扩展停用仍失败”和“tab new可用但open失败”；这些是他机报告，不是本机已排除扩展冲突的证据。
- [v1.8.8发布记录](https://github.com/jackwener/OpenCLI/releases/tag/v1.8.8)含依赖安全更新及CDP endpoint相关改动，但没有明确声明修复这个attach错误。未升级，未修改adapter/extension源码。
- 本机Surfingkeys停用对照仍未确认完成；不重复无意义调用、不凭猜测修改适配器。

## 停用Surfingkeys后的验证结果

用户确认已停用Surfingkeys后，新会话`strata-no-surfingkeys`：

- doctor：通过，OpenCLI扩展仍连接。
- `open https://example.com --window background`：exit0。
- `state`：exit0，读到Example Domain、交互元素和iframes=0。

停用前反复失败、停用后同类新页面成功，强烈支持Surfingkeys为本机触发因素。没有重新启用做反向复现，不声称所有机器或所有扩展版本都存在此冲突。未升级OpenCLI、未改适配器或扩展源码。

搜索复测：`duckduckgo search`不再报attach_failed，但返回exit66/EMPTY_RESULT。Trace状态快照明确显示DuckDuckGo人机验证（challenge-form、要求用户确认搜索由人进行），因此不是有效的“0个匹配”。已停止自动重试，不绕过验证、不修改选择器掩盖问题。

新Trace：`C:/Users/Administrator/.opencli/profiles/default/traces/20261017111458-5ca03d35/summary.md`及`state/0001.json`。

## 状态

**浏览器导航与页面状态读取已恢复；DuckDuckGo搜索待用户手动完成网站验证后复测。** 当前使用OpenCLI时建议保持Surfingkeys停用；若需同时使用，可另建仅安装OpenCLI的Chrome profile再验证兼容性。旧问题清单中的“attach故障未修复”以本节复测结果为准。

Trace：`C:/Users/Administrator/.opencli/profiles/default/traces/20261017094651-45c7a6f5/summary.md`。
