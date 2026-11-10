"""Plots for the pinned CADTestBench EvaluationRunner JSON format.

These functions only READ official results; they never execute CAD code, alter
CADTests, or calculate replacement PR/RS scores. All plot calls require a
``run_kind`` and ``title`` to identify the evaluated run.
Optional dependencies (trimesh, Plotly) are imported only by mesh functions.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

CATEGORIES = [
    'topology_checks', 'solid_shell_validity', 'dimensions_ratios',
    'volumetric_checks', 'spatial_arrangement', 'geometry_types',
]
CATEGORY_LABELS = {
    'topology_checks': 'Topology', 'solid_shell_validity': 'Solid / shell',
    'dimensions_ratios': 'Dimensions / ratios', 'volumetric_checks': 'Volume',
    'spatial_arrangement': 'Spatial arrangement', 'geometry_types': 'Geometry types',
}
BLUE, TEAL, RED = '#3274A1', '#269C93', '#C65B55'


def _label(*, run_kind: str, title: str) -> str:
    if not str(run_kind).strip() or not str(title).strip():
        raise ValueError('run_kind and title must be non-empty provenance labels.')
    return f'{run_kind}\n{title}'


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def _percent(value, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f'{name} should be an official percentage in [0, 100].')
    return value


def load_official_run(eval_dir) -> dict:
    """Read evaluation_summary.json and samples/*/summary.json without scoring.

    Returns official ``summary``/``aggregate`` plus three normalized DataFrames:
    ``samples``, ``categories`` and ``sample_categories``. The last frame's
    ``test_pass_rate`` is a descriptive passed/total percentage, NOT official PR.
    Missing category observations remain absent, never converted to failures.
    """
    root = Path(eval_dir)
    if root.name == 'evaluation_summary.json':
        root = root.parent
    summary = json.loads((root / 'evaluation_summary.json').read_text(encoding='utf-8'))
    aggregate = summary['aggregate_metrics']['cadtest']
    samples, sample_categories = [], []
    for path in sorted((root / 'samples').glob('*/summary.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        metric = (doc.get('metrics') or {}).get('cadtest') or {}
        meta = metric.get('metadata') or {}
        s = meta.get('summary') or {}
        sid = str(doc.get('sample_id', path.parent.name))
        stl = path.parent / (doc.get('generated_stl') or 'generated.stl')
        samples.append({
            'sample_id': sid, 'cadtest_pass_rate': s.get('pass_rate', np.nan),
            'rs': s.get('rs', np.nan), 'passed': s.get('passed', np.nan),
            'total_cadtests': s.get('total_cadtests', np.nan),
            'model_compile_error': s.get('model_compile_error'),
            'evaluation_error': s.get('evaluation_error'),
            'error': doc.get('error_message') or metric.get('error'),
            'generated_stl': str(stl) if stl.is_file() else None,
        })
        for cat, counts in (s.get('category_breakdown') or {}).items():
            total, passed = int(counts['total']), int(counts['passed'])
            sample_categories.append({
                'sample_id': sid, 'category': cat, 'passed': passed, 'total': total,
                'test_pass_rate': passed / total * 100 if total else np.nan,
            })
    category_rows = [dict(category=cat, **values)
                     for cat, values in aggregate.get('category_accuracy', {}).items()]
    return {
        'root': root, 'summary': summary, 'aggregate': aggregate,
        'samples': pd.DataFrame(samples),
        'categories': pd.DataFrame(category_rows),
        'sample_categories': pd.DataFrame(sample_categories),
    }


