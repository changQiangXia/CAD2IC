# 从 CAD 到 IC 的项目复现与基准迁移方案

## 0. 目标与边界

本方案分两阶段完成：

1. **忠实跑通现有 CAD 基准项目**：在不修改算法和评测逻辑的前提下，验证“自然语言题目 → 多智能体生成 → 工具执行 → 官方测试台评分 → 指标与记录”的完整链路。
2. **迁移到同质输入的 IC 多智能体工作**：以 MAGE 为代码基础，先复现 VerilogEval，再通过独立的 benchmark adapter 换到第二个 RTL 基准。

核心思路始终不变：**使用基准类工作的开源题目、参考实现和官方测试用例，先忠实跑通一个基准，再换另一个基准跑通。** 多智能体流程不涉及异质数据输入，因此更换题目、测试台、参考实现和评测入口即可，不重新设计智能体职责与协作关系。

本方案不采用 ChipMATE 的 Verilog/Python 异质双智能体结构，也不把“CAD 参数改写成 IC 参数”当作技术路线。

项目定位是**研究生保研/复试项目展示**。目标不是提出新算法或新基准，而是展示以下能力：

- 能读懂并忠实运行开源项目；
- 能处理环境、版本、API 和工具链集成；
- 能用官方测试用例而不是主观判断评价生成结果；
- 能将同一套多智能体流程迁移到第二个基准；
- 能解释修改边界、失败原因和结果局限。

因此成功标准是“能运行、能复现、能解释、有数据”，不是“论文创新点足够强”。

### 0.1 尽可能少造轮子

直接复用成熟组件：

- CAD 阶段直接使用方法论和代码已经现成的 `mac_api_cadtestbench`；
- IC 阶段直接使用 MAGE 的多智能体编排和修复流程；
- 测试用例、参考 RTL 和官方 testbench 直接使用 VerilogEval 与 RTLLM；
- 编译、仿真和判分直接使用 iverilog、vvp 及基准官方实现；
- 使用现有 OpenAI-compatible 客户端接入 DeepSeek API。

不自行发明以下内容：

- 新的多智能体框架；
- 新的 benchmark；
- 新的 Verilog 解析器；
- 新的 testbench 通过规则；
- 新的模型训练流程；
- RAG、向量数据库、前端界面或复杂服务化。

允许自行编写的只有必要的适配胶水：模型 provider 配置、benchmark loader、官方评测器入口，以及运行记录。

## 1. 固定材料与版本

### 1.1 CAD 基线

- 项目目录：`/Users/chenxiang/Documents/projects/ICBenchMark/mac_api_cadtestbench`
- Notebook：`MAC_API_CADTestBench.ipynb`
- 模型：`deepseek-flash`
- API 地址：`https://api.deepseek.com`
- 密钥环境变量：`DEEPSEEK_API_KEY`

CAD 阶段固定使用项目内已有的 MAC、CADTestBench、数据和依赖版本，不升级、不替换、不修复源码。

### 1.2 IC 主工作

主工作采用 **MAGE: A Multi-Agent Engine for Automated RTL Code Generation**：

- 论文：https://arxiv.org/abs/2412.07822
- 仓库：https://github.com/stable-lab/MAGE
- 固定提交：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- 许可证：MIT

MAGE 的智能体共享自然语言规格、RTL、testbench 和仿真日志，符合“同质输入、换基准即可复用流程”的要求。

### 1.3 基准与工具

- 第一基准：VerilogEval V2，用于第一次忠实复现。
- 第二基准：当前默认 RTLLM V2，待 MAGE/VerilogEval 跑通后最终确认。
- 仿真器：Icarus Verilog 12.0、`vvp`。
- 静态工具：MAGE 要求的 Pyverilog 和 Verilator。

实施前为 MAGE、VerilogEval 和 RTLLM 分别记录 commit/revision、数据文件哈希和工具版本。第二基准的官方评测命令必须以其仓库实现为准，不使用自定义关键字判定。

### 1.4 修改边界

预计只涉及以下工程改动：

