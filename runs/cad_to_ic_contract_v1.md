# CAD 到 IC 迁移契约 v1

状态：冻结于 CAD detailed 全量运行完成后。

## Task

- `task_id`：保持基准中的原始标识，不用序号替代。
- `natural_language_spec`：保持官方自然语言规格原文。
- `official_testbench_path`：官方 testbench 或官方测试资源的显式路径。
- `reference_rtl_path`：官方参考实现路径；不存在时可为空，但必须明确记录。
- `metadata`：来源版本、分区、输入哈希及基准专属字段。

契约要求 loader 只做字段映射，不重写题目语义。

## Generator

- 输入：Task 的自然语言规格和 MAGE 原有同质上下文。
- 输出：RTL、内部生成的 testbench、中间代码与修复记录。
- MAGE 的 Agent 角色、提示词、候选与修复循环保持不变。

## Executor

- 输入：RTL、testbench 和官方工具链配置。
- 输出：结构化编译/仿真结果、stdout、stderr、退出码和耗时。
- 必须区分编译器缺失、编译失败、仿真失败和超时。

## Evaluator

- 只调用基准官方 testbench 和官方判分入口。
- 输出：`passed`、基准指标、逐测试结果、错误类别和原始日志路径。
- CAD 的 PR/RS 不迁移到 RTL；VerilogEval 使用 `pass@1`，重复运行才记录
  `pass@5`；RTLLM 使用其官方指标。

## RunRecord

每条任务记录至少包含：

- `task_id`、benchmark 名称和固定 revision；
- 模型名、base URL 和运行日期；
- 输入哈希与官方资源路径；
- 生成状态、修复状态、调用次数和耗时；
- RTL、testbench、仿真日志和最终产物路径；
- 编译、仿真、超时或基础设施错误分类；
- 官方评分结果和包装器错误；
- 实际修改过的文件清单。

## 保持不变与允许替换

保持不变：

- MAGE 的 `TopAgent`、`RTLGenerator`、`TBGenerator`、`Judge` 和编辑修复流程；
- 同质自然语言/TB/RTL/日志输入；
- 每任务独立目录、失败保留在分母和原始日志留存。

允许替换：

- DeepSeek provider 配置；
- benchmark loader；
- 官方 evaluator adapter；
- runner、记录和 README。

禁止替换：

- 用自定义关键字代替官方 testbench；
- 为迁就单一基准修改多个核心 Agent；
- 捕获异常后不写任务记录；
- 将 Key、绝对路径或大体积运行产物写入源码。

## 衔接 IC 阶段的最小测试集

1. loader 正确读取官方题目、testbench 和参考 RTL；
2. 官方参考 RTL 通过 evaluator；
3. 故意破坏的 RTL 被 evaluator 判为失败；
4. 缺少题目、testbench、参考 RTL 或生成产物时返回明确状态；
5. adapter 字段转换不改变题目语义；
6. 一次真实 API 单题 smoke 完成生成、仿真、官方判分和结果记录。

只有第 1 至 5 项通过后才运行第 6 项；第 6 项通过后才进入全量。
