# MAGE / VerilogEval V2 预检记录

## 固定版本

- MAGE：`90c96366c518d32bd7b81703bdef3cc46eeaeaf9`
- VerilogEval：`c498220d0a52248f8e3fdffe279075215bde2da6`
- MAGE pyproject 版本：1.0.1
- VerilogEval spec-to-rtl 题目：156
- prompt、testbench、参考 RTL：各 156
- VerilogEval 通过 MAGE gitlink 固定 revision，并使用该 revision 的官方
  codeload 归档解包；Git 协议连接超时，不影响内容版本。

## 环境

- Conda 环境：`mage`
- Python：3.11.18
- Icarus Verilog：12.0 stable
- vvp：12.0 stable
- Verilator：5.054
- Pyverilog：1.3.0
- LangChain：0.3.30（仅供 VerilogEval 官方 `sv-iv-analyze` 使用）
- `pip check`：通过

## 最小测试

`pytest -q tests/test_mage_integration.py`：4 passed

覆盖：

1. loader 逐字读取官方 prompt、testbench 和参考 RTL；
2. 由参考 RTL 改名的官方答案通过官方 testbench；
3. 故意错误 RTL 被官方 testbench 判为失败；
4. 不存在的 benchmark 路径明确抛出 `FileNotFoundError`。

VerilogEval 自带 Makefile 的独立预检结果为官方通过率 1/2：参考 RTL 标记 `.`，
故意错误 RTL 标记 `R`。记录见
`runs/verilog_eval_official_preflight_20261109/`。

## 真实 API 运行

- provider：`deepseek`
- model：`deepseek-flash`
- base URL：`https://api.deepseek.com`
- thinking：disabled
- temperature：0.85
- top_p：0.95
- max_tokens：8192
- `use_golden_tb_in_mage=True`
- 因此结果必须标注为“测试台辅助生成”，不能解释为零样本独立生成。
- 最终成绩只使用 VerilogEval 官方 testbench。

### 单题 smoke

- `Prob011_norgate`：官方通过，`pass@1=1.0`
- 生成耗时：约 9.15 秒
- Token：输入 5022，输出 1754
- 目录：`runs/mage_verilogeval_smoke_20261109`

### 3 题固定验证

- `Prob070_ece241_2013_q2`、`Prob150_review2015_fsmonehot`、
  `Prob151_review2015_fsm`
- 官方通过：3/3，`pass@1=1.0`
- 目录：`runs/mage_verilogeval_three_20261109`

### 失败路径验证

- `Prob153_gshare`：通过
- `Prob154_fsm_ps2data`：通过
- `Prob156_review2015_fancytimer`：失败
- 官方通过：2/3，`pass@1=0.6667`
- 失败分类：生成修复阶段上游 JSON 解析异常；最终 RTL 可编译和仿真，但与官方
  参考输出有 32598 个 mismatch，因此官方判分失败。
- 目录：`runs/mage_verilogeval_failure_probe_20261109`

所有已完成运行目录中 API Key 出现次数均为 0。

## 代码边界

仅修改 MAGE 的 provider 与 tokenizer 兼容层：

- `src/mage/gen_config.py`：新增 DeepSeek 分支和模型元数据；
- `src/mage/token_counter.py`：未知 OpenAI-compatible 模型回退到
  `cl100k_base`；
- `tests/test_mage_integration.py`：新增 4 个集成测试。

VerilogEval 的 Agent 角色、提示词、候选数量、修复循环和仿真判分规则均未修改。
