# MAGE × RTLLM V2 全量结果

## 配置

- RTLLM V2：`41b26896e33b536940116a975626455eed3de65e`
- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- 模型：`deepseek-flash`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- max_tokens：8192
- `use_golden_tb_in_mage=True`
- 结果性质：测试台辅助生成
- 官方 testbench：直接使用 RTLLM 原始 `testbench.v`

## 最终指标

- 样本：50
- 官方通过：42
- 官方失败：8
- `pass@1 = 84.0%`
- MAGE 内置判分通过：38/50

正式分数采用独立官方 testbench 评测。

## 类别结果

| 类别 | 通过/总数 | 通过率 |
|---|---:|---:|
| Arithmetic | 18/19 | 94.74% |
| Control | 6/6 | 100% |
| Memory | 3/5 | 60% |
| Miscellaneous | 15/20 | 75% |

## 失败分类

功能 mismatch（4）：

- `float_multi`
- `barrel_shifter`
- `freq_divbyfrac`
- `freq_divbyodd`

官方 testbench 输出 Error（3）：

- `asyn_fifo`
- `alu`
- `signal_generator`

仿真超时（1）：

- `serial2parallel`

无 RTL 缺失和编译错误。

## 仿真器

- Icarus 12：46
- Verilator 5.054：4

Verilator fallback 只用于以下 Icarus 不兼容 testbench：

- `asyn_fifo`
- `ring_counter`
- `radix2_div`
- `clkgenerator`

所有 50 个参考 RTL 在相同评测器中 50/50 通过。

## Token 与时间

- 输入 token：1,462,034
- 输出 token：839,015
- 总 token：2,301,049
- 逐题累计耗时：约 3782 秒（约 1 小时 3 分）
- 全部 50 题状态：`completed`
- 非空 RTL：50
- 非空 TB：50

## 产物

- `protocol.json`：固定版本、模型和运行配置
- `records.json`：逐题生成和官方评分
- `summary.json`：最终汇总
- `output/`：50 个 MAGE 输出目录
- `logs/`：50 个 MAGE 日志目录
- `official_evaluation/`：50 个官方 testbench 编译/仿真日志

全量目录中 API Key 出现次数为 0。
