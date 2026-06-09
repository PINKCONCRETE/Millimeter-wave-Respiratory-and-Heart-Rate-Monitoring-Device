"""Offline scan analysis for millimeter-wave raw byte captures.

This module decodes raw serial-byte CSV captures using the same frame protocol
as ``src/mmw_radar.py`` and exports:

1. Per-frame amplitude/phase CSV files for every channel/bin.
2. Per-position channel/bin summary metrics.
3. Respiration and SCG candidate waveforms.
4. Scan-level ranking for robotic localization.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.signal import butter, detrend, filtfilt

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - plotting is optional at runtime
    plt = None


@dataclass
class ChannelPacket:
    """One decoded channel packet."""

    timestamp: float
    channel_id: int
    offset: int
    data: np.ndarray


@dataclass
class DecodedCapture:
    """Decoded frames for one capture file."""

    source_file: Path
    position_index: int
    position_cm: float
    timestamps: np.ndarray
    offsets: np.ndarray
    complex_cube: np.ndarray
    packet_count: int
    discarded_packets: int


class OfflineRadarDecoder:
    """Byte-wise frame decoder matching the mmWave UART state machine."""

    STATE_WAITING_DLC_LOW = 0
    STATE_WAITING_DLC_HIGH = 1
    STATE_WAITING_BIN_ID = 2
    STATE_WAITING_OFFSET = 3
    STATE_CHECK_OFFSET = 4
    STATE_GET_REAL_LOW = 5
    STATE_GET_REAL_HIGH = 6
    STATE_GET_IMAG_LOW = 7
    STATE_GET_IMAG_HIGH = 8

    def __init__(self, channel_num: int = 8, bins_per_channel: int = 10) -> None:
        self.channel_num = channel_num
        self.bins_per_channel = bins_per_channel
        self.state = self.STATE_WAITING_DLC_LOW
        self._temp_bins_count = 0
        self._temp_channel_id = 0
        self._temp_offset = 0
        self._temp_real = 0
        self._temp_imag = 0
        self._complex_count = 0
        self._temp_complexes: list[complex] = []

    def feed(self, byte_value: int, timestamp: float) -> ChannelPacket | None:
        """Feed one byte and return a decoded channel packet when complete."""

        if self.state == self.STATE_WAITING_DLC_LOW:
            self._temp_bins_count = byte_value
            self.state = self.STATE_WAITING_DLC_HIGH
            return None

        if self.state == self.STATE_WAITING_DLC_HIGH:
            self._temp_bins_count |= byte_value << 8
            if self._temp_bins_count == self.bins_per_channel:
                self.state = self.STATE_WAITING_BIN_ID
            else:
                self.state = self.STATE_WAITING_DLC_LOW
            return None

        if self.state == self.STATE_WAITING_BIN_ID:
            self._temp_channel_id = byte_value
            if self._temp_channel_id >= self.channel_num:
                self.state = self.STATE_WAITING_DLC_LOW
                return None

            if self._temp_channel_id == 0:
                self.state = self.STATE_WAITING_OFFSET
            else:
                self.state = self.STATE_CHECK_OFFSET
            return None

        if self.state == self.STATE_WAITING_OFFSET:
            self._temp_offset = byte_value
            self._complex_count = 0
            self._temp_complexes = []
            self.state = self.STATE_GET_REAL_LOW
            return None

        if self.state == self.STATE_CHECK_OFFSET:
            if byte_value == 0:
                self._complex_count = 0
                self._temp_complexes = []
                self.state = self.STATE_GET_REAL_LOW
            else:
                self.state = self.STATE_WAITING_DLC_LOW
            return None

        if self.state == self.STATE_GET_REAL_LOW:
            self._temp_real = byte_value
            self.state = self.STATE_GET_REAL_HIGH
            return None

        if self.state == self.STATE_GET_REAL_HIGH:
            self._temp_real |= byte_value << 8
            self._temp_real = struct.unpack("<h", struct.pack("<H", self._temp_real))[0]
            self.state = self.STATE_GET_IMAG_LOW
            return None

        if self.state == self.STATE_GET_IMAG_LOW:
            self._temp_imag = byte_value
            self.state = self.STATE_GET_IMAG_HIGH
            return None

        if self.state == self.STATE_GET_IMAG_HIGH:
            self._temp_imag |= byte_value << 8
            self._temp_imag = struct.unpack("<h", struct.pack("<H", self._temp_imag))[0]
            self._temp_complexes.append(complex(self._temp_real, self._temp_imag))
            self._complex_count += 1

            if self._complex_count < self._temp_bins_count:
                self.state = self.STATE_GET_REAL_LOW
                return None

            packet = ChannelPacket(
                timestamp=timestamp,
                channel_id=self._temp_channel_id,
                offset=self._temp_offset,
                data=np.asarray(self._temp_complexes, dtype=np.complex128),
            )
            self.state = self.STATE_WAITING_DLC_LOW
            return packet

        return None


def numeric_file_key(path: Path) -> tuple[int, str]:
    """Sort capture files by numeric prefix."""

    match = re.match(r"^(\d+)_", path.name)
    if match:
        return int(match.group(1)), path.name
    return 10**9, path.name


def ensure_dir(path: Path) -> None:
    """Create a directory if missing."""

    path.mkdir(parents=True, exist_ok=True)


def safe_bandpass(
    signal_data: np.ndarray,
    fs: float,
    lowcut: float,
    highcut: float,
    order: int = 4,
) -> np.ndarray:
    """Apply a stable band-pass filter when enough samples are available."""

    if signal_data.size == 0:
        return signal_data

    nyquist = 0.5 * fs
    low = max(lowcut / nyquist, 1e-6)
    high = min(highcut / nyquist, 0.999)
    if low >= high:
        return signal_data - np.mean(signal_data)

    b, a = butter(order, [low, high], btype="band")
    min_samples = 3 * (max(len(a), len(b)) - 1) + 1
    if signal_data.size < min_samples:
        return signal_data - np.mean(signal_data)
    return filtfilt(b, a, signal_data)


def differentiator_filter_double(data: np.ndarray, h: float) -> np.ndarray:
    """Seven-point second-order differentiator."""

    result = np.zeros_like(data, dtype=float)
    length = data.shape[0] - 6
    if length <= 0:
        return result

    result[3 : length + 3] = (
        data[3 : length + 3] * 4.0
        + (data[4 : length + 4] + data[2 : length + 2])
        - 2.0 * (data[5 : length + 5] + data[1 : length + 1])
        - (data[6 : length + 6] + data[:length])
    ) / (16.0 * h * h)
    return result


def compute_spectrum(signal_data: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Return one-sided frequency axis and power spectrum."""

    if signal_data.size == 0:
        return np.array([]), np.array([])

    centered = signal_data - np.mean(signal_data)
    window = np.hanning(centered.size)
    spectrum = np.fft.rfft(centered * window)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(centered.size, d=1.0 / fs)
    return freqs, power


