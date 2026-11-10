#!/usr/bin/env python3
"""Build Plan 4 charts, diagrams, gallery, and provenance manifest."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS = PROJECT_ROOT / "runs"
FIGURES = PROJECT_ROOT / "docs" / "figures"
VISUALIZATIONS = PROJECT_ROOT / "docs" / "visualizations"
RESULTS_PATH = RUNS / "plan3_results_20261110.json"
SELECTION_PATH = RUNS / "plan3_repeat_selection_20261110.json"
REPAIR_PATH = RUNS / "plan3_repair_analysis_20261110" / "summary.json"
CAD_RUN = (
    PROJECT_ROOT
    / "mac_api_cadtestbench"
    / "outputs"
    / "mac_api_deepseek_deepseek-flash_text_20261109T162808Z_d9a653"
)
CAD_METRICS_PATH = CAD_RUN / "metrics.csv"
CAD_EVALUATIONS_PATH = CAD_RUN / "evaluations.json"
CAD_PLOT_INDEX_PATH = CAD_RUN / "plot_index.json"

BENCHMARKS = ("verilog_eval_v2", "rtllm_v2")
BENCHMARK_LABELS = {
    "verilog_eval_v2": "VerilogEval V2",
    "rtllm_v2": "RTLLM V2",
}
ARMS = ("A", "B", "C", "D")
ARM_LABELS = {
    "A": "A | MAGE | testbench-assisted",
    "B": "B | MAGE | testbench-hidden",
    "C": "C | Single | testbench-hidden",
    "D": "D | Single | testbench-assisted",
}
ARM_SHORT_LABELS = {
    "A": "MAGE\nassisted",
    "B": "MAGE\nhidden",
    "C": "Single\nhidden",
    "D": "Single\nassisted",
}
COLORS = {
    "A": "#2F6BFF",
    "B": "#00A6A6",
    "C": "#F59E0B",
    "D": "#8B5CF6",
    "positive": "#2E9D66",
    "neutral": "#64748B",
    "negative": "#C2413A",
    "grid": "#E5E7EB",
    "ink": "#0F172A",
    "muted": "#475569",
    "border": "#CBD5E1",
    "paper": "#FFFFFF",
    "soft": "#F8FAFC",
    "soft_blue": "#EFF6FF",
    "soft_teal": "#ECFDF5",
}

FULL_RESULT_PATHS = {
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

EFFECT_KEYS = (
    "architecture_hidden_C_minus_B",
    "architecture_assisted_D_minus_A",
    "testbench_effect_mage_A_minus_B",
    "testbench_effect_single_D_minus_C",
)
EFFECT_LABELS = {
    "architecture_hidden_C_minus_B": "Architecture | hidden\nC - B",
    "architecture_assisted_D_minus_A": "Architecture | assisted\nD - A",
    "testbench_effect_mage_A_minus_B": "Testbench | MAGE\nA - B",
    "testbench_effect_single_D_minus_C": "Testbench | Single\nD - C",
}

FAILURE_ORDER = {
    "verilog_eval_v2": ("m", "R", "C", "T", "r"),
    "rtllm_v2": (
        "compile_error",
        "functional_mismatch",
        "runtime_error",
        "simulation_timeout",
        "artifact_missing",
    ),
}
FAILURE_LABELS = {
    "m": "m | missing RTL",
    "R": "R | simulation mismatch",
    "C": "C | compile error",
    "T": "T | timeout",
    "r": "r | simulation runtime error",
    "compile_error": "Compile error",
    "functional_mismatch": "Functional mismatch",
    "runtime_error": "Runtime error",
    "simulation_timeout": "Simulation timeout",
    "artifact_missing": "Artifact missing",
}
FAILURE_COLORS = {
    "m": "#94A3B8",
    "R": "#C2413A",
    "C": "#8B5CF6",
    "T": "#2F6BFF",
    "r": "#00A6A6",
    "compile_error": "#8B5CF6",
    "functional_mismatch": "#C2413A",
    "runtime_error": "#F59E0B",
    "simulation_timeout": "#2F6BFF",
    "artifact_missing": "#94A3B8",
}

OUTCOME_ORDER = (
    "unchanged_pass",
    "repair_recovery",
    "persistent_fail",
    "regression",
)
OUTCOME_LABELS = {
    "unchanged_pass": "Unchanged pass",
    "repair_recovery": "Repair recovery",
    "persistent_fail": "Persistent fail",
    "regression": "Regression",
}
OUTCOME_COLORS = {
    "unchanged_pass": "#2E9D66",
    "repair_recovery": "#00A6A6",
    "persistent_fail": "#94A3B8",
    "regression": "#C2413A",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def relative_source(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def resolve_recorded_path(value: str | Path) -> Path:
    """Resolve historical absolute paths against the active repository root."""
    path = Path(value)
    normalized = path.as_posix()
    marker = "/mac_api_cadtestbench/"
    marker_index = normalized.rfind(marker)
    if marker_index >= 0:
        candidate = PROJECT_ROOT / normalized[marker_index + 1 :]
        if candidate.exists():
            return candidate
    return path


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.labelsize": 10,
            "axes.edgecolor": COLORS["border"],
            "axes.labelcolor": COLORS["muted"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "text.color": COLORS["ink"],
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": COLORS["paper"],
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "svg.fonttype": "none",
        }
    )


def new_figure(
    title: str,
    subtitle: str,
    *,
    panels: int = 1,
    footer: str | None = None,
):
    fig, axes = plt.subplots(
        1,
        panels,
        figsize=(9, 5),
        dpi=200,
        squeeze=False,
        constrained_layout=False,
    )
    axes = axes.ravel()
    fig.suptitle(
        title,
        x=0.045,
        y=0.965,
        ha="left",
        va="top",
        fontsize=18,
        fontweight="bold",
        color=COLORS["ink"],
    )
    fig.text(
        0.045,
        0.91,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.5,
        color=COLORS["muted"],
    )
    if footer:
        fig.text(
            0.955,
            0.025,
            footer,
            ha="right",
            va="bottom",
            fontsize=7.5,
            color=COLORS["neutral"],
        )
    fig.subplots_adjust(
        left=0.075,
        right=0.965,
        top=0.75,
        bottom=0.17,
        wspace=0.25,
    )
    return fig, axes


def style_axis(ax, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, linewidth=0.8, color=COLORS["grid"], alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=6)


def save_figure(fig, stem: str) -> dict[str, Path]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    png_path = FIGURES / f"{stem}.png"
    svg_path = FIGURES / f"{stem}.svg"
    metadata = {
        "Title": stem,
        "Creator": "Plan 4 visualization pipeline",
        "Date": "2026-11-10",
    }
    fig.savefig(
        png_path,
        dpi=200,
        facecolor="white",
        metadata=metadata,
        bbox_inches=None,
    )
    fig.savefig(
        svg_path,
        facecolor="white",
        metadata=metadata,
        bbox_inches=None,
    )
    plt.close(fig)
    return {"png": png_path, "svg": svg_path}


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def arm_legend_handles() -> list[Patch]:
    return [
        Patch(facecolor=COLORS[arm], edgecolor="none", label=ARM_LABELS[arm])
        for arm in ARMS
    ]


def build_full_2x2(results: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Official pass@1 across the complete 2 x 2 design",
        "Final RTL scored by each benchmark official evaluator | axes 0-100%",
        panels=2,
        footer="Positive bars are official passes; denominators remain the complete benchmark.",
    )
    fig.legend(
        handles=arm_legend_handles(),
        loc="upper left",
        bbox_to_anchor=(0.045, 0.835, 0.91, 0.05),
        mode="expand",
        ncol=4,
        fontsize=7.7,
        handlelength=1.2,
        columnspacing=1.0,
    )
    width = 0.18
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(ARMS))
    for ax, benchmark in zip(axes, BENCHMARKS):
        data = results[benchmark]["arms"]
        x = np.arange(len(ARMS))
        for arm_index, (arm, offset) in enumerate(zip(ARMS, offsets)):
            full = data[arm]["full"]
            value = full["pass_at_1"] * 100
            bars = ax.bar(
                x + offset,
                value,
                width,
                color=COLORS[arm],
                edgecolor="white",
                linewidth=0.6,
                zorder=3,
            )
            ax.text(
                x[arm_index] + offset,
                3,
                f"{full['passed']}/{full['total']}",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=6.7,
                color="white",
                fontweight="bold",
            )
            ax.text(
                x[arm_index] + offset,
                value + 1.2,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8,
                color=COLORS["ink"],
            )
        ax.set_title(
            f"{BENCHMARK_LABELS[benchmark]} | n={data['A']['full']['total']}",
            loc="left",
            pad=10,
        )
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 20))
        ax.set_ylabel("Official pass@1 (%)")
        ax.set_xticks(np.arange(len(ARMS)), ARMS)
        style_axis(ax)
    return save_figure(fig, "rtl_full_2x2")


def build_repeat_mean_std(results: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Three-repeat stability on the fixed 10-task subset",
        "Bars show mean official pass@1 | error bars show population standard deviation",
        panels=2,
        footer="Each point is one independent repeat; the subset was frozen before model runs.",
    )
    fig.legend(
        handles=arm_legend_handles(),
        loc="upper left",
        bbox_to_anchor=(0.045, 0.835, 0.91, 0.05),
        mode="expand",
        ncol=4,
        fontsize=7.7,
        handlelength=1.2,
        columnspacing=1.0,
    )
    for ax, benchmark in zip(axes, BENCHMARKS):
        arm_data = results[benchmark]["arms"]
        x = np.arange(len(ARMS))
        for index, arm in enumerate(ARMS):
            repeat = arm_data[arm]["repeat"]
            total = repeat["pooled_total"] // 3
            values = np.asarray(repeat["pass_at_1_per_repeat"], dtype=float) * 100
            average = float(np.mean(values))
            spread = float(np.std(values))
            ax.bar(
                x[index],
                average,
                width=0.62,
                color=COLORS[arm],
                alpha=0.9,
                edgecolor="white",
                linewidth=0.8,
                zorder=2,
            )
            ax.errorbar(
                x[index],
                average,
                yerr=spread,
                fmt="none",
                ecolor=COLORS["ink"],
                elinewidth=1.1,
                capsize=4,
                zorder=4,
            )
            jitter = np.linspace(-0.12, 0.12, len(values))
            ax.scatter(
                x[index] + jitter,
                values,
                s=19,
                facecolor="white",
                edgecolor=COLORS["ink"],
                linewidth=0.8,
                zorder=5,
            )
            ax.text(
                x[index],
                min(98.5, average + spread + 2.4),
                f"{average:.1f}%\n±{spread:.1f}",
                ha="center",
                va="bottom",
                fontsize=7.6,
                color=COLORS["ink"],
            )
            ax.text(
                0.5,
                -0.17,
                f"n={total} tasks per repeat",
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=8,
                color=COLORS["muted"],
            )
        ax.set_title(BENCHMARK_LABELS[benchmark], loc="left", pad=10)
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 20))
        ax.set_ylabel("Repeat mean pass@1 (%)")
        ax.set_xticks(x, ARMS)
        style_axis(ax)
    return save_figure(fig, "rtl_repeat_mean_std")


def draw_forest_panel(
    ax,
    benchmark_data: dict,
    effect_group: str,
    *,
    xlim: tuple[float, float],
    title: str,
    show_row_labels: bool,
) -> None:
    effects = benchmark_data[effect_group]
    y_positions = np.arange(len(EFFECT_KEYS))[::-1]
    for y, key in zip(y_positions, EFFECT_KEYS):
        effect = effects[key]
        delta = effect["mean_difference"] * 100
        low = effect["ci95_low"] * 100
        high = effect["ci95_high"] * 100
        color = (
            COLORS["positive"]
            if delta > 0
            else COLORS["negative"]
            if delta < 0
            else COLORS["neutral"]
        )
        crosses_zero = low <= 0 <= high
        ax.errorbar(
            delta,
            y,
            xerr=np.asarray([[delta - low], [high - delta]]),
            fmt="o",
            markersize=7.5,
            markerfacecolor="white" if crosses_zero else color,
            markeredgecolor=color,
            markeredgewidth=1.5,
            ecolor=color,
            elinewidth=1.8,
            capsize=4,
            zorder=3,
        )
        label = f"{delta:+.1f} [{low:+.1f}, {high:+.1f}]"
        if delta >= 0:
            ax.text(
                low - 1,
                y,
                label,
                va="center",
                ha="right",
                fontsize=7.5,
                color=COLORS["muted"],
            )
        else:
            ax.text(
                high + 1,
                y,
                label,
                va="center",
                ha="left",
                fontsize=7.5,
                color=COLORS["muted"],
            )
    ax.axvline(0, color=COLORS["ink"], linewidth=1.0, zorder=1)
    ax.set_yticks(y_positions, [EFFECT_LABELS[key] for key in EFFECT_KEYS])
    if not show_row_labels:
        ax.tick_params(axis="y", labelleft=False)
    ax.set_xlim(*xlim)
    ax.set_xlabel("Paired pass@1 difference (percentage points)")
    ax.set_title(title, loc="left", pad=10)
    style_axis(ax, grid_axis="x")
    ax.spines["left"].set_visible(False)


def build_full_effect_ci(results: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Full-benchmark paired effects with 95% bootstrap intervals",
        "Filled marker: interval excludes zero | hollow marker: interval includes zero",
        panels=2,
        footer="Positive values favor the second arm; negative values favor the first arm.",
    )
    fig.subplots_adjust(left=0.18, right=0.965, wspace=0.36)
    for ax, benchmark in zip(axes, BENCHMARKS):
        sample = results[benchmark]["arms"]["A"]["full"]["total"]
        draw_forest_panel(
            ax,
            results[benchmark],
            "full_effects",
            xlim=(-30, 42),
            title=f"{BENCHMARK_LABELS[benchmark]} | n={sample}",
            show_row_labels=benchmark == BENCHMARKS[0],
        )
    return save_figure(fig, "rtl_effect_ci_forest")


def build_repeat_effect_ci(results: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Fixed-subset paired effects with 95% bootstrap intervals",
        "Task-level bootstrap combines three repeats for each arm",
        panels=2,
        footer="Positive values favor the second arm; negative values favor the first arm.",
    )
    fig.subplots_adjust(left=0.18, right=0.965, wspace=0.36)
    for ax, benchmark in zip(axes, BENCHMARKS):
        sample = results[benchmark]["arms"]["A"]["repeat"]["pooled_total"] // 3
        draw_forest_panel(
            ax,
            results[benchmark],
            "repeat_effects",
            xlim=(-60, 68),
            title=f"{BENCHMARK_LABELS[benchmark]} | {sample} tasks x 3 repeats",
            show_row_labels=benchmark == BENCHMARKS[0],
        )
    return save_figure(fig, "rtl_repeat_effect_ci")


def build_complexity_subset(results: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Official pass@1 on the predefined complex-task subset",
        "Subset definition: top 50% by specification token count, frozen before scoring",
        panels=2,
        footer="Complexity is a prespecified secondary analysis with original task denominators.",
    )
    fig.legend(
        handles=arm_legend_handles(),
        loc="upper left",
        bbox_to_anchor=(0.045, 0.835, 0.91, 0.05),
        mode="expand",
        ncol=4,
        fontsize=7.7,
        handlelength=1.2,
        columnspacing=1.0,
    )
    for ax, benchmark in zip(axes, BENCHMARKS):
        data = results[benchmark]["arms"]
        x = np.arange(len(ARMS))
        values = []
        labels = []
        for arm in ARMS:
            subset = data[arm]["full"]["complexity_subset"]
            values.append(subset["pass_at_1"] * 100)
            labels.append(f"{subset['passed']}/{subset['total']}")
        bars = ax.bar(
            x,
            values,
            width=0.64,
            color=[COLORS[arm] for arm in ARMS],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        for bar, value, label in zip(bars, values, labels):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                3,
                label,
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=6.8,
                color="white",
                fontweight="bold",
            )
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.6,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=COLORS["ink"],
            )
        total = data["A"]["full"]["complexity_subset"]["total"]
        ax.set_title(
            f"{BENCHMARK_LABELS[benchmark]} | n={total}", loc="left", pad=10
        )
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 20))
        ax.set_ylabel("Official pass@1 (%)")
        ax.set_xticks(x, ARMS)
        style_axis(ax)
    return save_figure(fig, "rtl_complexity_subset")


def load_failure_counts() -> dict[str, dict[str, Counter]]:
    counts: dict[str, dict[str, Counter]] = {}
    for benchmark in BENCHMARKS:
        counts[benchmark] = {}
        for arm in ARMS:
            rows = load_json(FULL_RESULT_PATHS[(benchmark, arm)])
            if benchmark == "verilog_eval_v2":
                statuses = [
                    str(row.get("code", "unknown"))
                    for row in rows
                    if not bool(row["passed"])
                ]
            else:
                statuses = [
                    str(row.get("status", "unknown"))
                    for row in rows
                    if not bool(row["passed"])
                ]
            counts[benchmark][arm] = Counter(statuses)
    return counts


def failure_codes_for_plot(
    benchmark: str, counts: dict[str, dict[str, Counter]]
) -> tuple[str, ...]:
    discovered = set().union(
        *(set(counts[benchmark][arm]) for arm in ARMS)
    )
    ordered = [
        code for code in FAILURE_ORDER[benchmark] if code in discovered
    ]
    ordered.extend(sorted(discovered.difference(ordered)))
    return tuple(ordered)


def build_failure_codes(results: dict) -> dict[str, Path]:
    counts = load_failure_counts()
    fig, axes = new_figure(
        "Official failure-code composition across the 2 x 2 design",
        "Horizontal bars show the composition of failed tasks; passed tasks sit outside this view",
        panels=2,
        footer="Counts are taken from each benchmark official evaluator output.",
    )
    for ax, benchmark in zip(axes, BENCHMARKS):
        codes = failure_codes_for_plot(benchmark, counts)
        y = np.arange(len(ARMS))[::-1]
        for row_index, arm in enumerate(ARMS):
            failed = int(
                results[benchmark]["arms"][arm]["full"]["total"]
                - results[benchmark]["arms"][arm]["full"]["passed"]
            )
            left = 0.0
            for code in codes:
                count = counts[benchmark][arm].get(code, 0)
                if count == 0:
                    continue
                width = count / failed * 100
                ax.barh(
                    y[row_index],
                    width,
                    left=left,
                    height=0.58,
                    color=FAILURE_COLORS.get(code, COLORS["neutral"]),
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=3,
                )
                ax.text(
                    left + width / 2,
                    y[row_index],
                    str(count),
                    ha="center",
                    va="center",
                    fontsize=7.6,
                    color="white",
                    fontweight="bold",
                )
                left += width
            ax.text(
                102,
                y[row_index],
                f"{failed} failed | {results[benchmark]['arms'][arm]['full']['passed']} pass",
                va="center",
                ha="left",
                fontsize=7.5,
                color=COLORS["muted"],
            )
        ax.set_xlim(0, 130)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Share of failed tasks (%)")
        ax.set_yticks(y, ARMS)
        total = results[benchmark]["arms"]["A"]["full"]["total"]
        ax.set_title(
            f"{BENCHMARK_LABELS[benchmark]} | n={total}",
            loc="left",
            pad=10,
        )
        handles = [
            Patch(
                facecolor=FAILURE_COLORS.get(code, COLORS["neutral"]),
                label=FAILURE_LABELS.get(code, code),
            )
            for code in codes
        ]
        ax.legend(
            handles=handles,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.19),
            ncol=2,
            fontsize=7.1,
            handlelength=1.0,
            columnspacing=0.9,
        )
        style_axis(ax, grid_axis="x")
        ax.spines["left"].set_visible(False)
    fig.subplots_adjust(bottom=0.29)
    return save_figure(fig, "rtl_failure_codes")


def aggregate_repair_pairs(repair: dict, benchmark: str, arm: str) -> dict:
    pairs = [
        pair
        for pair in repair["pairs"]
        if pair["benchmark"] == benchmark and pair["arm"] == arm
    ]
    full = [pair for pair in pairs if pair["stage"] == "full"]
    repeats = [pair for pair in pairs if pair["stage"].startswith("repeat_")]
    if len(full) != 1:
        raise ValueError(f"Expected one full repair pair for {benchmark}/{arm}")
    full_pair = full[0]
    repeat_pair = {"task_count": 0}
    for outcome in OUTCOME_ORDER:
        repeat_pair[outcome] = sum(pair.get(outcome, 0) for pair in repeats)
        repeat_pair["task_count"] += repeat_pair[outcome]
    return {
        f"{arm} full": {
            "task_count": full_pair["task_count"],
            **{
                outcome: full_pair.get(outcome, 0)
                for outcome in OUTCOME_ORDER
            },
        },
        f"{arm} repeat total": {
            "task_count": repeat_pair["task_count"],
            **{
                outcome: repeat_pair[outcome]
                for outcome in OUTCOME_ORDER
            },
        },
    }


def build_repair_analysis(repair: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "Round-1 to final RTL outcomes under the official evaluator",
        "C and D are evaluated independently at round 1 and at the final repaired state",
        panels=2,
        footer="Repeat total pools the three fixed-subset repeats for task-level outcome counts.",
    )
    legend_handles = [
        Patch(facecolor=OUTCOME_COLORS[key], label=OUTCOME_LABELS[key])
        for key in OUTCOME_ORDER
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.045, 0.835, 0.91, 0.05),
        mode="expand",
        ncol=4,
        fontsize=8,
        handlelength=1.1,
    )
    for ax, benchmark in zip(axes, BENCHMARKS):
        values = {}
        values.update(aggregate_repair_pairs(repair, benchmark, "C"))
        values.update(aggregate_repair_pairs(repair, benchmark, "D"))
        names = list(values)
        x = np.arange(len(names))
        for index, name in enumerate(names):
            item = values[name]
            total = item["task_count"]
            left = 0.0
            for outcome in OUTCOME_ORDER:
                count = item.get(outcome, 0)
                width = count / total * 100 if total else 0.0
                if width <= 0:
                    continue
                ax.bar(
                    x[index],
                    width,
                    bottom=left,
                    width=0.62,
                    color=OUTCOME_COLORS[outcome],
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=3,
                )
                if width >= 5:
                    ax.text(
                        x[index],
                        left + width / 2,
                        str(count),
                        ha="center",
                        va="center",
                        fontsize=7.8,
                        color="white",
                        fontweight="bold",
                    )
                else:
                    ax.annotate(
                        str(count),
                        xy=(x[index] + 0.34, left + width / 2),
                        xytext=(5, 0),
                        textcoords="offset points",
                        va="center",
                        fontsize=7.2,
                        color=OUTCOME_COLORS[outcome],
                        fontweight="bold",
                    )
                left += width
        ax.set_xlim(-0.6, len(names) - 0.4)
        ax.set_ylim(0, 100)
        ax.set_yticks(np.arange(0, 101, 20))
        ax.set_ylabel("Outcome share (%)")
        ax.set_xticks(
            x,
            [
                f"{name.replace(' repeat total', ' repeats')}\nn={values[name]['task_count']}"
                for name in names
            ],
        )
        ax.set_title(BENCHMARK_LABELS[benchmark], loc="left", pad=10)
        style_axis(ax)
    return save_figure(fig, "rtl_repair_analysis")


def load_cad_metrics() -> dict:
    with CAD_METRICS_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError("Expected one detailed CAD metrics row")
    row = rows[0]
    return {
        "partition": row["partition"],
        "total_samples": int(row["total_samples"]),
        "pr": float(row["pr"]),
        "rs": float(row["rs"]),
        "invalid_sample_percentage": float(row["invalid_sample_percentage"]),
    }


def load_cad_categories() -> dict:
    evaluations = load_json(CAD_EVALUATIONS_PATH)
    categories = evaluations[0]["summary"]["aggregate_metrics"]["cadtest"][
        "category_accuracy"
    ]
    return categories


def build_cad_official_metrics(metrics: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "CADTestBench detailed official metrics",
        "Official PR, requirement satisfaction, and invalid-sample percentage",
        footer=f"Frozen CAD run | n={metrics['total_samples']} | official CADTestBench evaluator",
        panels=1,
    )
    ax = axes[0]
    labels = [
        "PR\nall tests pass",
        "RS\nrequirement groups",
        "Invalid\nsample share",
    ]
    values = [
        metrics["pr"],
        metrics["rs"],
        metrics["invalid_sample_percentage"],
    ]
    colors = [COLORS["A"], COLORS["B"], COLORS["negative"]]
    x = np.arange(3)
    bars = ax.bar(x, values, width=0.62, color=colors, zorder=3)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.8,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color=COLORS["ink"],
        )
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_ylabel("Official percentage (%)")
    ax.set_title(
        f"CADTestBench | {metrics['partition']} | n={metrics['total_samples']}",
        loc="left",
        pad=12,
    )
    style_axis(ax)
    return save_figure(fig, "cad_official_metrics")


def pretty_category(name: str) -> str:
    return name.replace("_", " ").title()


def build_cad_category_accuracy(categories: dict) -> dict[str, Path]:
    fig, axes = new_figure(
        "CADTestBench detailed accuracy by official test category",
        "Each bar reports passed / total official checks and category accuracy",
        footer="Category check counts differ; categories are not treated as equal-weight samples.",
        panels=1,
    )
    ax = axes[0]
    ordered = sorted(
        categories.items(), key=lambda item: item[1]["accuracy"], reverse=True
    )
    names = [pretty_category(name) for name, _ in ordered]
    values = [item["accuracy"] for _, item in ordered]
    passed = [item["passed"] for _, item in ordered]
    totals = [item["total"] for _, item in ordered]
    palette = [
        "#2F6BFF",
        "#2563EB",
        "#0284C7",
        "#0EA5E9",
        "#64748B",
        "#94A3B8",
    ]
    y = np.arange(len(names))[::-1]
    bars = ax.barh(
        y,
        values,
        height=0.62,
        color=palette[: len(names)],
        zorder=3,
    )
    for bar, value, count, total in zip(bars, values, passed, totals):
        ax.text(
            value + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%  |  {count}/{total}",
            va="center",
            fontsize=8.8,
            color=COLORS["ink"],
        )
    total_checks = sum(totals)
    ax.set_xlim(0, 100)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_xlabel("Official category accuracy (%)")
    ax.set_yticks(y, names)
    ax.set_title(
        f"Official category checks | {total_checks} checks",
        loc="left",
        pad=12,
    )
    fig.subplots_adjust(left=0.245, right=0.935)
    style_axis(ax, grid_axis="x")
    ax.spines["left"].set_visible(False)
    return save_figure(fig, "cad_category_accuracy")


def add_box(
    ax,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    lines: list[str],
    *,
    edge: str = COLORS["border"],
    face: str = COLORS["soft"],
    title_color: str = COLORS["ink"],
    linestyle: str = "solid",
    title_size: float = 9.2,
    body_size: float = 7.8,
) -> FancyBboxPatch:
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.5,rounding_size=0.8",
        linewidth=1.2,
        edgecolor=edge,
        facecolor=face,
        linestyle=linestyle,
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + height - 3.4,
        title,
        ha="center",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color=title_color,
    )
    if lines:
        ax.text(
            x + width / 2,
            y + height / 2 - 2.4,
            "\n".join(lines),
            ha="center",
            va="center",
            fontsize=body_size,
            color=COLORS["muted"],
            linespacing=1.35,
        )
    return box


def add_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#94A3B8",
    connectionstyle: str = "arc3,rad=0",
    linewidth: float = 1.5,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            color=color,
            linewidth=linewidth,
            connectionstyle=connectionstyle,
            shrinkA=2,
            shrinkB=2,
            zorder=1,
        )
    )


def diagram_canvas(title: str, subtitle: str):
    fig, ax = plt.subplots(figsize=(9, 5), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.suptitle(
        title,
        x=0.045,
        y=0.965,
        ha="left",
        va="top",
        fontsize=18,
        fontweight="bold",
        color=COLORS["ink"],
    )
    fig.text(
        0.045,
        0.91,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.5,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(left=0.025, right=0.975, top=0.84, bottom=0.04)
    return fig, ax


def build_project_architecture(results: dict) -> dict[str, Path]:
    fig, ax = diagram_canvas(
        "End-to-end experiment architecture",
        "Official inputs feed two generation workflows, official evaluators, reproducible records, and the 2 x 2 contrast layer",
    )
    ax.text(2, 91, "OFFICIAL INPUTS", fontsize=8.5, fontweight="bold", color=COLORS["neutral"])
    ax.text(25, 91, "GENERATION WORKFLOWS", fontsize=8.5, fontweight="bold", color=COLORS["neutral"])
    ax.text(61, 91, "OFFICIAL EVALUATION", fontsize=8.5, fontweight="bold", color=COLORS["neutral"])
    ax.text(81, 91, "REPRODUCIBLE RECORD", fontsize=8.5, fontweight="bold", color=COLORS["neutral"])

    add_box(ax, 2, 68, 18, 16, "CADTestBench", ["detailed partition", "200 official tasks"], edge="#93C5FD", face=COLORS["soft_blue"])
    add_box(ax, 2, 47, 18, 14, "VerilogEval V2", ["156 spec-to-RTL tasks"], edge="#93C5FD", face=COLORS["soft_blue"])
    add_box(ax, 2, 26, 18, 14, "RTLLM V2", ["50 official tasks"], edge="#93C5FD", face=COLORS["soft_blue"])

    add_box(ax, 26, 62, 29, 22, "CAD workflow", ["MAC roles", "CAD code generation", "STEP artifact bridge"], edge="#60A5FA", face="#F0F7FF", title_size=10)
    add_box(ax, 26, 22, 29, 30, "RTL workflow", ["MAGE TopAgent", "TB / RTL generation", "simulation and repair loop"], edge="#5EEAD4", face="#F0FDFA", title_size=10)

    add_box(ax, 60, 62, 16, 22, "CAD official evaluator", ["CadQuery checks", "PR / RS", "category accuracy"], edge="#A78BFA", face="#F5F3FF", title_size=8.2)
    add_box(ax, 60, 22, 16, 30, "RTL official evaluator", ["VerilogEval", "official analyzer", "RTLLM testbench"], edge="#A78BFA", face="#F5F3FF", title_size=8.2)

    add_box(ax, 81, 38, 17, 42, "RunRecord", ["protocol.json", "records.json", "RTL / TB / STEP", "official logs", "scores and summary"], edge="#FCD34D", face="#FFFBEB", title_size=10)

    add_arrow(ax, (20, 76), (26, 73))
    add_arrow(ax, (20, 56), (26, 44))
    add_arrow(ax, (20, 33), (26, 33))
    add_arrow(ax, (55, 73), (60, 73))
    add_arrow(ax, (55, 38), (60, 38))
    add_arrow(ax, (76, 73), (81, 65))
    add_arrow(ax, (76, 38), (81, 50))

    ax.add_patch(
        FancyBboxPatch(
            (2, 5),
            96,
            13,
            boxstyle="round,pad=0.5,rounding_size=1",
            facecolor="#F8FAFC",
            edgecolor=COLORS["border"],
            linewidth=1.0,
        )
    )
    ax.text(4, 11.5, "2 x 2 CONTRAST LAYER", fontsize=8.5, fontweight="bold", color=COLORS["neutral"])
    arm_x = [25, 43, 61, 79]
    arm_short = {
        "A": "MAGE / assisted",
        "B": "MAGE / hidden",
        "C": "Single / hidden",
        "D": "Single / assisted",
    }
    for x, arm in zip(arm_x, ARMS):
        ax.add_patch(
            FancyBboxPatch(
                (x, 7),
                14,
                7,
                boxstyle="round,pad=0.3,rounding_size=0.6",
                facecolor=COLORS[arm],
                edgecolor="white",
                linewidth=0.8,
            )
        )
        ax.text(x + 7, 10.5, arm_short[arm], ha="center", va="center", fontsize=7.6, color="white", fontweight="bold")
    add_arrow(ax, (89.5, 38), (89.5, 18), linewidth=1.8, color="#F59E0B")
    return save_figure(fig, "project_architecture")


def build_benchmark_adapter(results: dict) -> dict[str, Path]:
    fig, ax = diagram_canvas(
        "Benchmark adapter and stable multi-agent boundary",
        "Benchmark-specific loaders and evaluators surround one unchanged MAGE collaboration workflow",
    )
    ax.add_patch(
        Rectangle(
            (2, 14),
            31,
            69,
            facecolor="#F8FAFC",
            edgecolor="#CBD5E1",
            linewidth=1.0,
            linestyle=(0, (4, 3)),
        )
    )
    ax.text(4, 80, "REPLACEMENT BOUNDARY: INPUT", fontsize=8.2, fontweight="bold", color=COLORS["neutral"])
    ax.add_patch(
        Rectangle(
            (67, 14),
            31,
            69,
            facecolor="#F8FAFC",
            edgecolor="#CBD5E1",
            linewidth=1.0,
            linestyle=(0, (4, 3)),
        )
    )
    ax.text(69, 80, "REPLACEMENT BOUNDARY: OUTPUT", fontsize=8.2, fontweight="bold", color=COLORS["neutral"])

    add_box(ax, 3.5, 58, 12, 16, "VerilogEval", ["spec + official TB", "reference audit"], edge="#93C5FD", face=COLORS["soft_blue"], title_size=8.8)
    add_box(ax, 3.5, 25, 12, 16, "RTLLM", ["design description", "official TB"], edge="#93C5FD", face=COLORS["soft_blue"], title_size=8.8)
    add_box(ax, 18.5, 58, 12.5, 16, "VE loader", ["Prompt / Task", "Makefile metadata"], edge="#60A5FA", face="#F0F7FF", title_size=8.8)
    add_box(ax, 18.5, 25, 12.5, 16, "RTLLM loader", ["Prompt / Task", "module mapping"], edge="#60A5FA", face="#F0F7FF", title_size=8.8)
    add_arrow(ax, (15.5, 66), (18.5, 66))
    add_arrow(ax, (15.5, 33), (18.5, 33))

    add_box(ax, 36.5, 30, 26, 43, "STABLE MAGE AGENT", ["TopAgent", "TBGenerator", "RTLGenerator", "SimJudge", "RTLEditor"], edge="#2E9D66", face="#ECFDF5", title_size=11, body_size=8.6)
    add_arrow(ax, (31, 66), (36.5, 61), connectionstyle="arc3,rad=-0.08")
    add_arrow(ax, (31, 33), (36.5, 39), connectionstyle="arc3,rad=0.08")

    add_box(ax, 68.5, 58, 12, 16, "VE evaluator", ["official Makefile", "sv-iv-analyze"], edge="#C4B5FD", face="#F5F3FF", title_size=8.8)
    add_box(ax, 68.5, 25, 12, 16, "RTLLM evaluator", ["official TB", "Icarus / Verilator"], edge="#C4B5FD", face="#F5F3FF", title_size=8.8)
    add_box(ax, 84.5, 58, 12, 16, "VE result", ["code", "pass@1"], edge="#FCD34D", face="#FFFBEB", title_size=8.8)
    add_box(ax, 84.5, 25, 12, 16, "RTLLM result", ["status", "pass@1"], edge="#FCD34D", face="#FFFBEB", title_size=8.8)

    add_arrow(ax, (62.5, 59), (68.5, 66), connectionstyle="arc3,rad=0.05")
    add_arrow(ax, (62.5, 43), (68.5, 33), connectionstyle="arc3,rad=-0.05")
    add_arrow(ax, (80.5, 66), (84.5, 66))
    add_arrow(ax, (80.5, 33), (84.5, 33))

    ax.add_patch(
        FancyBboxPatch(
            (18.5, 6),
            78,
            6,
            boxstyle="round,pad=0.4,rounding_size=0.8",
            facecolor="#FFFBEB",
            edgecolor="#FCD34D",
            linewidth=1.0,
        )
    )
    ve_n = results["verilog_eval_v2"]["arms"]["A"]["full"]["total"]
    rt_n = results["rtllm_v2"]["arms"]["A"]["full"]["total"]
    ax.text(
        57.5,
        9,
        f"Shared RunRecord contract | VerilogEval n={ve_n} | RTLLM n={rt_n}",
        ha="center",
        va="center",
        fontsize=8.3,
        fontweight="bold",
        color=COLORS["muted"],
    )
    return save_figure(fig, "benchmark_adapter")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_paths(stem: str) -> list[str]:
    return [
        relative_source(FIGURES / f"{stem}.png"),
        relative_source(FIGURES / f"{stem}.svg"),
    ]


def build_manifest(
    results: dict,
    repair: dict,
    cad_metrics: dict,
    cad_categories: dict,
) -> dict:
    ve = results["verilog_eval_v2"]
    rt = results["rtllm_v2"]
    full_sources = [
        relative_source(RESULTS_PATH),
        relative_source(SELECTION_PATH),
    ]
    failure_sources = [
        relative_source(FULL_RESULT_PATHS[(benchmark, arm)])
        for benchmark in BENCHMARKS
        for arm in ARMS
    ]
    cad_sources = [
        relative_source(CAD_METRICS_PATH),
        relative_source(CAD_EVALUATIONS_PATH),
        relative_source(CAD_RUN / "protocol.json"),
    ]
    manifests = [
        {
            "id": "project_architecture",
            "title": "End-to-end experiment architecture",
            "type": "diagram",
            "outputs": output_paths("project_architecture"),
            "sources": [
                relative_source(RESULTS_PATH),
                *cad_sources,
                relative_source(RUNS / "experiment_manifest.json"),
            ],
            "sample_size": {
                "CADTestBench detailed": cad_metrics["total_samples"],
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "CAD 与 RTL 两条生成链路、官方评测入口、RunRecord 记录层和 2×2 对照层。",
        },
        {
            "id": "benchmark_adapter",
            "title": "Benchmark adapter and stable MAGE boundary",
            "type": "diagram",
            "outputs": output_paths("benchmark_adapter"),
            "sources": [
                relative_source(RESULTS_PATH),
                relative_source(PROJECT_ROOT / "docs" / "benchmark_adapter.md"),
                *failure_sources[4:],
            ],
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "输入 loader 与官方 evaluator 的替换边界，以及保持原样的 MAGE 多角色工作流。",
        },
        {
            "id": "rtl_full_2x2",
            "title": "Officially scored 2×2 comparison",
            "type": "chart",
            "outputs": output_paths("rtl_full_2x2"),
            "sources": full_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "四组全量官方 pass@1，柱内同时保留通过数与完整分母。",
        },
        {
            "id": "rtl_repeat_mean_std",
            "title": "Three-repeat mean and standard deviation",
            "type": "chart",
            "outputs": output_paths("rtl_repeat_mean_std"),
            "sources": full_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["repeat"]["pooled_total"] // 3,
                "RTLLM V2": rt["arms"]["A"]["repeat"]["pooled_total"] // 3,
                "repeats": 3,
            },
            "caption": "固定 10 题子集的三次重复均值、标准差与单次通过率散点。",
        },
        {
            "id": "rtl_effect_ci_forest",
            "title": "Full-benchmark paired effect intervals",
            "type": "chart",
            "outputs": output_paths("rtl_effect_ci_forest"),
            "sources": full_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "全量配对效应与 95% task bootstrap 区间，零线对应无方向差异。",
        },
        {
            "id": "rtl_repeat_effect_ci",
            "title": "Fixed-subset repeat effect intervals",
            "type": "chart",
            "outputs": output_paths("rtl_repeat_effect_ci"),
            "sources": full_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["repeat"]["pooled_total"] // 3,
                "RTLLM V2": rt["arms"]["A"]["repeat"]["pooled_total"] // 3,
                "repeats": 3,
            },
            "caption": "固定子集三次重复的 task-level 配对效应与 95% bootstrap 区间。",
        },
        {
            "id": "rtl_complexity_subset",
            "title": "Predefined complex-task subset",
            "type": "chart",
            "outputs": output_paths("rtl_complexity_subset"),
            "sources": full_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["full"]["complexity_subset"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["complexity_subset"]["total"],
            },
            "caption": "按题目规格 token 数预先选出的复杂任务子集，各组使用统一题集。",
        },
        {
            "id": "rtl_failure_codes",
            "title": "Official failure-code composition",
            "type": "chart",
            "outputs": output_paths("rtl_failure_codes"),
            "sources": failure_sources,
            "sample_size": {
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "各正式 run 的官方失败码构成，失败任务数与总分母可追溯。",
        },
        {
            "id": "rtl_repair_analysis",
            "title": "Round-1 and final RTL outcomes",
            "type": "chart",
            "outputs": output_paths("rtl_repair_analysis"),
            "sources": [relative_source(REPAIR_PATH)],
            "sample_size": {
                "full": {
                    "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                    "RTLLM V2": rt["arms"]["A"]["full"]["total"],
                },
                "repeat_total": {
                    "VerilogEval V2": ve["arms"]["A"]["repeat"]["pooled_total"],
                    "RTLLM V2": rt["arms"]["A"]["repeat"]["pooled_total"],
                },
            },
            "caption": "round-1 与最终 RTL 的官方判定迁移，涵盖修复恢复、持续失败与回归。",
        },
        {
            "id": "cad_official_metrics",
            "title": "CADTestBench official metrics",
            "type": "chart",
            "outputs": output_paths("cad_official_metrics"),
            "sources": cad_sources,
            "sample_size": {"CADTestBench detailed": cad_metrics["total_samples"]},
            "caption": "CADTestBench detailed 的 PR、RS 与无效样本比例。",
        },
        {
            "id": "cad_category_accuracy",
            "title": "CAD category accuracy",
            "type": "chart",
            "outputs": output_paths("cad_category_accuracy"),
            "sources": cad_sources,
            "sample_size": {
                "category_checks": sum(item["total"] for item in cad_categories.values())
            },
            "caption": "CAD 六类官方检查的通过数与总检查数，保留类别分母差异。",
        },
    ]

    plot_index = load_json(CAD_PLOT_INDEX_PATH)[0]["paths"]
    cad_assets = []
    for key, absolute in plot_index.items():
        path = resolve_recorded_path(absolute)
        if not path.exists():
            raise FileNotFoundError(path)
        asset_type = "interactive" if path.suffix.lower() == ".html" else "asset"
        cad_assets.append(
            {
                "id": f"cad_asset_{key}",
                "title": pretty_category(key),
                "type": asset_type,
                "outputs": [relative_source(path)],
                "sources": cad_sources,
                "sample_size": {
                    "CADTestBench detailed": cad_metrics["total_samples"]
                },
                "caption": "冻结 CAD 正式 run 的官方展示资产。",
            }
        )
    manifests.extend(cad_assets)
    manifests.append(
        {
            "id": "visualization_gallery",
            "title": "Visualization gallery",
            "type": "gallery",
            "outputs": [
                relative_source(VISUALIZATIONS / "index.html"),
            ],
            "sources": [
                relative_source(RESULTS_PATH),
                relative_source(REPAIR_PATH),
                *cad_sources,
            ],
            "sample_size": {
                "CADTestBench detailed": cad_metrics["total_samples"],
                "VerilogEval V2": ve["arms"]["A"]["full"]["total"],
                "RTLLM V2": rt["arms"]["A"]["full"]["total"],
            },
            "caption": "按实验阶段组织的响应式图册，集中提供 PNG、SVG、源数据与交互资产入口。",
        }
    )

    for item in manifests:
        item["files"] = [
            {
                "path": output,
                "sha256": sha256_file(PROJECT_ROOT / output),
            }
            for output in item["outputs"]
        ]

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "CAD to IC multi-agent reproduction and benchmark transfer",
        "visual_spec": {
            "document_canvas": [1800, 1000],
            "png_dpi": 200,
            "svg_text": "editable",
            "arm_colors": {arm: COLORS[arm] for arm in ARMS},
        },
        "figure_count": len(manifests) - 1,
        "asset_count": len(cad_assets),
        "figures": manifests,
    }


def rel_link(path: str | Path, from_dir: Path) -> str:
    target = PROJECT_ROOT / Path(path)
    return Path(os.path.relpath(target, from_dir)).as_posix()


def figure_card(
    *,
    figure_id: str,
    title: str,
    caption: str,
    image: str | Path,
    svg: str | Path | None,
    sources: list[str],
    eyebrow: str,
) -> str:
    image_rel = rel_link(image, VISUALIZATIONS)
    source_links = " ".join(
        f'<a href="{html.escape(rel_link(source, VISUALIZATIONS))}">{html.escape(Path(source).name)}</a>'
        for source in sources
    )
    svg_link = (
        f'<a class="ghost" href="{html.escape(rel_link(svg, VISUALIZATIONS))}">Open SVG</a>'
        if svg
        else ""
    )
    return f"""
    <article class="card" id="{html.escape(figure_id)}">
      <div class="eyebrow">{html.escape(eyebrow)}</div>
      <h3>{html.escape(title)}</h3>
      <a class="figure-link" href="{html.escape(image_rel)}">
        <img src="{html.escape(image_rel)}" alt="{html.escape(title)}" loading="lazy">
      </a>
      <p>{html.escape(caption)}</p>
      <div class="links">
        <a class="primary" href="{html.escape(image_rel)}">Open PNG</a>
        {svg_link}
      </div>
      <div class="sources"><span>Source data</span>{source_links}</div>
    </article>
    """


def asset_card(
    *,
    title: str,
    caption: str,
    asset_path: str,
    sources: list[str],
    interactive: bool = False,
) -> str:
    asset_rel = rel_link(asset_path, VISUALIZATIONS)
    source_links = " ".join(
        f'<a href="{html.escape(rel_link(source, VISUALIZATIONS))}">{html.escape(Path(source).name)}</a>'
        for source in sources
    )
    if interactive:
        preview = """
        <div class="interactive-preview">
          <span>3D</span>
          <strong>Interactive CAD model</strong>
          <p>Open the standalone viewer to rotate the frozen generated model.</p>
        </div>
        """
        action = f'<a class="primary" href="{html.escape(asset_rel)}">Launch viewer</a>'
    else:
        preview = (
            f'<a class="figure-link" href="{html.escape(asset_rel)}">'
            f'<img src="{html.escape(asset_rel)}" alt="{html.escape(title)}" loading="lazy"></a>'
        )
        action = f'<a class="primary" href="{html.escape(asset_rel)}">Open full image</a>'
    return f"""
    <article class="card">
      <div class="eyebrow">Frozen CAD run</div>
      <h3>{html.escape(title)}</h3>
      {preview}
      <p>{html.escape(caption)}</p>
      <div class="links">{action}</div>
      <div class="sources"><span>Source data</span>{source_links}</div>
    </article>
    """


def section_icon(kind: str) -> str:
    icons = {
        "system": (
            '<circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="6" r="2.2"/>'
            '<circle cx="12" cy="18" r="2.2"/><path d="M7.2 6h9.6M6.2 8l4.4 8"/>'
        ),
        "compare": (
            '<path d="M5 19V9M12 19V5M19 19v-7"/>'
            '<path d="M3 19h18"/><circle cx="5" cy="7" r="1.2"/>'
            '<circle cx="12" cy="3" r="1.2"/><circle cx="19" cy="10" r="1.2"/>'
        ),
        "evidence": (
            '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>'
            '<path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>'
        ),
        "diagnostics": (
            '<path d="M3 13h4l2-7 4 12 2-5h6"/>'
        ),
        "repair": (
            '<path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 1-2-5"/>'
        ),
        "cad": (
            '<path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"/>'
            '<path d="m3 7 9 5 9-5M12 12v10"/>'
        ),
    }
    return (
        '<span class="section-icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f"{icons[kind]}</svg></span>"
    )


def build_score_table(results: dict) -> str:
    arm_design = {
        "A": ("MAGE", "Assisted"),
        "B": ("MAGE", "Hidden"),
        "C": ("Single", "Hidden"),
        "D": ("Single", "Assisted"),
    }
    best = {
        benchmark: max(
            ARMS,
            key=lambda arm: results[benchmark]["arms"][arm]["full"]["pass_at_1"],
        )
        for benchmark in BENCHMARKS
    }
    rows = []
    for arm in ARMS:
        architecture, visibility = arm_design[arm]
        cells = []
        for benchmark in BENCHMARKS:
            full = results[benchmark]["arms"][arm]["full"]
            best_class = " best" if best[benchmark] == arm else ""
            cells.append(
                '<td class="num'
                f'{best_class}"><strong>{full["passed"]}/{full["total"]}</strong>'
                f"<small>{full['pass_at_1'] * 100:.1f}%</small></td>"
            )
        rows.append(
            f"""
            <tr>
              <td class="arm"><i style="background:{COLORS[arm]}"></i><strong>{arm}</strong></td>
              <td>{architecture}</td>
              <td><span class="visibility">{visibility}</span></td>
              {''.join(cells)}
            </tr>
            """
        )
    return f"""
    <div class="score-shell">
      <div class="score-head">
        <div><span>Core evidence snapshot</span><h3>四组官方结果总表</h3></div>
        <p>Complete denominators · official evaluator · pass@1</p>
      </div>
      <div class="score-scroll">
        <table class="score-table">
          <thead><tr><th>Arm</th><th>Architecture</th><th>Testbench</th><th>VerilogEval V2</th><th>RTLLM V2</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """


def build_gallery(
    results: dict,
    repair: dict,
    cad_metrics: dict,
    cad_categories: dict,
) -> Path:
    VISUALIZATIONS.mkdir(parents=True, exist_ok=True)
    ve = results["verilog_eval_v2"]
    rt = results["rtllm_v2"]
    ve_effect = ve["full_effects"]["testbench_effect_mage_A_minus_B"]
    rt_effect = rt["full_effects"]["testbench_effect_mage_A_minus_B"]
    score_table = build_score_table(results)
    ve_hidden = ve["full_effects"]["architecture_hidden_C_minus_B"]
    rt_hidden = rt["full_effects"]["architecture_hidden_C_minus_B"]
    source_results = relative_source(RESULTS_PATH)
    source_repair = relative_source(REPAIR_PATH)
    cad_sources = [
        relative_source(CAD_METRICS_PATH),
        relative_source(CAD_EVALUATIONS_PATH),
        relative_source(CAD_RUN / "protocol.json"),
    ]
    failure_sources = [
        relative_source(FULL_RESULT_PATHS[(benchmark, arm)])
        for benchmark in BENCHMARKS
        for arm in ARMS
    ]
    effect_cards = "".join(
        [
            figure_card(
                figure_id="full-effect-ci",
                title="全量配对效应区间",
                caption="森林图展示架构与 testbench 可见性的配对效应，实心点对应区间离开零线。",
                image=FIGURES / "rtl_effect_ci_forest.png",
                svg=FIGURES / "rtl_effect_ci_forest.svg",
                sources=[source_results],
                eyebrow="Full-benchmark inference",
            ),
            figure_card(
                figure_id="repeat-effect-ci",
                title="固定子集重复效应区间",
                caption="三次重复按题目聚合后重新估计配对效应，区间宽度反映子集规模与模型波动。",
                image=FIGURES / "rtl_repeat_effect_ci.png",
                svg=FIGURES / "rtl_repeat_effect_ci.svg",
                sources=[source_results],
                eyebrow="Repeat inference",
            ),
        ]
    )
    diagrams = "".join(
        [
            figure_card(
                figure_id="project-architecture",
                title="总体实验架构",
                caption="CAD 与 RTL 输入沿两条生成链路进入官方评测，最终汇聚到统一 RunRecord 与四组对照层。",
                image=FIGURES / "project_architecture.png",
                svg=FIGURES / "project_architecture.svg",
                sources=[
                    source_results,
                    relative_source(CAD_METRICS_PATH),
                    relative_source(CAD_EVALUATIONS_PATH),
                ],
                eyebrow="System view",
            ),
            figure_card(
                figure_id="benchmark-adapter",
                title="跨基准适配边界",
                caption="VerilogEval 与 RTLLM 各自替换 loader、模块名映射与官方 evaluator，MAGE 协作关系保持原样。",
                image=FIGURES / "benchmark_adapter.png",
                svg=FIGURES / "benchmark_adapter.svg",
                sources=[source_results, "docs/benchmark_adapter.md"],
                eyebrow="Transfer view",
            ),
        ]
    )
    rtl_main = "".join(
        [
            figure_card(
                figure_id="full-2x2",
                title="完整 2×2 官方对照",
                caption="A/B/C/D 四组全量 pass@1 来自各基准官方 evaluator，分母保留原始全部题目。",
                image=FIGURES / "rtl_full_2x2.png",
                svg=FIGURES / "rtl_full_2x2.svg",
                sources=[source_results],
                eyebrow="Full benchmark",
            ),
            figure_card(
                figure_id="repeat-stability",
                title="三次重复稳定性",
                caption="固定 10 题子集的三次重复均值与总体标准差，空心点保留每次独立运行结果。",
                image=FIGURES / "rtl_repeat_mean_std.png",
                svg=FIGURES / "rtl_repeat_mean_std.svg",
                sources=[source_results, relative_source(SELECTION_PATH)],
                eyebrow="Frozen subset",
            ),
        ]
    )
    diagnostics = "".join(
        [
            figure_card(
                figure_id="complexity-subset",
                title="复杂任务子集",
                caption="题目在正式评分前按规格 token 数冻结为前 50%，图表沿用统一子集与官方判定。",
                image=FIGURES / "rtl_complexity_subset.png",
                svg=FIGURES / "rtl_complexity_subset.svg",
                sources=[source_results, relative_source(SELECTION_PATH)],
                eyebrow="Secondary analysis",
            ),
            figure_card(
                figure_id="failure-codes",
                title="官方失败码构成",
                caption="失败任务按官方 code 或仿真状态分类，柱末保留每个 arm 的失败总数。",
                image=FIGURES / "rtl_failure_codes.png",
                svg=FIGURES / "rtl_failure_codes.svg",
                sources=failure_sources,
                eyebrow="Failure audit",
            ),
        ]
    )
    cad_main = "".join(
        [
            figure_card(
                figure_id="cad-metrics",
                title="CAD 官方总指标",
                caption=f"CADTestBench detailed 分区共 {cad_metrics['total_samples']} 题，PR、RS 与无效样本比例读取自正式 CSV。",
                image=FIGURES / "cad_official_metrics.png",
                svg=FIGURES / "cad_official_metrics.svg",
                sources=cad_sources,
                eyebrow="CAD baseline",
            ),
            figure_card(
                figure_id="cad-categories",
                title="CAD 类别准确率",
                caption=f"六类官方检查共 {sum(item['total'] for item in cad_categories.values())} 项，右侧标签保留每类 passed / total。",
                image=FIGURES / "cad_category_accuracy.png",
                svg=FIGURES / "cad_category_accuracy.svg",
                sources=cad_sources,
                eyebrow="CAD diagnostics",
            ),
        ]
    )
    plot_index = load_json(CAD_PLOT_INDEX_PATH)[0]["paths"]
    cad_assets = []
    cad_archive = []
    for key, absolute in plot_index.items():
        path = resolve_recorded_path(absolute)
        title = {
            "cad_gallery": "Generated STL Gallery",
            "interactive_html": "Rotatable CAD Viewer",
        }.get(key, pretty_category(key))
        if key not in {"cad_gallery", "interactive_html"}:
            cad_archive.append(
                f'<a href="{html.escape(rel_link(relative_source(path), VISUALIZATIONS))}">'
                f'<span>{html.escape(title)}</span>'
                f'<small>{html.escape(path.name)}</small></a>'
            )
            continue
        caption = (
            "正式 CAD run 的生成实体总览，使用实际导出的 STL 网格。"
            if key == "cad_gallery"
            else "正式 CAD run 的可旋转模型入口，用于答辩现场查看生成实体。"
        )
        cad_assets.append(
            asset_card(
                title=title,
                caption=caption,
                asset_path=relative_source(path),
                sources=cad_sources,
                interactive=path.suffix.lower() == ".html",
            )
        )

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAD2IC 芯桥 · 实验可视化总览</title>
  <style>
    :root {{
      --ink: #0f172a;
      --muted: #475569;
      --border: #dbe3ee;
      --paper: #ffffff;
      --soft: #f6f8fb;
      --blue: #2f6bff;
      --teal: #00a6a6;
      --amber: #f59e0b;
      --violet: #8b5cf6;
      --positive: #2e9d66;
      --negative: #c2413a;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 8% 0%, rgba(47,107,255,.12), transparent 30rem),
        radial-gradient(circle at 92% 8%, rgba(0,166,166,.10), transparent 28rem),
        #f7f9fc;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ width: min(1280px, calc(100% - 40px)); margin: 0 auto; }}
    header {{ padding: 64px 0 38px; }}
    .kicker {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 11px; border: 1px solid #c7d7fe; border-radius: 999px;
      color: #1e4fd7; background: #eff6ff; font-size: 12px; font-weight: 700;
      letter-spacing: .08em; text-transform: uppercase;
    }}
    h1 {{ font-size: clamp(38px, 6vw, 76px); line-height: 1.02; margin: 18px 0 16px; letter-spacing: -.045em; }}
    .lead {{ max-width: 850px; color: var(--muted); font-size: clamp(17px, 2vw, 21px); }}
    .hero-layout {{
      display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(300px, .82fr);
      gap: 16px; margin-top: 30px; align-items: stretch;
    }}
    .summary {{
      display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px; margin-top: 0;
    }}
    .metric {{
      padding: 20px 22px; background: rgba(255,255,255,.86); border: 1px solid var(--border);
      border-radius: 18px; box-shadow: 0 10px 32px rgba(15,23,42,.05);
    }}
    .metric span {{ color: var(--muted); font-size: 13px; font-weight: 650; }}
    .metric strong {{ display: block; margin: 4px 0 0; font-size: 28px; letter-spacing: -.03em; }}
    .metric small {{ color: var(--muted); font-size: 12px; }}
    .hero-evidence {{
      display: flex; flex-direction: column; justify-content: space-between;
      padding: 22px; border: 1px solid #25324a; border-radius: 18px;
      background:
        radial-gradient(circle at 100% 0%, rgba(46,157,102,.28), transparent 14rem),
        #111827;
      color: #f8fafc; box-shadow: 0 16px 40px rgba(15,23,42,.16);
    }}
    .hero-evidence > span {{ color: #86efac; font-size: 11px; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }}
    .hero-evidence strong {{ display: block; margin: 8px 0 2px; color: #fff; font-size: 36px; line-height: 1; letter-spacing: -.04em; }}
    .hero-evidence small {{ display: block; color: #cbd5e1; font-size: 11px; }}
    .hero-evidence p {{ margin: 12px 0 0; color: #cbd5e1; font-size: 12px; }}
    nav {{
      position: sticky; top: 0; z-index: 20; background: rgba(247,249,252,.86);
      backdrop-filter: blur(14px); border-block: 1px solid rgba(219,227,238,.85);
    }}
    nav .wrap {{ display: flex; gap: 22px; overflow-x: auto; padding: 13px 0; white-space: nowrap; }}
    nav a {{ color: var(--muted); font-size: 13px; font-weight: 650; }}
    section {{ padding: 54px 0 12px; scroll-margin-top: 54px; }}
    .section-head {{ display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 22px; }}
    h2 {{ font-size: clamp(27px, 4vw, 42px); line-height: 1.1; margin: 0; letter-spacing: -.035em; }}
    .section-title {{ display: flex; align-items: center; gap: 11px; }}
    .section-icon {{
      width: 38px; height: 38px; display: inline-grid; place-items: center; flex: 0 0 auto;
      border: 1px solid #d6e2fb; border-radius: 12px; color: #245be8;
      background: linear-gradient(145deg, #fff, #eef4ff); box-shadow: 0 5px 14px rgba(47,107,255,.08);
    }}
    .section-icon svg {{ width: 20px; height: 20px; }}
    .section-head p {{ max-width: 560px; margin: 0; color: var(--muted); font-size: 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .grid.three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .single-feature {{ max-width: 1040px; margin: 0 auto; }}
    .card {{
      min-width: 0; background: var(--paper); border: 1px solid var(--border);
      border-radius: 20px; padding: 20px; box-shadow: 0 10px 32px rgba(15,23,42,.055);
    }}
    .eyebrow {{ color: var(--blue); font-size: 11px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }}
    .card h3 {{ font-size: 20px; margin: 6px 0 13px; letter-spacing: -.02em; }}
    .figure-link {{ display: block; background: #fff; border: 1px solid #edf1f6; border-radius: 13px; overflow: hidden; }}
    .figure-link img {{ display: block; width: 100%; height: auto; }}
    .card p {{ color: var(--muted); font-size: 13px; margin: 13px 0; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .links a {{ display: inline-flex; align-items: center; padding: 7px 10px; border-radius: 9px; font-size: 12px; font-weight: 700; }}
    .primary {{ color: white; background: var(--ink); }}
    .primary:hover {{ text-decoration: none; background: #1e293b; }}
    .ghost {{ color: var(--muted); border: 1px solid var(--border); background: var(--soft); }}
    .sources {{ margin-top: 12px; padding-top: 11px; border-top: 1px solid #eef2f7; display: flex; flex-wrap: wrap; gap: 5px 10px; font-size: 10.5px; }}
    .sources span {{ color: #64748b; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }}
    .sources a {{ color: #64748b; overflow-wrap: anywhere; }}
    .finding {{
      margin: 24px 0 4px; padding: 22px 24px; border-left: 4px solid var(--positive);
      border-radius: 0 15px 15px 0; background: #f0fdf4; color: #14532d; font-size: 15px;
    }}
    .finding strong {{ color: #166534; }}
    .score-shell {{
      margin-bottom: 20px; overflow: hidden; border: 1px solid var(--border);
      border-radius: 18px; background: #fff; box-shadow: 0 10px 32px rgba(15,23,42,.05);
    }}
    .score-head {{
      display: flex; justify-content: space-between; align-items: end; gap: 18px;
      padding: 17px 20px 14px; border-bottom: 1px solid #edf1f6;
      background: linear-gradient(90deg, #f8fbff, #fff);
    }}
    .score-head span {{ color: var(--blue); font-size: 10px; font-weight: 850; letter-spacing: .1em; text-transform: uppercase; }}
    .score-head h3 {{ margin: 3px 0 0; font-size: 19px; letter-spacing: -.02em; }}
    .score-head p {{ margin: 0; color: #718096; font-size: 11px; }}
    .score-scroll {{ overflow-x: auto; }}
    .score-table {{ width: 100%; min-width: 740px; border-collapse: collapse; font-size: 13px; }}
    .score-table th {{ padding: 11px 16px; color: #718096; background: #fbfcfe; font-size: 10px; font-weight: 800; letter-spacing: .055em; text-transform: uppercase; text-align: left; }}
    .score-table td {{ padding: 13px 16px; border-top: 1px solid #eef2f7; white-space: nowrap; }}
    .score-table tbody tr:hover {{ background: #f8fbff; }}
    .score-table .arm {{ display: flex; align-items: center; gap: 8px; }}
    .score-table .arm i {{ width: 8px; height: 8px; border-radius: 50%; }}
    .score-table .num {{ text-align: right; }}
    .score-table .num strong {{ display: block; font-size: 14px; }}
    .score-table .num small {{ display: block; margin-top: 1px; color: #7b8aa0; font-size: 10px; }}
    .score-table td.best {{ background: #effdf5; box-shadow: inset 3px 0 0 var(--positive); }}
    .visibility {{ display: inline-block; padding: 3px 7px; border-radius: 99px; color: #52637a; background: #f1f5f9; font-size: 10px; font-weight: 750; }}
    .interactive-preview {{
      min-height: 300px; display: grid; place-content: center; text-align: center;
      border-radius: 13px; background:
        linear-gradient(135deg, rgba(47,107,255,.15), rgba(0,166,166,.12)),
        repeating-linear-gradient(0deg, #fff, #fff 19px, #edf2f7 20px),
        repeating-linear-gradient(90deg, #fff, #fff 19px, #edf2f7 20px);
      border: 1px solid #dbe3ee;
    }}
    .interactive-preview span {{ font-size: 66px; line-height: 1; font-weight: 900; color: #1e4fd7; letter-spacing: -.08em; }}
    .interactive-preview strong {{ margin-top: 10px; }}
    .interactive-preview p {{ max-width: 250px; margin: 4px auto 0; }}
    .archive-panel {{
      margin-top: 18px; padding: 18px 20px; border: 1px solid var(--border);
      border-radius: 16px; background: rgba(255,255,255,.72);
    }}
    .archive-panel summary {{ cursor: pointer; font-size: 13px; font-weight: 750; color: var(--muted); }}
    .archive-list {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 15px; }}
    .archive-list a {{
      display: flex; flex-direction: column; gap: 2px; padding: 11px 12px;
      border: 1px solid #e6ebf2; border-radius: 11px; background: #fff;
    }}
    .archive-list a:hover {{ text-decoration: none; border-color: #b9cdf9; }}
    .archive-list span {{ color: var(--ink); font-size: 12px; font-weight: 700; }}
    .archive-list small {{ color: #8190a5; font-size: 10px; overflow-wrap: anywhere; }}
    footer {{ padding: 52px 0 64px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 1080px) {{
      .hero-layout {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 900px) {{
      .summary, .grid, .grid.three, .archive-list {{ grid-template-columns: 1fr; }}
      .section-head {{ display: block; }}
      .section-head p {{ margin-top: 10px; }}
      .score-head {{ display: block; }}
      .score-head p {{ margin-top: 6px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      nav {{ display: none; }}
      header, section {{ break-inside: avoid; }}
      .card, .metric, .score-shell, .archive-panel {{ box-shadow: none; }}
      .links, .sources {{ display: none; }}
      details > :not(summary) {{ display: block; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <div class="kicker">Plan 4 · Frozen results</div>
      <h1>CAD2IC 芯桥</h1>
      <p class="lead">多智能体 RTL 生成与跨基准评测。从 CAD 基线到 VerilogEval 与 RTLLM 跨基准迁移，再到单 Agent 对照与修复审计。全部图表读取冻结结果，统一呈现官方评分口径、效应方向与证据边界。</p>
      <div class="hero-layout">
        <div class="summary">
          <div class="metric"><span>CADTestBench detailed</span><strong>{cad_metrics['pr']:.1f}% PR</strong><small>{cad_metrics['total_samples']} 题 · RS {cad_metrics['rs']:.1f}%</small></div>
          <div class="metric"><span>VerilogEval V2</span><strong>{ve['arms']['A']['full']['passed']}/{ve['arms']['A']['full']['total']}</strong><small>MAGE-assisted · {ve['arms']['A']['full']['pass_at_1']*100:.1f}% pass@1</small></div>
          <div class="metric"><span>RTLLM V2</span><strong>{rt['arms']['A']['full']['passed']}/{rt['arms']['A']['full']['total']}</strong><small>MAGE-assisted · {rt['arms']['A']['full']['pass_at_1']*100:.1f}% pass@1</small></div>
        </div>
        <aside class="hero-evidence">
          <div>
            <span>Key finding</span>
            <strong>{ve_effect['mean_difference']*100:+.1f} pp</strong>
            <small>MAGE vs Single · VerilogEval assisted</small>
            <p>95% CI [{ve_effect['ci95_low']*100:+.1f}, {ve_effect['ci95_high']*100:+.1f}] · paired official pass@1</p>
          </div>
        </aside>
      </div>
    </div>
  </header>
  <nav><div class="wrap">
    <a href="#system">系统结构</a>
    <a href="#rtl-main">全量与稳定性</a>
    <a href="#rtl-effects">效应区间</a>
    <a href="#diagnostics">复杂题与失败分析</a>
    <a href="#repair">修复审计</a>
    <a href="#cad">CAD 可视化</a>
  </div></nav>
  <main class="wrap">
    <section id="system">
      <div class="section-head"><div><div class="section-title">{section_icon('system')}<h2>系统与迁移结构</h2></div></div><p>两张结构图给出完整实验链路与 adapter 替换边界，便于答辩时快速建立全局认识。</p></div>
      <div class="grid">{diagrams}</div>
    </section>
    <section id="rtl-main">
      <div class="section-head"><div><div class="section-title">{section_icon('compare')}<h2>全量对照与稳定性</h2></div></div><p>主图直接使用各官方 evaluator 的最终 RTL 结果，重复图保留三次运行的离散程度。</p></div>
      {score_table}
      <div class="grid">{rtl_main}</div>
      <div class="finding"><strong>核心正向证据：</strong>VerilogEval-assisted 中，MAGE 与 Single 的配对差值为 {ve_effect['mean_difference']*100:+.1f} 个百分点，95% bootstrap 区间为 [{ve_effect['ci95_low']*100:+.1f}, {ve_effect['ci95_high']*100:+.1f}]。RTLLM 对应差值为 {rt_effect['mean_difference']*100:+.1f} 个百分点，区间 [{rt_effect['ci95_low']*100:+.1f}, {rt_effect['ci95_high']*100:+.1f}]。hidden 设置下 VerilogEval 的 C−B 为 {ve_hidden['mean_difference']*100:+.1f} 个百分点，RTLLM 的 C−B 为 {rt_hidden['mean_difference']*100:+.1f} 个百分点。项目结论保持“有条件有效”的边界。</div>
    </section>
    <section id="rtl-effects">
      <div class="section-head"><div><div class="section-title">{section_icon('evidence')}<h2>效应与方向</h2></div></div><p>森林图同时呈现点估计与区间。正值偏向 second arm，负值偏向 first arm，空心点表示区间跨过零线。</p></div>
      <div class="grid">{effect_cards}</div>
    </section>
    <section id="diagnostics">
      <div class="section-head"><div><div class="section-title">{section_icon('diagnostics')}<h2>复杂题与失败码</h2></div></div><p>诊断图区分预设复杂子集与官方失败构成，保留独立分析口径。</p></div>
      <div class="grid">{diagnostics}</div>
    </section>
    <section id="repair">
      <div class="section-head"><div><div class="section-title">{section_icon('repair')}<h2>修复贡献审计</h2></div></div><p>同一官方 evaluator 分别检查 round-1 与最终 RTL，修复收益和回归均保留。</p></div>
      <div class="single-feature">{figure_card(figure_id='repair-detail', title='C/D 修复结果迁移', caption='全量与三次重复合计同时展示，颜色对应稳定通过、修复恢复、持续失败与回归。', image=FIGURES / 'rtl_repair_analysis.png', svg=FIGURES / 'rtl_repair_analysis.svg', sources=[source_repair], eyebrow='Official outcome audit')}</div>
    </section>
    <section id="cad">
      <div class="section-head"><div><div class="section-title">{section_icon('cad')}<h2>CAD 官方评测</h2></div></div><p>正式 detailed run 的总指标、六类检查、生成实体图册和可旋转模型集中索引。</p></div>
      <div class="grid">{cad_main}</div>
      <div class="grid" style="margin-top:18px">{''.join(cad_assets)}</div>
      <details class="archive-panel">
        <summary>展开 CAD 原始诊断档案 · {len(cad_archive)} 个文件</summary>
        <div class="archive-list">{''.join(cad_archive)}</div>
      </details>
    </section>
  </main>
  <footer><div class="wrap">数据冻结日期 2026-11-10 · 图表由 <code>integration/plan4_visualize.py</code> 生成 · PNG 200 dpi · SVG 保留可编辑文字 · 源数据索引见 <a href="../figures/manifest.json">manifest.json</a></div></footer>
</body>
</html>
"""
    output = VISUALIZATIONS / "index.html"
    output.write_text(html_text, encoding="utf-8")
    return output


