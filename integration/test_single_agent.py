import pytest
from llama_index.core.llms import ChatMessage, MessageRole

from budget_guard import BudgetExceeded, build_budgeted_llm
from single_agent_runner import (
    rtllm_tasks,
    run_self_test,
    parse_response,
    verilog_eval_tasks,
)


def test_response_parser_requires_complete_pair():
    parsed = parse_response(
        '{"reasoning": "r", "rtl": "module x; endmodule", '
        '"testbench": "module tb; endmodule"}'
    )
    assert parsed["rtl"].startswith("module")
    with pytest.raises(ValueError):
        parse_response('{"reasoning": "missing fields"}')


def test_hidden_tasks_expose_only_specification():
    verilog_task = verilog_eval_tasks(
        r"^(Prob011_norgate)$", assisted=False
    )[0]
    assert set(verilog_task) == {
        "task_id",
        "benchmark",
        "spec",
        "module_name",
        "official_testbench",
    }
    assert verilog_task["official_testbench"] is None
    rtllm_task = rtllm_tasks(
        r"^(freq_divbyeven)$", assisted=False
    )[0]
    assert set(rtllm_task) == {
        "task_id",
        "benchmark",
        "spec",
        "module_name",
        "official_testbench",
    }
    assert rtllm_task["official_testbench"] is None
    assert "testbench" not in rtllm_task
    assert "reference" not in rtllm_task


def test_assisted_tasks_expose_official_testbench_only():
    verilog_task = verilog_eval_tasks(
        r"^(Prob011_norgate)$", assisted=True
    )[0]
    rtllm_task = rtllm_tasks(
        r"^(freq_divbyeven)$", assisted=True
    )[0]
    assert "module tb()" in verilog_task["official_testbench"]
    assert "freq_divbyeven uut" in rtllm_task["official_testbench"]
    assert rtllm_task["module_name"] == "freq_divbyeven"
    assert "reference" not in rtllm_task


def test_single_agent_self_test_runs(tmp_path):
    rtl = tmp_path / "rtl.sv"
    tb = tmp_path / "tb.sv"
    rtl.write_text("module top; endmodule\n")
    tb.write_text(
        'module tb; initial begin $display("SIMULATION PASSED"); end endmodule\n'
    )
    result = run_self_test(rtl, tb, tmp_path / "run")
    assert result["passed"]


def test_budget_guard_stops_before_extra_call(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-a-real-key")
    llm = build_budgeted_llm()
    assert llm.max_retries == 0
    llm.reset_budget()
    llm._calls = llm._max_calls
    with pytest.raises(BudgetExceeded) as exc:
        llm.chat(messages=[ChatMessage(role=MessageRole.USER, content="x")])
    assert exc.value.kind == "api_budget_exhausted"