1. MAGE 的模型配置：支持 DeepSeek API Key 和 base URL；
2. benchmark 选择入口：登记 VerilogEval V2 和 RTLLM V2；
3. benchmark adapter：把第二基准的题目转换成 MAGE 已有的同质输入；
4. evaluator adapter：调用第二基准的官方编译、仿真和判分命令；
5. README 和运行脚本：让实验能够被他人按步骤复现。

不修改 `TopAgent`、`RTLGenerator`、`TBGenerator`、`SimJudge`、`RTLEditor` 的协作逻辑。若需要大改这些模块才能换基准，说明选错了目标基准或适配层，应重新选择同质基准，而不是扩大改造范围。

### 1.5 运行环境与项目布局

当前阶段只整理方案和项目材料，不在本地 Mac 安装依赖或运行实验。后续将整个 `ICBenchMark` 目录迁移到服务器后再开始环境安装、模型调用和基准运行。

服务器上保持两个项目独立：

```text
ICBenchMark/
├── plan.md
├── mac_api_cadtestbench/    # CAD 基线，尽量保持原样
├── MAGE/                    # IC 多智能体工作，独立目录
└── runs/                    # 新生成的实验记录和结果
```

- 不把 MAGE 代码复制进 CAD 项目，也不让两个项目共享虚拟环境；
- `mac_api_cadtestbench`、其第三方源码、数据、约束文件和已有输出整体迁移；
- 服务器实验使用新的运行目录，不复用归档中的 Windows 绝对路径；
- 记录服务器操作系统、Python/Conda、iverilog、vvp、MAGE、VerilogEval 和 RTLLM 版本；
- Notebook 通过浏览器端口转发或服务器端执行，不改变其原运行逻辑。

## 2. 阶段 A：忠实跑通 CAD 基线

### 2.1 最小改动原则

只允许修改 Notebook 中的运行配置和环境变量：

- 首次安装时将 `INSTALL_ENVIRONMENTS` 设为 `True`，安装完成后恢复为 `False`；
- 冒烟阶段将 `N_SAMPLES` 设为 `1`；
- `PARTITIONS` 保持 `['detailed']`；
- `SEED`、`REPAIR_BUDGET`、`MAX_API_CALLS_PER_TASK`、`JUDGE_ENABLED`、模型名和 API 地址保持原值；
- API Key 只通过环境变量或 Notebook 隐藏输入提供。

禁止修改：

- `third_party/Multi-Agent-CAD`；
- `third_party/CADTestBench`；
- `data/CADTestBench`；
- Notebook 中的智能体、执行器、桥接和评测代码；
- `ctb_plots.py`；
- 已有 `outputs`；
- 样本筛选和 SHA256 排序规则。

### 2.2 冒烟运行

1. 从 `mac_api_cadtestbench` 根目录打开 Notebook。
2. 安装 `mac-gen` 和 `mac-eval` 两个环境。
3. 将 `INSTALL_ENVIRONMENTS` 改回 `False`。
4. 切换到 `MAC · CADTestBench (eval)` 内核并从头运行。
5. 设置 `N_SAMPLES=1`，其余配置不变。

按照现有协议，第一道样本由 `SHA256(seed:sample_id)` 排序选出，当前应为 `00985494`。不得为了选择已知成功题而修改排序逻辑。

### 2.3 冒烟验收

以下链路全部完成才算跑通：

- 产生新的独立运行目录；
- 完成 DeepSeek 调用并保存任务记录；
- 生成非空 STEP，或明确记录无产物状态；
- STEP 成功进入 CadQuery 桥接；
- 官方 CADTestBench 完成评分；
- 生成逐题结果、汇总指标和可视化文件；
- 失败样本不中断批处理；
- 日志和 JSON 不包含 API Key。

官方测试没有全部通过不等于跑通失败。此阶段的判定标准是评测链路完整，而不是 CAD 通过率。

### 2.4 完整运行

完整运行是必做项，不只是可选验证。冒烟成功后，设置 `N_SAMPLES=None`，使用完全相同的代码和配置运行 detailed 分区 200 题。保留新的运行目录，并与归档结果比较：

- 本机是否产生相同的目录结构和评测产物；
- 相同样本的状态是否可解释；
- 差异是否来自远程模型波动、生成失败或已有工具链问题；
- 不要求 PR、RS 与归档数值完全一致。

