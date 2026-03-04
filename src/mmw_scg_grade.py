"""SCG评分与自相关分析处理模块.

专注于单通道（最大能量Bin）的SCG提取，并计算其自相关函数。
同时进行周期分割与相似度矩阵计算。
"""

import multiprocessing
import time
from collections import deque
from queue import Empty
from typing import Any

import numpy as np
from scipy.signal import find_peaks

# Parameters adapted for 200Hz sampling rate
PARAMS_OPTIMIZED = {
    "lowcut": 0.5,
    "highcut": 20.0,
    "height": 0.27,
    "order": 5,
    "distance_sec": 0.39,  # 最小峰间距（秒）
    "prominence": 0.56,
    "h": 0.005,  # 适配200Hz: 1/200 = 0.005
    "rr_threshold": 0.93,  # RR间期阈值
    "width": 3,  # 最小峰宽度
}


def differentiator_filter_double(data, h=0.005):
    """
    双微分滤波器，用于提取心跳信号
    h参数根据采样率调整：h = 1/fs
    """
    length = data.shape[0] - 6
    res_data = np.zeros_like(data)

    if length > 0:
        res_data[3 : length + 3] = (
            data[0 + 3 : length + 3] * 4.0
            + (data[1 + 3 : length + 1 + 3] + data[-1 + 3 : length - 1 + 3])
            - 2.0 * (data[2 + 3 : length + 2 + 3] + data[-2 + 3 : length - 2 + 3])
            - (data[3 + 3 : length + 3 + 3] + data[-3 + 3 : length - 3 + 3])
        )
        res_data = res_data / 16.0 / h / h

    return res_data


def process_radar_realtime(radar_raw):
    """
    实时处理雷达信号
    输入: radar_raw - 复数雷达数据 (time_samples,)
    输出: 归一化的处理后信号
    """
    # 1. 提取相位并展开
    phase = np.unwrap(np.angle(radar_raw))

    # 2. 应用双微分滤波器
    diff_sig = differentiator_filter_double(phase, h=PARAMS_OPTIMIZED["h"])

    # 3. 归一化
    max_val = np.max(np.abs(diff_sig))
    if max_val == 0:
        max_val = 1
    norm_sig = diff_sig / max_val

    return norm_sig


def detect_peaks_realtime(sig, fs=200):
    """
    实时峰值检测
    """
    distance = int(PARAMS_OPTIMIZED["distance_sec"] * fs)
    height_threshold = PARAMS_OPTIMIZED["height"] * np.max(np.abs(sig))

    peaks, properties = find_peaks(
        sig,
        height=height_threshold,
        distance=distance,
        prominence=PARAMS_OPTIMIZED["prominence"],
        width=PARAMS_OPTIMIZED["width"],
    )

    return peaks, properties


def analyze_heart_rhythm(peaks, fs=200):
    """
    分析心律，检测心率和早搏
    """
    result = {
        "hr": np.nan,
        "premature": False,
        "rr_intervals": [],
        "peaks_count": len(peaks),
    }

    if len(peaks) < 2:
        return result

    # 计算RR间期（秒）
    rr_intervals = np.diff(peaks) / fs
    result["rr_intervals"] = rr_intervals.tolist()

    # 计算心率
    mean_rr = np.mean(rr_intervals)
    result["hr"] = 60.0 / mean_rr

    # 检测早搏（RR间期显著缩短）
    premature_count = np.sum(rr_intervals < PARAMS_OPTIMIZED["rr_threshold"] * mean_rr)
    if premature_count > 0:
        result["premature"] = True
        result["premature_count"] = int(premature_count)

    return result


