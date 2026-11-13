"""Matplotlib presentation of prepared single-run analyses."""

import math
from collections.abc import Mapping

from matplotlib import colormaps
from matplotlib.cbook import boxplot_stats
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, MaxNLocator, NullFormatter

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


def plot_client_scaling(runs, *, fontsize=12, dpi=200):
    """Plot run-level throughput and mean runtime against concurrent clients.

    runs is a DataFrame with backend, clients, scale_factor,
    throughput_queries_per_second and mean_runtime_seconds columns. Each row is
    one run. Repetitions have equal weight; shading spans their minimum/maximum.
    Missing combinations remain gaps. Runtime NaNs (no successes) are not zeros.
    Columns represent scale factors; rows show throughput and successful runtime.
    Return a Figure without displaying or saving it.
    """
    required = {
        "backend",
        "clients",
        "scale_factor",
        "throughput_queries_per_second",
        "mean_runtime_seconds",
    }
    if runs.empty or not required <= set(runs.columns):
        raise ValueError("Supply nonempty run summaries with all required columns")
    scales = sorted(runs["scale_factor"].unique())
    clients = sorted(runs["clients"].unique())
    figure = Figure(figsize=(5 * len(scales), 7), dpi=dpi, layout="constrained")
    axes = figure.subplots(2, len(scales), squeeze=False)
    metrics = [
        ("throughput_queries_per_second", "Throughput (queries/s)"),
        ("mean_runtime_seconds", "Mean query runtime (s)"),
    ]
    for column, scale in enumerate(scales):
        subset = runs[runs["scale_factor"] == scale]
        axes[0, column].set_title(f"SF = {scale:g}", fontsize=fontsize + 1)
        for row, (metric, ylabel) in enumerate(metrics):
            ax = axes[row, column]
            for backend in ("mongodb", "couchbase"):
                values = subset[subset["backend"] == backend]
                if values.empty:
                    continue
                stats = values.groupby("clients")[metric].agg(["mean", "min", "max"])
                stats = stats.reindex(clients)
                color = _BACKEND_COLORS[backend]
                ax.plot(
                    range(len(clients)),
                    stats["mean"],
                    marker="o",
                    color=color,
                    label={"mongodb": "MongoDB", "couchbase": "Couchbase"}[backend],
                )
                ax.fill_between(
                    range(len(clients)), stats["min"], stats["max"], color=color, alpha=0.15
                )
            # Keep zero throughput visible. Log scaling is used only for positive data.
            observed = subset[metric].dropna()
            if not observed.empty and (observed > 0).all():
                ax.set_yscale("log")
                ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
                ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
                ax.yaxis.set_minor_formatter(NullFormatter())
            ax.set_xticks(range(len(clients)), clients)
            ax.set_xlabel("Concurrent clients", fontsize=fontsize)
            ax.set_ylabel(ylabel, fontsize=fontsize)
            ax.tick_params(labelsize=fontsize)
            ax.grid(alpha=0.2)
            ax.set_axisbelow(True)
        axes[0, column].legend(fontsize=fontsize)
    return figure


def plot_outcome_percentages(cohort, *, fontsize=11, dpi=200):
    """Draw backend rows and SF columns; bars average run-level percentages."""
    runs = cohort.runs
    scales, clients = sorted(runs.scale_factor.unique()), sorted(runs.clients.unique())
    backends = [b for b in _BACKEND_COLORS if b in set(runs.backend)]
    figure = Figure(figsize=(4.5 * len(scales), 3.4 * len(backends)), dpi=dpi, layout="constrained")
    axes = figure.subplots(len(backends), len(scales), squeeze=False)
    for row, backend in enumerate(backends):
        for col, sf in enumerate(scales):
            ax = axes[row, col]
            data = runs[(runs.backend == backend) & (runs.scale_factor == sf)]
            bottom = [0.0] * len(clients)
            for key, label, color in _OUTCOMES:
                values = (
                    data.groupby("clients")[key.replace("_count", "_percent")]
                    .mean()
                    .reindex(clients)
                )
                ax.bar(range(len(clients)), values, bottom=bottom, color=color, label=label)
                bottom = [a + b for a, b in zip(bottom, values, strict=True)]
            for i, client in enumerate(clients):
                if data[data.clients == client].measurement_admissions.sum() == 0:
                    ax.text(i, 50, "No data", rotation=90, ha="center", va="center")
            ax.set_title(
                f"{backend.title() if backend == 'couchbase' else 'MongoDB'} — SF = {sf:g}",
                fontsize=fontsize,
            )
            ax.set_xticks(range(len(clients)), clients)
            ax.set_xlabel("Concurrent clients", fontsize=fontsize)
            ax.set_ylabel("Query attempts (%)", fontsize=fontsize)
            ax.set_ylim(0, 100)
            ax.tick_params(labelsize=fontsize)
    axes[-1, 0].legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, fontsize=fontsize - 1
    )
    return figure


