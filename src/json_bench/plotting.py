"""Matplotlib presentation of prepared single-run analyses."""

import math
from collections.abc import Mapping

from matplotlib.cbook import boxplot_stats
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from json_bench.analysis import LoadAnalysis

_BACKEND_COLORS = {"mongodb": "#2166ac", "couchbase": "#b35806"}
_FALLBACK_COLORS = ("#2166ac", "#b35806", "#6a3d9a", "#008080")
_OUTCOMES = (
    ("success_count", "Success", "#59a14f"),
    ("error_count", "Error", "#e15759"),
    ("timeout_count", "Timeout", "#f28e2b"),
    ("unresolved_count", "Unresolved", "#9c9c9c"),
)
_HATCHES = ("", "//", "xx", "..", "++", "oo")


def _inputs(analyses, figsize, fontsize, dpi):
    """Require aligned query identities and valid figure dimensions."""
    if not analyses:
        raise ValueError("analyses must contain at least one labelled run")
    expected = None
    for backend, analysis in analyses.items():
        if not isinstance(backend, str) or not backend.strip():
            raise ValueError("Backend labels must be nonblank strings")
        keys = [(query.workload_position, query.label) for query in analysis.queries]
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("Each analysis must have nonempty, distinct query identities")
        if expected is not None and keys != expected:
            raise ValueError("Analyses must have matching query positions and labels")
        expected = keys
    if len(figsize) != 2 or any(not math.isfinite(value) or value <= 0 for value in figsize):
        raise ValueError("figsize must contain two positive finite dimensions")
    if any(not math.isfinite(value) or value <= 0 for value in (fontsize, dpi)):
        raise ValueError("fontsize and dpi must be positive and finite")
    return [label for _, label in expected]


def _backend_label(name, analysis):
    """Keep observed early termination visible in the legend."""
    return name + (" (early stop)" if analysis.summary.early_terminated else "")


def _axes(labels, figsize, fontsize, dpi, ylabel):
    """Create a standalone figure without changing global plotting settings."""
    figure = Figure(figsize=figsize, dpi=dpi)
    axes = figure.subplots()
    axes.set_xticks(range(len(labels)), labels)
    axes.set_xlim(-0.6, len(labels) - 0.4)
    axes.set_xlabel("Query template", fontsize=fontsize)
    axes.set_ylabel(ylabel, fontsize=fontsize)
    axes.tick_params(labelsize=fontsize)
    axes.grid(axis="y", alpha=0.2)
    axes.set_axisbelow(True)
    return figure, axes


