#!/usr/bin/env python3
"""Create Plan 3 deterministic repeat and complexity subsets."""

import hashlib
import json
import math
from pathlib import Path

import tiktoken

from mage.benchmark_read_helper import (
    TypeBenchmark,
    TypeBenchmarkFile,
    get_benchmark_contents,
)

from rtllm import load_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERILOG_EVAL_ROOT = PROJECT_ROOT / "MAGE" / "verilog-eval"
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"
SEED = "plan3:20261110:"


def rank_key(task_id: str) -> str:
    return hashlib.sha256(f"{SEED}{task_id}".encode()).hexdigest()


def complexity_subset(specs: dict[str, str]) -> list[str]:
    encoding = tiktoken.get_encoding("cl100k_base")
    ranked = sorted(
        specs,
        key=lambda task_id: (-len(encoding.encode(specs[task_id])), task_id),
    )
    return ranked[: math.ceil(len(ranked) / 2)]


def main() -> None:
    ve_specs = get_benchmark_contents(
        TypeBenchmark.VERILOG_EVAL_V2,
        TypeBenchmarkFile.SPEC,
        str(VERILOG_EVAL_ROOT),
        r"^(.*)$",
    )
    ve_repeat = sorted(ve_specs, key=rank_key)[:10]

    rt_tasks = load_tasks(
        RTLLM_ROOT, include_official_contents=False
    )
    rt_specs = {task.task_id: task.natural_language_spec for task in rt_tasks}
    category_counts = {
        "Arithmetic": 4,
        "Memory": 1,
        "Control": 2,
        "Miscellaneous": 3,
    }
    rt_repeat = []
    for category, count in category_counts.items():
        task_ids = [task.task_id for task in rt_tasks if task.category == category]
        rt_repeat.extend(sorted(task_ids, key=rank_key)[:count])

    if len(ve_specs) != 156 or len(rt_specs) != 50:
        raise ValueError("Unexpected task count")
    value = {
        "seed": SEED,
        "repeat_subset": {
            "verilog_eval_v2": ve_repeat,
            "rtllm_v2": rt_repeat,
        },
        "complexity_subset": {
            "verilog_eval_v2": complexity_subset(ve_specs),
            "rtllm_v2": complexity_subset(rt_specs),
        },
        "rules": {
            "verilog_eval_repeat": "global SHA256 rank, first 10",
            "rtllm_repeat": "category-stratified SHA256 rank: 4/1/2/3",
            "complexity": "top 50% by cl100k_base specification token count",
        },
    }
    output = PROJECT_ROOT / "runs" / "plan3_repeat_selection_20261110.json"
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
