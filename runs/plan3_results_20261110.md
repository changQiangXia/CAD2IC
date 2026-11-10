# Plan 3 结果：完整 2×2、重复性与修复贡献

## 结论摘要

Plan 3 找到了一个有条件支持多智能体的结果：

- 在 **官方 testbench 可见** 的 VerilogEval 全量中，MAGE 通过 141/156，
  单 Agent 通过 125/156。配对 bootstrap 显示 MAGE 高 10.26 个百分点，
  95% CI 为 `[+4.49, +16.03]`；exact McNemar `p=0.00154`。
- 同一设置下 RTLLM 为 MAGE 42/50、单 Agent 41/50，差异只有 1 题，
  不支持稳定优势。
- 官方 testbench 隐藏时，单 Agent 的点估计略高：
  VerilogEval 121 vs 115，RTLLM 37 vs 36；差异均不稳定。
- 10 题 × 3 次重复显示模型波动明显，因此不能把单次全量结果解释为普遍规律。

最稳妥的结论是：

> MAGE 多智能体在 VerilogEval、官方 testbench 可见的条件下表现出明确的正向信号；
> 该优势没有在 RTLLM 和 testbench-hidden 条件下得到稳定复现。

## 完整 2×2 全量

| 基准 | A: MAGE-assisted | B: MAGE-hidden | C: Single-hidden | D: Single-assisted |
|---|---:|---:|---:|---:|
| VerilogEval V2 | 141/156，90.38% | 115/156，73.72% | 121/156，77.56% | 125/156，80.13% |
| RTLLM V2 | 42/50，84.0% | 36/50，72.0% | 37/50，74.0% | 41/50，82.0% |

### 结构与 Testbench 效应

VerilogEval：

- 隐藏：`C-B = +3.85` 个百分点，CI `[-3.21, +10.90]`；
- 可见：`D-A = -10.26` 个百分点，即 MAGE 高 10.26 个百分点，
  CI `[-16.03, -4.49]`；
- 官方 TB 对 MAGE 的效应 `A-B = +16.67` 个百分点，
  CI `[+9.62, +23.72]`；
- 官方 TB 对单 Agent 的效应 `D-C = +2.56` 个百分点，
  CI `[-2.56, +7.69]`。

RTLLM：

- 隐藏：`C-B = +2` 个百分点，CI `[0, +6]`；
- 可见：`D-A = -2` 个百分点，即 MAGE 高 2 个百分点，
  CI `[-14, +10]`；
- 官方 TB 对 MAGE 的效应 `A-B = +12` 个百分点，CI `[+2, +24]`；
- 官方 TB 对单 Agent 的效应 `D-C = +8` 个百分点，CI `[0, +18]`。

VerilogEval 的 A/D 对比 discordant count 为：

- A 通过、D 失败：20；
- D 通过、A 失败：4；
- exact McNemar `p=0.00154`。

该结果仍来自 A/D 两次独立生成，p 值只作配对描述，不包含跨运行方差。

## 固定 10 题 × 3 次重复

| 基准 | 组 | 三次通过数 | 均值 | 标准差 |
|---|---|---:|---:|---:|
| VerilogEval | A | 9, 9, 7 | 8.33/10，83.33% | 0.94 |
| VerilogEval | B | 7, 8, 6 | 7.00/10，70.0% | 0.82 |
| VerilogEval | C | 8, 8, 7 | 7.67/10，76.67% | 0.47 |
| VerilogEval | D | 6, 6, 6 | 6.00/10，60.0% | 0.00 |
| RTLLM | A | 9, 8, 8 | 8.33/10，83.33% | 0.47 |
| RTLLM | B | 5, 7, 7 | 6.33/10，63.33% | 0.94 |
| RTLLM | C | 7, 7, 7 | 7.00/10，70.0% | 0.00 |
| RTLLM | D | 10, 8, 8 | 8.67/10，86.67% | 0.94 |

重复实验中：

- VerilogEval 的 MAGE-assisted 均值比 Single-assisted 高 23.33 个百分点，
  方向与全量一致，但 10 题 bootstrap CI `[-50, +3.33]` 很宽；
