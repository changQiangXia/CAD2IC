# Plan 3：补全 2×2 对照、重复性与多智能体贡献分析

执行状态：已完成（2026-11-10）。

结果见 `runs/plan3_results_20261110.md` 与 `runs/plan3_results_20261110.json`。

## 0. 背景

Plan 2 已完成三组全量实验：

```text
A. MAGE-assisted      MAGE + 官方 TB 生成阶段可见
B. MAGE-hidden        MAGE + 官方 TB 生成阶段隐藏
C. Single-hidden      单 Agent + 官方 TB 生成阶段隐藏
```

当前单次全量结果：

| 组 | VerilogEval V2 | RTLLM V2 |
|---|---:|---:|
| A | 141/156 | 42/50 |
| B | 115/156 | 36/50 |
| C | 121/156 | 37/50 |

Plan 3 不改变已经完成的 A/B/C 正式结果，不根据历史成败挑选任务，不通过修改 Agent
提示词或官方判分来追求显著结果。

## 1. 目标

Plan 3 要补足三个缺口：

1. 尚缺 `Single-assisted`，无法完成 2×2 factorial 对照；
2. 每个全量组只有一次运行，无法区分模型波动和架构效应；
3. 还没有量化“修复轮次”本身带来的官方通过率增益。

Plan 3 的目标是形成可核验的证据：

- 官方 TB 可见时，多智能体是否优于单 Agent；
- 官方 TB 隐藏时，差异是否稳定；
- 官方 TB 与 Agent 结构是否存在交互效应；
- 修复流程是否把初始官方失败转换为最终官方通过；
- 多智能体是否在特定类别、复杂任务或失败恢复上具有优势。

## 2. 四组实验

```text
A. MAGE-assisted      MAGE + 官方 TB 可见
B. MAGE-hidden        MAGE + 官方 TB 隐藏
C. Single-hidden      单 Agent + 官方 TB 隐藏
D. Single-assisted    单 Agent + 官方 TB 可见
```

D 组定义：

- 仍只有一个系统角色和一份对话历史；
- 可以看到任务官方 testbench；
- 不可以读取官方 reference RTL；
- 生成自己的 RTL 和反馈用 testbench；
- 根据自生成 testbench 日志闭环修复；
- 最终只使用官方 testbench 评分。

允许 D 读取官方 testbench，是因为 A 同样在生成阶段使用官方 testbench。两组在
“官方 TB 是否可见”这一维度上必须一致。

## 3. 固定材料与信息边界

- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- VerilogEval V2：`c498220d0a52248f8e3fdffe279075215bde2da6`
- RTLLM V2：`41b26896e33b536940116a975626455eed3de65e`
- 模型：`deepseek-flash`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- max_tokens：8192
- Icarus 12.0；RTLLM 的 4 个兼容题使用 Verilator 5.054

A/B/C/D 的所有生成 prompt 不得包含官方 reference RTL。

- B/C：官方 testbench 和 reference RTL 均不可见；
- A/D：官方 testbench 可见，reference RTL 仍不可见；
- 官方 TB 只在最终评分时由 evaluator 读取。

## 4. 阶段一：D 组全量

为完成四组各一次全量的 2×2 表：

- VerilogEval V2：156 题；
- RTLLM V2：50 题；
- 使用 Plan 2 相同模型与生成参数；
- 每任务预算：120 calls、500000 token、1800 秒；
- SDK 自动重试关闭；
- 每 benchmark 独立 run 目录。

官方参考 RTL 不能进入 D prompt。D 的最终分数只来自独立官方 evaluator。

验收：

- 覆盖全部 156/50 题；
- 每题保存 RTL、反馈 testbench、轮次日志、token、调用次数和耗时；
- 成功率统一按官方 `pass@1`；
- API 超时、500、余额不足必须记录并显式 resume，不自动重试。

## 5. 阶段二：固定 10 题 × 3 次重复

重复实验用于估计远程模型波动，不使用全量重跑。

### 5.1 固定任务选择

VerilogEval：

```text
HASH_SORT(SHA256("plan3:20261110:" + task_id))[:10]
```

RTLLM 按类别分层，类内使用相同 SHA256 排序：

```text
Arithmetic       4
Memory           1
Control          2
Miscellaneous    3
```

筛选列表在任何 Plan 3 API 运行前生成并写入
`runs/plan3_repeat_selection_20261110.json`。不得按 A/B/C 的历史通过结果替换题目。

### 5.2 重复次数

- 每个 benchmark、每个 arm 独立运行 3 次；
- 每次 run 使用新的 run 目录；
- run id 固定为 `repeat_1`、`repeat_2`、`repeat_3`；
- 同一组三次运行使用相同任务、prompt、模型参数和预算；
- 不启用 SDK 自动重试。

总任务数：

```text
2 benchmarks × 4 arms × 10 tasks × 3 repeats = 240 task runs
```

### 5.3 主指标

- 每次重复的官方 `pass@1`；
- 三次重复的平均通过率和标准差；
- 每个任务的 `0/3` 到 `3/3` 通过次数；
- 各 arm 的 pooled pass rate；
- task-level bootstrap 95% CI。

