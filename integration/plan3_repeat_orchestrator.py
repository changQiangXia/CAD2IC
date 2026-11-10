#!/usr/bin/env python3
"""Run the pre-registered Plan 3 repeat matrix."""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / "runs"
SELECTION = RUNS_ROOT / "plan3_repeat_selection_20261110.json"
MAGE_RUNNER = PROJECT_ROOT / "integration" / "mage_benchmark_runner.py"
RT_RUNNER = PROJECT_ROOT / "integration" / "rtllm_runner.py"
SINGLE_RUNNER = PROJECT_ROOT / "integration" / "single_agent_runner.py"
VE_EVAL = PROJECT_ROOT / "integration" / "verilog_eval_official_eval.py"
RT_EVAL = PROJECT_ROOT / "integration" / "rtllm_official_eval.py"


def task_filter(tasks: list[str]) -> str:
    return "^(" + "|".join(re.escape(task) for task in tasks) + ")$"


def count_records(run_dir: Path) -> int:
    path = run_dir / "records.json"
    if not path.is_file():
        return 0
    return len(json.loads(path.read_text()))


def run_logged(command: list[str], cwd: Path, log_path: Path) -> int:
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.run(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=None,
        )
        log.write(f"\nexit_code={process.returncode}\n")
        return process.returncode


def generation_command(
    arm: str, benchmark: str, run_dir: Path, selected: list[str]
) -> tuple[list[str], Path]:
    pattern = task_filter(selected)
    common_single = [
        sys.executable,
        str(SINGLE_RUNNER),
        "--benchmark",
        benchmark,
        "--run-dir",
        str(run_dir),
        "--filter",
        pattern,
        "--temperature",
        "0.85",
        "--top-p",
        "0.95",
        "--max-tokens",
        "8192",
        "--max-rounds",
        "8",
    ]
    if arm == "A":
        mage_script = (
            RT_RUNNER if benchmark == "rtllm_v2" else MAGE_RUNNER
        )
        return (
            [
                sys.executable,
                str(mage_script),
                "--run-dir",
                str(run_dir),
                "--filter",
                pattern,
                "--temperature",
                "0.85",
                "--top-p",
                "0.95",
                "--max-tokens",
                "8192",
                "--use-golden-tb",
            ],
            PROJECT_ROOT / "MAGE",
        )
    if arm == "B":
        mage_script = (
            RT_RUNNER if benchmark == "rtllm_v2" else MAGE_RUNNER
        )
        return (
            [
                sys.executable,
                str(mage_script),
                "--run-dir",
                str(run_dir),
                "--filter",
                pattern,
                "--temperature",
                "0.85",
                "--top-p",
                "0.95",
                "--max-tokens",
                "8192",
                "--no-use-golden-tb",
            ],
            PROJECT_ROOT / "MAGE",
        )
    if arm == "C":
        return common_single, PROJECT_ROOT / "integration"
    if arm == "D":
        return (
            common_single + ["--use-official-tb"],
            PROJECT_ROOT / "integration",
        )
    raise ValueError(arm)


def official_command(benchmark: str, run_dir: Path) -> list[str]:
    output = run_dir / "official_eval"
    if benchmark == "verilog_eval_v2":
        return [
            sys.executable,
            str(VE_EVAL),
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(output),
        ]
    return [
        sys.executable,
        str(RT_EVAL),
        "--run-dir",
        str(run_dir),
        "--output-dir",
        str(output),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        required=True,
        choices=("verilog_eval_v2", "rtllm_v2"),
    )
    parser.add_argument("--arms", default="A,B,C,D")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    selection = json.loads(SELECTION.read_text())
    selected = selection["repeat_subset"][args.benchmark]
    arms = [arm.strip() for arm in args.arms.split(",") if arm.strip()]
    if len(selected) != 10:
        raise ValueError("Expected ten pre-registered repeat tasks")

    overall_started = time.monotonic()
    for repeat in range(1, args.repeats + 1):
        for arm in arms:
            run_dir = (
                RUNS_ROOT
                / "plan3_repeats"
                / f"{args.benchmark}_{arm}_repeat_{repeat}"
            )
            run_dir.parent.mkdir(parents=True, exist_ok=True)
            log_path = run_dir.parent / f"{run_dir.name}.orchestrator.log"
            command, cwd = generation_command(
                arm, args.benchmark, run_dir, selected
            )
            resume_count = 0
            while count_records(run_dir) < len(selected) and resume_count <= 3:
                current = command if resume_count == 0 else command + ["--resume"]
                run_logged(current, cwd, log_path)
                if count_records(run_dir) >= len(selected):
                    break
                resume_count += 1

            records = count_records(run_dir)
            print(
                f"{args.benchmark} {arm} repeat={repeat} records={records}",
                flush=True,
            )
            if records == len(selected) and not (
                run_dir / "official_eval" / "official_summary.json"
            ).is_file():
                run_logged(
                    official_command(args.benchmark, run_dir),
                    PROJECT_ROOT / "integration",
                    log_path,
                )

    duration = time.monotonic() - overall_started
    summary = {
        "benchmark": args.benchmark,
        "arms": arms,
        "repeats": args.repeats,
        "selected_tasks": selected,
        "elapsed_seconds": duration,
    }
    output = RUNS_ROOT / "plan3_repeats" / f"{args.benchmark}_orchestration.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
