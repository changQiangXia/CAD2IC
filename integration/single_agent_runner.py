#!/usr/bin/env python3
"""Plan 2 closed-loop single-agent control with official testbenches hidden."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from llama_index.core.llms import ChatMessage, MessageRole

from mage.benchmark_read_helper import (
    TypeBenchmark,
    TypeBenchmarkFile,
    get_benchmark_contents,
)
from mage.gen_config import set_exp_setting
from mage.token_counter import TokenCounter

from budget_guard import BudgetExceeded, build_budgeted_llm
from rtllm import load_tasks as load_rtllm_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAGE_ROOT = PROJECT_ROOT / "MAGE"
VERILOG_EVAL_ROOT = MAGE_ROOT / "verilog-eval"
RTLLM_ROOT = PROJECT_ROOT / "RTLLM"

SYSTEM_PROMPT = r"""
You are one senior RTL engineer. Work as a single role.
You must generate and repair both the RTL and your own testbench.
Never assume access to an external or hidden official testbench.
Return valid JSON only.
"""

INITIAL_PROMPT = r"""
Implement the requested design from the natural-language specification.
Write:
1. one complete RTL module whose module name and interface match the specification;
2. one complete self-generated testbench that checks the specified behavior.

The testbench must print exactly one of:
- "SIMULATION PASSED" when all checks pass;
- "SIMULATION FAILED - <number> MISMATCHES DETECTED" otherwise.

Do not reference any external testbench or reference implementation.

Return JSON with this exact shape:
{
  "reasoning": "brief reasoning",
  "rtl": "complete RTL source",
  "testbench": "complete testbench source"
}

<input_spec>
{input_spec}
</input_spec>
"""

ASSISTED_INITIAL_PROMPT = r"""
Implement the requested design from the natural-language specification.
The official testbench is provided only as interface and behavior context.
Do not assume access to an official reference RTL implementation.

Write:
1. one complete RTL module whose module name and interface match the testbench;
2. one complete self-generated testbench for the repair loop.

The self-generated testbench must print exactly one of:
- "SIMULATION PASSED" when all checks pass;
- "SIMULATION FAILED - <number> MISMATCHES DETECTED" otherwise.

Return JSON with this exact shape:
{
  "reasoning": "brief reasoning",
  "rtl": "complete RTL source",
  "testbench": "complete self-generated testbench source"
}

<input_spec>
{input_spec}
</input_spec>

<official_testbench>
{official_testbench}
</official_testbench>
"""

FEEDBACK_PROMPT = r"""
Your previous RTL and self-generated testbench did not pass your own closed-loop test.
Repair the RTL and, only if justified, the testbench.
Return the complete replacement pair in the same JSON shape.
Do not reference any external or hidden official testbench.

<self_test_log>
{self_test_log}
</self_test_log>
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)


def redact(text: str) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return text.replace(key, "[REDACTED_API_KEY]") if key else text


def parse_response(text: str) -> dict:
    candidates = [text.strip()]
    first = text.find("{")
    last = text.rfind("}")
    if 0 <= first < last:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate, strict=False)
            if not all(
                isinstance(value.get(field), str)
                for field in ("reasoning", "rtl", "testbench")
            ):
                continue
            return value
        except (json.JSONDecodeError, AttributeError):
            continue
    raise ValueError("Response is not a valid single-agent JSON object")