def plot_failure_heatmaps(cohort, *, fontsize=11, dpi=200):
    """Show mean run-level (error + timeout) percentages; unresolved stays separate."""
    import numpy as np

    runs = cohort.runs
    scales, clients = sorted(runs.scale_factor.unique()), sorted(runs.clients.unique())
    backends = [b for b in _BACKEND_COLORS if b in set(runs.backend)]
    figure = Figure(
        figsize=(max(5, len(clients)), max(3.5, len(backends) * (len(scales) * 0.65 + 1))),
        dpi=dpi,
        layout="constrained",
    )
    axes = figure.subplots(len(backends), 1, squeeze=False, sharex=True)
    for ax, backend in zip(axes.flat, backends, strict=True):
        grid = (
            runs[runs.backend == backend]
            .pivot_table(
                index="scale_factor", columns="clients", values="failure_percent", aggfunc="mean"
            )
            .reindex(index=scales, columns=clients)
        )
        cmap = colormaps["YlOrRd"].with_extremes(bad="#dddddd")
        im = ax.imshow(
            np.ma.masked_invalid(grid.to_numpy()), vmin=0, vmax=100, cmap=cmap, aspect="equal"
        )
        for i in range(len(scales)):
            for j in range(len(clients)):
                value = grid.iloc[i, j]
                ax.text(
                    j,
                    i,
                    "—" if np.isnan(value) else f"{value:.1f}",
                    ha="center",
                    va="center",
                    fontsize=fontsize - 1,
                    color="white" if value > 65 else "black",
                )
        ax.set_title(
            "MongoDB" if backend == "mongodb" else "Couchbase", fontsize=fontsize + 1, pad=10
        )
        ax.set_yticks(range(len(scales)), scales)
        ax.set_xticks(range(len(clients)), clients)
        ax.set_ylabel("Scale factor", fontsize=fontsize)
        ax.tick_params(labelsize=fontsize)
    axes[-1, 0].set_xlabel("Concurrent clients", fontsize=fontsize)
    bar = figure.colorbar(im, ax=list(axes.flat), orientation="horizontal", shrink=0.6, aspect=30)
    bar.set_label("Mean error + timeout rate (%)", fontsize=fontsize)
    return figure


def plot_cohort_query_runtimes(cohort, *, fontsize=12, dpi=200):
    """Return SF-to-Figure mapping plus None for all SF; pool successful runtimes."""
    queries = cohort.queries
    figures = {}
    for sf in [*sorted(queries.scale_factor.unique()), None]:
        data = queries if sf is None else queries[queries.scale_factor == sf]
        labels = data.sort_values("workload_position").label.unique().tolist()
        figure, ax = _axes(
            labels, (max(6, len(labels) * 0.8), 4.8), fontsize, dpi, "Successful query runtime (s)"
        )
        for b, (backend, color) in enumerate(_BACKEND_COLORS.items()):
            for i, label in enumerate(labels):
                rows = data[(data.backend == backend) & (data.label == label)]
                samples = [v for values in rows.successful_runtime_seconds for v in values]
                position = i + (b - 0.5) * 0.35
                if samples:
                    stats = boxplot_stats(samples, whis=(5, 95))
                    ax.bxp(
                        stats,
                        positions=[position],
                        widths=0.29,
                        showfliers=False,
                        patch_artist=True,
                        manage_ticks=False,
                        boxprops={"facecolor": color, "alpha": 0.7},
                        medianprops={"color": "black"},
                    )
                else:
                    ax.text(
                        position,
                        0.03,
                        "No successes" if not rows.empty else "No data",
                        rotation=90,
                        ha="center",
                        fontsize=fontsize - 3,
                        transform=ax.get_xaxis_transform(),
                    )
        samples = [v for values in data.successful_runtime_seconds for v in values]
        if samples and min(samples) > 0:
            ax.set_yscale("log")
            ax.yaxis.set_major_locator(LogLocator(subs=(1, 2, 5)))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
            ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_title("All SF combined" if sf is None else f"SF = {sf:g}")
        ax.legend(
            handles=[
                Patch(facecolor=c, label="MongoDB" if b == "mongodb" else "Couchbase")
                for b, c in _BACKEND_COLORS.items()
            ],
            fontsize=fontsize,
        )
        figure.tight_layout()
        figures[sf] = figure
    return figures


def plot_cohort_query_outcomes(cohort, *, fontsize=11, dpi=200):
    """Return SF-to-Figure mapping plus None for all SF; pool outcome counts."""
    queries = cohort.queries
    figures = {}
    for sf in [*sorted(queries.scale_factor.unique()), None]:
        data = queries if sf is None else queries[queries.scale_factor == sf]
        labels = data.sort_values("workload_position").label.unique().tolist()
        figure, ax = _axes(
            labels, (max(6, len(labels) * 0.8), 5), fontsize, dpi, "Query attempts (count)"
        )
        for b, backend in enumerate(_BACKEND_COLORS):
            rows = data[data.backend == backend]
            positions = [i + (b - 0.5) * 0.36 for i in range(len(labels))]
            bottom = [0] * len(labels)
            for key, _, color in _OUTCOMES:
                values = rows.groupby("label")[key].sum().reindex(labels, fill_value=0)
                ax.bar(
                    positions,
                    values,
                    width=0.33,
                    bottom=bottom,
                    color=color,
                    hatch="///" if b else "",
                    edgecolor="0.25",
                    linewidth=0.35,
                )
                bottom = [a + v for a, v in zip(bottom, values, strict=True)]
            for i, label in enumerate(labels):
                if rows[rows.label == label].empty:
                    ax.text(
                        positions[i],
                        0.02,
                        "No data",
                        rotation=90,
                        ha="center",
                        transform=ax.get_xaxis_transform(),
                        fontsize=fontsize - 2,
                    )
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_title("All SF combined" if sf is None else f"SF = {sf:g}")
        figure.legend(
            handles=[Patch(facecolor=color, label=label) for _, label, color in _OUTCOMES],
            loc="lower center",
            bbox_to_anchor=(0.5, 0.06),
            ncol=4,
            fontsize=fontsize - 1,
        )
        figure.legend(
            handles=[
                Patch(facecolor="white", edgecolor="black", hatch=h, label=b)
                for b, h in [("MongoDB (left)", ""), ("Couchbase (right)", "///")]
            ],
            loc="lower center",
            ncol=2,
            fontsize=fontsize - 1,
        )
        figure.tight_layout(rect=(0, 0.16, 1, 1))
        figures[sf] = figure
    return figures