def compute_respiration_metrics(
    unwrapped_phase: np.ndarray,
    fs: float,
) -> tuple[np.ndarray, float, float, float]:
    """Compute respiration waveform, score, dominant bpm and band energy."""

    corrected = detrend(unwrapped_phase)
    filtered = safe_bandpass(corrected, fs=fs, lowcut=0.10, highcut=0.60, order=2)
    freqs, power = compute_spectrum(filtered, fs)

    if freqs.size == 0:
        return filtered, 0.0, 0.0, 0.0

    band_mask = (freqs >= 0.10) & (freqs <= 0.60)
    total_mask = (freqs >= 0.05) & (freqs <= 2.00)
    if not np.any(band_mask):
        return filtered, 0.0, 0.0, 0.0

    band_power = float(np.sum(power[band_mask]))
    total_power = float(np.sum(power[total_mask])) if np.any(total_mask) else 0.0
    band_freqs = freqs[band_mask]
    band_power_values = power[band_mask]
    peak_index = int(np.argmax(band_power_values))
    dominant_freq = float(band_freqs[peak_index])
    dominant_bpm = dominant_freq * 60.0
    peak_power = float(band_power_values[peak_index])
    score = peak_power / total_power if total_power > 0 else 0.0
    return filtered, score, dominant_bpm, band_power