若遇到 `Vector.to_tuple` 等已有上游兼容问题，先记录日志并分类，不为修复 CAD 性能扩大改动范围。

## 3. CAD 阶段提取的迁移契约

CAD 跑通后，只提取以下稳定契约，不迁移 CAD 内部实现：

| 契约 | 含义 |
|---|---|
| Task | `task_id`、自然语言规格、官方测试资源路径 |
| Generator | 生成可执行产物和中间代码 |
| Executor | 运行产物并返回结构化错误 |
| Evaluator | 使用官方测试台判定通过或失败 |
| RunRecord | 保存状态、耗时、调用次数、产物路径和错误类型 |

可复用的实验习惯包括固定版本、样本哈希、每任务独立目录、失败保留在分母、官方评测与生成记录分离。

不迁移 `CADBrief`、`ArchitectPlan`、build123d、CadQuery、几何 QA 和 CAD 专用修复提示词。

在实现层，不建设一套新的通用 agent framework。CAD 和 MAGE 各自负责多智能体执行；两者之间只共享“Task → Generator → Executor → Evaluator → RunRecord”这一层抽象。

## 4. 阶段 B：复现 MAGE 与 VerilogEval

### 4.1 保持 MAGE 工作流

MAGE 的主要角色保持原样：

1. `TBGenerator`：根据规格生成接口和 testbench；
2. `RTLGenerator`：生成 RTL；
3. `SimReviewer`：执行 iverilog/vvp 并捕获日志；
4. `SimJudge`：判断问题来自 testbench 还是 RTL；
5. `RTLEditor`：根据仿真日志修复 RTL；
6. `TopAgent`：候选生成、选择和修复循环。

不把 MAGE 改造成 CAD 式的 Planner/Coder/QA，也不引入其他模态的参考模型。

### 4.2 DeepSeek 接入

MAGE 原生支持 OpenAI-compatible 客户端，但当前 `get_llm()` 没有向 OpenAI 客户端显式传入 `base_url`。只允许增加最小 provider 适配：

- 从环境变量读取 `DEEPSEEK_API_KEY`；
- 将 base URL 设置为 `https://api.deepseek.com`；
- 模型名设置为计划使用的 DeepSeek 模型；
- 其他智能体、提示词、候选数和修复逻辑保持不变。

记录模型标识和调用日期。使用 API 运行 MAGE 属于“工作流复现”，不是复现 MAGE 论文中专用训练模型的数值。

### 4.3 第一次运行

先运行 VerilogEval V2：

1. 使用固定提交的 MAGE 和 VerilogEval V2；
2. 先运行 1 道题，检查规格读取、RTL、testbench、仿真日志和官方判分；
3. 再运行 3 道固定题目，覆盖通过和失败；
4. 最后运行完整 VerilogEval V2。

忠实复现阶段保持 MAGE 的 `use_golden_tb_in_mage` 原配置，并明确记录该配置。若该开关为 `True`，报告中必须标注为“测试台辅助生成”，不能与仅依赖自然语言规格的独立评测混用。

测试台和判分优先使用基准官方实现，不自行编写一套替代 testbench 或通过规则。MAGE 内部生成的 testbench 只服务于其原有修复流程，最终成绩仍以官方 testbench 和官方评测结果为准。

VerilogEval 的主要指标使用 `pass@1`；若重复运行，再记录 `pass@5`。不要沿用 CAD 的 PR 和 RS 名称。

## 5. 阶段 B2：更换第二个基准

第二基准当前按 RTLLM V2 设计，但尚未最终锁定。先保持这一默认路线；若 MAGE 与 VerilogEval 本身无法在不修改智能体的情况下顺利跑通，再及时切换同质工作或基准，不陷入长期修补。换基准只改 benchmark 层，不改 MAGE 智能体编排。

### 5.1 Benchmark Loader

将 RTLLM 题目转换成统一结构：

```text
task_id
natural_language_spec
official_testbench_path
reference_rtl_path
metadata
```

### 5.2 Benchmark Evaluator

为 RTLLM 增加独立评测器：

