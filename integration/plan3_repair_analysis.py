#!/usr/bin/env python3
"""Evaluate first-round C/D RTL with official testbenches."""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from single_agent_runner import parse_response


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS = PROJECT_ROOT / "runs"
OUTPUT = RUNS / "plan3_repair_analysis_20261110"

SOURCE_RUNS = {
    ("verilog_eval_v2", "C", "full"): RUNS
    / "plan2_C_verilog_eval_full_20261110T002",
    ("verilog_eval_v2", "D", "full"): RUNS
    / "plan3_D_verilog_eval_full_20261110",
    ("rtllm_v2", "C", "full"): RUNS
    / "plan2_C_rtllm_full_20261110T002",
    ("rtllm_v2", "D", "full"): RUNS
    / "plan3_D_rtllm_full_20261110",
}
for benchmark in ("verilog_eval_v2", "rtllm_v2"):
    for arm in ("C", "D"):
        for repeat in range(1, 4):
            SOURCE_RUNS[(benchmark, arm, f"repeat_{repeat}")] = (
                RUNS
                / "plan3_repeats"
                / f"{benchmark}_{arm}_repeat_{repeat}"
            )


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluator_command(benchmark: str, derived_run: Path) -> list[str]:
    if benchmark == "verilog_eval_v2":
        evaluator = PROJECT_ROOT / "integration" / "verilog_eval_official_eval.py"
    else:
        evaluator = PROJECT_ROOT / "integration" / "rtllm_official_eval.py"
    return [
        sys.executable,
        str(evaluator),
        "--run-dir",
        str(derived_run),
        "--output-dir",
        str(derived_run / "official_eval"),
    ]


def load_passes(path: Path) -> dict[str, bool]:
    return {
        row["task_id"]: bool(row["passed"])
        for row in json.loads(path.read_text())
    }


def materialize_round_one(source_run: Path, derived_run: Path) -> list[dict]:
    records = json.loads((source_run / "records.json").read_text())
    derived_records = []
    for record in records:
        task_id = record["task_id"]
        output_dir = derived_run / "output" / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        rtl_path = output_dir / "rtl.sv"
        response_ok = False
        if record.get("rounds"):
            try:
                parsed = parse_response(record["rounds"][0]["response"])
                rtl_path.write_text(parsed["rtl"], encoding="utf-8")
                response_ok = True
            except Exception:
                pass
        derived_records.append(
            {
                "task_id": task_id,
                "output_dir": str(output_dir),
                "first_round_response_parsed": response_ok,
                "first_round_self_status": (
                    record["rounds"][0].get("status")
                    if record.get("rounds")
                    else "missing_round"
                ),
            }
        )
    save_json(derived_run / "records.json", derived_records)
    save_json(
        derived_run / "protocol.json",
        {
            "source_run": str(source_run),
            "derived_artifact": "round 1 RTL",
            "purpose": "official repair-gain analysis",
        },
    )
    return derived_records


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=False)
    comparisons = []
    for (benchmark, arm, stage), source_run in SOURCE_RUNS.items():
        derived_run = OUTPUT / benchmark / arm / stage
        materialize_round_one(source_run, derived_run)
        log_path = derived_run / "official_eval.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(
                evaluator_command(benchmark, derived_run),
                cwd=PROJECT_ROOT / "integration",
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if process.returncode != 0:
            comparisons.append(
                {
                    "benchmark": benchmark,
                    "arm": arm,
                    "stage": stage,
                    "error": f"evaluator exit {process.returncode}",
                }
            )
            continue
        round1 = load_passes(derived_run / "official_eval" / "results.json")
        final = load_passes(source_run / "official_eval" / "results.json")
        outcomes = Counter()
        for task_id in round1:
            if not round1[task_id] and final[task_id]:
                outcomes["repair_recovery"] += 1
            elif round1[task_id] and not final[task_id]:
                outcomes["regression"] += 1
            elif round1[task_id] and final[task_id]:
                outcomes["unchanged_pass"] += 1
            else:
                outcomes["persistent_fail"] += 1
        comparisons.append(
            {
                "benchmark": benchmark,
                "arm": arm,
                "stage": stage,
                "task_count": len(round1),
                "round1_passed": sum(round1.values()),
                "final_passed": sum(final.values()),
                **dict(outcomes),
            }
        )
        save_json(OUTPUT / "comparisons.json", comparisons)
        print(
            benchmark,
            arm,
            stage,
            "round1",
            sum(round1.values()),
            "final",
            sum(final.values()),
            dict(outcomes),
            flush=True,
        )

    summary = {
        "pairs": comparisons,
        "mage_initial_rtl": "not_recoverable from stable logs; not guessed",
    }
    save_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