def compute_autocorr_peak(signal_data: np.ndarray, fs: float) -> tuple[float, float]:
    """Compute heartbeat-like periodicity score and dominant bpm."""

    if signal_data.size < int(fs):
        return 0.0, 0.0

    centered = signal_data - np.mean(signal_data)
    peak_scale = np.max(np.abs(centered))
    if peak_scale == 0:
        return 0.0, 0.0

    normalized = centered / peak_scale
    autocorr = np.correlate(normalized, normalized, mode="full")[normalized.size - 1 :]
    if autocorr[0] == 0:
        return 0.0, 0.0

    autocorr = autocorr / autocorr[0]
    min_lag = max(1, int(fs * 60.0 / 150.0))
    max_lag = min(autocorr.size - 1, int(fs * 60.0 / 40.0))
    if max_lag <= min_lag:
        return 0.0, 0.0

    search = autocorr[min_lag : max_lag + 1]
    peak_rel_index = int(np.argmax(search))
    peak_value = float(search[peak_rel_index])
    lag = min_lag + peak_rel_index
    dominant_bpm = 60.0 * fs / lag if lag > 0 else 0.0
    return max(peak_value, 0.0), dominant_bpm


def compute_scg_metrics(
    unwrapped_phase: np.ndarray,
    fs: float,
) -> tuple[np.ndarray, float, float, float]:
    """Compute SCG-like waveform, score, dominant bpm and RMS."""

    derivative = differentiator_filter_double(unwrapped_phase, h=1.0 / fs)
    derivative[np.abs(derivative) > 1500] = 0.0
    filtered = safe_bandpass(derivative, fs=fs, lowcut=8.0, highcut=35.0, order=4)
    score, dominant_bpm = compute_autocorr_peak(filtered, fs)
    rms = float(np.sqrt(np.mean(np.square(filtered)))) if filtered.size else 0.0
    return filtered, score, dominant_bpm, rms


def iter_capture_rows(file_path: Path) -> Iterable[tuple[float, list[int]]]:
    """Yield timestamp and raw byte batches from a capture CSV file."""

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = float(row["timestamp"])
            raw_bytes = ast.literal_eval(row["raw_bytes"])
            yield timestamp, raw_bytes


def decode_capture_file(
    file_path: Path,
    position_index: int,
    position_cm: float,
    channel_num: int,
    bins_per_channel: int,
) -> DecodedCapture:
    """Decode one raw-byte capture file into complete complex frames."""

    decoder = OfflineRadarDecoder(channel_num=channel_num, bins_per_channel=bins_per_channel)
    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    offsets: list[int] = []
    packet_count = 0
    discarded_packets = 0

    current_frame: np.ndarray | None = None
    current_offset = 0
    seen_channels: set[int] = set()

    for batch_timestamp, raw_bytes in iter_capture_rows(file_path):
        for byte_value in raw_bytes:
            packet = decoder.feed(int(byte_value), batch_timestamp)
            if packet is None:
                continue

            packet_count += 1
            if packet.channel_id == 0:
                current_frame = np.zeros((channel_num, bins_per_channel), dtype=np.complex128)
                current_offset = packet.offset
                seen_channels = set()

            if current_frame is None:
                discarded_packets += 1
                continue

            current_frame[packet.channel_id, :] = packet.data
            seen_channels.add(packet.channel_id)

            if packet.channel_id == channel_num - 1 and len(seen_channels) == channel_num:
                frames.append(current_frame.copy())
                timestamps.append(packet.timestamp)
                offsets.append(current_offset)
                current_frame = None
                seen_channels = set()

    complex_cube = (
        np.stack(frames, axis=0)
        if frames
        else np.zeros((0, channel_num, bins_per_channel), dtype=np.complex128)
    )
    return DecodedCapture(
        source_file=file_path,
        position_index=position_index,
        position_cm=position_cm,
        timestamps=np.asarray(timestamps, dtype=float),
        offsets=np.asarray(offsets, dtype=int),
        complex_cube=complex_cube,
        packet_count=packet_count,
        discarded_packets=discarded_packets,
    )


def export_amp_phase_csv(capture: DecodedCapture, output_path: Path) -> None:
    """Export per-frame amplitude and phase for all channel/bin pairs."""

    frame_count = capture.complex_cube.shape[0]
    if frame_count == 0:
        return

    channels = capture.complex_cube.shape[1]
    bins_per_channel = capture.complex_cube.shape[2]
    amplitudes = np.abs(capture.complex_cube).reshape(frame_count, channels * bins_per_channel)
    phases = np.angle(capture.complex_cube).reshape(frame_count, channels * bins_per_channel)

    interleaved = np.empty((frame_count, amplitudes.shape[1] * 2), dtype=float)
    interleaved[:, 0::2] = amplitudes
    interleaved[:, 1::2] = phases

    prefix = np.column_stack(
        [
            np.arange(frame_count, dtype=float),
            capture.timestamps.astype(float),
            capture.offsets.astype(float),
        ]
    )
    export_array = np.column_stack([prefix, interleaved])

    header = ["frame_index", "timestamp", "offset"]
    for channel_id in range(channels):
        for bin_id in range(bins_per_channel):
            header.append(f"channel_{channel_id}_bin_{bin_id}_amplitude")
            header.append(f"channel_{channel_id}_bin_{bin_id}_phase")

    np.savetxt(
        output_path,
        export_array,
        delimiter=",",
        header=",".join(header),
        comments="",
        fmt="%.10f",
    )


