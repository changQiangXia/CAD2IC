# 3 分钟项目介绍

大家好，我的项目是“基于开源多智能体框架的 Verilog RTL 生成复现与跨基准迁移”。

项目目标聚焦一条完整的工程链路：
自然语言题目进入多智能体系统，生成可执行产物，经过工具执行和修复，最后只使用官方
测试资源评分，并留下可复现的实验记录。

第一步是 CAD 基线。我原样运行了 MAC 与 CADTestBench，先完成固定版本、数据和
环境隔离，再跑单题和 200 题全量。最终 PR 是 22%，RS 是 48.08%。这次结果与归档
运行相差约 4.5 个百分点和 2.95 个百分点。两次生成状态分布一致，差异主要来自远程
模型输出波动。我的重点放在证明生成、STEP 桥接、官方评分和可视化链路完整。
要求随机模型逐题数值完全一致。

第二步是 RTL 主基准。我使用 MAGE 固定 commit，保留它原有的 testbench 生成、
RTL 生成、仿真判断和编辑修复流程，只增加 DeepSeek provider。为了验证真正的官方
评测，我既运行了 MAGE 内置 golden-sim，也把最终 RTL 重新放入 VerilogEval 官方
Makefile。最终官方结果是 141/156，即 90.38% pass@1。两套判分在 4 题上存在启发式
差异，因此正式结果采用官方 Makefile，内置结果保留作为审计。

第三步是基准迁移。我选择 RTLLM V2，围绕 50 个设计实现 loader 和 evaluator。
没有修改 TopAgent、RTLGenerator、TBGenerator 或修复逻辑。RTLLM 有 4 个 testbench
无法由 Icarus 12 执行，因此 adapter 对固定 4 题使用 Verilator 5.054 fallback；
其余 46 题继续使用 Icarus。最终官方结果是 42/50，即 84%。参考 RTL 预检为
50/50，说明 loader、模块名转换和 official testbench 入口正确。

这个项目最终证明三点：第一，能忠实复现并运行已有 CAD 与 RTL 工作；第二，能使用
官方测试评价生成结果；第三，在两个基准之间只替换 loader、模块名适配和
evaluator，Agent 协作结构保持原样。

我还补做了 Plan 2 对照。隐藏官方 testbench 后，MAGE 在 VerilogEval 的通过率从
90.38% 降到 73.72%，在 RTLLM 从 84% 降到 72%，说明 testbench 可见性的影响很大。
在相同隐藏信息和预算下，单 Agent 的官方结果是 VerilogEval 77.56%、RTLLM 74%，
点估计略高于 MAGE；VerilogEval 的置信区间跨 0，因此结论范围限于描述性比较。

Plan 3 补全单 Agent-assisted 后，VerilogEval 上 MAGE 为 90.38%，单 Agent 为
80.13%，配对差异为 10.26 个百分点，bootstrap 区间为 4.49 到 16.03 个百分点，
exact McNemar p=0.00154。这是当前最明确的多智能体正向证据。但在 RTLLM-assisted
只差 1 题，hidden 设置下优势稳定性有限。因此项目结论是“有条件有效”，适用范围
限于当前实验条件。10 题三次重复也说明远程模型存在明显波动。

需要明确的是，最初的 A 组开启了 golden testbench 辅助生成，因此报告口径为
测试台辅助生成。Plan 3 提供了 VerilogEval-assisted 的正向证据，hidden 设置、
RTLLM 和 10 题重复都没有稳定复现这一优势，因此只能表述为“有条件有效”。项目展示的
是工作流复现、工具链集成、官方评测和跨基准迁移能力。

## 可视化展示入口

答辩时先打开[完整图册](visualizations/index.html)。推荐讲解顺序如下：

1. 总体架构图：说明 CAD 与 RTL 两条链路、官方 evaluator 与 RunRecord。
2. Benchmark adapter 图：说明输入 loader 与输出 evaluator 的替换边界。
3. 全量 2×2 图：给出四个 arm 的官方 pass@1。
4. 配对效应森林图：说明 VerilogEval-assisted 的正向证据与区间方向。
5. 重复稳定性图：强调远程模型存在运行波动。
6. 复杂子集与失败码图：说明预设分析与官方失败构成。
7. 修复贡献图：说明 round-1 到最终 RTL 的恢复、持续失败与回归。
8. CAD 区：用总指标、类别准确率、STL 图册与可旋转模型完成展示收尾。

现场可用一句话串起图册：

> 四组结果来自冻结实验，主图给出官方分数，森林图给出区间，诊断图解释复杂题与失败，
> 修复审计保留过程收益和回归，CAD 区展示生成实体与官方几何检查。

PNG 适合报告与幻灯片，SVG 适合缩放展示。全部资产与源数据记录在
[manifest.json](figures/manifest.json)。
