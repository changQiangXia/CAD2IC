"""Automated checks for Plan 4 visualization assets and provenance."""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from PIL import Image

import plan4_visualize as p4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES = PROJECT_ROOT / "docs" / "figures"
GALLERY = PROJECT_ROOT / "docs" / "visualizations" / "index.html"
MANIFEST = FIGURES / "manifest.json"
EXPECTED_STEMS = {
    "rtl_full_2x2",
    "rtl_repeat_mean_std",
    "rtl_effect_ci_forest",
    "rtl_repeat_effect_ci",
    "rtl_complexity_subset",
    "rtl_failure_codes",
    "rtl_repair_analysis",
    "cad_official_metrics",
    "cad_category_accuracy",
    "project_architecture",
    "benchmark_adapter",
}


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        for attribute in ("src", "href"):
            if values.get(attribute):
                self.references.append(values[attribute])


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_png_files_are_complete_documents() -> None:
    for stem in EXPECTED_STEMS:
        path = FIGURES / f"{stem}.png"
        assert path.stat().st_size > 50_000
        with Image.open(path) as image:
            assert image.size == (1800, 1000)
            assert image.format == "PNG"
            image.verify()


def test_svg_files_are_well_formed_and_keep_editable_text() -> None:
    for stem in EXPECTED_STEMS:
        path = FIGURES / f"{stem}.svg"
        root = ET.parse(path).getroot()
        assert root.tag.endswith("svg")
        assert path.stat().st_size > 5_000
        text_nodes = [node for node in root.iter() if node.tag.endswith("text")]
        assert text_nodes


def test_manifest_has_unique_ids_and_valid_hashes() -> None:
    manifest = load_manifest()
    entries = manifest["figures"]
    ids = [item["id"] for item in entries]
    assert len(ids) == len(set(ids))
    assert manifest["figure_count"] == len(entries) - 1
    assert manifest["asset_count"] == 10
    for item in entries:
        assert item["sources"]
        assert item["outputs"]
        assert item["caption"]
        for source in item["sources"]:
            assert (PROJECT_ROOT / source).exists(), source
        for file_record in item["files"]:
            path = PROJECT_ROOT / file_record["path"]
            assert path.exists(), path
            assert sha256(path) == file_record["sha256"]


def test_gallery_local_links_resolve() -> None:
    parser = ReferenceParser()
    parser.feed(GALLERY.read_text(encoding="utf-8"))
    missing = []
    for reference in parser.references:
        if reference.startswith(("#", "http:", "https:", "mailto:")):
            continue
        path = unquote(urlsplit(reference).path)
        target = (GALLERY.parent / path).resolve()
        if not target.exists():
            missing.append(reference)
    assert missing == []
    assert {
        "system",
        "rtl-main",
        "rtl-effects",
        "diagnostics",
        "repair",
        "cad",
    }.issubset(parser.ids)


def test_gallery_visual_hierarchy_is_refined() -> None:
    text = GALLERY.read_text(encoding="utf-8")
    assert text.count('id="full-effect-ci"') == 1
    assert text.count('id="repeat-effect-ci"') == 1
    assert text.count('id="repair-detail"') == 1
    assert text.count('<span class="section-icon"') == 6
    assert 'class="score-shell"' in text
    assert 'class="hero-evidence"' in text
    assert '<details class="archive-panel">' in text
    assert "Cad Gallery" not in text
    assert "Interactive Html" not in text
    assert "不" not in text
    assert "而" not in text


def test_failure_counts_match_official_result_files() -> None:
    results = p4.load_json(p4.RESULTS_PATH)
    counts = p4.load_failure_counts()
    for benchmark in p4.BENCHMARKS:
        for arm in p4.ARMS:
            full = results[benchmark]["arms"][arm]["full"]
            failed = full["total"] - full["passed"]
            assert sum(counts[benchmark][arm].values()) == failed


def test_repair_aggregates_match_pair_task_counts() -> None:
    repair = p4.load_json(p4.REPAIR_PATH)
    for benchmark in p4.BENCHMARKS:
        for arm in ("C", "D"):
            aggregate = p4.aggregate_repair_pairs(repair, benchmark, arm)
            full = aggregate[f"{arm} full"]
            repeats = aggregate[f"{arm} repeat total"]
            assert sum(full[outcome] for outcome in p4.OUTCOME_ORDER) == full[
                "task_count"
            ]
            assert sum(repeats[outcome] for outcome in p4.OUTCOME_ORDER) == repeats[
                "task_count"
            ]
            assert repeats["task_count"] == 30


def test_cad_metrics_match_official_evaluations() -> None:
    metrics = p4.load_cad_metrics()
    evaluations = p4.load_json(p4.CAD_EVALUATIONS_PATH)
    cadtest = evaluations[0]["summary"]["aggregate_metrics"]["cadtest"]
    assert metrics["total_samples"] == cadtest["total_samples"]
    assert metrics["pr"] == cadtest["pr"]
    assert metrics["rs"] == cadtest["rs"]
    assert (
        metrics["invalid_sample_percentage"]
        == cadtest["invalid_sample_percentage"]
    )
    categories = p4.load_cad_categories()
    assert categories == cadtest["category_accuracy"]


def test_recorded_cad_paths_resolve_inside_repository() -> None:
    plot_index = p4.load_json(p4.CAD_PLOT_INDEX_PATH)[0]["paths"]
    for value in plot_index.values():
        path = p4.resolve_recorded_path(value).resolve()
        assert path.exists(), value
        path.relative_to(PROJECT_ROOT.resolve())


def test_svg_data_labels_match_machine_readable_results() -> None:
    results = p4.load_json(p4.RESULTS_PATH)
    full_text = (FIGURES / "rtl_full_2x2.svg").read_text(encoding="utf-8")
    for benchmark in p4.BENCHMARKS:
        for arm in p4.ARMS:
            full = results[benchmark]["arms"][arm]["full"]
            assert f"{full['passed']}/{full['total']}" in full_text
            assert f"{full['pass_at_1'] * 100:.1f}%" in full_text

    forest_text = (FIGURES / "rtl_effect_ci_forest.svg").read_text(
        encoding="utf-8"
    )
    for benchmark in p4.BENCHMARKS:
        for key in p4.EFFECT_KEYS:
            effect = results[benchmark]["full_effects"][key]
            label = (
                f"{effect['mean_difference'] * 100:+.1f} "
                f"[{effect['ci95_low'] * 100:+.1f}, "
                f"{effect['ci95_high'] * 100:+.1f}]"
            )
            assert label in forest_text


def test_active_documents_use_required_wording() -> None:
    documents = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "PROJECT_FINAL_REPORT.md",
        PROJECT_ROOT / "plan4.md",
        PROJECT_ROOT / "docs" / "architecture.md",
        PROJECT_ROOT / "docs" / "benchmark_adapter.md",
        PROJECT_ROOT / "docs" / "results_and_failures.md",
        PROJECT_ROOT / "docs" / "presentation_3min.md",
    ]
    for document in documents:
        text = document.read_text(encoding="utf-8")
        assert "不" not in text, document
        assert "而" not in text, document


def test_documents_reference_visualization_entry_points() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    report = (PROJECT_ROOT / "PROJECT_FINAL_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "docs/visualizations/index.html" in readme
    assert "docs/figures/manifest.json" in readme
    assert "docs/visualizations/index.html" in report
    assert "docs/figures/manifest.json" in report