def save_waveform_csv(
    output_path: Path,
    time_axis: np.ndarray,
    raw_phase: np.ndarray,
    unwrapped_phase: np.ndarray,
    waveform: np.ndarray,
) -> None:
    """Save waveform traces for one selected candidate."""

    export_array = np.column_stack([time_axis, raw_phase, unwrapped_phase, waveform])
    np.savetxt(
        output_path,
        export_array,
        delimiter=",",
        header="time_s,raw_phase,unwrapped_phase,processed_waveform",
        comments="",
        fmt="%.10f",
    )


def plot_position_heatmaps(
    capture: DecodedCapture,
    amp_mean: np.ndarray,
    phase_std: np.ndarray,
    resp_score: np.ndarray,
    scg_score: np.ndarray,
    output_path: Path,
) -> None:
    """Plot per-position heatmaps."""

    if plt is None:
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    panels = [
        ("Mean amplitude", amp_mean),
        ("Phase std", phase_std),
        ("Respiration score", resp_score),
        ("SCG score", scg_score),
    ]
    for ax, (title, panel) in zip(axes.ravel(), panels):
        image = ax.imshow(panel, aspect="auto", cmap="viridis")
        ax.set_title(title)
        ax.set_xlabel("Bin")
        ax.set_ylabel("Channel")
        ax.set_xticks(np.arange(panel.shape[1]))
        ax.set_yticks(np.arange(panel.shape[0]))
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(
        f"Position {capture.position_index} ({capture.position_cm:.1f} cm) - {capture.source_file.name}"
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_scan_summary(position_rows: list[dict[str, float]], output_path: Path) -> None:
    """Plot scan-level respiration / SCG / combined scores."""

    if plt is None or not position_rows:
        return

    positions = np.asarray([row["position_cm"] for row in position_rows], dtype=float)
    resp_scores = np.asarray([row["best_resp_score"] for row in position_rows], dtype=float)
    scg_scores = np.asarray([row["best_scg_score"] for row in position_rows], dtype=float)
    combined_scores = np.asarray([row["combined_position_score"] for row in position_rows], dtype=float)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(positions, resp_scores, marker="o", label="Respiration score")
    ax.plot(positions, scg_scores, marker="s", label="SCG score")
    ax.plot(positions, combined_scores, marker="^", label="Combined localization score")
    ax.set_xlabel("Robot scan position (cm)")
    ax.set_ylabel("Score")
    ax.set_title("Robotic scan ranking")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def analyze_capture(
    capture: DecodedCapture,
    output_root: Path,
    fs: float,
) -> tuple[list[dict[str, float]], dict[str, float], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Analyze one decoded capture and export its artifacts."""

    frame_count, channel_num, bins_per_channel = capture.complex_cube.shape
    if frame_count == 0:
        return [], {}, np.zeros((channel_num, bins_per_channel)), np.zeros((channel_num, bins_per_channel)), np.zeros((channel_num, bins_per_channel)), np.zeros((channel_num, bins_per_channel))

    amplitude = np.abs(capture.complex_cube)
    raw_phase = np.angle(capture.complex_cube)
    unwrapped_phase = np.unwrap(raw_phase, axis=0)

    amp_mean = amplitude.mean(axis=0)
    phase_std = unwrapped_phase.std(axis=0)
    resp_score_map = np.zeros((channel_num, bins_per_channel), dtype=float)
    scg_score_map = np.zeros((channel_num, bins_per_channel), dtype=float)

    per_position_dir = output_root / f"position_{capture.position_index:02d}"
    ensure_dir(per_position_dir)

    np.savez_compressed(
        per_position_dir / f"{capture.source_file.stem}_complex_cube.npz",
        timestamps=capture.timestamps,
        offsets=capture.offsets,
        complex_cube=capture.complex_cube,
    )
    export_amp_phase_csv(capture, per_position_dir / f"{capture.source_file.stem}_amp_phase.csv")

    summary_rows: list[dict[str, float]] = []
    time_axis = capture.timestamps - capture.timestamps[0]
    best_resp_payload: dict[str, object] | None = None
    best_scg_payload: dict[str, object] | None = None

    for channel_id in range(channel_num):
        for bin_id in range(bins_per_channel):
            raw_phase_trace = raw_phase[:, channel_id, bin_id]
            unwrapped_trace = unwrapped_phase[:, channel_id, bin_id]

            resp_waveform, resp_score, resp_bpm, resp_band_power = compute_respiration_metrics(
                unwrapped_trace, fs
            )
            scg_waveform, scg_score, scg_bpm, scg_rms = compute_scg_metrics(unwrapped_trace, fs)

            resp_score_map[channel_id, bin_id] = resp_score
            scg_score_map[channel_id, bin_id] = scg_score

            row = {
                "position_index": capture.position_index,
                "position_cm": capture.position_cm,
                "channel": channel_id,
                "bin": bin_id,
                "frame_count": frame_count,
                "offset_mean": float(np.mean(capture.offsets)),
                "amplitude_mean": float(amp_mean[channel_id, bin_id]),
                "amplitude_std": float(amplitude[:, channel_id, bin_id].std()),
                "unwrapped_phase_std": float(phase_std[channel_id, bin_id]),
                "respiration_score": float(resp_score),
                "respiration_bpm": float(resp_bpm),
                "respiration_band_power": float(resp_band_power),
                "scg_score": float(scg_score),
                "scg_bpm": float(scg_bpm),
                "scg_rms": float(scg_rms),
            }
            summary_rows.append(row)

            if best_resp_payload is None or resp_score > float(best_resp_payload["score"]):
                best_resp_payload = {
                    "channel": channel_id,
                    "bin": bin_id,
                    "score": float(resp_score),
                    "bpm": float(resp_bpm),
                    "raw_phase": raw_phase_trace.copy(),
                    "unwrapped_phase": unwrapped_trace.copy(),
                    "waveform": resp_waveform.copy(),
                }

            if best_scg_payload is None or scg_score > float(best_scg_payload["score"]):
                best_scg_payload = {
                    "channel": channel_id,
                    "bin": bin_id,
                    "score": float(scg_score),
                    "bpm": float(scg_bpm),
                    "raw_phase": raw_phase_trace.copy(),
                    "unwrapped_phase": unwrapped_trace.copy(),
                    "waveform": scg_waveform.copy(),
                }

    summary_csv = per_position_dir / f"{capture.source_file.stem}_channel_bin_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(summary_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    plot_position_heatmaps(
        capture=capture,
        amp_mean=amp_mean,
        phase_std=phase_std,
        resp_score=resp_score_map,
        scg_score=scg_score_map,
        output_path=per_position_dir / f"{capture.source_file.stem}_heatmaps.png",
    )

    position_summary = {
        "source_file": capture.source_file.name,
        "position_index": capture.position_index,
        "position_cm": capture.position_cm,
        "frame_count": frame_count,
        "packet_count": capture.packet_count,
        "discarded_packets": capture.discarded_packets,
        "offset_min": int(np.min(capture.offsets)),
        "offset_max": int(np.max(capture.offsets)),
        "best_resp_channel": int(best_resp_payload["channel"]) if best_resp_payload else -1,
        "best_resp_bin": int(best_resp_payload["bin"]) if best_resp_payload else -1,
        "best_resp_score": float(best_resp_payload["score"]) if best_resp_payload else 0.0,
        "best_resp_bpm": float(best_resp_payload["bpm"]) if best_resp_payload else 0.0,
        "best_scg_channel": int(best_scg_payload["channel"]) if best_scg_payload else -1,
        "best_scg_bin": int(best_scg_payload["bin"]) if best_scg_payload else -1,
        "best_scg_score": float(best_scg_payload["score"]) if best_scg_payload else 0.0,
        "best_scg_bpm": float(best_scg_payload["bpm"]) if best_scg_payload else 0.0,
    }
    position_summary["combined_position_score"] = (
        0.5 * position_summary["best_resp_score"] + 0.5 * position_summary["best_scg_score"]
    )

    if best_resp_payload is not None:
        save_waveform_csv(
            per_position_dir / f"{capture.source_file.stem}_best_resp_waveform.csv",
            time_axis,
            np.asarray(best_resp_payload["raw_phase"], dtype=float),
            np.asarray(best_resp_payload["unwrapped_phase"], dtype=float),
            np.asarray(best_resp_payload["waveform"], dtype=float),
        )

    if best_scg_payload is not None:
        save_waveform_csv(
            per_position_dir / f"{capture.source_file.stem}_best_scg_waveform.csv",
            time_axis,
            np.asarray(best_scg_payload["raw_phase"], dtype=float),
            np.asarray(best_scg_payload["unwrapped_phase"], dtype=float),
            np.asarray(best_scg_payload["waveform"], dtype=float),
        )

    return summary_rows, position_summary, amp_mean, phase_std, resp_score_map, scg_score_map


def write_scan_summary(
    output_root: Path,
    position_rows: list[dict[str, float]],
    channel_bin_rows: list[dict[str, float]],
) -> None:
    """Write scan-level CSV and JSON summaries."""

    ensure_dir(output_root)
    if position_rows:
        with (output_root / "scan_summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(position_rows[0].keys()))
            writer.writeheader()
            writer.writerows(position_rows)

        ranking_rows = sorted(
            position_rows, key=lambda row: float(row["combined_position_score"]), reverse=True
        )
        with (output_root / "scan_ranking.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ranking_rows[0].keys()))
            writer.writeheader()
            writer.writerows(ranking_rows)

        plot_scan_summary(position_rows, output_root / "scan_ranking.png")

    if channel_bin_rows:
        with (output_root / "scan_channel_bin_summary.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(channel_bin_rows[0].keys()))
            writer.writeheader()
            writer.writerows(channel_bin_rows)

    best_position = (
        max(position_rows, key=lambda row: float(row["combined_position_score"]))
        if position_rows
        else None
    )
    metadata = {
        "best_position": best_position,
        "positions_analyzed": len(position_rows),
        "channel_bin_candidates": len(channel_bin_rows),
    }
    with (output_root / "scan_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Offline mmWave robotic scan analysis")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing raw-byte CSV capture files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory used to store decoded exports and scan summaries.",
    )
    parser.add_argument(
        "--position-step-cm",
        type=float,
        default=5.0,
        help="Mechanical-arm scan step between files, in centimeters.",
    )
    parser.add_argument(
        "--position-start-cm",
        type=float,
        default=0.0,
        help="Physical position of the first file, in centimeters.",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        default=200.0,
        help="Frame sampling rate in Hz.",
    )
    parser.add_argument(
        "--channel-num",
        type=int,
        default=8,
        help="Number of radar channels.",
    )
    parser.add_argument(
        "--bins-per-channel",
        type=int,
        default=10,
        help="Number of range bins per channel.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Optional limit for debugging. 0 means all files.",
    )
    return parser


def main() -> None:
    """Run the full scan analysis pipeline."""

    parser = build_arg_parser()
    args = parser.parse_args()

    ensure_dir(args.output_dir)
    scan_summary_dir = args.output_dir / "summary"
    ensure_dir(scan_summary_dir)

    capture_files = [
        path
        for path in sorted(args.input_dir.glob("*.csv"), key=numeric_file_key)
        if re.match(r"^\d+_.*\.csv$", path.name)
    ]
    if args.max_files > 0:
        capture_files = capture_files[: args.max_files]

    if not capture_files:
        raise FileNotFoundError(f"No raw-byte CSV files found in {args.input_dir}")

    position_rows: list[dict[str, float]] = []
    channel_bin_rows: list[dict[str, float]] = []

    for zero_based_index, capture_file in enumerate(capture_files):
        position_index = zero_based_index + 1
        position_cm = args.position_start_cm + zero_based_index * args.position_step_cm
        capture = decode_capture_file(
            file_path=capture_file,
            position_index=position_index,
            position_cm=position_cm,
            channel_num=args.channel_num,
            bins_per_channel=args.bins_per_channel,
        )
        rows, position_summary, _, _, _, _ = analyze_capture(
            capture=capture,
            output_root=args.output_dir,
            fs=args.sampling_rate,
        )
        if rows:
            channel_bin_rows.extend(rows)
        if position_summary:
            position_rows.append(position_summary)

    write_scan_summary(
        output_root=scan_summary_dir,
        position_rows=position_rows,
        channel_bin_rows=channel_bin_rows,
    )


if __name__ == "__main__":
    main()
