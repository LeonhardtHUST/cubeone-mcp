---
name: Bug report
about: 报告一个可复现的错误（判据错判、脚本崩溃、通道接不上…）
title: "[bug] "
labels: ["bug"]
---

<!--
提交前请确认：
1. 这不是"能力边界"问题。本仓**只能可靠代做普通 GPIO**（新增引脚 / 改模式 / 改上下拉）；
   UART / SPI / TIM / ADC / I2C 的增改**没有工具能力**，会回 KO 或"回 OK 却一字未改"。
   详见 README「能力边界（先读这段）」与 references/capability-boundary.md。
2. 你已经把 mcp.json / 日志里的 token 换成 ***REDACTED***。
   本仓不做凭据回收，泄露了只能靠自己轮换。
-->

## 一条命令能复现吗

```bash
# 贴出你实际执行的命令（python scripts/... / node tools/... / npx cubeone-mcp ...）
```

**期望**：

**实际**：

## 输出尾行

> 只贴**末尾 10–20 行**就够。判据相关的行（`verdict` / `exit=` / `[越界]` / `[策略拦截]`）请保留原样，不要改写。

```
```

## 环境

| 项 | 值 |
|---|---|
| 操作系统 | （例：Windows 11 23H2 / Ubuntu 24.04） |
| Python | `python --version` |
| Node | `node --version` |
| cubeone-mcp | `node -p "require('./package.json').version"` 或 npm 版本 |
| 通道 | ① 源码直调脚本 ② `npx cubeone-mcp`（MCP） ③ CLI 等价通道 |
| CubeMX / PlatformIO | 版本（不涉及可写"未用"） |

## 相关配置（**脱敏后**）

```jsonc
// 只贴本包这一条；token / Authorization / *_TOKEN / *_KEY 一律替换为 ***REDACTED***
"cubeone-mcp": {
  "command": "vpx",
  "args": ["cubeone-mcp"],
  "env": { "CUBEONE_POLICY": "read_only", "CUBEONE_ALLOWED_ROOTS": "D:\\Projects\\my-project" }
}
```

> `CUBEONE_ALLOWED_ROOTS` **未设置 = 拒绝所有路径参数**（0.7.0 起，BREAKING）。
> 若返回文本以 `[cubeone-mcp][策略拦截] 未配置 CUBEONE_ALLOWED_ROOTS` 开头，那多半不是 bug，
> 而是没配白名单——先看 `docs/guides/npm-publish-and-codebuddy.md` §0 与 §2「注册后自检」。

## 你已经排除了什么

- [ ] 重启过 MCP 客户端（配置是启动时读的）
- [ ] 按 `docs/guides/npm-publish-and-codebuddy.md` §2 做过自检，`allowed_roots=` 是我配的路径
- [ ] 确认改的是普通 GPIO（不是 UART / SPI / TIM / ADC）
- [ ] 确认操作对象是 `testbeds/` 里的副本，不是模板原仓

## 补充

（截图、`verify.json`、日志路径都可以，注意脱敏）
