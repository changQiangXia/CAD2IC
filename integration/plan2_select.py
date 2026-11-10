#!/usr/bin/env python3
"""Create the deterministic Plan 2 screening task lists."""

import hashlib
import json
from pathlib import Path

from mage.benchmark_read_helper import (
    TypeBenchmark,
    TypeBenchmarkFile,
    get_benchmark_contents,
)

from rtllm import load_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERILOG_EVAL_ROOT = PROJECT_ROOT / "MAGE" / "verilog-eval"
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"
SEED = "plan2:20261110:"


def rank_key(task_id: str) -> str:
    return hashlib.sha256(f"{SEED}{task_id}".encode()).hexdigest()


def main() -> None:
    ve_tasks = get_benchmark_contents(
        TypeBenchmark.VERILOG_EVAL_V2,
        TypeBenchmarkFile.SPEC,
        str(VERILOG_EVAL_ROOT),
        r"^(.*)$",
    )
    verilog_selected = sorted(ve_tasks, key=rank_key)[:20]

    rtllm_tasks = load_tasks(
        RTLLM_ROOT, include_official_contents=False
    )
    category_counts = {
        "Arithmetic": 8,
        "Memory": 2,
        "Control": 3,
        "Miscellaneous": 7,
    }
    rtllm_selected = []
    for category, count in category_counts.items():
        tasks = [task.task_id for task in rtllm_tasks if task.category == category]
        rtllm_selected.extend(sorted(tasks, key=rank_key)[:count])
    if len(ve_tasks) != 156 or len(rtllm_tasks) != 50:
        raise ValueError("Unexpected benchmark task count")

    value = {
        "seed": SEED,
        "verilog_eval_v2": verilog_selected,
        "rtllm_v2": rtllm_selected,
        "rules": {
            "verilog_eval_v2": "global SHA256 rank, first 20",
            "rtllm_v2": "category-stratified SHA256 rank: 8/2/3/7",
        },
    }
    output = PROJECT_ROOT / "runs" / "plan2_selection_20261110.json"
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
