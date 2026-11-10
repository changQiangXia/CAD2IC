# 总体架构

```mermaid
flowchart LR
    A[CADTestBench<br/>200 个官方题目] --> B[CAD 官方执行与评分]
    B --> C[RunRecord<br/>状态/产物/指标/日志]

    D[VerilogEval V2<br/>156 题] --> E[Benchmark Loader]
    F[RTLLM V2<br/>50 题] --> E
    E --> G[MAGE TopAgent]
    G --> H[TBGenerator]
    H --> I[RTLGenerator]
    I --> J[iverilog / vvp<br/>Verilator fallback]
    J --> K[SimJudge / RTLEditor]
    K --> J
    G --> L[官方 Testbench Evaluator]
    L --> M[RunRecord<br/>RTL/TB/仿真日志/指标]

    C -. 共同抽象 .-> M
```

稳定抽象是：

```text
Task -> Generator -> Executor -> Evaluator -> RunRecord
```

CAD 和 MAGE 各自保留原有生成流程；共享部分是实验记录与“官方测试资源判定结果”
思想。两套 Agent 分别保持原有实现，统一层仅承载实验抽象。

## 结构图资产

![总体实验架构](figures/project_architecture.png)

架构图按官方输入、生成工作流、官方评测、RunRecord 与 2×2 对照层组织。PNG 适合
报告与答辩页，SVG 保留文字编辑能力：

- [PNG](figures/project_architecture.png)
- [SVG](figures/project_architecture.svg)

## 实验链路

1. 从固定 revision 读取官方自然语言规格、testbench 和参考 RTL。
2. MAGE 使用原有的 TB 生成、RTL 生成、仿真归因和编辑修复循环。
3. Executor 捕获编译、仿真、超时和运行时错误。
4. Evaluator 直接执行基准官方 testbench。
5. RunRecord 保存任务输入哈希、模型、调用量、token、耗时、产物和分数。

## 日志与复现

每个全量 run 目录保留：

- `protocol.json`
- `records.json`
- `summary.json`
- 每任务详细日志
- 最终 RTL、TB 和中间接口
- 官方评分日志
- 预检与 adapter 复算记录