```text
compile_command
simulation_command
timeout
pass_parser
error_classifier
```

评测器必须执行 RTLLM 官方测试台并解析其官方输出，不能只检查固定关键字。

### 5.3 保持不变的部分

- MAGE 的智能体角色和输入类型；
- `TopAgent` 的候选生成与修复流程；
- RTL/testbench/仿真日志的数据形态；
- 每任务记录、超时和失败处理方式。

### 5.4 迁移验收

先跑 1 道 RTLLM 题，确认 loader、iverilog 命令、官方 testbench 和评测器全部接通；再跑 3 道；最后跑完整 RTLLM V2。

若 RTLLM V2 官方接口与当前 MAGE 版本存在无法在不改智能体的情况下解决的冲突，改用另一套同质 spec-to-RTL 基准。不要以 TC-Bench 作为首选，因为它是门级电路效率基准，输入和目标语义与当前 RTL 流程不同。

## 6. 保研/复试展示口径

当前优先级是先跑通实验并形成项目材料。正式复试报告、PPT 和演讲稿等结果确定后再制作，不在实验未完成时投入大量包装工作。

每个阶段记录：

- 来源 commit/revision；
- 模型名、API 地址和运行日期；
- 样本 ID 和输入哈希；
- 智能体调用次数、token 和耗时；
- RTL、testbench、仿真日志和最终产物；
- 官方评分结果；
- 编译失败、仿真失败、超时和基础设施失败；
- 实际修改过的文件清单。

最终至少形成以下作品材料：

1. 一份可执行的 README，包含环境、命令、单题验证和全量运行方法；
2. 一张总体架构图，说明 CAD 与 MAGE 如何共用基准评测思想；
3. 一张 benchmark adapter 图，说明换基准时哪些部分不变、哪些部分替换；
4. 一张结果表，分别列出 VerilogEval V2 与 RTLLM V2 的样本数、通过数和失败分类；
5. 一份失败分析，区分编译、仿真、超时、测试台问题和 API/环境问题；
6. 一份修改清单，证明只改了必要的 provider、loader 和 evaluator；
7. 一段可以现场讲解的 3 分钟项目介绍。

标题建议为：

> 《基于开源多智能体框架的 Verilog RTL 生成复现与跨基准迁移》

工作内容应表述为：

> 先忠实跑通现有 CAD 基准项目，验证生成、执行和官方评分链路；随后基于 MAGE 复现规格到 RTL 的多智能体生成、仿真归因与修复流程；保持智能体输入和协作结构不变，通过 benchmark adapter 从 VerilogEval V2 迁移到 RTLLM V2，并使用两套官方测试用例完成评测。

结果只陈述实际完成的内容。没有单智能体对照时，不声称多智能体提高了通过率；没有独立测试台实验时，不把测试台辅助生成称为零样本生成能力。

对外展示的重点应是：

- 为什么选择这两个开源工作；
- 为什么多智能体输入是同质的；
- 为什么换基准只需要改 adapter；
- 如何保证使用官方测试而非自定义判分；
- 实际改动减少到了哪些文件；
- 两套基准运行中出现了哪些工程问题。

不要把它包装成完整 IC 设计系统。该项目证明的是 RTL 生成工作流复现、工具链集成和基准迁移能力。

## 7. 执行顺序与停止条件

1. 项目迁移到服务器并记录环境；
2. CAD 环境安装完成；
3. CAD 单题端到端完成；
4. CAD detailed 全量完成；
5. 提取并冻结迁移契约；
6. MAGE 单题运行通过；
7. VerilogEval V2 全量运行；
8. RTLLM V2 单题 adapter 通过；
9. RTLLM V2 全量运行；
10. 汇总结果和失败类型，形成项目材料。

每一步产生新的独立运行记录后才进入下一步。遇到环境、数据或官方评测器问题时停止并记录，不通过修改智能体逻辑绕过。重点是证明同一套同质多智能体流程能够忠实复现并完成基准切换。

## 8. 代码边界与 Review 规则

### 8.1 基本边界

上游 CAD 和 MAGE 代码按依赖处理，不作为本项目的主代码库随意重构。集成代码与上游代码分开存放，外部差异集中在 provider、benchmark loader 和 evaluator adapter 中。

