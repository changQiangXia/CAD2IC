# 修改清单

## MAGE 上游最小修改

### `MAGE/src/mage/gen_config.py`

- 新增 `DeepSeekOpenAI` 元数据适配；
- 新增 `deepseek` provider；
- 从 `DEEPSEEK_API_KEY` 读取密钥；
- base URL 默认 `https://api.deepseek.com`；
- 通过 `extra_body.thinking.type=disabled` 关闭 thinking。

### `MAGE/src/mage/token_counter.py`

- 未知 OpenAI-compatible 模型的 tokenizer 回退到 `cl100k_base`。

未修改 MAGE 的 Agent 角色、提示词、候选数量、修复循环或官方基准判分规则。

## 项目集成代码

- `integration/mage_benchmark_runner.py`
  - VerilogEval 真实 API runner；
- `integration/verilog_eval_official_eval.py`
  - VerilogEval 官方 Makefile evaluator adapter；
- `integration/rtllm.py`
  - RTLLM loader、模块名适配和官方 testbench evaluator；
- `integration/rtllm_runner.py`
  - RTLLM 真实 API runner；
- `integration/test_rtllm.py`
  - RTLLM 最小测试；
- `integration/single_agent_runner.py`
  - Plan 2 单 Agent 闭环 controller；
- `integration/budget_guard.py`
  - 每任务 API/token/time 预算；
- `integration/rtllm_official_eval.py`
  - 独立 RTLLM 官方 evaluator；
- `integration/plan2_select.py`
  - 固定 20 题筛选列表；
- `integration/plan2_analyze.py`
  - A/B/C 配对比较和 bootstrap CI；
- `integration/plan3_select.py`
  - Plan 3 固定重复任务和复杂子集；
- `integration/plan3_repeat_orchestrator.py`
  - 4×2×3 重复实验编排；
- `integration/plan3_analyze.py`
  - 2×2 全量、重复性和复杂子集汇总；
- `integration/plan3_repair_analysis.py`
  - round-1 与最终 RTL 官方评分对比；
- `integration/test_single_agent.py`
  - 隐藏信息边界和预算测试；
- `MAGE/tests/test_mage_integration.py`
  - VerilogEval 最小测试。

## CAD

- 未修改第三方源码、数据、评测代码或已有输出；
- Notebook 只切换了样本运行配置；最终保留 `N_SAMPLES=None`；
- 新增独立 CAD 单题/全量运行记录与预检产物。

## 未修改

- `mac_api_cadtestbench/third_party/Multi-Agent-CAD`
- `mac_api_cadtestbench/third_party/CADTestBench`
- `mac_api_cadtestbench/data/CADTestBench`
- RTLLM 源码
- VerilogEval 源码

## 版本

- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- VerilogEval：`c498220d0a52248f8e3fdffe279075215bde2da6`
- RTLLM V2：`41b26896e33b536940116a975626455eed3de65e`
