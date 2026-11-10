#!/usr/bin/env python3
"""Evaluate a MAGE VerilogEval run with the benchmark's official Makefile."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = PROJECT_ROOT / "MAGE" / "verilog-eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--jobs", type=int, default=4)
    return parser.parse_args()


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_summary_csv(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        problem, passed, total, rate, code = line.rsplit(",", 4)
        rows.append(
            {
                "task_id": problem,
                "passed": int(passed),
                "total": int(total),
                "pass_rate": float(rate),
                "code": code,
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    benchmark_root = args.benchmark_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    build_dir = output_dir / "build"
    build_dir.mkdir()

    records = json.loads((run_dir / "records.json").read_text())
    tasks = [record["task_id"] for record in records]
    if len(tasks) != len(set(tasks)) or not tasks:
        raise ValueError("records.json must contain unique task IDs")
    problems_file = output_dir / "selected_problems.txt"
    problems_file.write_text("".join(f"{task}\n" for task in tasks))

    subprocess.run(
        [
            str(benchmark_root / "configure"),
            "--with-task=spec-to-rtl",
            "--with-model=mage-final-rtl",
            "--with-examples=0",
            "--with-samples=1",
            "--with-temperature=0.85",
            "--with-top-p=0.95",
            f"--with-problems={problems_file}",
        ],
        cwd=build_dir,
        check=True,
    )

    # The upstream configure script pipes through `column`, which is absent in
    # this image. Regenerate only the generated sample-count file directly.
    (build_dir / "samples.mk").write_text(
        "".join(f"{task}_num_samples =  1\n" for task in tasks)
    )

    for record in records:
        task_id = record["task_id"]
        task_dir = build_dir / task_id
        task_dir.mkdir()
        sample = task_dir / f"{task_id}_sample01.sv"
        source_rtl = Path(record["output_dir"]) / "rtl.sv"
        if source_rtl.is_file():
            shutil.copy2(source_rtl, sample)
        else:
            sample.touch()
        (task_dir / f"{task_id}_sample01-sv-generate.log").touch()

    environment = os.environ.copy()
    subprocess.run(
        ["make", f"-j{args.jobs}", "SHELL=/bin/bash", "sv-iv-test"],
        cwd=build_dir,
        check=True,
        env=environment,
    )
    analyzer = subprocess.run(
        [
            sys.executable,
            str(benchmark_root / "scripts" / "sv-iv-analyze"),
            "--csv=summary.csv",
        ],
        cwd=build_dir,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
    )
    (output_dir / "analyzer.txt").write_text(analyzer.stdout, encoding="utf-8")

    rows = parse_summary_csv(build_dir / "summary.csv")
    if len(rows) != len(tasks):
        raise ValueError("Official analyzer did not return one row per task")
    passed = sum(row["passed"] for row in rows)
    total = sum(row["total"] for row in rows)
    codes = Counter(row["code"] for row in rows)
    official_summary = {
        "benchmark": "VerilogEval V2",
        "source_run": str(run_dir),
        "build_dir": str(build_dir),
        "task_count": len(rows),
        "passed": passed,
        "total": total,
        "pass_at_1": passed / total,
        "result_codes": dict(sorted(codes.items())),
        "failures": [row for row in rows if row["code"] != "."],
    }
    save_json(output_dir / "official_summary.json", official_summary)
    save_json(output_dir / "results.json", rows)
    print(json.dumps(official_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
