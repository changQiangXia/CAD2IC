#!/usr/bin/env python3
"""Analyze Plan 3 full, repeat, and complexity-subset experiments."""

import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

from plan2_analyze import bootstrap_difference as full_bootstrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS = PROJECT_ROOT / "runs"
SELECTION = RUNS / "plan3_repeat_selection_20261110.json"

FULL_PATHS = {
    ("verilog_eval_v2", "A"): RUNS
    / "mage_verilogeval_full_20261109"
    / "official_verilog_eval_repro"
    / "results.json",
    ("verilog_eval_v2", "B"): RUNS
    / "plan2_B_verilog_eval_full_20261110T002"
    / "official_eval"
    / "results.json",
    ("verilog_eval_v2", "C"): RUNS
    / "plan2_C_verilog_eval_full_20261110T002"
    / "official_eval"
    / "results.json",
    ("verilog_eval_v2", "D"): RUNS
    / "plan3_D_verilog_eval_full_20261110"
    / "official_eval"
    / "results.json",
    ("rtllm_v2", "A"): RUNS
    / "rtllm_full_20261109"
    / "official_eval"
    / "results.json",
    ("rtllm_v2", "B"): RUNS
    / "plan2_B_rtllm_full_20261110T002_v2"
    / "official_eval"
    / "results.json",
    ("rtllm_v2", "C"): RUNS
    / "plan2_C_rtllm_full_20261110T002"
    / "official_eval"
    / "results.json",
    ("rtllm_v2", "D"): RUNS
    / "plan3_D_rtllm_full_20261110"
    / "official_eval"
    / "results.json",
}


def load_results(path: Path) -> dict[str, bool]:
    return {
        row["task_id"]: bool(row["passed"])
        for row in json.loads(path.read_text())
    }


def repeat_run_dir(benchmark: str, arm: str, repeat: int) -> Path:
    return RUNS / "plan3_repeats" / f"{benchmark}_{arm}_repeat_{repeat}"


def load_repeat_results(
    benchmark: str, arm: str, repeats: int = 3
) -> list[dict[str, bool]]:
    return [
        load_results(
            repeat_run_dir(benchmark, arm, repeat)
            / "official_eval"
            / "results.json"
        )
        for repeat in range(1, repeats + 1)
    ]


def bootstrap_task_effect(
    first_runs: list[dict[str, bool]],
    second_runs: list[dict[str, bool]],
    first_label: str,
    second_label: str,
    seed: int = 20261110,
    samples: int = 10000,
) -> dict:
    tasks = sorted(set(first_runs[0]) & set(second_runs[0]))
    task_differences = []
    second_only = 0
    first_only = 0
    for task_id in tasks:
        first_rate = mean(int(run[task_id]) for run in first_runs)
        second_rate = mean(int(run[task_id]) for run in second_runs)
        task_differences.append(second_rate - first_rate)
        second_only += sum(int(run[task_id]) for run in second_runs)
        first_only += sum(int(run[task_id]) for run in first_runs)
    generator = random.Random(seed)
    estimates = [
        mean(generator.choice(task_differences) for _ in tasks)
        for _ in range(samples)
    ]
    estimates.sort()
    return {
        "first": first_label,
        "second": second_label,
        "tasks": len(tasks),
        "second_passes_across_repeats": second_only,
        "first_passes_across_repeats": first_only,
        "mean_difference": mean(task_differences),
        "ci95_low": estimates[int(0.025 * samples)],
        "ci95_high": estimates[int(0.975 * samples) - 1],
    }


