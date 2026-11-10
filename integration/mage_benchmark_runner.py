#!/usr/bin/env python3
"""Run MAGE on VerilogEval V2 without changing the agent implementation."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from mage.agent import TopAgent
from mage.benchmark_read_helper import (
    TypeBenchmark,
    TypeBenchmarkFile,
    get_benchmark_contents,
)
from mage.gen_config import set_exp_setting
from mage.sim_reviewer import sim_review_golden_benchmark

from budget_guard import build_budgeted_llm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAGE_ROOT = PROJECT_ROOT / "MAGE"
BENCHMARK_ROOT = MAGE_ROOT / "verilog-eval"
BENCHMARK = TypeBenchmark.VERILOG_EVAL_V2
VERILOG_EVAL_COMMIT = "c498220d0a52248f8e3fdffe279075215bde2da6"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(MAGE_ROOT), *args], text=True).strip()


def save_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)


def token_snapshot(agent: TopAgent) -> dict:
    counts = agent.token_counter.get_sum_count()
    return {
        "input_tokens": counts.in_token_cnt,
        "output_tokens": counts.out_token_cnt,
        "total_tokens": agent.token_counter.get_total_token(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--filter", default=r"^(Prob011_norgate)$")
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--use-golden-tb", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if args.resume:
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Resume run directory is missing: {run_dir}")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    task_filter = re.compile(args.filter)
    optional_files = {
        file_type: get_benchmark_contents(
            BENCHMARK, file_type, str(BENCHMARK_ROOT), args.filter
        )
        for file_type in (
            TypeBenchmarkFile.SPEC,
            TypeBenchmarkFile.TEST_PATH,
            TypeBenchmarkFile.GOLDEN_PATH,
        )
    }
    tasks = optional_files[TypeBenchmarkFile.SPEC]
    if not tasks:
        raise ValueError("No official tasks matched the requested filter")
    if not all(task_filter.match(task_id) for task_id in tasks):
        raise ValueError("Official task selection does not match the requested filter")

    llm = build_budgeted_llm(max_tokens=args.max_tokens)
    set_exp_setting(temperature=args.temperature, top_p=args.top_p)

    agent = TopAgent(llm)
    agent.set_output_path(str(run_dir / "output"))
    agent.set_log_path(str(run_dir / "logs"))
    agent.set_redirect_log(True)

    protocol = {
        "run_kind": "real_api_inference_hidden"
        if not args.use_golden_tb
        else "real_api_inference_assisted",
        "benchmark": "VerilogEval V2",
        "task": "spec-to-rtl",
        "mage_commit": git_output("rev-parse", "HEAD"),
        "verilog_eval_commit": VERILOG_EVAL_COMMIT,
        "provider": "deepseek",
        "model": "deepseek-flash",
        "api_base_url": "https://api.deepseek.com",
        "thinking": "disabled",
        "filter_instance": args.filter,
        "task_count": len(tasks),
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "use_golden_tb_in_mage": args.use_golden_tb,
        "testbench_assisted_generation": args.use_golden_tb,
        "official_benchmark_tests_used_for_generation": False,
    }
    if args.resume:
        existing_protocol = json.loads((run_dir / "protocol.json").read_text())
        existing_protocol.setdefault("resume_history", []).append(
            {"resumed_at": utc_now()}
        )
        protocol = existing_protocol
    else:
        protocol["started_at"] = utc_now()
    save_json(run_dir / "protocol.json", protocol)

    records_path = run_dir / "records.json"
    records = json.loads(records_path.read_text()) if records_path.is_file() else []
    retryable = {
        record["task_id"]
        for record in records
        if record.get("status") in {"api_error", "infrastructure_error"}
    }
    records = [record for record in records if record["task_id"] not in retryable]
    completed_ids = {record["task_id"] for record in records}
    save_json(records_path, records)
    fatal_api_error = False
    for index, (task_id, spec) in enumerate(tasks.items(), 1):
        if task_id in completed_ids:
            continue
        llm.reset_budget()
        started = time.monotonic()
        print(f"({index}/{len(tasks)}) {task_id}", flush=True)
        record = {
            "task_id": task_id,
            "prompt_sha256": sha256_text(spec),
            "use_golden_tb_in_mage": args.use_golden_tb,
        }
        try:
            mage_pass, mage_output = agent.run(
                benchmark_type_name=BENCHMARK.name,
                task_id=task_id,
                spec=spec,
                golden_tb_path=(
                    optional_files[TypeBenchmarkFile.TEST_PATH][task_id]
                    if args.use_golden_tb
                    else None
                ),
                golden_rtl_blackbox_path=(
                    optional_files[TypeBenchmarkFile.GOLDEN_PATH][task_id]
                    if args.use_golden_tb
                    else None
                ),
            )
            record.update(status="completed", mage_self_pass=bool(mage_pass))
            if not mage_pass:
                record["mage_output"] = mage_output
                if "Insufficient Balance" in str(mage_output):
                    record["generation_status"] = "completed"
                    record["status"] = "api_error"
                    fatal_api_error = True
        except BaseException as exc:
            record.update(
                status="mage_error",
                mage_self_pass=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        # Official resources are read only after all generation has finished.
        record.update(
            testbench_sha256=hashlib.sha256(
                Path(
                    optional_files[TypeBenchmarkFile.TEST_PATH][task_id]
                ).read_bytes()
            ).hexdigest(),
            reference_rtl_sha256=hashlib.sha256(
                Path(
                    optional_files[TypeBenchmarkFile.GOLDEN_PATH][task_id]
                ).read_bytes()
            ).hexdigest(),
        )

        output_dir = run_dir / "output" / f"{BENCHMARK.name}_{task_id}"
        try:
            official_pass, official_output = sim_review_golden_benchmark(
                task_id=task_id,
                output_path=str(run_dir / "output"),
                benchmark_type=BENCHMARK,
                benchmark_path=str(BENCHMARK_ROOT),
            )
            official_result = json.loads(official_output)
            record.update(
                official_pass=bool(official_pass),
                official_return_success=(
                    not official_result.get("stderr")
                    and "First mismatch occurred at time"
                    not in official_result.get("stdout", "")
                ),
            )
        except BaseException as exc:
            record.update(
                official_pass=False,
                evaluator_error=f"{type(exc).__name__}: {exc}",
            )

        budget = llm.budget_snapshot()
        if budget["exceeded_kind"]:
            record["generation_status"] = record["status"]
            record["status"] = budget["exceeded_kind"]
        record.update(
            generation_budget=budget,
            token_usage=token_snapshot(agent),
            elapsed_seconds=time.monotonic() - started,
            output_dir=str(output_dir),
            artifacts={
                name: str(output_dir / name)
                for name in (
                    "rtl.sv",
                    "tb.sv",
                    "if.sv",
                    "sim_review_output.json",
                    "properly_finished.tag",
                )
                if (output_dir / name).is_file()
            },
        )
        records.append(record)
        save_json(run_dir / "records.json", records)
        if fatal_api_error:
            break

    completed_at = utc_now()
    summary = {
        "task_count": len(records),
        "official_pass_count": sum(bool(r.get("official_pass")) for r in records),
        "pass_at_1": (
            sum(bool(r.get("official_pass")) for r in records) / len(records)
            if records
            else 0.0
        ),
        "mage_self_pass_count": sum(bool(r.get("mage_self_pass")) for r in records),
        "elapsed_seconds": sum(float(r["elapsed_seconds"]) for r in records),
        "completed_at": completed_at,
    }
    save_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