### 5.4 次指标

- API calls；
- input/output/total token；
- wall time；
- compile success；
- executable artifact rate；
- 修复后恢复数；
- MAGE-only pass 和 Single-only pass；
- 按类别统计通过率。

## 6. 阶段三：官方评分下界与修复增益

从 C/D 的记录中保存了每轮模型响应。对每个任务的 round 1 RTL 和最终 RTL：

1. 用独立官方 evaluator 分别评分；
2. 比较 `round1` 与 `final`；
3. 统计：
   - unchanged pass；
   - repair recovery：round1 fail -> final pass；
   - regression：round1 pass -> final fail；
   - persistent fail；
4. 对 10 题重复运行同样统计“最终修复增益”。

该分析只验证修复是否有贡献，不把自生成 testbench 的通过当成官方通过。

对 A/B 的 MAGE 日志仅在字段稳定、可无歧义解析时做同样分析；无法可靠恢复初始 RTL
时明确标记 `not_recoverable`，不猜测。

## 7. 预先定义的复杂任务分析

复杂任务集合必须由与结果无关的固定规则定义：

VerilogEval：

- 自然语言 prompt token 数排名前 50% 的任务；

RTLLM：

- 自然语言 description token 数排名前 50% 的任务。

仅使用官方输入长度，不参考 A/B/C/D 的通过情况。复杂集合结果作为预设 secondary
analysis，不作为挑选样本的依据。

## 8. 统计口径

主比较：

```text
Architecture effect, TB hidden:  C - B
Architecture effect, TB visible: D - A
TB effect, MAGE:                 A - B
TB effect, Single:               D - C
```

重复实验中：

- 报告每个 arm 三次重复的平均值和标准差；
- 报告配对任务的 discordant counts；
- 使用 task-level bootstrap 95% CI；
- 可增加 exact McNemar 作为配对二分类补充检验；
- 不因一次显著结果扩大结论。

允许结论：

- “在某设置下点估计更高”；
- “在三次重复中更稳定”；
- “在复杂任务子集中更高”；
- “未观察到显著优势”。

禁止结论：

- 全量单次差异直接称为显著；
- 从测试集结果反向挑题后仍称为预先定义；
- 用自测分数代替官方分数；
- 将 assisted 结果称为零样本独立生成。

## 9. 代码边界

允许新增/修改：

- `integration/single_agent_runner.py`：增加 official-testbench-assisted 模式；
- Plan 3 任务选择、runner 调用和汇总脚本；
- 测试与文档；
- provider 预算层；
- derived-run 和官方 evaluator 复算脚本。

禁止修改：

- MAGE Agent 拓扑；
- MAGE 角色提示词以偏袒 MAGE；
- 单 Agent prompt 使其故意表现较差；
- VerilogEval/RTLLM 官方 testbench；
- 官方评分规则。

## 10. 测试

真实 API 运行前必须通过：

1. D prompt 包含官方 TB，且不包含官方 reference RTL；
2. C prompt 不包含官方 TB 或 reference RTL；
3. 同一 task 在 C/D 中得到相同自然语言规格；
4. 预算守卫；
5. resume 不重复已完成任务；
6. 官方参考 RTL 通过 evaluator；
7. 错误 RTL 被官方 evaluator 判失败；
8. round-1 RTL 与 final RTL 能独立导出；
9. API Key 不出现在任何 run 文件。

## 11. 执行顺序

1. 写 Plan 3 选择脚本并生成固定任务列表；
2. 增加 D-assisted 模式及测试；
3. D × VerilogEval 单题 smoke；
4. D × RTLLM 单题 smoke；
5. D 全量 VerilogEval；
6. D 全量 RTLLM；
7. 4 arms × 2 benchmarks × 10 tasks 的 repeat 1；
8. repeat 2；
9. repeat 3；
10. 官方复算和首次/最终修复分析；
11. 更新结果表和 README；
12. 冻结 Plan 3 结果，不再根据结果追加挑题。

## 12. 停止条件

- prompt 泄漏 reference RTL；
- C/D 信息边界不符合定义；
- 官方 evaluator 被替换；
- 数据或版本变化；
- 同一基础设施错误连续出现且无法显式恢复；
- 发现自动重试未关闭；
- API Key 泄漏。

模型输出失败、官方不通过和预算耗尽不是停止条件。

## 13. 输出目录

```text
runs/plan3_D_verilog_eval_full_<timestamp>/
runs/plan3_D_rtllm_full_<timestamp>/
runs/plan3_<arm>_<benchmark>_repeat_<n>_<timestamp>/
runs/plan3_repair_analysis_<timestamp>/
runs/plan3_results_<timestamp>.json
runs/plan3_results_<timestamp>.md
```

旧 run 不得覆盖。

## 14. 最终交付

- 完整 2×2 全量结果表；
- 10 题 × 3 次重复的均值、标准差和 paired CI；
- 修复恢复/回归统计；
- 复杂任务 secondary analysis；
- 多智能体有效/有限/无效的具体条件；
- 更新后的保研项目结果表和 3 分钟讲解口径。