def plot_query_runtimes(
    analyses: Mapping[str, LoadAnalysis],
    *,
    log_scale: bool = True,
    whisker_percentiles: tuple[float, float] = (5, 95),
    figsize: tuple[float, float] = (10, 5),
    fontsize: float = 12,
    dpi: float = 200,
) -> Figure:
    """Draw paired successful-runtime distributions for aligned per-query analyses.

    Args:
        analyses: Display label to one LoadAnalysis, in legend/bar order. No pooling.
        log_scale: Use a logarithmic runtime axis. Nonpositive samples raise ValueError.
        whisker_percentiles: Lower/upper whisker percentiles (default 5 and 95).
            They must bracket the box's 25th and 75th percentiles.
        figsize: Figure width and height in inches.
        fontsize: Label, tick and legend font size.
        dpi: Figure resolution, default 200.

    Returns:
        A Figure without displaying or saving it. Boxes show median and quartiles;
        outliers are hidden, not discarded from analysis. Empty samples are labelled
        "No successes". Early-stopped runs are identified in the legend.

    Raises:
        ValueError: Misaligned queries, invalid options or invalid runtime samples.

    Successful measurement admissions include drain completions. The plot uses
    samples prepared by analyse_load_results; it does not redefine measurement.
    """
    labels = _inputs(analyses, figsize, fontsize, dpi)
    if len(whisker_percentiles) != 2 or not (
        0 <= whisker_percentiles[0] <= 25 and 75 <= whisker_percentiles[1] <= 100
    ):
        raise ValueError("Whisker percentiles must bracket 25 and 75 within [0, 100]")
    for analysis in analyses.values():
        for query in analysis.queries:
            if any(
                not math.isfinite(value) or value < 0 for value in query.successful_runtime_seconds
            ):
                raise ValueError("Runtime samples must be finite and nonnegative")
            if log_scale and any(value <= 0 for value in query.successful_runtime_seconds):
                raise ValueError("Log runtime plots require positive samples; use log_scale=False")
    figure, axes = _axes(labels, figsize, fontsize, dpi, "Successful query runtime (s)")
    width = 0.8 / len(analyses)
    handles = []
    for backend_index, (backend, analysis) in enumerate(analyses.items()):
        color = _BACKEND_COLORS.get(
            backend.lower(), _FALLBACK_COLORS[backend_index % len(_FALLBACK_COLORS)]
        )
        handles.append(Patch(facecolor=color, alpha=0.7, label=_backend_label(backend, analysis)))
        for index, query in enumerate(analysis.queries):
            position = index - 0.4 + width * (backend_index + 0.5)
            if query.successful_runtime_seconds:
                axes.bxp(
                    boxplot_stats(query.successful_runtime_seconds, whis=whisker_percentiles),
                    positions=[position],
                    widths=width * 0.8,
                    patch_artist=True,
                    showfliers=False,
                    manage_ticks=False,
                    boxprops=dict(facecolor=color, edgecolor=color, alpha=0.7),
                    whiskerprops=dict(color=color),
                    capprops=dict(color=color),
                    medianprops=dict(color="black", linewidth=1.2),
                )
            else:
                axes.text(
                    position,
                    0.03,
                    "No successes",
                    rotation=90,
                    ha="center",
                    va="bottom",
                    fontsize=fontsize * 0.8,
                    color=color,
                    transform=axes.get_xaxis_transform(),
                )
    if log_scale:
        axes.set_yscale("log")
        if not any(q.successful_runtime_seconds for a in analyses.values() for q in a.queries):
            axes.set_ylim(0.1, 10)
    else:
        axes.set_ylim(bottom=0)
    axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    axes.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
        ncol=len(handles),
        frameon=False,
        fontsize=fontsize,
    )
    figure.tight_layout()
    return figure


def plot_query_outcomes(
    analyses: Mapping[str, LoadAnalysis],
    *,
    figsize: tuple[float, float] = (10, 5),
    fontsize: float = 12,
    dpi: float = 200,
) -> Figure:
    """Draw grouped stacked outcome counts for each query and backend.

    Args:
        analyses: Display label to aligned LoadAnalysis, in backend order.
        figsize: Figure width and height in inches.
        fontsize: Label, tick and legend font size.
        dpi: Figure resolution, default 200.

    Returns:
        A Figure without displaying or saving it. Each backend has a separate bar
        per query. Colors identify success/error/timeout/unresolved; hatches identify
        backends. Counts include drain outcomes for measurement admissions.
        These are absolute counts, not percentages or throughput.

    Raises:
        ValueError: Misaligned queries or invalid figure options.
    """
    labels = _inputs(analyses, figsize, fontsize, dpi)
    figure, axes = _axes(labels, figsize, fontsize, dpi, "Query attempts")
    width = 0.8 / len(analyses)
    for backend_index, (_, analysis) in enumerate(analyses.items()):
        positions = [i - 0.4 + width * (backend_index + 0.5) for i in range(len(labels))]
        bottom = [0] * len(labels)
        for field, _, color in _OUTCOMES:
            heights = [getattr(query, field) for query in analysis.queries]
            axes.bar(
                positions,
                heights,
                width=width * 0.85,
                bottom=bottom,
                color=color,
                edgecolor="black",
                linewidth=0.5,
                hatch=_HATCHES[backend_index % len(_HATCHES)],
            )
            bottom = [base + height for base, height in zip(bottom, heights, strict=True)]
    axes.yaxis.set_major_locator(MaxNLocator(integer=True))
    axes.set_ylim(bottom=0)
    # Separate legend rows keep outcome colors distinct from backend hatches.
    outcome_legend = axes.legend(
        handles=[Patch(facecolor=color, label=label) for _, label, color in _OUTCOMES],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
        ncol=4,
        frameon=False,
        fontsize=fontsize,
    )
    axes.add_artist(outcome_legend)
    axes.legend(
        handles=[
            Patch(
                facecolor="white",
                edgecolor="black",
                hatch=_HATCHES[i % len(_HATCHES)],
                label=_backend_label(name, analysis),
            )
            for i, (name, analysis) in enumerate(analyses.items())
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.3),
        ncol=len(analyses),
        frameon=False,
        fontsize=fontsize,
    )
    figure.tight_layout()
    return figure
