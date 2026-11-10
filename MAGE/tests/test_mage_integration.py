import hashlib
import re
from pathlib import Path

import pytest

from mage.benchmark_read_helper import (
    TypeBenchmark,
    TypeBenchmarkFile,
    get_benchmark_contents,
)
from mage.sim_reviewer import sim_review_golden


BENCHMARK_ROOT = Path(__file__).resolve().parents[1] / "verilog-eval"
TASK_ID = "Prob011_norgate"
BENCHMARK = TypeBenchmark.VERILOG_EVAL_V2


@pytest.fixture(scope="module")
def official_files():
    spec = get_benchmark_contents(
        BENCHMARK, TypeBenchmarkFile.SPEC, str(BENCHMARK_ROOT), rf"^({TASK_ID})$"
    )
    testbench = get_benchmark_contents(
        BENCHMARK, TypeBenchmarkFile.TEST_PATH, str(BENCHMARK_ROOT), rf"^({TASK_ID})$"
    )
    reference = get_benchmark_contents(
        BENCHMARK, TypeBenchmarkFile.GOLDEN_PATH, str(BENCHMARK_ROOT), rf"^({TASK_ID})$"
    )
    return spec, testbench, reference


def write_reference_candidate(tmp_path, reference_path):
    reference = Path(reference_path).read_text()
    candidate = re.sub(r"\bmodule\s+RefModule\b", "module TopModule", reference)
    path = tmp_path / "rtl.sv"
    path.write_text(candidate)
    return path


def test_loader_reads_official_fields_verbatim(official_files):
    spec, testbench, reference = official_files
    prompt_path = BENCHMARK_ROOT / "dataset_spec-to-rtl" / f"{TASK_ID}_prompt.txt"
    assert spec == {TASK_ID: prompt_path.read_text()}
    assert Path(testbench[TASK_ID]).name == f"{TASK_ID}_test.sv"
    assert Path(reference[TASK_ID]).name == f"{TASK_ID}_ref.sv"
    assert hashlib.sha256(spec[TASK_ID].encode()).digest()


def test_official_reference_passes_official_testbench(tmp_path, official_files):
    _, _, reference = official_files
    rtl_path = write_reference_candidate(tmp_path, reference[TASK_ID])
    is_pass, _ = sim_review_golden(
        str(rtl_path),
        TASK_ID,
        BENCHMARK,
        str(BENCHMARK_ROOT),
        str(tmp_path),
    )
    assert is_pass


def test_broken_rtl_fails_official_testbench(tmp_path):
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(
        "module TopModule(input a, input b, output out);\n"
        "  assign out = 1'b0;\n"
        "endmodule\n"
    )
    is_pass, _ = sim_review_golden(
        str(rtl_path),
        TASK_ID,
        BENCHMARK,
        str(BENCHMARK_ROOT),
        str(tmp_path),
    )
    assert not is_pass


def test_missing_benchmark_resource_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_benchmark_contents(
            BENCHMARK,
            TypeBenchmarkFile.SPEC,
            str(tmp_path / "missing"),
            r"^(.*)$",
        )
