from pathlib import Path

import pytest

from rtllm import evaluate_rtl, load_tasks, materialize_reference


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"


@pytest.fixture(scope="module")
def tasks():
    loaded = load_tasks(RTLLM_ROOT)
    return {task.task_id: task for task in loaded}


def test_loader_reads_all_official_tasks(tasks):
    assert len(tasks) == 50
    assert tasks["asyn_fifo"].module_name == "asyn_fifo"
    assert tasks["freq_divbyeven"].module_name == "freq_divbyeven"
    assert tasks["fixed_point_substractor"].module_name == "fixed_point_subtractor"
    for task in tasks.values():
        assert task.natural_language_spec
        assert Path(task.official_testbench_path).is_file()
        assert Path(task.reference_rtl_path).is_file()


def test_reference_rtl_passes_official_testbench(tmp_path, tasks):
    task = tasks["adder_8bit"]
    rtl = materialize_reference(task, tmp_path / "rtl.v")
    result = evaluate_rtl(task, rtl, tmp_path / "eval")
    assert result["passed"]
    assert result["status"] == "passed"


def test_broken_rtl_fails_official_testbench(tmp_path, tasks):
    task = tasks["adder_8bit"]
    rtl = tmp_path / "rtl.v"
    rtl.write_text(
        "module adder_8bit(input [7:0] a, input [7:0] b, input cin, "
        "output [7:0] sum, output cout);\n"
        "  assign {cout, sum} = 9'b0;\n"
        "endmodule\n"
    )
    result = evaluate_rtl(task, rtl, tmp_path / "eval")
    assert not result["passed"]
    assert result["status"] == "functional_mismatch"


def test_missing_rtllm_dataset_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tasks(tmp_path / "missing")
