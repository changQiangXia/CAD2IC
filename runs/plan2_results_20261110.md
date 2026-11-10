# Plan 2 结果：隐藏官方 Testbench 与单 Agent 对照

## 结论先行

在本次单次全量运行中：

1. 官方 testbench 辅助生成带来明显提升；
2. 隐藏官方 testbench 后，单 Agent 的点估计略高于 MAGE；
3. VerilogEval 上 MAGE vs 单 Agent 的 95% bootstrap 区间跨 0，不能声称差异显著；
4. RTLLM 上只有 1 题差异，证据很弱；
5. 单 Agent 使用更少 API 调用和 token。

因此不能声称“多智能体提高通过率”。更准确的结论是：

> 在当前 DeepSeek、单次采样、测试台隐藏和统一预算下，MAGE 多智能体没有表现出
> 稳定优于单 Agent 闭环修复的效果；官方 testbench 是否在生成阶段可见，是更强的
> 影响因素。

这里的 bootstrap 只在 task 维度重采样，不覆盖远程模型跨重复运行产生的随机波动。
A 组与 B 组还是不同时间采集的独立运行，因此 testbench 辅助效应应解释为当前数据中的
方向性证据，而不是严格的单变量因果估计。若需要显著性结论，应让 A/B/C 各重复
3 次并使用重复实验方差。

## 三组实验

```text
A. MAGE-assisted：官方 testbench 在生成阶段可见
B. MAGE-hidden：官方 testbench/reference RTL 在生成阶段隐藏
C. Single-hidden：单 Agent 闭环，官方 testbench/reference RTL 在生成阶段隐藏
```

信息边界：

- B 的 `golden_tb_path=None`；
- B 的 `golden_rtl_blackbox_path=None`；
- C 只有一个系统角色和一份对话历史；
- C 只获得规格，自生成 RTL 与 testbench；
- 官方 testbench 仅在生成结束后由独立 evaluator 读取。

## 20 题筛选

筛选列表按固定哈希和类别分层生成，不以结果挑选：

| 基准 | MAGE-hidden | Single-hidden |
|---|---:|---:|
| VerilogEval V2 | 17/20 | 15/20 |
| RTLLM V2 | 16/20 | 15/20 |

筛选阶段 MAGE 点估计更高，全量阶段单 Agent 点估计更高。这个方向变化本身说明
单次运行的差异并不稳定。

## VerilogEval V2 全量

| 组 | 描述 | 通过 | 官方 pass@1 |
|---|---|---:|---:|
| A | MAGE + 官方 TB 可见 | 141/156 | 90.3846% |
| B | MAGE + 官方 TB 隐藏 | 115/156 | 73.7179% |
| C | 单 Agent + 官方 TB 隐藏 | 121/156 | 77.5641% |

### Testbench 辅助效应

`A - B = +26 题 = +16.6667` 个百分点。

配对 bootstrap 95% CI：`[+9.6154, +23.7179]` 个百分点。

A 单独通过而 B 未通过 30 题；B 单独通过而 A 未通过 4 题。

### B vs C

以 C-B 表示单 Agent 减 MAGE：

- 差值：`+6 题 = +3.8462` 个百分点；
- 任务级配对差值 95% CI：`[-3.2051, +10.8974]` 个百分点；
- C 单独通过 18 题；
- B 单独通过 12 题。

CI 跨 0，只能作描述性结论。

### 官方结果码

B：

- `.`：115
- `R`：29
- `m`：8
- `T`：3
- `C`：1

C：

- `.`：121
- `R`：30
- `C`：1
- `T`：3
- `m`：1

## RTLLM V2 全量

| 组 | 描述 | 通过 | 官方 pass@1 |
|---|---|---:|---:|
| A | MAGE + 官方 TB 可见 | 42/50 | 84.0% |
| B | MAGE + 官方 TB 隐藏 | 36/50 | 72.0% |
| C | 单 Agent + 官方 TB 隐藏 | 37/50 | 74.0% |

### Testbench 辅助效应

`A - B = +6 题 = +12` 个百分点。

配对 bootstrap 95% CI：`[+2, +24]` 个百分点。

A 单独通过 7 题；B 单独通过 1 题。

### B vs C

以 C-B 表示：

- 差值：`+1 题 = +2` 个百分点；
- 95% CI：`[0, +6]` 个百分点；
- 只有 1 题从 B 失败变为 C 通过，没有反向变化。

只有 1 题差异，不能据此作稳定结论。

### 官方失败分类

B：

- artifact missing：2
- compile error：4
- functional mismatch：4
- runtime error：3
- simulation timeout：1

C：

- compile error：5
- functional mismatch：4
- runtime error：3
- simulation timeout：1

## 自测与官方判分

| run | 自测通过 | 官方通过 |
|---|---:|---:|
| B × VerilogEval | MAGE self 138 | 115 |
| C × VerilogEval | 151 | 121 |
| B × RTLLM | MAGE self 36 | 36 |
| C × RTLLM | 50 | 37 |

单 Agent 自生成 testbench 明显偏乐观，尤其 RTLLM 自测 50/50、官方 37/50。
因此自测不能替代官方 testbench。

## 资源使用

| run | API calls | 总 token | 累计耗时 |
|---|---:|---:|---:|
| B × VerilogEval | 792 | 4,700,676 | 约 104 分钟 |
| C × VerilogEval | 281 | 1,760,722 | 约 58 分钟 |
| B × RTLLM | 236 | 1,686,637 | 约 47 分钟 |
| C × RTLLM | 95 | 673,601 | 约 23 分钟 |

单 Agent 在两组基准上都使用更少调用和 token。

## 预算与中断

- 每任务上限：120 calls、500000 token、1800 秒；
- C × VerilogEval：1 题 token 预算耗尽，保留在官方分母；
- C × VerilogEval 曾在第 54 题后因 DeepSeek 402 余额不足中断，
  充值后显式 resume，正式记录完整；
- C × RTLLM 遇到多次 HTTP 500/超时，SDK 自动重试关闭，使用独立 resume；
- 首个 B × RTLLM partial run 因出现一次 SDK 自动重试而作废，未纳入正式结果；
  正式结果来自关闭自动重试后的 `_v2` run。

## 产物

- `runs/plan2_results_20261110.json`
- `runs/plan2_B_verilog_eval_full_20261110T002/`
- `runs/plan2_C_verilog_eval_full_20261110T002/`
- `runs/plan2_B_rtllm_full_20261110T002_v2/`
- `runs/plan2_C_rtllm_full_20261110T002/`
- `runs/plan2_B_verilog_eval_screen20_20261110T002/`
- `runs/plan2_C_verilog_eval_screen20_20261110T002/`
- `runs/plan2_B_rtllm_screen20_20261110T002/`
- `runs/plan2_C_rtllm_screen20_20261110T002/`

全部 Plan 2 运行目录中 API Key 出现次数为 0。

## 对外表述建议

可以说：

> 在单次全量、同模型、同信息权限和统一预算条件下，MAGE 隐藏官方 testbench 后的
> pass@1 为 VerilogEval 73.72%、RTLLM 72.0%；单 Agent 闭环分别为 77.56% 和
> 74.0%。差异方向和置信区间不足以支持“多智能体更优”的结论。

不可以说：

- “MAGE 多智能体显著提高通过率”；
- “测试台辅助结果等于独立生成结果”；
- “单 Agent 在所有任务上优于 MAGE”；
- “单次 1 题差异具有统计显著性”。
