"""Reflector-angle analysis for offline millimeter-wave captures.

This script is intended for experiments where a strong reflector (for example,
metal at different angles) is measured across a small number of captures and
the user wants to see which channel/bin changes the most.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - plotting is optional
    plt = None

try:
    from .mmw_scan_analysis import decode_capture_file, ensure_dir, numeric_file_key
except ImportError:
    from mmw_scan_analysis import decode_capture_file, ensure_dir, numeric_file_key


@dataclass
class CaptureStats:
    """Statistics for one reflector capture."""

    source_file: Path
    label: str
    frame_count: int
    complex_mean: np.ndarray
    amplitude_mean: np.ndarray
    amplitude_std: np.ndarray
    phase_std: np.ndarray
    dominant_channel: int
    dominant_bin: int
    dominant_amplitude: float


def discover_groups(input_root: Path) -> dict[str, Path]:
    """Discover analyzable groups under the input root."""

    direct_csvs = sorted(input_root.glob("*.csv"), key=numeric_file_key)
    if direct_csvs:
        return {input_root.name: input_root}

    groups: dict[str, Path] = {}
    for child in sorted(input_root.iterdir()):
        if not child.is_dir():
            continue
        if any(child.glob("*.csv")):
            groups[child.name] = child
    return groups


def load_group_stats(
    group_dir: Path,
    channel_num: int,
    bins_per_channel: int,
    labels: list[str] | None = None,
) -> list[CaptureStats]:
    """Decode all captures in one group and compute per-capture statistics."""

    raw_files = [path for path in sorted(group_dir.glob("*.csv"), key=numeric_file_key)]
    if not raw_files:
        return []

    if labels is not None and len(labels) != len(raw_files):
        raise ValueError(
            f"Label count mismatch for {group_dir.name}: expected {len(raw_files)}, got {len(labels)}"
        )

    capture_stats: list[CaptureStats] = []
    for zero_based_index, raw_file in enumerate(raw_files):
        label = labels[zero_based_index] if labels is not None else str(zero_based_index + 1)
        capture = decode_capture_file(
            file_path=raw_file,
            position_index=zero_based_index + 1,
            position_cm=float(zero_based_index + 1),
            channel_num=channel_num,
            bins_per_channel=bins_per_channel,
        )
        complex_mean = capture.complex_cube.mean(axis=0)
        amplitude = np.abs(capture.complex_cube)
        unwrapped_phase = np.unwrap(np.angle(capture.complex_cube), axis=0)
        amplitude_mean = amplitude.mean(axis=0)
        amplitude_std = amplitude.std(axis=0)
        phase_std = unwrapped_phase.std(axis=0)
        dominant_idx = np.unravel_index(np.argmax(amplitude_mean), amplitude_mean.shape)
        capture_stats.append(
            CaptureStats(
                source_file=raw_file,
                label=label,
                frame_count=int(capture.complex_cube.shape[0]),
                complex_mean=complex_mean,
                amplitude_mean=amplitude_mean,
                amplitude_std=amplitude_std,
                phase_std=phase_std,
                dominant_channel=int(dominant_idx[0]),
                dominant_bin=int(dominant_idx[1]),
                dominant_amplitude=float(amplitude_mean[dominant_idx]),
            )
        )
    return capture_stats


def build_cell_summary(captures: list[CaptureStats]) -> list[dict[str, object]]:
    """Build one summary row per channel/bin across captures."""

    amplitude_stack = np.stack([capture.amplitude_mean for capture in captures], axis=0)
    phase_std_stack = np.stack([capture.phase_std for capture in captures], axis=0)
    mean_amplitude = amplitude_stack.mean(axis=0)
    amplitude_range = amplitude_stack.max(axis=0) - amplitude_stack.min(axis=0)
    amplitude_series_std = amplitude_stack.std(axis=0)
    amplitude_cv = amplitude_series_std / np.maximum(mean_amplitude, 1e-9)
    mean_phase_std = phase_std_stack.mean(axis=0)
    phase_std_range = phase_std_stack.max(axis=0) - phase_std_stack.min(axis=0)

    rows: list[dict[str, object]] = []
    for channel_id in range(amplitude_stack.shape[1]):
        for bin_id in range(amplitude_stack.shape[2]):
            row: dict[str, object] = {
                "channel": channel_id,
                "bin": bin_id,
                "mean_amplitude": float(mean_amplitude[channel_id, bin_id]),
                "amplitude_range": float(amplitude_range[channel_id, bin_id]),
                "amplitude_series_std": float(amplitude_series_std[channel_id, bin_id]),
                "amplitude_cv": float(amplitude_cv[channel_id, bin_id]),
                "mean_phase_std": float(mean_phase_std[channel_id, bin_id]),
                "phase_std_range": float(phase_std_range[channel_id, bin_id]),
            }
            for capture_index, capture in enumerate(captures, start=1):
                row[f"capture_{capture_index}_label"] = capture.label
                row[f"capture_{capture_index}_amplitude"] = float(
                    amplitude_stack[capture_index - 1, channel_id, bin_id]
                )
                row[f"capture_{capture_index}_phase_std"] = float(
                    phase_std_stack[capture_index - 1, channel_id, bin_id]
                )
            rows.append(row)
    return rows


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    """Write rows to CSV if non-empty."""

    if not rows:
        return

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def select_top_cells(
    cell_rows: list[dict[str, object]],
    captures: list[CaptureStats],
    top_k: int,
) -> list[tuple[int, int]]:
    """Select dominant cell plus top varying cells."""

    if not captures:
        return []

    dominant_matrix = np.stack([capture.amplitude_mean for capture in captures], axis=0).mean(axis=0)
    dominant_idx = np.unravel_index(np.argmax(dominant_matrix), dominant_matrix.shape)

    sorted_rows = sorted(
        cell_rows,
        key=lambda row: (float(row["amplitude_range"]), float(row["mean_amplitude"])),
        reverse=True,
    )
    selected = [(int(dominant_idx[0]), int(dominant_idx[1]))]
    for row in sorted_rows:
        cell = (int(row["channel"]), int(row["bin"]))
        if cell in selected:
            continue
        selected.append(cell)
        if len(selected) >= top_k:
            break
    return selected


def plot_capture_heatmaps(
    metric_stack: np.ndarray,
    capture_labels: list[str],
    title_prefix: str,
    output_path: Path,
    cmap: str = "viridis",
) -> None:
    """Plot one heatmap per capture."""

    if plt is None or metric_stack.size == 0:
        return

    capture_count = metric_stack.shape[0]
    fig, axes = plt.subplots(1, capture_count, figsize=(4.5 * capture_count, 4.5), squeeze=False)
    for index in range(capture_count):
        ax = axes[0, index]
        image = ax.imshow(metric_stack[index], aspect="auto", cmap=cmap)
        ax.set_title(f"{title_prefix} - {capture_labels[index]}")
        ax.set_xlabel("Bin")
        ax.set_ylabel("Channel")
        ax.set_xticks(np.arange(metric_stack.shape[2]))
        ax.set_yticks(np.arange(metric_stack.shape[1]))
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_residual_heatmaps(
    residual_stack: np.ndarray,
    capture_labels: list[str],
    output_path: Path,
) -> None:
    """Plot complex-mean residual heatmaps after background subtraction."""

    if plt is None or residual_stack.size == 0:
        return

    capture_count = residual_stack.shape[0]
    fig, axes = plt.subplots(1, capture_count, figsize=(4.5 * capture_count, 4.5), squeeze=False)
    for index in range(capture_count):
        ax = axes[0, index]
        image = ax.imshow(residual_stack[index], aspect="auto", cmap="inferno")
        ax.set_title(f"Residual vs background - {capture_labels[index]}")
        ax.set_xlabel("Bin")
        ax.set_ylabel("Channel")
        ax.set_xticks(np.arange(residual_stack.shape[2]))
        ax.set_yticks(np.arange(residual_stack.shape[1]))
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_single_heatmap(
    metric: np.ndarray,
    title: str,
    output_path: Path,
    cmap: str = "magma",
) -> None:
    """Plot one summary heatmap."""

    if plt is None or metric.size == 0:
        return

    fig, ax = plt.subplots(figsize=(6.5, 5))
    image = ax.imshow(metric, aspect="auto", cmap=cmap)
    ax.set_title(title)
    ax.set_xlabel("Bin")
    ax.set_ylabel("Channel")
    ax.set_xticks(np.arange(metric.shape[1]))
    ax.set_yticks(np.arange(metric.shape[0]))
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_top_series(
    captures: list[CaptureStats],
    selected_cells: list[tuple[int, int]],
    output_path: Path,
) -> None:
    """Plot amplitude change and phase spread for selected cells."""

    if plt is None or not captures or not selected_cells:
        return

    labels = [capture.label for capture in captures]
    x = np.arange(len(captures))

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for channel_id, bin_id in selected_cells:
        amplitude_series = [capture.amplitude_mean[channel_id, bin_id] for capture in captures]
        phase_std_series = [capture.phase_std[channel_id, bin_id] for capture in captures]
        axes[0].plot(x, amplitude_series, marker="o", label=f"ch{channel_id}/bin{bin_id}")
        axes[1].plot(x, phase_std_series, marker="o", label=f"ch{channel_id}/bin{bin_id}")

    axes[0].set_ylabel("Mean amplitude")
    axes[0].set_title("Top reflector-sensitive cells")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=2)

    axes[1].set_ylabel("Phase std")
    axes[1].set_xlabel("Measurement")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(ncol=2)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_relative_change(
    captures: list[CaptureStats],
    selected_cells: list[tuple[int, int]],
    output_path: Path,
) -> None:
    """Plot relative amplitude change against the first capture."""

    if plt is None or not captures or not selected_cells:
        return

    labels = [capture.label for capture in captures]
    x = np.arange(len(captures))
    fig, ax = plt.subplots(figsize=(10, 4.5))

    for channel_id, bin_id in selected_cells:
        amplitude_series = np.asarray(
            [capture.amplitude_mean[channel_id, bin_id] for capture in captures], dtype=float
        )
        base_value = amplitude_series[0] if amplitude_series[0] != 0 else 1.0
        relative_change = (amplitude_series / base_value - 1.0) * 100.0
        ax.plot(x, relative_change, marker="o", label=f"ch{channel_id}/bin{bin_id}")

    ax.set_title("Relative amplitude change vs first measurement")
    ax.set_ylabel("Change (%)")
    ax.set_xlabel("Measurement")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_channel_all_bins(
    captures: list[CaptureStats],
    channel_id: int,
    output_path: Path,
    normalize_to_bin: int | None = None,
) -> None:
    """Plot all bins for one channel across captures."""

    if plt is None or not captures:
        return

    labels = [capture.label for capture in captures]
    x = np.arange(len(captures))
    fig, ax = plt.subplots(figsize=(10, 5))

    for bin_id in range(captures[0].amplitude_mean.shape[1]):
        series = np.asarray(
            [capture.amplitude_mean[channel_id, bin_id] for capture in captures], dtype=float
        )
        if normalize_to_bin is not None:
            base = np.asarray(
                [capture.amplitude_mean[channel_id, normalize_to_bin] for capture in captures],
                dtype=float,
            )
            series = series / np.maximum(base, 1e-9)
            ylabel = f"Amplitude / bin{normalize_to_bin + 1}"
        else:
            ylabel = "Mean amplitude"
        ax.plot(x, series, marker="o", label=f"bin{bin_id + 1}")

    title = f"Channel {channel_id} all-bin change"
    if normalize_to_bin is not None:
        title += f" (normalized by bin{normalize_to_bin + 1})"
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Measurement")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def analyze_group(
    group_name: str,
    group_dir: Path,
    output_root: Path,
    channel_num: int,
    bins_per_channel: int,
    top_k: int,
    labels: list[str] | None = None,
) -> dict[str, object] | None:
    """Analyze one reflector group and export plots plus summaries."""

    captures = load_group_stats(
        group_dir=group_dir,
        channel_num=channel_num,
        bins_per_channel=bins_per_channel,
        labels=labels,
    )
    if not captures:
        return None

    group_output = output_root / group_name
    ensure_dir(group_output)

    capture_rows = [
        {
            "group": group_name,
            "capture_label": capture.label,
            "source_file": capture.source_file.name,
            "frame_count": capture.frame_count,
            "dominant_channel": capture.dominant_channel,
            "dominant_bin": capture.dominant_bin,
            "dominant_amplitude": capture.dominant_amplitude,
        }
        for capture in captures
    ]
    write_csv(capture_rows, group_output / "capture_summary.csv")

    amplitude_stack = np.stack([capture.amplitude_mean for capture in captures], axis=0)
    phase_std_stack = np.stack([capture.phase_std for capture in captures], axis=0)
    complex_mean_stack = np.stack([capture.complex_mean for capture in captures], axis=0)
    amplitude_range = amplitude_stack.max(axis=0) - amplitude_stack.min(axis=0)
    phase_std_range = phase_std_stack.max(axis=0) - phase_std_stack.min(axis=0)
    background_complex = complex_mean_stack[0]
    residual_stack = np.abs(complex_mean_stack - background_complex[None, :, :])
    dominant_matrix = amplitude_stack.mean(axis=0)
    dominant_idx = np.unravel_index(np.argmax(dominant_matrix), dominant_matrix.shape)

    residual_rows = []
    for capture_index in range(1, len(captures)):
        residual = residual_stack[capture_index]
        dominant_idx = np.unravel_index(np.argmax(residual), residual.shape)
        residual_rows.append(
            {
                "background_label": captures[0].label,
                "capture_label": captures[capture_index].label,
                "source_file": captures[capture_index].source_file.name,
                "dominant_residual_channel": int(dominant_idx[0]),
                "dominant_residual_bin": int(dominant_idx[1]),
                "dominant_residual": float(residual[dominant_idx]),
                "channel_3_residual_series": [float(value) for value in residual[3].tolist()],
            }
        )

    cell_rows = build_cell_summary(captures)
    write_csv(cell_rows, group_output / "cell_variation_summary.csv")
    write_csv(residual_rows, group_output / "background_residual_summary.csv")

    top_rows = sorted(
        cell_rows,
        key=lambda row: (float(row["amplitude_range"]), float(row["mean_amplitude"])),
        reverse=True,
    )[:top_k]
    write_csv(top_rows, group_output / "top_variation_cells.csv")

    selected_cells = select_top_cells(cell_rows=cell_rows, captures=captures, top_k=top_k)
    plot_capture_heatmaps(
        metric_stack=amplitude_stack,
        capture_labels=[capture.label for capture in captures],
        title_prefix="Amplitude mean",
        output_path=group_output / "amplitude_mean_heatmaps.png",
    )
    plot_capture_heatmaps(
        metric_stack=phase_std_stack,
        capture_labels=[capture.label for capture in captures],
        title_prefix="Phase std",
        output_path=group_output / "phase_std_heatmaps.png",
        cmap="plasma",
    )
    if residual_stack.shape[0] > 1:
        plot_residual_heatmaps(
            residual_stack=residual_stack[1:],
            capture_labels=[capture.label for capture in captures[1:]],
            output_path=group_output / "background_residual_heatmaps.png",
        )
    plot_single_heatmap(
        metric=amplitude_range,
        title=f"{group_name} amplitude range",
        output_path=group_output / "amplitude_range_heatmap.png",
    )
    plot_single_heatmap(
        metric=phase_std_range,
        title=f"{group_name} phase std range",
        output_path=group_output / "phase_std_range_heatmap.png",
        cmap="cividis",
    )
    plot_top_series(
        captures=captures,
        selected_cells=selected_cells,
        output_path=group_output / "top_variation_series.png",
    )
    plot_relative_change(
        captures=captures,
        selected_cells=selected_cells,
        output_path=group_output / "relative_amplitude_change.png",
    )
    plot_channel_all_bins(
        captures=captures,
        channel_id=int(dominant_idx[0]),
        output_path=group_output / "dominant_channel_all_bins.png",
    )
    plot_channel_all_bins(
        captures=captures,
        channel_id=int(dominant_idx[0]),
        normalize_to_bin=int(dominant_idx[1]),
        output_path=group_output / "dominant_channel_all_bins_normalized.png",
    )

    varying_idx = np.unravel_index(np.argmax(amplitude_range), amplitude_range.shape)
    residual_max_idx = np.unravel_index(np.argmax(residual_stack[1:]), residual_stack[1:].shape) if residual_stack.shape[0] > 1 else None
    group_summary = {
        "group": group_name,
        "capture_count": len(captures),
        "dominant_channel": int(dominant_idx[0]),
        "dominant_bin": int(dominant_idx[1]),
        "dominant_mean_amplitude": float(dominant_matrix[dominant_idx]),
        "most_varying_channel": int(varying_idx[0]),
        "most_varying_bin": int(varying_idx[1]),
        "most_varying_amplitude_range": float(amplitude_range[varying_idx]),
        "most_varying_phase_std_range": float(phase_std_range[varying_idx]),
        "most_varying_series": [
            float(capture.amplitude_mean[varying_idx]) for capture in captures
        ],
        "selected_cells": [
            {"channel": int(channel_id), "bin": int(bin_id)} for channel_id, bin_id in selected_cells
        ],
    }
    if residual_max_idx is not None:
        group_summary["background_label"] = captures[0].label
        group_summary["max_background_residual_capture_index"] = int(residual_max_idx[0] + 2)
        group_summary["max_background_residual_channel"] = int(residual_max_idx[1])
        group_summary["max_background_residual_bin"] = int(residual_max_idx[2])
        group_summary["max_background_residual"] = float(residual_stack[1:][residual_max_idx])
    with (group_output / "group_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(group_summary, handle, indent=2, ensure_ascii=False)
    return group_summary


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Reflector-angle variation analysis")
    parser.add_argument(
        "--input-root",
        type=Path,
        required=True,
        help="Root directory containing one or more capture groups.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for exported summaries and plots.",
    )
    parser.add_argument(
        "--channel-num",
        type=int,
        default=8,
        help="Number of channels in the decoded radar frames.",
    )
    parser.add_argument(
        "--bins-per-channel",
        type=int,
        default=10,
        help="Number of bins per channel.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=6,
        help="How many changing cells to highlight in summary plots.",
    )
    parser.add_argument(
        "--labels",
        nargs="*",
        default=None,
        help="Optional labels for capture order. Only valid when input-root contains one group.",
    )
    return parser


def main() -> None:
    """Run reflector-angle analysis."""

    parser = build_parser()
    args = parser.parse_args()

    groups = discover_groups(args.input_root)
    if not groups:
        raise FileNotFoundError(f"No analyzable CSV groups found in {args.input_root}")

    if args.labels is not None and len(groups) > 1:
        raise ValueError("--labels can only be used when input-root points to a single group")

    ensure_dir(args.output_dir)
    group_summaries: list[dict[str, object]] = []
    for group_name, group_dir in groups.items():
        labels = args.labels if len(groups) == 1 else None
        summary = analyze_group(
            group_name=group_name,
            group_dir=group_dir,
            output_root=args.output_dir,
            channel_num=args.channel_num,
            bins_per_channel=args.bins_per_channel,
            top_k=args.top_k,
            labels=labels,
        )
        if summary is not None:
            group_summaries.append(summary)

    if group_summaries:
        write_csv(group_summaries, args.output_dir / "overall_group_summary.csv")
        with (args.output_dir / "overall_group_summary.json").open("w", encoding="utf-8") as handle:
            json.dump(group_summaries, handle, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