- RTLLM 的 Single-assisted 均值高 3.33 个百分点，CI `[-10, +20]`；
- hidden 条件下，单 Agent 在两组基准的点估计均略高，但 CI 接近或跨 0。

重复实验结果说明全量单次差异不能直接当作稳定优势，但 VerilogEval assisted
实验的方向在全量和重复集中一致。

## 按输入长度定义的复杂任务子集

复杂子集在运行前由规格 `cl100k_base` token 数前 50% 固定。

| 基准 | 复杂子集题数 | A | B | C | D |
|---|---:|---:|---:|---:|---:|
| VerilogEval | 78 | 66/78，84.62% | 47/78，60.26% | 47/78，60.26% | 54/78，69.23% |
| RTLLM | 25 | 19/25，76.0% | 17/25，68.0% | 17/25，68.0% | 20/25，80.0% |

VerilogEval 复杂任务上，MAGE-assisted 高于 Single-assisted 15.38 个百分点；
RTLLM 复杂任务上，Single-assisted 高于 MAGE-assisted 4 个百分点。

## 修复贡献

对 C/D 的 round-1 RTL 和最终 RTL 分别使用官方 evaluator：

| run | round1 官方通过 | final 官方通过 | 恢复 | 回归 |
|---|---:|---:|---:|---:|
| C × VerilogEval full | 109 | 121 | 13 | 1 |
| D × VerilogEval full | 120 | 125 | 5 | 0 |
| C × RTLLM full | 34 | 37 | 3 | 0 |
| D × RTLLM full | 35 | 41 | 7 | 1 |

三次 repeat 合计：

- C × VerilogEval：round1 19/30，final 23/30；
- D × VerilogEval：round1 16/30，final 18/30；
- C × RTLLM：round1 19/30，final 21/30；
- D × RTLLM：round1 18/30，final 26/30。

修复确实可以把官方失败转换为官方通过，但也会出现偶发回归。

MAGE A/B 的初始 RTL 无法从现有日志稳定、无歧义地恢复，因此标记为
`not_recoverable`，未进行猜测。

## 资源使用

三次重复生成总资源：

| 基准/组 | API calls | 总 token | 累计耗时 |
|---|---:|---:|---:|
| VE A | 275 | 1,918,574 | 约 31.7 分钟 |
| VE B | 163 | 1,041,385 | 约 25.0 分钟 |
| VE C | 51 | 196,892 | 约 7.4 分钟 |
| VE D | 51 | 315,703 | 约 6.9 分钟 |
| RT A | 156 | 805,458 | 约 27.9 分钟 |
| RT B | 170 | 1,191,068 | 约 18.6 分钟 |
| RT C | 59 | 436,975 | 约 7.0 分钟 |
| RT D | 66 | 542,843 | 约 9.0 分钟 |

MAGE 的调用/token 成本明显更高；单 Agent 是更经济的基线。

## 失败与中断

- API 余额不足、HTTP 500 和超时均保留原记录；
- SDK 自动重试关闭，中断通过显式 `--resume` 恢复；
- 首次 Plan 3 重复编排因目录职责和 RTLLM runner 路由错误产生的空 run 已隔离，
  未纳入结果；
- 正式重复 run 均补满 10/10 任务并完成官方评测；
- Plan 3 所有正式运行目录中 API Key 出现次数为 0。

## 最终判断

可以支持：

- 官方 testbench 可见性具有明显实验价值；
- MAGE 在 VerilogEval-assisted 全量中优于单 Agent；
- 多智能体在复杂 VerilogEval 任务上也有正向点估计；
- 修复循环把部分官方失败转换为官方通过。

不能支持：

- MAGE 在所有基准和设置下都优于单 Agent；
- RTLLM-assisted 已证明多智能体稳定占优；
- hidden 条件下多智能体优于单 Agent；
- 单次 p 值可以替代重复运行方差。

## 产物

- `runs/plan3_results_20261110.json`
- `runs/plan3_repeat_selection_20261110.json`
- `runs/plan3_D_verilog_eval_full_20261110/`
- `runs/plan3_D_rtllm_full_20261110/`
- `runs/plan3_repeats/`
- `runs/plan3_repair_analysis_20261110/`