def main() -> None:
    configure_matplotlib()
    results = load_json(RESULTS_PATH)
    selection = load_json(SELECTION_PATH)
    repair = load_json(REPAIR_PATH)
    cad_metrics = load_cad_metrics()
    cad_categories = load_cad_categories()

    if set(selection["complexity_subset"]) != set(BENCHMARKS):
        raise ValueError("Complexity selection benchmark keys differ from chart inputs")

    generated = {}
    generated["rtl_full_2x2"] = build_full_2x2(results)
    generated["rtl_repeat_mean_std"] = build_repeat_mean_std(results)
    generated["rtl_effect_ci_forest"] = build_full_effect_ci(results)
    generated["rtl_repeat_effect_ci"] = build_repeat_effect_ci(results)
    generated["rtl_complexity_subset"] = build_complexity_subset(results)
    generated["rtl_failure_codes"] = build_failure_codes(results)
    generated["rtl_repair_analysis"] = build_repair_analysis(repair)
    generated["cad_official_metrics"] = build_cad_official_metrics(cad_metrics)
    generated["cad_category_accuracy"] = build_cad_category_accuracy(cad_categories)
    generated["project_architecture"] = build_project_architecture(results)
    generated["benchmark_adapter"] = build_benchmark_adapter(results)

    gallery = build_gallery(results, repair, cad_metrics, cad_categories)
    manifest = build_manifest(results, repair, cad_metrics, cad_categories)
    manifest_path = FIGURES / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Generated {len(generated)} chart/diagram stems in {FIGURES}")
    print(f"Gallery: {gallery}")
    print(f"Manifest: {manifest_path}")
    for stem, outputs in generated.items():
        print(f"  {stem}: {outputs['png'].stat().st_size:,} B PNG")


if __name__ == "__main__":
    main()
