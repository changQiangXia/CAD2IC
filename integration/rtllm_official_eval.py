#!/usr/bin/env python3
"""Evaluate MAGE or single-agent RTLLM outputs with official testbenches."""

import argparse
import json
from pathlib import Path

from rtllm import evaluate_rtl, load_tasks, save_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--benchmark-root", type=Path, default=RTLLM_ROOT)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    records = json.loads((run_dir / "records.json").read_text())
    tasks = {
        task.task_id: task
        for task in load_tasks(
            args.benchmark_root.resolve(), include_official_contents=True
        )
    }
    results = []
    for record in records:
        task_id = record["task_id"]
        rtl_path = Path(record["output_dir"]) / "rtl.sv"
        result = evaluate_rtl(
            tasks[task_id],
            rtl_path,
            output_dir / task_id,
            timeout_s=args.timeout,
        )
        results.append(result)
        save_json(output_dir / "results.json", results)
        print(task_id, result["status"], result.get("simulator"), flush=True)

    passed = sum(bool(result["passed"]) for result in results)
    summary = {
        "benchmark": "RTLLM V2",
        "source_run": str(run_dir),
        "task_count": len(results),
        "passed": passed,
        "total": len(results),
        "pass_at_1": passed / len(results),
        "simulators": {
            simulator: sum(
                result.get("simulator") == simulator for result in results
            )
            for simulator in ("iverilog", "verilator")
        },
        "statuses": {
            status: sum(result.get("status") == status for result in results)
            for status in sorted({result.get("status") for result in results})
        },
        "failures": [
            {
                "task_id": result["task_id"],
                "status": result.get("status"),
                "simulator": result.get("simulator"),
            }
            for result in results
            if not result["passed"]
        ],
    }
    save_json(output_dir / "official_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
