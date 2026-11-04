## 这个 PR 做了什么

<!-- 一句话。为什么这么改，不要复述 diff。 -->

关联看板行：<!-- 例：`docs/TASKBOARD.md` M2 / R-C2；没有就写"无（说明原因）" -->

## 提交前自检（**勾完再提**）

### 三层测试，贴尾行

```bash
# ① Python 单元测试（记得传干净 basetemp）
python -m pytest tests/ -q --basetemp=<干净目录>
# ② Node 层单测（必须 glob，别传目录）
node --test tests/node/*.test.mjs
# ③ 工具通道冒烟（本机必须加 --require-materials）
node tools/npm_mcp_handshake.mjs --require-materials
```

```
① 
② 
③ 
```

> ⚠️ **`skip` 不算通过**。冒烟汇总里 `skip>0` 时，必须解释缺什么素材；`--require-materials` 下 SKIP 即失败。
> ⚠️ 涉及 `docs/TASKBOARD.md` 的改动，另跑 `python tools/check_taskboard.py`，**必须 rc=0**。
> ⚠️ 涉及版本号/发布正文的改动，另跑 `python tools/check_release.py`，**必须 rc=0**。

### 清单

- [ ] 三条测试尾行已贴（不是"跑过了"，是**贴输出**）
- [ ] `check_taskboard.py` rc=0（改了看板时）
- [ ] `check_release.py` rc=0（改了版本轴或发布正文时）
- [ ] **L 等级已声明**并如实：`L<n> — <实际执行的命令与结果>`，定义见 README「验证等级」
- [ ] 改 `.ioc` 相关的：说明走的是**路径 A（GPIO 透传）**还是**路径 B（非 GPIO 手改）**，
      且 `verdict` / 三级确认（回显 / diff / G1）结论已贴
- [ ] 没有 `push --force` / `--no-verify` / **任何 AI 署名尾注**
- [ ] 一个 PR 只做一件事（格式化 / 行尾 / 版本戳重写单独开）
- [ ] 没有提交 `testbeds/`、`docs/logs/`、`mcp.json`、任何 token
- [ ] 没碰 `D:\Projects\GitHub\` 下的模板原仓 / `NUEDC_2027` / `HUSTRadio` / `leonskill-*`

## 已知风险 / 没覆盖到的部分

<!-- 这一栏空着比写"无"更好—— 真的没有风险再写"无"。 -->

## 变更类型

- [ ] 判据变更（改 `scripts/`）—— 需说明对现有 `verify.json` 兼容性的影响
- [ ] MCP 封装层（改 `lib/`）—— 需说明是否影响退出码映射 / 白名单 / 写策略
- [ ] 纯文档
- [ ] CI / 发布流程
- [ ] 版本 bump（三处同值：`package.json` / `SKILL.md` frontmatter / README 表）
