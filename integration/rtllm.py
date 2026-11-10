"""RTLLM V2 loader and official-testbench evaluator."""

import hashlib
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


CATEGORY_DIRS = ("Arithmetic", "Memory", "Control", "Miscellaneous")
VERILATOR_FALLBACK_TOP_MODULES = {
    "asyn_fifo": "asyn_fifo_tb",
    "ring_counter": "testbench",
    "radix2_div": "radix2_div_tb",
    "clkgenerator": "clkgenerator_tb",
}


@dataclass(frozen=True)
class RTLLMTask:
    task_id: str
    module_name: str
    category: str
    natural_language_spec: str
    official_testbench_path: str
    reference_rtl_path: str
    metadata: dict


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def description_module_name(spec: str) -> str:
    match = re.search(
        r"Module\s+name\s*:\s*\n\s*([A-Za-z_]\w*)", spec, flags=re.IGNORECASE
    )
    if not match:
        raise ValueError("RTLLM design description has no module name")
    return match.group(1)


def load_tasks(
    root: Path, *, include_official_contents: bool = True
) -> list[RTLLMTask]:
    root = root.resolve()
    tasks = []
    for category in CATEGORY_DIRS:
        category_root = root / category
        if not category_root.is_dir():
            raise FileNotFoundError(f"Missing RTLLM category: {category_root}")
        for description_path in sorted(category_root.rglob("design_description.txt")):
            design_dir = description_path.parent
            task_id = design_dir.name
            spec = description_path.read_text(encoding="utf-8")
            testbench_path = design_dir / "testbench.v"
            if not testbench_path.is_file():
                raise FileNotFoundError(f"Missing testbench for {task_id}")
            references = sorted(design_dir.glob("verified_*.v"))
            if len(references) != 1:
                raise ValueError(
                    f"Expected one verified RTL for {task_id}, found {len(references)}"
                )
            described_module = description_module_name(spec)
            if include_official_contents:
                testbench = testbench_path.read_text(encoding="utf-8")
                module_name = task_id if task_id in testbench else described_module
                metadata = {
                    "source_relative_dir": str(design_dir.relative_to(root)),
                    "description_sha256": sha256_text(spec),
                    "testbench_sha256": hashlib.sha256(
                        testbench_path.read_bytes()
                    ).hexdigest(),
                    "reference_rtl_sha256": hashlib.sha256(
                        references[0].read_bytes()
                    ).hexdigest(),
                    "description_module_name": described_module,
                    "testbench_module_name": module_name,
                }
            else:
                module_name = described_module
                metadata = {
                    "source_relative_dir": str(design_dir.relative_to(root)),
                    "description_sha256": sha256_text(spec),
                    "description_module_name": described_module,
                }
            tasks.append(
                RTLLMTask(
                    task_id=task_id,
                    module_name=module_name,
                    category=category,
                    natural_language_spec=spec,
                    official_testbench_path=str(testbench_path.resolve()),
                    reference_rtl_path=str(references[0].resolve()),
                    metadata=metadata,
                )
            )
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("RTLLM task IDs are not unique")
    return tasks


