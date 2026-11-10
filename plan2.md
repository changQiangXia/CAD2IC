# Plan 2：官方测试台隐藏实验与单智能体对照

执行状态：已完成（2026-11-10）。

结果见 `runs/plan2_results_20261110.md` 与 `runs/plan2_results_20261110.json`。

## 0. 目标与现有基线

本计划只解决两个尚未完成的问题：

1. 消除当前 RTL 结果中“官方 testbench 在生成阶段可见”的辅助效应；
2. 增加一个信息权限和资源预算可比的单 Agent 对照。

不重新设计 MAGE Agent，不更换基准，不修改官方 testbench，不使用自定义判分替代
VerilogEval 或 RTLLM 的官方评测入口。

已有且不再重复运行的实验：

```text
A. MAGE-assisted
   - 官方 testbench 在生成阶段可见
   - VerilogEval 官方：141/156 = 90.3846%
   - RTLLM 官方：42/50 = 84.0%
```

Plan 2 新增：

```text
B. MAGE-hidden
   - MAGE 原有协作结构
   - 官方 testbench 和参考 RTL 在生成阶段均不可见

C. Single-hidden
   - 单 Agent 闭环生成与修复
   - 官方 testbench 和参考 RTL 在生成阶段均不可见
```

## 1. 可以回答的问题

主问题：

> 在相同模型、输入信息、资源预算和官方评分下，MAGE 多智能体结构是否优于单 Agent
> 闭环修复？

次要问题：

> 将官方 testbench 从生成阶段移除后，MAGE 的官方通过率下降多少？

对应比较：

```text
Testbench 辅助效应： A vs B
多智能体结构效应：   B vs C
```

不能使用 A vs C 单独声称多智能体优势，因为两者信息权限不同。

## 2. 固定材料

- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- VerilogEval V2：`c498220d0a52248f8e3fdffe279075215bde2da6`
- RTLLM V2：`41b26896e33b536940116a975626455eed3de65e`
- 模型：`deepseek-flash`
- API：`https://api.deepseek.com`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- 单次最大输出：8192 token
- Icarus Verilog：12.0
- Verilator：5.054
- Pyverilog：1.3.0

任何版本变化都必须新建实验，不与本计划结果混合。

## 3. 信息边界

B 和 C 在生成、候选生成、内部测试和修复阶段：

- 可以看到官方自然语言规格；
- 可以看到 MAGE/静态提示词中的通用示例；
- 不可以读取任务官方 `testbench`；
- 不可以读取任务官方 reference RTL；
- 不可以读取官方 testbench 编译或仿真日志；
- 不可以使用 A 组已有任务产物作为提示或初始答案。

官方 testbench 和 reference RTL 只允许在最终 RTL 写入磁盘后，由 separate evaluator
进程读取。

必须通过自动检查确认：

- B runner 的 `golden_tb_path=None`；
- B runner 的 `golden_rtl_blackbox_path=None`；
- C prompt 不包含任务官方 testbench；
- C prompt 不包含任务 reference RTL；
- C feedback 只来自其自生成 testbench；
- 最终 evaluator 与生成进程分离。

## 4. B 组：MAGE-hidden

直接复用 MAGE 现有流程：

- `TopAgent`
- `TBGenerator`
- `RTLGenerator`
- `SimReviewer`
- `SimJudge`
- `RTLEditor`

只修改运行时信息入口：

```python
golden_tb_path = None
golden_rtl_blackbox_path = None
use_golden_tb_in_mage = False
```

TBGenerator 必须从自然语言规格自行生成 testbench。后续 RTL 生成、仿真归因和修复
只使用这个自生成 testbench。

不修改候选数量、提示词、Agent 分工或修复算法。

## 5. C 组：Single-hidden 闭环单 Agent

### 5.1 Controller 定义

Single-hidden 不是“一枪式输出”，而是一个单角色闭环：

