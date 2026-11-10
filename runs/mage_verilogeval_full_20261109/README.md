# MAGE × VerilogEval V2 全量结果

## 配置

- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- VerilogEval：`c498220d0a52248f8e3fdffe279075215bde2da6`
- 模型：`deepseek-flash`
- API：`https://api.deepseek.com`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- max_tokens：8192
- `use_golden_tb_in_mage=True`
- 结果性质：测试台辅助生成，不是仅依赖自然语言规格的独立生成能力。
- 运行开始：2026-11-09T19:38:57Z
- 运行结束：2026-11-09T21:49:38Z

## 最终指标

最终成绩以 VerilogEval 官方 Makefile 和 `sv-iv-analyze` 为准：

- `pass@1 = 141 / 156 = 90.3846%`
- 通过：141
- 失败：15
- 官方不可用/未生成产物：6（分类 `m`）
- 官方 raw mismatch：5（分类 `R`）
- 官方编译失败：1（分类 `C`）
- 官方 timeout 标签：3（分类 `T`）

MAGE 内置 golden-sim 统计为 143/156。两者有 4 题差异：

- `Prob078_dualedge`：内置判分因文本存在 “First mismatch” 判失败；官方
  analyzer 依据末行 `Mismatches: 0` 判通过。
- `Prob082_lfsr32`、`Prob141_count_clock`、
  `Prob156_review2015_fancytimer`：实际 mismatch 为 0，但日志含测试台正常结束时的
  `TIMEOUT` 文本，官方 analyzer 将其分类为 `T`。

对外结果使用官方 141/156，并单独保留 143/156 的内置判分记录用于审计。

## 官方失败列表

`m`（6）：`Prob071_always_casez`、`Prob115_shift18`、`Prob145_circuit8`、
`Prob146_fsm_serialdata`、`Prob148_2013_q2afsm`、`Prob154_fsm_ps2data`。

`R`（5）：`Prob054_edgedetect`、`Prob062_bugs_mux2`、
`Prob093_ece241_2014_q3`、`Prob117_circuit9`、`Prob149_ece241_2013_q4`。

`C`（1）：`Prob099_m2014_q6c`。

`T`（3）：`Prob082_lfsr32`、`Prob141_count_clock`、
`Prob156_review2015_fancytimer`。

## Token 与时间

- 输入 token：5,064,720
- 输出 token：2,219,927
- 总 token：7,284,647
- MAGE 逐题累计耗时：约 7841 秒（约 2 小时 10 分）
- 官方 156 题编译与仿真复算：约 20 秒
- 全部 156 题状态：`completed`
- testbench：156
- golden simulation 记录：156
- 非空最终 RTL：150
- MAGE 包装器/API/评测器级异常：0

## 产物

- `protocol.json`：固定版本与运行配置
- `records.json`：逐题 RTL、TB、仿真日志、耗时、token 和官方结果
- `summary.json`：MAGE 内置 golden-sim 汇总（143/156）
- `official_summary.json`：最终官方 Makefile 汇总（141/156）
- `official_verilog_eval/build/summary.csv`：官方逐题结果码
- `official_verilog_eval_repro/`：由可复用 adapter 独立重复得到的相同官方结果
- `output/`：156 个逐题 MAGE 输出目录
- `logs/`：156 个逐题 MAGE 日志目录

全量目录中 API Key 出现次数为 0。
