#!/usr/bin/env python3
"""Run MAGE on RTLLM V2 and evaluate with the official testbench."""

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from mage.agent import TopAgent
from mage.gen_config import set_exp_setting

from budget_guard import build_budgeted_llm
from rtllm import evaluate_rtl, load_tasks, save_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAGE_ROOT = PROJECT_ROOT / "MAGE"
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"
RTLLM_COMMIT = "41b26896e33b536940116a975626455eed3de65e"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(MAGE_ROOT), *args], text=True).strip()


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
    parser.add_argument("--filter", default=r"^(adder_8bit)$")
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
    all_tasks = load_tasks(
        RTLLM_ROOT, include_official_contents=args.use_golden_tb
    )
    tasks = [task for task in all_tasks if task_filter.search(task.task_id)]
    if not tasks:
        raise ValueError("No official RTLLM tasks matched the requested filter")

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
        "benchmark": "RTLLM V2",
        "rtllm_commit": RTLLM_COMMIT,
        "mage_commit": git_output("rev-parse", "HEAD"),
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
        "official_testbench_used_for_final_scoring": True,
        "simulator_policy": "Icarus 12; Verilator fallback for four known-incompatible testbenches",
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
    for index, task in enumerate(tasks, 1):
        if task.task_id in completed_ids:
            continue
        llm.reset_budget()
        started = time.monotonic()
        print(f"({index}/{len(tasks)}) {task.task_id}", flush=True)
        record = {
            "task_id": task.task_id,
            "module_name": task.module_name,
            "category": task.category,
            "prompt_sha256": task.metadata["description_sha256"],
            "testbench_sha256": task.metadata.get("testbench_sha256"),
            "reference_rtl_sha256": task.metadata.get("reference_rtl_sha256"),
            "use_golden_tb_in_mage": args.use_golden_tb,
        }
        try:
            mage_pass, mage_output = agent.run(
                benchmark_type_name="RTLLM_V2",
                task_id=task.task_id,
                spec=task.natural_language_spec,
                golden_tb_path=(
                    task.official_testbench_path if args.use_golden_tb else None
                ),
                golden_rtl_blackbox_path=None,
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

        output_dir = run_dir / "output" / f"RTLLM_V2_{task.task_id}"
        rtl_path = output_dir / "rtl.sv"
        official = evaluate_rtl(
            task,
            rtl_path,
            run_dir / "official_evaluation" / task.task_id,
            timeout_s=180,
        )
        budget = llm.budget_snapshot()
        if budget["exceeded_kind"]:
            record["generation_status"] = record["status"]
            record["status"] = budget["exceeded_kind"]
        record.update(
            generation_budget=budget,
            mage_official_pass=bool(official["passed"]),
            official=official,
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

    passed = sum(bool(record["mage_official_pass"]) for record in records)
    summary = {
        "task_count": len(records),
        "official_pass_count": passed,
        "pass_at_1": passed / len(records),
        "simulators": {
            name: sum(
                record["official"].get("simulator") == name for record in records
            )
            for name in ("iverilog", "verilator")
        },
        "elapsed_seconds": sum(record["elapsed_seconds"] for record in records),
        "completed_at": utc_now(),
    }
    save_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
