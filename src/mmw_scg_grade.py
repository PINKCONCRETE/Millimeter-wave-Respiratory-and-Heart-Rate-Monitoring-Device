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
from scipy.signal import butter, filtfilt


class SCGGradeProcess(multiprocessing.Process):
    """SCG评分与自相关分析处理进程."""
    
    # 滤波参数
    SAMPLING_RATE = 200
    LOWCUT = 20
    HIGHCUT = 40
    FILTER_ORDER = 4
    
    # 缓冲区参数
    MIN_BUFFER_SIZE = 200 # 至少需要1秒数据
    MAX_BUFFER_SIZE = 1000
    OUTLIER_THRESHOLD = 1500
    TIME_STEP = 0.005

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

    def run(self) -> None:
        print("SCG评分进程已启动...")
        self._frame_buffer = deque(maxlen=self.MAX_BUFFER_SIZE)
        self._current_frame_build = None
        self._completed_frames = 0
        self._generated_scg_points = 0
        self._current_max_bin = 0
        self._current_score = 0.0
        self._current_offset = 0
        
        last_fps_time = time.time()
        last_fps_frame_count = 0
        
        try:
            while not self._stop_event.is_set():
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                    
                    now = time.time()
                    if now - last_fps_time >= 1.0:
                        fps = (self._completed_frames - last_fps_frame_count) / (now - last_fps_time)
                        print(f"[SCG] FPS: {fps:.1f}")
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
            self._current_frame_build = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            self._current_frame_build[channel_id] = data
            # Update offset if needed
            self._current_offset = frame_data.get("offset", 0)
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return
            
        if channel_id == self._channel_num - 1 and self._current_frame_build is not None:
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
        """计算相位差分（近似导数）."""
        unwrapped_phase = np.unwrap(phase_data)
        # 简单一阶差分
        return np.diff(unwrapped_phase, prepend=unwrapped_phase[0])

    def _compute_score_and_fft(self, signal: np.ndarray) -> tuple[float, np.ndarray, int]:
        fft_signal = signal - np.mean(signal)
        window = np.hanning(len(fft_signal))
        n_fft = 4096
        fft_result = np.fft.fft(fft_signal * window, n=n_fft)
        fft_magnitude = np.abs(fft_result)[:n_fft//2]
        if len(fft_signal) > 0:
            fft_magnitude = fft_magnitude / len(fft_signal) * 2
            
        idx_20hz = int(20 * n_fft / 200)
        energy_spectrum = fft_magnitude ** 2
        total_energy = np.sum(energy_spectrum)
        
        score = 0.0
        if total_energy > 0:
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            score = (low_freq_energy / total_energy) * 100.0
            
        return score, fft_magnitude, n_fft

    def _generate_new_scg_point(self) -> None:
        fft_data = np.array(self._frame_buffer)
        
        # Optimization: Only select best bin every 100 frames (0.5s)
        # Otherwise use current max bin
        if self._completed_frames % 100 == 0:
            current_selected_bin = self._current_max_bin if 0 <= self._current_max_bin < self._bins_per_channel else 0
            best_bin_idx = 0
            max_score = -1.0
            bin_results = {}
            
            for bin_idx in range(self._bins_per_channel):
                 phase_data = self._extract_phase(fft_data, bin_idx)
                 scg_waveform = self._compute_derivative_waveform(phase_data)
                 
                 outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
                 scg_waveform[outlier_idx] = 0.0
                 
                 score, fft_mag, n_fft = self._compute_score_and_fft(scg_waveform)
                 bin_results[bin_idx] = (score, scg_waveform, fft_mag, n_fft)
                 
                 if score > max_score:
                     max_score = score
                     best_bin_idx = bin_idx
            
            # Hysteresis logic
            current_bin_score = bin_results[current_selected_bin][0]
            HYSTERESIS_THRESHOLD = 5.0 # Score is now 0-100
            
            if max_score > current_bin_score + HYSTERESIS_THRESHOLD:
                final_bin_idx = best_bin_idx
                self._current_score = max_score
            else:
                final_bin_idx = current_selected_bin
                self._current_score = current_bin_score
                
            self._current_max_bin = final_bin_idx
        
        # Always compute waveform for the current selected bin (to get the latest point)
        # Note: We still compute the full waveform for the selected bin to ensure continuity/filtering
        # But we save computing 9 other bins 99% of the time.
        final_bin_idx = self._current_max_bin
        phase_data = self._extract_phase(fft_data, final_bin_idx)
        scg_waveform = self._compute_derivative_waveform(phase_data)
        outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
        scg_waveform[outlier_idx] = 0.0
        
        latest_value = scg_waveform[-1] # Use last value
        
        # Autocorrelation (Optional: Compute less frequently?)
        # Let's keep it for now as it might be needed for HR calculation if we move it here
        # But currently we don't send it.
            
        result = {
            "type": "scg_data",
            "frame_idx": self._generated_scg_points,
            #"scg_waveform": scg_waveform.tolist(), # Optimization: Don't send full waveform
            "isArrhythmia": 0,
            "scg_value": float(latest_value),
            #"autocorrelation": corr.tolist(), # Optimization: Don't send heavy data
            #"fft_magnitude": fft_magnitude.tolist(), # Optimization: Don't send heavy data
            "timestamp": self._generated_scg_points * self.TIME_STEP,
            "max_bin": final_bin_idx,
            "offset": self._current_offset,
            #"n_fft": n_fft,
            "score": self._current_score,
        }
        
        if not self._output_queue.full():
            self._output_queue.put(result)
        self._generated_scg_points += 1
