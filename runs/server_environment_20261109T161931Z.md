# 服务器环境记录

记录时间：2026-11-09T16:19:31Z

## 主机

- 操作系统：Ubuntu 22.04.3 LTS
- 内核：Linux 5.15.0-78-generic
- CPU：Intel Xeon Platinum 8352V CPU @ 2.10GHz
- 逻辑 CPU：128
- 内存：1.0 TiB
- 项目目录：`/root/autodl-tmp/mac_api_cadtestbench`
- 归档 SHA256：`9efaee30b91c22852af33dda4ab1e9fd18de16e61304172e81cb5c0e256f4325`

## 工具链

- Conda：22.11.1
- Python：3.12.16
- JupyterLab：4.3.6
- Notebook 内核：`MAC · CADTestBench (eval)`（kernelspec 名 `mac-eval`）
- Icarus Verilog：未安装（CAD 阶段不需要，IC 阶段安装）
- vvp：未安装（CAD 阶段不需要，IC 阶段安装）
- Verilator：未安装（IC 阶段安装）

## mac-gen

- 用途：MAC 生成与 CAD 代码执行
- Python：3.12.16
- multi-agent-cad：1.0.0（项目源码 editable 安装）
- build123d：0.12.0
- cadquery-ocp-novtk：7.9.3.1.1
- numpy：2.5.4
- scipy：1.18.1
- langgraph：0.2.76
- openai：3.42.0
- `pip check`：通过
- 核心模块导入：通过

## mac-eval

- 用途：CadQuery 桥接、官方 CADTestBench 评测与绘图
- Python：3.12.16
- cadquery：2.7.0
- cadquery-ocp：7.8.1.1.post1
- numpy：2.3.5
- scipy：1.17.0
- pandas：2.2.3
- pyarrow：19.0.1
- datasets：2.21.0
- `pip check`：通过
- 核心模块导入：通过

## 固定快照

- Multi-Agent-CAD commit：`487f94b7064e935c1a9a2f9b426525d5c94cd857`
- CADTestBench commit：`e29283cc61db7329039d95b429766a50bfd37f89`
- CADTestBench 数据 revision：`2b9a4a972d142d2bc634d072e9d4485f171ced06`
- 已验证文件：112 个
- detailed 样本：200 个
- SHA256 冒烟首题：`00985494`
- 前三题：`00985494`、`00039681`、`00033624`

## API 与运行状态

- API 地址：`https://api.deepseek.com`
- 模型：`deepseek-flash`
- 凭据变量：`DEEPSEEK_API_KEY`
- 当前凭据状态：未设置
- Notebook 冒烟配置：`N_SAMPLES = 1`
- 其余运行配置保持原值

## IC 阶段材料

MAGE、VerilogEval 与 RTLLM 尚未初始化。按计划，它们在 CAD 单题和 detailed 全量运行完成后才开始，不在当前阶段提前混入。