def plot_official_metrics(eval_dir, *, run_kind: str, title: str, out_dir,
                          heatmap_page_size: int = 35) -> dict:
    """Save official PR/RS/invalid, category accuracy and paged heatmap PNGs.

    PR/RS/invalid and category accuracy are copied directly from the official
    aggregate JSON. Heatmap cells only divide per-sample category counts.
    The function returns {descriptive_name: Path}, suitable for notebook display.
    """
    heading = _label(run_kind=run_kind, title=title)
    if heatmap_page_size < 1:
        raise ValueError('heatmap_page_size must be positive.')
    data, out = load_official_run(eval_dir), Path(out_dir)
    agg = data['aggregate']
    values = [_percent(agg[k], k) for k in ['pr', 'rs', 'invalid_sample_percentage']]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    bars = ax.bar(['PR\nAll CADTests pass', 'RS\nRequirement satisfaction',
                   'Invalid samples'], values, color=[BLUE, TEAL, RED], width=.58)
    ax.bar_label(bars, labels=[f'{v:.2f}%' for v in values], padding=6, fontsize=12)
    ax.set(ylim=(0, 115), ylabel='Percent (%)')
    ax.set_title(heading, pad=18)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.18)
    ax.set_axisbelow(True)
    fig.text(.5, .015,
             f"Official aggregate | n={agg['total_samples']} | "
             f"CADTests={agg['total_cadtests']} | lower invalid is better", ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    paths = {'official_metrics': _save(fig, out / 'official_metrics.png')}

    cats = data['categories']
    if not cats.empty:
        order = CATEGORIES + sorted(set(cats['category']) - set(CATEGORIES))
        lookup = cats.set_index('category')
        vals = [float(lookup.loc[c, 'accuracy']) if c in lookup.index else np.nan for c in order]
        fig, ax = plt.subplots(figsize=(10, 6.2))
        y = np.arange(len(order))
        ax.barh(y, [0 if not np.isfinite(v) else v for v in vals], color=BLUE, height=.65)
        for i, (cat, value) in enumerate(zip(order, vals)):
            if np.isfinite(value):
                _percent(value, f'category_accuracy.{cat}')
                row = lookup.loc[cat]
                msg = f"{value:.1f}%  ({int(row['passed'])}/{int(row['total'])})"
                ax.text(min(value + 1, 102), i, msg, va='center', fontsize=9)
            else:
                ax.text(1, i, 'N/A: no tests in this run', va='center', color='#777777', fontsize=9)
        ax.set(yticks=y, yticklabels=[CATEGORY_LABELS.get(c, c) for c in order],
               xlim=(0, 136), xlabel='CADTest pass rate (%) - official category_accuracy')
        ax.set_xticks([0, 20, 40, 60, 80, 100])
        ax.invert_yaxis()
        ax.set_title(heading + '\nCategory-level CADTest pass rate', pad=16)
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='x', alpha=.15)
        ax.set_axisbelow(True)
        fig.tight_layout()
        paths['category_accuracy'] = _save(fig, out / 'category_accuracy.png')

    rows = data['sample_categories']
    if not rows.empty:
        matrix = rows.pivot(index='sample_id', columns='category', values='test_pass_rate')
        columns = CATEGORIES + sorted(set(matrix.columns) - set(CATEGORIES))
        matrix = matrix.reindex(columns=columns).sort_index()
        # Include samples with missing category summaries as N/A, not 0%.
        if not data['samples'].empty:
            matrix = matrix.reindex(data['samples']['sample_id'].sort_values().unique())
        cmap = plt.get_cmap('YlGnBu').copy()
        cmap.set_bad('#e2e5e8')
        for start in range(0, len(matrix), heatmap_page_size):
            part = matrix.iloc[start:start + heatmap_page_size]
            fig, ax = plt.subplots(figsize=(10, max(4.8, .29 * len(part) + 2.5)))
            im = ax.imshow(np.ma.masked_invalid(part.to_numpy(dtype=float)),
                           vmin=0, vmax=100, cmap=cmap, aspect='auto')
            ax.set(xticks=range(len(columns)),
                   xticklabels=[CATEGORY_LABELS.get(c, c) for c in columns],
                   yticks=range(len(part)), yticklabels=part.index, ylabel='Official sample ID')
            plt.setp(ax.get_xticklabels(), rotation=25, ha='right', rotation_mode='anchor')
            if len(part) <= 15:
                for (i, j), val in np.ndenumerate(part.to_numpy(dtype=float)):
                    ax.text(j, i, 'N/A' if np.isnan(val) else f'{val:.0f}', ha='center', va='center',
                            fontsize=9, color='white' if np.isfinite(val) and val >= 65 else '#222222')
            page = start // heatmap_page_size + 1
            ax.set_title(heading + f'\nPer-sample CADTest pass rate | page {page}', pad=16)
            fig.colorbar(im, ax=ax, label='CADTest pass rate (%)')
            fig.text(.5, .01, 'Gray = no category observation. These cells are not benchmark PR or RS.',
                     ha='center', fontsize=9)
            fig.tight_layout(rect=(0, .035, 1, 1))
            key = f'sample_category_{page:02d}'
            paths[key] = _save(fig, out / f'{key}.png')
    return paths


