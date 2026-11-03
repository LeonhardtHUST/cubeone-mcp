# 生成核验报告（G1）

- **verdict**：`PASS`
- **errors / warnings**：0 / 0
- **期望外设**：GPIO
- **schema**：`platform32.verify_generation/1`
- **生成时间**：2026-11-03T11:59:31+08:00
- **生成日志**：`D:\Projects\GitHub\cubeone-mcp\docs\logs\phase1\regen-success\cubemx-generate.log`
- **main.c**：`D:\Projects\GitHub\cubeone-mcp\testbeds\_verifier-regen\g474\Core\Src\main.c`
- **.mxproject**：`D:\Projects\GitHub\cubeone-mcp\testbeds\_verifier-regen\g474\.mxproject`

| 检查项 | 结果 | 级别 | 说明 |
|---|---|---|---|
| `log_cannot_map` | pass | error | 生成日志无 'Cannot map' 命中（另有 1 条 OptionalMessage_ERROR，属 CubeMX 已知噪音，如 G474 的 VP_RIF_VS_RIF1 见模板 D8，不计入判定） |
| `main_init_present` | pass | error | 全部 1 个期望外设都有初始化函数定义：GPIO → MX_GPIO_Init（exact，定义 L152） |
| `main_init_called` | pass | error | 全部 1 个初始化函数都在 main() 内被调用：GPIO → MX_GPIO_Init（调用 L88） |
| `mxproject_abs_path` | pass | error | '.mxproject' 无盘符绝对路径（换机可复现） |
| `syscalls_path` | pass | error | 生成日志无 syscalls.c / sysmem.c 叠加路径异常 |