def materialize_reference(task: RTLLMTask, target: Path) -> Path:
    source = Path(task.reference_rtl_path).read_text(encoding="utf-8")
    matches = list(re.finditer(r"\bmodule\s+([A-Za-z_]\w*)", source))
    if not matches:
        raise ValueError(f"No module declaration in {task.reference_rtl_path}")
    match = next(
        (item for item in matches if item.group(1).startswith("verified_")),
        matches[0],
    )
    if match.group(1) != task.module_name:
        source = (
            source[: match.start(1)]
            + task.module_name
            + source[match.end(1) :]
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return target


def classify_simulation(stdout: str, stderr: str) -> str:
    compact = re.sub(r"\s+", "", stdout).lower()
    if "yourdesignpassed" in compact:
        return "passed"
    if "testcompletedwith" in compact:
        return "functional_mismatch"
    if "error" in compact:
        return "runtime_error"
    return "missing_official_result"


def evaluate_rtl_with_verilator(
    task: RTLLMTask,
    rtl_path: Path,
    work_dir: Path,
    timeout_s: float,
) -> dict:
    build_dir = work_dir / "verilator"
    build_dir.mkdir(parents=True, exist_ok=True)
    testbench_path = Path(task.official_testbench_path).resolve()
    binary_path = build_dir / "simv"
    compile_command = [
        "verilator",
        "--timing",
        "--binary",
        "--top-module",
        VERILATOR_FALLBACK_TOP_MODULES[task.task_id],
        "-Wno-fatal",
        "-Wno-lint",
        "-Wno-style",
        "--Mdir",
        str(build_dir),
        "-o",
        "simv",
        str(rtl_path),
        str(testbench_path),
    ]
    compile_log = work_dir / "compile.log"
    simulation_log = work_dir / "simulation.log"
    started = time.monotonic()
    result = {
        "task_id": task.task_id,
        "module_name": task.module_name,
        "rtl_path": str(rtl_path),
        "testbench_path": str(testbench_path),
        "simulator": "verilator",
        "compile_command": compile_command,
        "simulation_command": [str(binary_path)],
    }
    try:
        compile_process = subprocess.run(
            compile_command,
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        compile_log.write_text(str(exc.stdout or ""), encoding="utf-8")
        result.update(
            status="compile_timeout",
            passed=False,
            error=f"Verilator compilation exceeded {timeout_s} seconds",
            elapsed_seconds=time.monotonic() - started,
        )
        return result
    compile_log.write_text(compile_process.stdout, encoding="utf-8")
    if compile_process.returncode != 0:
        result.update(
            status="compile_error",
            passed=False,
            error=f"Verilator exited with {compile_process.returncode}",
            elapsed_seconds=time.monotonic() - started,
        )
        return result
    try:
        simulation_process = subprocess.run(
            [str(binary_path)],
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        simulation_log.write_text(str(exc.stdout or ""), encoding="utf-8")
        result.update(
            status="simulation_timeout",
            passed=False,
            error=f"Verilator simulation exceeded {timeout_s} seconds",
            elapsed_seconds=time.monotonic() - started,
        )
        return result
    simulation_log.write_text(simulation_process.stdout, encoding="utf-8")
    status = classify_simulation(simulation_process.stdout, "")
    result.update(
        status=status,
        passed=status == "passed" and simulation_process.returncode == 0,
        simulation_returncode=simulation_process.returncode,
        elapsed_seconds=time.monotonic() - started,
    )
    return result


def evaluate_rtl(
    task: RTLLMTask,
    rtl_path: Path,
    work_dir: Path,
    timeout_s: float = 60.0,
) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    rtl_path = Path(rtl_path).resolve()
    testbench_path = Path(task.official_testbench_path).resolve()
    for support_file in testbench_path.parent.iterdir():
        if support_file.is_file() and support_file.suffix.lower() not in {".v", ".sv"}:
            shutil.copy2(support_file, work_dir / support_file.name)
    if task.task_id in VERILATOR_FALLBACK_TOP_MODULES:
        return evaluate_rtl_with_verilator(task, rtl_path, work_dir, timeout_s)
    binary_path = work_dir / "simv"
    compile_log = work_dir / "compile.log"
    simulation_log = work_dir / "simulation.log"
    started = time.monotonic()
    result = {
        "task_id": task.task_id,
        "module_name": task.module_name,
        "rtl_path": str(rtl_path),
        "testbench_path": str(testbench_path),
        "simulator": "iverilog",
        "compile_command": [
            "iverilog",
            "-g2012",
            "-Wall",
            "-o",
            str(binary_path),
            str(rtl_path),
            str(testbench_path),
        ],
        "simulation_command": ["vvp", str(binary_path)],
    }
    if not rtl_path.is_file() or rtl_path.stat().st_size == 0:
        result.update(
            status="artifact_missing",
            passed=False,
            error="Generated RTL is absent or empty",
            elapsed_seconds=time.monotonic() - started,
        )
        return result

    try:
        compile_process = subprocess.run(
            result["compile_command"],
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        compile_log.write_text(str(exc.stdout or ""), encoding="utf-8")
        result.update(
            status="compile_timeout",
            passed=False,
            error=f"Compilation exceeded {timeout_s} seconds",
            elapsed_seconds=time.monotonic() - started,
        )
        return result
    compile_log.write_text(compile_process.stdout, encoding="utf-8")
    if compile_process.returncode != 0:
        result.update(
            status="compile_error",
            passed=False,
            error=f"iverilog exited with {compile_process.returncode}",
            elapsed_seconds=time.monotonic() - started,
        )
        return result

    try:
        simulation_process = subprocess.run(
            result["simulation_command"],
            cwd=work_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        simulation_log.write_text(simulation_process.stdout, encoding="utf-8")
        status = classify_simulation(simulation_process.stdout, "")
        passed = status == "passed" and simulation_process.returncode == 0
        result.update(
            status=status if passed else (
                "simulation_process_error"
                if simulation_process.returncode != 0
                else status
            ),
            passed=passed,
            simulation_returncode=simulation_process.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        simulation_log.write_text(str(exc.stdout or ""), encoding="utf-8")
        result.update(
            status="simulation_timeout",
            passed=False,
            error=f"Simulation exceeded {timeout_s} seconds",
        )
    result["elapsed_seconds"] = time.monotonic() - started
    return result


def save_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=asdict),
        encoding="utf-8",
    )


def copy_candidate(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