def _load_mesh(stl_path):
    import trimesh
    mesh = trimesh.load_mesh(str(stl_path), process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError(f'Empty mesh: {stl_path}')
    if not np.isfinite(mesh.vertices).all():
        raise ValueError(f'Non-finite mesh coordinates: {stl_path}')
    return mesh


def plot_stl_gallery(eval_dir, *, run_kind: str, title: str, out_dir,
                     max_samples: int = 6, sample_ids=None) -> Path | None:
    """Render actual exported STL files; no reference shape is inferred.

    Returns None if there are no STL files. Geometry is shown in source numerical
    coordinates with equal X/Y/Z scales. Axis labels deliberately do not say mm.
    Optional sample_ids chooses already evaluated samples without altering scores.
    """
    heading = _label(run_kind=run_kind, title=title)
    if max_samples < 1:
        raise ValueError('max_samples must be positive.')
    samples = load_official_run(eval_dir)['samples']
    if samples.empty:
        return None
    samples = samples[samples['generated_stl'].notna()]
    if sample_ids is not None:
        samples = samples[samples['sample_id'].isin([str(x) for x in sample_ids])]
    samples = samples.head(max_samples)
    if samples.empty:
        return None
    ncols = min(3, len(samples))
    nrows = math.ceil(len(samples) / ncols)
    fig = plt.figure(figsize=(4.5 * ncols, 4.1 * nrows + 1))
    for idx, row in enumerate(samples.to_dict('records'), 1):
        mesh = _load_mesh(row['generated_stl'])
        ax = fig.add_subplot(nrows, ncols, idx, projection='3d')
        # Face-normal shading only changes appearance; geometry stays unchanged.
        normals = mesh.face_normals
        light = np.array([.3, -.4, .85]); light /= np.linalg.norm(light)
        illumination = .55 + .45 * np.clip(normals @ light, 0, 1)
        rgb = np.asarray(colors.to_rgb(BLUE))
        facecolors = np.clip(illumination[:, None] * rgb[None, :], 0, 1)
        collection = Poly3DCollection(mesh.vertices[mesh.faces], facecolors=facecolors,
                                      linewidths=0, edgecolors='none', antialiaseds=False, alpha=1)
        ax.add_collection3d(collection)
        low, high = mesh.bounds
        mid, radius = (low + high) / 2, max(float((high - low).max()) * .57, 1e-9)
        ax.set(xlim=(mid[0]-radius, mid[0]+radius),
               ylim=(mid[1]-radius, mid[1]+radius), zlim=(mid[2]-radius, mid[2]+radius),
               xlabel='X', ylabel='Y', zlabel='Z')
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=24, azim=-52)
        ax.tick_params(labelsize=7)
        rs = row['rs']
        score = '' if pd.isna(rs) else f' | RS {rs:.1f}%'
        ax.set_title(f"Sample {row['sample_id']}{score}", fontsize=10)
    fig.suptitle(heading + '\nActual generated STL; source coordinates; no reference mesh', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .9))
    return _save(fig, Path(out_dir) / 'generated_stl_gallery.png')


def write_stl_html(stl_path, *, run_kind: str, title: str, output_html) -> Path:
    """Write one standalone, rotatable Plotly mesh (Plotly JS embedded offline)."""
    import plotly.graph_objects as go
    heading = _label(run_kind=run_kind, title=title)
    mesh = _load_mesh(stl_path)
    xyz, tri = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    fig = go.Figure(go.Mesh3d(x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2],
                             i=tri[:, 0], j=tri[:, 1], k=tri[:, 2],
                             color=BLUE, opacity=1, flatshading=True,
                             hovertemplate='X %{x:.5g}<br>Y %{y:.5g}<br>Z %{z:.5g}<extra></extra>'))
    fig.update_layout(title=heading.replace('\n', '<br>'), template='plotly_white',
                      scene=dict(aspectmode='data', xaxis_title='X', yaxis_title='Y', zaxis_title='Z'),
                      margin=dict(l=0, r=0, b=25, t=85),
                      annotations=[dict(text='Source coordinates | actual exported STL | no reference mesh',
                                        x=.5, y=0, xref='paper', yref='paper', showarrow=False)])
    path = Path(output_html); path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(path), include_plotlyjs=True, full_html=True)
    return path


