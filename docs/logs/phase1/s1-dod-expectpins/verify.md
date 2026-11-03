# 生成核验报告（G1）

- **verdict**：`PASS`
- **errors / warnings**：0 / 1
- **期望外设**：GPIO
- **schema**：`platform32.verify_generation/2`
- **生成时间**：2026-11-03T12:43:20+08:00
- **生成日志**：`D:\Projects\GitHub\cubeone-mcp\docs\logs\phase1\s1-regen\cubemx-generate.log`
- **main.c**：`D:\Projects\GitHub\cubeone-mcp\testbeds\template-mcu-STM32G474-series\Core\Src\main.c`
- **.mxproject**：`D:\Projects\GitHub\cubeone-mcp\testbeds\template-mcu-STM32G474-series\.mxproject`
- **工程根**：`D:\Projects\GitHub\cubeone-mcp\testbeds\template-mcu-STM32G474-series`
- **生效白名单**：VP_RIF_VS_RIF1

| 检查项 | 结果 | 失败时阻塞 | 说明 |
|---|---|---|---|
| `log_cannot_map` | pass | 是 | 生成日志无 'Cannot map' 命中（另有 1 条 OptionalMessage_ERROR，属 CubeMX 已知噪音，如 G474 的 VP_RIF_VS_RIF1 见模板 D8，不计入判定） |
| `main_init_present` | pass | 是 | 全部 1 个期望外设都有初始化函数定义：GPIO → MX_GPIO_Init（exact，定义 L152） |
| `main_init_called` | pass | 是 | 全部 1 个初始化函数都在 main() 内被调用：GPIO → MX_GPIO_Init（调用 L88） |
| `pins_present` | pass | 是 | 全部 1 个期望引脚都在 .ioc 与生成物中对上：PB0.Signal=GPIO_Output + __HAL_RCC_GPIOB_CLK_ENABLE() |
| `mxproject_abs_path` | pass | 是 | '.mxproject' 无盘符绝对路径（换机可复现） |
| `mx_script_abs_path` | warn | 是 | 1 处占位符未替换（脚本未配置，直接跑会失败）：scripts/cubemx-init.mx:5: __PROJECT_DIR__（in_comment=false） ← project path __PROJECT_DIR__。扫描 3 个 .mx 脚本，0 处绝对路径指向本工程 |
| `syscalls_path` | pass | 否 | 生成日志无 syscalls.c / sysmem.c 叠加路径异常 |