def run_self_test(rtl_path: Path, testbench_path: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    binary_path = work_dir / "self_simv"
    compile_command = [
        "iverilog",
        "-g2012",
        "-Wall",
        "-o",
        str(binary_path),
        str(rtl_path),
        str(testbench_path),
    ]
    started = time.monotonic()
    try:
        compile = subprocess.run(
            compile_command,
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "compile_timeout",
            "passed": False,
            "log": str(exc.stdout or ""),
            "elapsed_seconds": time.monotonic() - started,
        }
    if compile.returncode != 0:
        return {
            "status": "compile_error",
            "passed": False,
            "log": compile.stdout,
            "elapsed_seconds": time.monotonic() - started,
        }
    try:
        simulation = subprocess.run(
            [str(binary_path)],
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "simulation_timeout",
            "passed": False,
            "log": str(exc.stdout or ""),
            "elapsed_seconds": time.monotonic() - started,
        }
    passed = (
        simulation.returncode == 0
        and "SIMULATION PASSED" in simulation.stdout
        and "SIMULATION FAILED" not in simulation.stdout
    )
    return {
        "status": "passed" if passed else "functional_mismatch",
        "passed": passed,
        "returncode": simulation.returncode,
        "log": simulation.stdout,
        "elapsed_seconds": time.monotonic() - started,
    }


def verilog_eval_tasks(
    filter_pattern: str, *, assisted: bool
) -> list[dict]:
    specs = get_benchmark_contents(
        TypeBenchmark.VERILOG_EVAL_V2,
        TypeBenchmarkFile.SPEC,
        str(VERILOG_EVAL_ROOT),
        filter_pattern,
    )
    testbenches = (
        get_benchmark_contents(
            TypeBenchmark.VERILOG_EVAL_V2,
            TypeBenchmarkFile.TEST_PATH,
            str(VERILOG_EVAL_ROOT),
            filter_pattern,
        )
        if assisted
        else {}
    )
    return [
        {
            "task_id": task_id,
            "benchmark": "VerilogEval V2",
            "spec": spec,
            "module_name": None,
            "official_testbench": (
                Path(testbenches[task_id]).read_text(encoding="utf-8")
                if assisted
                else None
            ),
        }
        for task_id, spec in specs.items()
    ]


def rtllm_tasks(filter_pattern: str, *, assisted: bool) -> list[dict]:
    regex = re.compile(filter_pattern)
    return [
        {
            "task_id": task.task_id,
            "benchmark": "RTLLM V2",
            "spec": task.natural_language_spec,
            "module_name": task.module_name,
            "official_testbench": (
                Path(task.official_testbench_path).read_text(encoding="utf-8")
                if assisted
                else None
            ),
        }
        for task in load_rtllm_tasks(
            RTLLM_ROOT, include_official_contents=assisted
        )
        if regex.search(task.task_id)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark", required=True, choices=("verilog_eval_v2", "rtllm_v2")
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--filter", default=r"^(.*)$")
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--use-official-tb", action="store_true")
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

    if args.benchmark == "verilog_eval_v2":
        tasks = verilog_eval_tasks(
            args.filter, assisted=args.use_official_tb
        )
    else:
        tasks = rtllm_tasks(args.filter, assisted=args.use_official_tb)
    if not tasks:
        raise ValueError("No tasks matched the requested filter")

    llm = build_budgeted_llm(max_tokens=args.max_tokens)
    token_counter = TokenCounter(llm)
    set_exp_setting(temperature=args.temperature, top_p=args.top_p)
    arm = "single_assisted" if args.use_official_tb else "single_hidden"

    if args.resume:
        protocol = json.loads((run_dir / "protocol.json").read_text())
        protocol.setdefault("resume_history", []).append({"resumed_at": utc_now()})
    else:
        protocol = {
            "run_kind": "real_api_single_agent",
            "arm": arm,
            "benchmark": tasks[0]["benchmark"],
            "provider": "deepseek",
            "model": "deepseek-flash",
            "api_base_url": "https://api.deepseek.com",
            "thinking": "disabled",
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "max_rounds": args.max_rounds,
            "task_count": len(tasks),
            "filter_instance": args.filter,
            "official_testbench_hidden": not args.use_official_tb,
            "testbench_assisted_generation": args.use_official_tb,
            "official_reference_rtl_hidden": True,
            "single_role_count": 1,
            "budget": {
                "max_api_calls": 120,
                "max_tokens": 500000,
                "max_seconds": 1800,
            },
            "started_at": utc_now(),
        }
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
        llm.reset_budget()
        token_counter.reset()
        token_counter.set_cur_tag("SingleAgent")
        task_started = time.monotonic()
        task_id = task["task_id"]
        if task_id in completed_ids:
            continue
        output_dir = run_dir / "output" / task_id
        output_dir.mkdir(parents=True, exist_ok=args.resume)
        rtl_path = output_dir / "rtl.sv"
        testbench_path = output_dir / "tb.sv"
        print(f"({index}/{len(tasks)}) {task_id}", flush=True)

        messages = [
            ChatMessage(content=SYSTEM_PROMPT, role=MessageRole.SYSTEM),
            ChatMessage(
                content=(
                    ASSISTED_INITIAL_PROMPT.replace(
                        "{input_spec}", task["spec"]
                    ).replace(
                        "{official_testbench}",
                        task["official_testbench"] or "",
                    )
                    if args.use_official_tb
                    else INITIAL_PROMPT.replace(
                        "{input_spec}", task["spec"]
                    )
                ),
                role=MessageRole.USER,
            ),
        ]
        rounds = []
        final_self_test = None
        status = "rounds_exhausted"
        for round_index in range(1, args.max_rounds + 1):
            round_started = time.monotonic()
            try:
                response, token_count = token_counter.count_chat(messages)
            except BudgetExceeded as exc:
                status = exc.kind
                break
            except Exception as exc:
                status = "api_error"
                rounds.append(
                    {
                        "round": round_index,
                        "status": "api_error",
                        "error": redact(f"{type(exc).__name__}: {exc}"),
                    }
                )
                fatal_api_error = True
                break
            content = redact(response.message.content or "")
            round_record = {
                "round": round_index,
                "token_usage": {
                    "input_tokens": token_count.in_token_cnt,
                    "output_tokens": token_count.out_token_cnt,
                },
                "response": content,
            }
            try:
                parsed = parse_response(content)
            except ValueError as exc:
                round_record.update(
                    status="json_parse_error",
                    elapsed_seconds=time.monotonic() - round_started,
                )
                rounds.append(round_record)
                messages.extend(
                    [
                        ChatMessage(content=content, role=MessageRole.ASSISTANT),
                        ChatMessage(
                            content=(
                                "The response must be valid JSON with string fields "
                                'reasoning, rtl, and testbench. Error: ' + str(exc)
                            ),
                            role=MessageRole.USER,
                        ),
                    ]
                )
                continue

            rtl_path.write_text(parsed["rtl"], encoding="utf-8")
            testbench_path.write_text(parsed["testbench"], encoding="utf-8")
            self_test = run_self_test(
                rtl_path,
                testbench_path,
                output_dir / "self_test" / f"round_{round_index:02d}",
            )
            self_test["log"] = redact(self_test["log"])
            round_record.update(
                status=self_test["status"],
                self_test=self_test,
                elapsed_seconds=time.monotonic() - round_started,
            )
            rounds.append(round_record)
            final_self_test = self_test
            if self_test["passed"]:
                status = "completed"
                break
            messages.extend(
                [
                    ChatMessage(content=content, role=MessageRole.ASSISTANT),
                    ChatMessage(
                        content=FEEDBACK_PROMPT.format(
                            self_test_log=self_test["log"]
                        ),
                        role=MessageRole.USER,
                    ),
                ]
            )

        counts = token_counter.get_sum_count()
        budget = llm.budget_snapshot()
        record = {
            "task_id": task_id,
            "benchmark": task["benchmark"],
            "module_name": task["module_name"],
            "spec_sha256": sha256_text(task["spec"]),
            "status": status,
            "self_test_passed": bool(
                final_self_test and final_self_test.get("passed")
            ),
            "rounds": rounds,
            "round_count": len(rounds),
            "token_usage": {
                "input_tokens": counts.in_token_cnt,
                "output_tokens": counts.out_token_cnt,
                "total_tokens": token_counter.get_total_token(),
            },
            "generation_budget": budget,
            "elapsed_seconds": time.monotonic() - task_started,
            "output_dir": str(output_dir),
            "rtl_path": str(rtl_path) if rtl_path.is_file() else None,
            "testbench_path": (
                str(testbench_path) if testbench_path.is_file() else None
            ),
        }
        records.append(record)
        save_json(run_dir / "records.json", records)
        if fatal_api_error:
            break

    summary = {
        "arm": arm,
        "benchmark": tasks[0]["benchmark"],
        "task_count": len(records),
        "self_test_passed": sum(record["self_test_passed"] for record in records),
        "statuses": {
            status: sum(record["status"] == status for record in records)
            for status in sorted({record["status"] for record in records})
        },
        "total_tokens": sum(
            record["token_usage"]["total_tokens"] for record in records
        ),
        "total_api_calls": sum(
            record["generation_budget"]["api_calls"] for record in records
        ),
        "elapsed_seconds": sum(record["elapsed_seconds"] for record in records),
        "completed_at": utc_now(),
    }
    save_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