def summary_for_arm(
    benchmark: str, arm: str, complexity_ids: set[str]
) -> tuple[dict, list[dict[str, bool]]]:
    full = load_results(FULL_PATHS[(benchmark, arm)])
    complex_values = {key: full[key] for key in complexity_ids}
    repeat_results = load_repeat_results(benchmark, arm)
    repeat_counts = [sum(result.values()) for result in repeat_results]
    stability = Counter(
        sum(int(result[task_id]) for result in repeat_results)
        for task_id in sorted(repeat_results[0])
    )
    record_summaries = []
    for repeat in range(1, 4):
        records = json.loads(
            (repeat_run_dir(benchmark, arm, repeat) / "records.json").read_text()
        )
        record_summaries.append(
            {
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
            }
        )
    value = {
        "full": {
            "passed": sum(full.values()),
            "total": len(full),
            "pass_at_1": sum(full.values()) / len(full),
            "complexity_subset": {
                "passed": sum(complex_values.values()),
                "total": len(complex_values),
                "pass_at_1": sum(complex_values.values()) / len(complex_values),
            },
        },
        "repeat": {
            "passed_per_repeat": repeat_counts,
            "pass_at_1_per_repeat": [
                count / len(repeat_results[0]) for count in repeat_counts
            ],
            "mean_passed": mean(repeat_counts),
            "mean_pass_at_1": mean(repeat_counts) / len(repeat_results[0]),
            "std_passed": pstdev(repeat_counts),
            "pooled_passed": sum(repeat_counts),
            "pooled_total": len(repeat_results[0]) * len(repeat_results),
            "task_stability_counts": {
                str(count): occurrences for count, occurrences in sorted(stability.items())
            },
            "resources": {
                "api_calls": sum(item["api_calls"] for item in record_summaries),
                "tokens": sum(item["tokens"] for item in record_summaries),
                "elapsed_seconds": sum(
                    item["elapsed_seconds"] for item in record_summaries
                ),
            },
        },
    }
    return value, repeat_results


def main() -> None:
    selection = json.loads(SELECTION.read_text())
    output = {}
    for benchmark, complete_keys in (
        ("verilog_eval_v2", ("A", "B", "C", "D")),
        ("rtllm_v2", ("A", "B", "C", "D")),
    ):
        complexity_ids = set(selection["complexity_subset"][benchmark])
        arms = {}
        repeat_results = {}
        for arm in complete_keys:
            value, results = summary_for_arm(benchmark, arm, complexity_ids)
            arms[arm] = value
            repeat_results[arm] = results

        output[benchmark] = {
            "arms": arms,
            "full_effects": {
                "architecture_hidden_C_minus_B": full_bootstrap(
                    load_results(FULL_PATHS[(benchmark, "B")]),
                    load_results(FULL_PATHS[(benchmark, "C")]),
                    first_label="B",
                    second_label="C",
                ),
                "architecture_assisted_D_minus_A": full_bootstrap(
                    load_results(FULL_PATHS[(benchmark, "A")]),
                    load_results(FULL_PATHS[(benchmark, "D")]),
                    first_label="A",
                    second_label="D",
                ),
                "testbench_effect_mage_A_minus_B": full_bootstrap(
                    load_results(FULL_PATHS[(benchmark, "B")]),
                    load_results(FULL_PATHS[(benchmark, "A")]),
                    first_label="B",
                    second_label="A",
                ),
                "testbench_effect_single_D_minus_C": full_bootstrap(
                    load_results(FULL_PATHS[(benchmark, "C")]),
                    load_results(FULL_PATHS[(benchmark, "D")]),
                    first_label="C",
                    second_label="D",
                ),
            },
            "repeat_effects": {
                "architecture_hidden_C_minus_B": bootstrap_task_effect(
                    repeat_results["B"],
                    repeat_results["C"],
                    "B",
                    "C",
                ),
                "architecture_assisted_D_minus_A": bootstrap_task_effect(
                    repeat_results["A"],
                    repeat_results["D"],
                    "A",
                    "D",
                ),
                "testbench_effect_mage_A_minus_B": bootstrap_task_effect(
                    repeat_results["B"],
                    repeat_results["A"],
                    "B",
                    "A",
                ),
                "testbench_effect_single_D_minus_C": bootstrap_task_effect(
                    repeat_results["C"],
                    repeat_results["D"],
                    "C",
                    "D",
                ),
            },
        }

    output_path = RUNS / "plan3_results_20261110.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