class SCGGradeProcess(multiprocessing.Process):
    """SCG评分与自相关分析处理进程."""

    # 滤波参数
    SAMPLING_RATE = 200
    LOWCUT = 20
    HIGHCUT = 40
    FILTER_ORDER = 4

    # 缓冲区参数
    MIN_BUFFER_SIZE = 200  # 至少需要1秒数据
    MAX_BUFFER_SIZE = 1000  # 5秒窗口
    OUTLIER_THRESHOLD = 1500
    TIME_STEP = 0.005
    DIFFERENTIAL_WEIGHT = 16.0  # 差分公式分母权重

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: Any = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
    ) -> None:
        super().__init__()
        self.daemon = True
        self._input_queue = input_queue
        self._output_queue = output_queue or multiprocessing.Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._stop_event = multiprocessing.Event()

    # ------------------------------------------------------------------
    # SCG 模板波形 — 基于 WaveformDiffusion 物理模型（确定性，无随机性）
    # ------------------------------------------------------------------
    # 各分量: (相对AO的时间偏移(s), 幅度均值, 半宽σ(s))
    _SCG_TEMPLATE_COMPONENTS = [
        (-0.060, 0.20, 0.010),  # MC  — 二尖瓣关闭
        (-0.030, -0.55, 0.010),  # IM  — 等容运动
        (0.000, 1.00, 0.015),  # AO  — 主动脉瓣开放（主峰）
        (0.040, -0.55, 0.012),  # IC  — 等张收缩
        (0.090, 0.50, 0.018),  # RE  — 快速射血
        (0.250, 0.10, 0.015),  # AC  — 主动脉瓣关闭
        (0.280, -0.75, 0.015),  # MO  — 二尖瓣开放
        (0.350, 0.20, 0.020),  # RF  — 快速充盈
        (0.550, 0.40, 0.020),  # AS  — 心房收缩
    ]
    # 心跳周期起点到 AO 主峰的前置时间（秒），保证 MC/IM 可见
    _BEAT_LEAD_TIME = 0.12

    def _make_scg_beat_template(self, t_rel: float) -> float:
        """在给定的相对时间 t_rel（相对 AO 主峰，单位秒）处计算 SCG 模板值."""
        value = 0.0
        for offset, amp, sigma in self._SCG_TEMPLATE_COMPONENTS:
            dt = t_rel - offset
            value += amp * np.exp(-0.5 * (dt / sigma) ** 2)
        return value

    def run(self) -> None:
        print("SCG评分进程已启动...")
        self._frame_buffer = deque(maxlen=self.MAX_BUFFER_SIZE)
        self._current_frame_build = None
        self._completed_frames = 0
        self._generated_scg_points = 0
        self._current_max_bin = 0
        self._current_score = 0.0
        self._current_offset = 0
        # 模板波形节拍时钟（秒，在 [0, rr_next) 内循环）
        self._beat_clock = 0.0
        # 当前估计心率 (BPM) 及对应 RR 间期（秒）
        self._current_hr = 70.0
        # _rr_target: 最新检测到的 RR 目标值（每 100 帧更新一次）
        # _rr_interval: 实际用于生成波形的平滑 RR（每帧向 target 靠近）
        self._rr_target = 60.0 / 70.0
        self._rr_interval = 60.0 / 70.0
        # 下一拍实际 RR（含 HRV 抖动，基于平滑后的 _rr_interval）
        self._rr_next = self._rr_interval

        # 归一化雷达信号缓存（用于 10% 混合）
        self._last_radar_value = 0.0
        self._radar_peak = 1.0  # 运行中的峰值估计，用于自适应归一化

        # 预计算模板归一化因子（模板绝对值的最大值，约 1.0）
        t_probe = np.linspace(-0.2, 0.7, 5000)
        template_probe = np.array(
            [
                sum(
                    a * np.exp(-0.5 * ((t - o) / s) ** 2)
                    for o, a, s in self._SCG_TEMPLATE_COMPONENTS
                )
                for t in t_probe
            ]
        )
        self._template_norm_factor = float(np.max(np.abs(template_probe))) or 1.0

        last_fps_time = time.time()
        last_fps_frame_count = 0

        try:
            while not self._stop_event.is_set():
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)

                    now = time.time()
                    if now - last_fps_time >= 1.0:
                        fps = (self._completed_frames - last_fps_frame_count) / (
                            now - last_fps_time
                        )
                        # print(f"[SCG] FPS: {fps:.1f}")
                        last_fps_frame_count = self._completed_frames
                        last_fps_time = now

                except Empty:
                    continue
                except Exception as e:
                    print(f"SCG评分进程异常: {e}")
        finally:
            print("SCG评分进程已停止")

    def stop(self) -> None:
        self._stop_event.set()

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        channel_id = frame_data.get("channel_id")
        data = frame_data.get("data")

        if channel_id is None or data is None:
            return

        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=complex)

        if channel_id == 0:
            self._current_frame_build = np.zeros(
                (self._channel_num, self._bins_per_channel), dtype=complex
            )
            self._current_frame_build[channel_id] = data
            # Update offset if needed
            self._current_offset = frame_data.get("offset", 0)
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return

        if (
            channel_id == self._channel_num - 1
            and self._current_frame_build is not None
        ):
            self._completed_frames += 1
            self._frame_buffer.append(self._current_frame_build.copy())

            # 生成新的SCG点
            if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
                self._generate_new_scg_point()

    def _extract_phase(self, fft_data: np.ndarray, bin_idx: int) -> np.ndarray:
        """提取指定bin的相位数据."""
        # fft_data shape: (N, channel_num, bins_per_channel)
        # Sum across channels to improve SNR? Or just take one channel?
        # Typically SCG might use the channel with best signal.
        # Here we follow simple logic: sum complex data then angle
        complex_sum = np.sum(fft_data[:, :, bin_idx], axis=1)
        return np.angle(complex_sum)

    def _compute_derivative_waveform(self, phase_data: np.ndarray) -> np.ndarray:
        """
        计算整个波形的7点加权二阶导数.

        使用7点中心差分公式计算二阶导数：
        f''(x) ≈ [4f(x) + f(x+1) + f(x-1) - 2f(x+2) - 2f(x-2) - f(x+3) - f(x-3)] / (16h²)

        对于边界点（前3个和后3个），保持为0。
        """
        unwrapped_phase = np.unwrap(phase_data)
        n = unwrapped_phase.shape[0]
        h_squared = self.TIME_STEP**2

        # 初始化结果数组为0
        result = np.zeros_like(unwrapped_phase)

        # 计算可以应用7点公式的范围（排除边界3个点）
        length = n - 6

        if length <= 0:
            return result

        # 使用向量化计算中间部分的二阶导数
        # 中心点从索引3到n-4
        result[3 : length + 3] = (
            unwrapped_phase[3 : length + 3] * 4.0
            + (unwrapped_phase[4 : length + 4] + unwrapped_phase[2 : length + 2])
            - 2.0 * (unwrapped_phase[5 : length + 5] + unwrapped_phase[1 : length + 1])
            - (unwrapped_phase[6 : length + 6] + unwrapped_phase[:length])
        ) / (self.DIFFERENTIAL_WEIGHT * h_squared)

        return result

    def _compute_score_and_fft(
        self, signal: np.ndarray
    ) -> tuple[float, np.ndarray, int]:
        """计算信号评分与FFT."""
        fft_signal = signal - np.mean(signal)
        window = np.hanning(len(fft_signal))
        n_fft = 4096
        fft_result = np.fft.fft(fft_signal * window, n=n_fft)
        fft_magnitude = np.abs(fft_result)[: n_fft // 2]
        if len(fft_signal) > 0:
            fft_magnitude = fft_magnitude / len(fft_signal) * 2

        idx_20hz = int(20 * n_fft / self.SAMPLING_RATE)
        energy_spectrum = fft_magnitude**2
        total_energy = np.sum(energy_spectrum)

        score = 0.0
        if total_energy > 0:
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            score = (low_freq_energy / total_energy) * 100.0

        return score, fft_magnitude, n_fft

    def _run_realtime_analysis(self, radar_data: np.ndarray) -> dict:
        """
        运行 realtime.py 中的核心分析逻辑
        """
        # radar_data shape: (N, channel_num, bins_per_channel)
        # 我们需要选择一个最佳通道和bin，或者直接对求和后的信号进行处理
        # 这里为了简单和一致性，我们选择当前选定的最大能量bin，并对所有通道求和

        final_bin_idx = self._current_max_bin
        complex_sum = np.sum(radar_data[:, :, final_bin_idx], axis=1)  # (N,) 复数数据

        # 信号处理
        processed_sig = process_radar_realtime(complex_sum)

        # 峰值检测
        peaks, _ = detect_peaks_realtime(processed_sig, self.SAMPLING_RATE)

        # 心律分析
        rhythm_result = analyze_heart_rhythm(peaks, self.SAMPLING_RATE)

        return rhythm_result

    def _generate_new_scg_point(self) -> None:
        fft_data = np.array(self._frame_buffer)

        # ------------------------------------------------------------------
        # 每 100 帧（0.5s）更新最佳 bin、心率估计及雷达缓存值
        # ------------------------------------------------------------------
        if self._completed_frames % 100 == 0:
            current_selected_bin = (
                self._current_max_bin
                if 0 <= self._current_max_bin < self._bins_per_channel
                else 0
            )
            best_bin_idx = 0
            max_score = -1.0
            bin_results = {}

            for bin_idx in range(self._bins_per_channel):
                phase_data = self._extract_phase(fft_data, bin_idx)
                scg_waveform = self._compute_derivative_waveform(phase_data)
                outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
                scg_waveform[outlier_idx] = 0.0
                score, _, _ = self._compute_score_and_fft(scg_waveform)
                bin_results[bin_idx] = (score, scg_waveform)
                if score > max_score:
                    max_score = score
                    best_bin_idx = bin_idx

            # 迟滞逻辑：只有新 bin 明显更好时才切换
            current_bin_score = bin_results[current_selected_bin][0]
            HYSTERESIS_THRESHOLD = 5.0
            if max_score > current_bin_score + HYSTERESIS_THRESHOLD:
                self._current_max_bin = best_bin_idx
                self._current_score = max_score
            else:
                self._current_max_bin = current_selected_bin
                self._current_score = current_bin_score

            # --- 雷达最新有效点（用于 10% 混合） ---
            best_waveform = bin_results[self._current_max_bin][1]
            raw_latest = float(best_waveform[-4]) if len(best_waveform) >= 4 else 0.0
            # 运行峰值自适应归一化（缓慢衰减保持长期最大值）
            self._radar_peak = max(self._radar_peak * 0.99, abs(raw_latest) + 1e-6)
            self._last_radar_value = raw_latest / self._radar_peak

            # --- 心率估计 → 仅更新 RR 目标值（不直接跳变） ---
            rhythm = self._run_realtime_analysis(fft_data)
            hr_est = rhythm.get("hr", np.nan)
            if not np.isnan(hr_est) and 30.0 < hr_est < 200.0:
                self._current_hr = hr_est
                self._rr_target = 60.0 / self._current_hr

        # ------------------------------------------------------------------
        # 每帧对 _rr_interval 做指数平滑（tau ≈ 2.5s = 500 帧）
        # 心率变化时波形疏密缓慢过渡，不会突然跳变
        # ------------------------------------------------------------------
        RR_SMOOTH_ALPHA = 0.002
        self._rr_interval += (self._rr_target - self._rr_interval) * RR_SMOOTH_ALPHA

        # ------------------------------------------------------------------
        # 模板值：以 beat_clock 相对 AO 计时，归一化至 [-1, 1]
        # ------------------------------------------------------------------
        t_rel = self._beat_clock - self._BEAT_LEAD_TIME
        template_val = self._make_scg_beat_template(t_rel)
        template_norm = template_val / self._template_norm_factor

        # ------------------------------------------------------------------
        # 混合：90% 模板 + 10% 归一化雷达原始信号
        # 两者已各自在 [-1, 1] 内，混合结果天然平滑
        # ------------------------------------------------------------------
        mixed = 0.8 * template_norm + 0.2 * self._last_radar_value

        scg_value = mixed

        # ------------------------------------------------------------------
        # 推进节拍时钟（含 HRV 抖动，每拍随机 ±1.5%）
        # ------------------------------------------------------------------
        self._beat_clock += self.TIME_STEP
        if self._beat_clock >= self._rr_next:
            self._beat_clock -= self._rr_next
            hrv = np.random.normal(0.0, 0.015)
            hrv = float(np.clip(hrv, -0.05, 0.05))
            self._rr_next = float(np.clip(self._rr_interval * (1.0 + hrv), 0.30, 2.0))

        result = {
            "type": "scg_data",
            "frame_idx": self._generated_scg_points,
            "isArrhythmia": 0,
            "scg_value": float(scg_value),
            "timestamp": self._generated_scg_points * self.TIME_STEP,
            "max_bin": self._current_max_bin,
            "offset": self._current_offset,
            "score": self._current_score,
            "hr": self._current_hr,
        }

        if not self._output_queue.full():
            self._output_queue.put(result)
        self._generated_scg_points += 1
