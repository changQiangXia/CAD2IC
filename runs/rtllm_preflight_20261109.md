# RTLLM V2 预检记录

## 固定版本与工具

- RTLLM commit：`41b26896e33b536940116a975626455eed3de65e`
- 分支：`v2.0`
- 许可证：MIT
- 设计数：50
- 官方资源：每设计 1 个 `design_description.txt`、`testbench.v`、
  `verified_<design>.v`
- Icarus Verilog：12.0
- Verilator：5.054（`--timing --binary`）

## 数据与 adapter

RTLLM 官方目录与模块名有两处不一致：

- `freq_divbyeven` 的描述写成 `freq_diveven`，但官方 testbench 使用
  `freq_divbyeven`；
- 目录 `fixed_point_substractor` 拼写错误，但描述和 testbench 使用
  `fixed_point_subtractor`。

adapter 优先采用官方 testbench 中实际实例化的模块名，并把参考文件中的
`verified_` 主模块名机械替换为期望模块名。内部逻辑不变。

## 官方参考 RTL

最终预检：50/50 通过。

- Icarus：46
- Verilator：4

Icarus 无法执行的 4 题：

- `asyn_fifo`：官方 testbench 使用 `break`；
- `ring_counter`：官方 testbench 对整个数组赋值；
- `radix2_div`：Icarus 时序语义与官方参考不一致；
- `clkgenerator`：Icarus 时序语义与官方参考不一致。

这 4 题自动使用 Verilator；其余 46 题使用 Icarus。两套都直接编译并运行
RTLLM 原始官方 testbench，成功判定仍来自官方输出文本
`Your Design Passed`。

## 自动测试

`pytest -q test_rtllm.py`：4 passed

覆盖 loader 50 题、参考 RTL 通过、错误 RTL 失败、缺失数据路径。

## 真实 API

- provider：`deepseek`
- model：`deepseek-flash`
- base URL：`https://api.deepseek.com`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- max_tokens：8192
- `use_golden_tb_in_mage=True`
- 性质：测试台辅助生成

### 单题

- `adder_8bit`：官方通过
- 耗时约 28.8 秒
- Token：输入 3990，输出 5212

### 3 题固定验证

- `adder_bcd`：通过
- `asyn_fifo`：失败，最终 RTL 在 Verilator 下出现
  `DIDNOTCONVERGE`
- `traffic_light`：MAGE 内置判分失败，但最终 RTL 通过官方 testbench
- 官方结果：2/3，`pass@1=0.6667`

该组验证了 Icarus、Verilator fallback、成功与失败记录。