1. 一个 LLM role 接收自然语言规格；
2. 一次响应生成完整 RTL 和用于自测的 testbench；
3. runner 编译并运行该自生成 testbench；
4. 编译/仿真日志反馈给同一个 Agent；
5. 同一 Agent 同时修复 RTL 和 testbench；
6. 自测通过、轮数耗尽、token 预算耗尽或超时后停止；
7. 最终 RTL 交给官方 evaluator。

只有一份对话历史和一份系统角色，不存在 TBGenerator、RTLGenerator、SimJudge、
RTLEditor 等职责分离。

### 5.2 输出契约

每次模型响应必须包含 JSON：

```json
{
  "reasoning": "reasoning text",
  "rtl": "complete RTL module",
  "testbench": "complete self-generated testbench"
}
```

自生成 testbench 必须输出：

```text
SIMULATION PASSED
SIMULATION FAILED - x MISMATCHES DETECTED
```

该文本只用于 C 组内部循环，不参与最终官方评分。

### 5.3 首版轮数

- 初始生成：1 次；
- 最多修复：7 次；
- 合计最多 8 个模型响应；
- JSON 解析失败可在同一个 round 内重试，重试计入 API 调用预算。

如果 8 轮仍失败，保留最后 RTL，并以官方 evaluator 结果记录，不人工挑选候选。

## 6. 统一运行预算

B 和 C 每任务统一使用以下软硬边界：

- 最多 120 次 LLM API 调用；
- 最多 500000 组合 input/output token；
- 最大 wall time：1800 秒；
- 每次响应 max_tokens：8192；
- 不启用 SDK 自动重试；
- API Key 不写入配置、日志或 prompt。

达到预算时立即停止该任务，状态记为：

```text
api_budget_exhausted
token_budget_exhausted
timeout
```

该任务仍保留在官方通过率分母中。

MAGE 内部候选数量和修复轮次保持原值；统一预算只限制总资源，不改变 Agent 选择机制。
最终报告必须同时给出官方通过率、实际 token、调用次数和 wall time。

## 7. 最终评测

### VerilogEval V2

- 最终 RTL 全部生成后，使用 `integration/verilog_eval_official_eval.py`；
- 使用 VerilogEval 官方 Makefile 和 `sv-iv-analyze`；
- 不采用 MAGE 内置 golden-sim 作为最终分数；
- 最终指标：官方 `pass@1`。

### RTLLM V2

- 使用 RTLLM 原始官方 `testbench.v`；
- 46 题使用 Icarus 12；
- 4 个已知兼容题使用 Verilator 5.054；
- 成功判断来自官方输出 `Your Design Passed`；
- 最终指标：官方 `pass@1`。

## 8. 样本与阶段

### 8.1 数据完整性

- VerilogEval 156 题；
- RTLLM 50 题；
- 每次运行前复核 commit、文件数量和 SHA256；
- 缺失题目或测试资源时停止，不跳过分母。

### 8.2 1 题 smoke

VerilogEval：

- `Prob011_norgate`

RTLLM：

- `adder_8bit`

每个基准分别运行 B 和 C，共 4 个 smoke run。验收：

- 不读取官方 testbench；
- 有自生成 testbench；
- 有独立 API 和 token 记录；
- 最终官方 evaluator 完成；
- 无 Key 泄漏；
- 失败样本不会中断脚本。

### 8.3 3 题固定验证

使用固定任务覆盖成功和失败路径：

- VerilogEval：
  - `Prob011_norgate`
  - `Prob070_ece241_2013_q2`
  - `Prob156_review2015_fancytimer`
- RTLLM：
  - `adder_8bit`
  - `asyn_fifo`
  - `traffic_light`

B/C 使用完全相同的任务列表。

### 8.4 20 题筛选

为控制成本先跑固定、不可按结果挑选的 20 题：

- VerilogEval：按 `SHA256("plan2:20261110:" + task_id)` 升序取前 20；
- RTLLM：按类别分层：
  - Arithmetic 8；
  - Memory 2；
  - Control 3；
  - Miscellaneous 7；
  - 每类内部按相同 SHA256 规则选择。