优先修改：

- 运行配置和环境变量；
- DeepSeek provider 的最小接入代码；
- VerilogEval/RTLLM 的题目读取和官方评测适配；
- runner、结果记录、测试和 README。

原则上不修改：

- MAGE 的智能体协作逻辑；
- CAD 的智能体、执行器和官方评测逻辑；
- 上游提示词；
- 已固定的第三方源码和依赖版本；
- 为了“更通用”而新增的抽象层。

若上游最小修改不可避免，必须满足以下条件：

1. 单独提交，不与 benchmark 适配或其他功能混在一起；
2. 修改范围足够小，并能引用上游失败原因；
3. 说明不修改就无法继续的原因；
4. 保留修改前后的运行证据；
5. 记录该修改在后续升级时如何处理。

如果一个问题需要同时修改多个核心 Agent 模块，先停止实现，重新判断是否选错了基准或放错了适配层。

### 8.2 修改粒度

- 一个 commit 只解决一个问题；
- 不把格式化、重命名、依赖升级和功能修改混在同一次提交中；
- 优先将单次改动控制在可人工完整 review 的规模，通常不超过 200–400 行；
- 不提前建立插件系统、通用注册中心或万能配置；
- 两个 benchmark 足以支撑的接口才抽象，不为假想中的第三个 benchmark 设计；
- 新增依赖必须说明现有依赖为何不能完成；
- 不在核心流程中出现 benchmark 专属路径、文件命名或解析字段；
- 所有外部命令、超时和失败状态必须可记录、可复现。

### 8.3 Review 顺序

每次修改按以下顺序 review，前一层不通过就不继续讨论代码风格：

1. **范围**：是否只解决当前问题，是否修改了不应修改的文件；
2. **契约**：Task、Generator、Executor、Evaluator 和 RunRecord 的输入输出是否清楚；
3. **评测正确性**：是否调用官方 testbench 和官方判分，是否区分编译、仿真、超时和基础设施失败；
4. **可靠性**：API Key 是否脱敏，路径是否可在服务器运行，子进程和网络请求是否有超时；
5. **可维护性**：是否存在重复逻辑、无用抽象、被吞掉的异常或散落的硬编码；
6. **运行证据**：是否提供命令、日志、样本 ID、官方结果和已知限制。

以下情况应阻止合并：

- 绕过官方评测，改用自定义关键字判分；
- 把官方测试台传入不允许使用它的生成阶段，却仍宣称独立评测；
- 修改 MAGE 核心智能体来迁就单个 benchmark；
- 捕获异常后不记录任务和失败阶段；
- 将 API Key、绝对路径或大体积运行产物写入源码；
- 没有单题运行证据就进入全量；
- 同时修改多个不相关问题，导致无法判断失败来源。

### 8.4 最小测试集

代码改动至少覆盖对应的测试：

1. loader 能从官方数据正确读取题目、testbench 和参考 RTL；
2. 官方参考 RTL 能通过 evaluator；
3. 故意破坏的 RTL 会被 evaluator 判为失败；
4. 缺少题目、testbench、参考 RTL 或生成产物时返回明确状态；
5. adapter 的字段转换不改变题目语义；
6. 一次真实 API 单题 smoke 能完成生成、仿真、官方判分和结果记录。

优先使用 mock 和官方参考实现验证 adapter，避免模型随机性掩盖基础设施错误。测试通过后再进入全量运行。

### 8.5 自我 Review

即使单人开发，也保留轻量 review 流程：

- 编码前写清楚目的、允许修改的文件、输入输出契约和验证方法；
- 编码后查看 `git diff --stat`、`git diff --check` 和完整 diff；
- 单独检查是否误改了上游文件；
- 先跑最小测试和单题 smoke，再看结果；
- 只审查当前改动，重点关注范围、测试泄漏、官方评测、异常处理和不必要抽象；
- 不进行缺少边界约束的大范围重构，不把“能运行”当作“实现正确”。

该规则的目的不是限制实验，而是保证本项目始终停留在“复现与适配”范围内，避免把证明题做成难以维护的重构工程。
