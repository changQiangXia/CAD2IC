#!/usr/bin/env python3
"""Summarize Plan 2 arms and paired bootstrap uncertainty."""

import json
import random
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS = PROJECT_ROOT / "runs"

VE_PATHS = {
    "A": RUNS
    / "mage_verilogeval_full_20261109"
    / "official_verilog_eval_repro"
    / "results.json",
    "B": RUNS
    / "plan2_B_verilog_eval_full_20261110T002"
    / "official_eval"
    / "results.json",
    "C": RUNS
    / "plan2_C_verilog_eval_full_20261110T002"
    / "official_eval"
    / "results.json",
}

RT_PATHS = {
    "A": RUNS / "rtllm_full_20261109" / "official_eval" / "results.json",
    "B": RUNS
    / "plan2_B_rtllm_full_20261110T002_v2"
    / "official_eval"
    / "results.json",
    "C": RUNS
    / "plan2_C_rtllm_full_20261110T002"
    / "official_eval"
    / "results.json",
}

RECORD_PATHS = {
    ("verilog_eval_v2", "B"): RUNS
    / "plan2_B_verilog_eval_full_20261110T002"
    / "records.json",
    ("verilog_eval_v2", "C"): RUNS
    / "plan2_C_verilog_eval_full_20261110T002"
    / "records.json",
    ("rtllm_v2", "B"): RUNS
    / "plan2_B_rtllm_full_20261110T002_v2"
    / "records.json",
    ("rtllm_v2", "C"): RUNS
    / "plan2_C_rtllm_full_20261110T002"
    / "records.json",
}


def load_outcomes(path: Path) -> dict[str, bool]:
    rows = json.loads(path.read_text())
    return {row["task_id"]: bool(row["passed"]) for row in rows}


def bootstrap_difference(
    first: dict[str, bool],
    second: dict[str, bool],
    *,
    first_label: str = "B",
    second_label: str = "C",
    seed: int = 20261110,
    samples: int = 10000,
) -> dict:
    task_ids = sorted(set(first) & set(second))
    differences = [int(second[task_id]) - int(first[task_id]) for task_id in task_ids]
    generator = random.Random(seed)
    estimates = []
    for _ in range(samples):
        estimate = mean(generator.choice(differences) for _ in task_ids)
        estimates.append(estimate)
    estimates.sort()
    return {
        "first": first_label,
        "second": second_label,
        "paired_tasks": len(task_ids),
        "second_only_pass": sum(
            second[task_id] and not first[task_id] for task_id in task_ids
        ),
        "first_only_pass": sum(
            first[task_id] and not second[task_id] for task_id in task_ids
        ),
        "mean_difference": mean(differences),
        "ci95_low": estimates[int(0.025 * samples)],
        "ci95_high": estimates[int(0.975 * samples) - 1],
    }


def arm_summary(records_path: Path) -> dict:
    records = json.loads(records_path.read_text())
    return {
        "task_count": len(records),
        "api_calls": sum(
            record.get("generation_budget", {}).get("api_calls", 0)
            for record in records
        ),
        "tokens": sum(
            record.get("token_usage", {}).get("total_tokens", 0)
            for record in records
        ),
        "elapsed_seconds": sum(
            float(record.get("elapsed_seconds", 0)) for record in records
        ),
        "statuses": {
            status: sum(record.get("status") == status for record in records)
            for status in sorted({record.get("status") for record in records})
        },
    }


def main() -> None:
    output = {"benchmarks": {}}
    for benchmark, paths in (
        ("verilog_eval_v2", VE_PATHS),
        ("rtllm_v2", RT_PATHS),
    ):
        outcomes = {arm: load_outcomes(path) for arm, path in paths.items()}
        arms = {}
        for arm, values in outcomes.items():
            arms[arm] = {
                "passed": sum(values.values()),
                "total": len(values),
                "pass_at_1": sum(values.values()) / len(values),
            }
            if (benchmark, arm) in RECORD_PATHS:
                arms[arm].update(arm_summary(RECORD_PATHS[(benchmark, arm)]))
        output["benchmarks"][benchmark] = {
            "arms": arms,
            "testbench_assistance_effect": bootstrap_difference(
                outcomes["B"],
                outcomes["A"],
                first_label="B",
                second_label="A",
            ),
            "multi_agent_vs_single_hidden": bootstrap_difference(
                outcomes["B"], outcomes["C"]
            ),
        }

    output_path = RUNS / "plan2_results_20261110.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