筛选实验用于检查基础设施、预算和失败分类，不以性能结果决定是否进入全量。

### 8.5 全量

- VerilogEval：156 题；
- RTLLM：50 题；
- B 和 C 均独立运行；
- 不把 smoke、3 题或 20 题产物拼入全量结果。

## 9. 统计与结果口径

主指标：

```text
official pass@1 = official passed / total tasks
```

配对任务分析：

- B、C 使用相同 task_id；
- 计算 task-level 配对差值；
- 报告总通过数和绝对百分点差异；
- 报告 bootstrap 95% 置信区间；
- 单次全量结果只作描述性结果，不声称统计显著。

次要指标：

- compile success rate；
- self-simulation pass rate；
- official pass rate；
- 平均/总 token；
- 平均/总 wall time；
- timeout 数；
- API 或工具基础设施失败数；
- testbench 自测通过与官方通过的一致率。

## 10. 失败分类

统一分类：

```text
official_pass
compile_error
elaboration_error
functional_mismatch
simulation_timeout
artifact_missing
api_budget_exhausted
token_budget_exhausted
timeout
infrastructure_error
```

保存：

- 原始编译日志；
- 原始仿真日志；
- 最终 RTL；
- C 的自生成 testbench；
- B 的 MAGE 自生成 testbench；
- API 调用次数、token 和耗时；
- official evaluator 原始结果。

## 11. 代码边界

允许新增：

- `integration/single_agent_runner.py`
- 对应的 prompt/parser 和预算控制；
- Plan 2 运行脚本与测试；
- 汇总脚本；
- README 和结果表。

允许最小修改：

- provider 层增加统一调用/token 预算；
- runner 层记录新增字段。

禁止修改：

- MAGE 的 Agent 角色和协作拓扑；
- MAGE 任务级提示词以偏袒 B；
- 为 C 提供官方 testbench 或 reference RTL；
- VerilogEval/RTLLM 官方 testbench；
- 官方 evaluator 通过规则；
- 通过人工选择候选改善单 Agent 或 MAGE 成绩。

## 12. 测试

在任何真实 API smoke 前必须通过：

1. hidden loader 不把官方 TB/reference 路径交给 Agent；
2. C prompt 不包含官方 TB/reference 内容；
3. 单 Agent JSON 输出能正确写出 RTL 和 TB；
4. 自生成 TB 的编译/仿真反馈可记录；
5. 官方参考 RTL 在四个 evaluator 组合中通过；
6. 错误 RTL 被判失败；
7. 缺失 RTL 返回明确状态；
8. budget wrapper 能在第 121 次调用或 500001 token 前停止；
9. API Key 不出现在 prompt、日志或结果中。

## 13. 输出目录

每个 run 必须独立：

```text
runs/plan2_<arm>_<benchmark>_<stage>_<timestamp>/
├── protocol.json
├── records.json
├── summary.json
├── output/
├── logs/
└── official_eval/
```

不得覆盖已有 run。

## 14. 停止条件

遇到以下情况停止当前阶段并记录：

- 官方 testbench 被泄露给 B 或 C；
- C 实际使用多个角色或调用 MAGE 的 Agent 模块；
- 官方 evaluator 被替换为自定义判分；
- prompt、日志或结果出现 API Key；
- 参考 RTL 不能通过官方 testbench；
- 数据哈希变化；
- 同一基础设施错误导致超过 3 题无法完成；
- token 缓存或远端 API 持续失败，无法区分模型与基础设施结果。

失败的模型输出本身不是停止条件。

## 15. 最终交付

新增：

- B/C 与已有 A 的三组结果表；
- testbench 辅助效应分析；
- 多智能体 vs 单 Agent 对照分析；
- token、耗时和失败类型对比；
- 修改清单；
- 更新 README 中的对外表述。

在完成 B/C 全量前，不声称多智能体优于单 Agent。
