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
import pywt
from scipy.signal import butter, filtfilt, find_peaks, correlate, lfilter, lfilter_zi, savgol_filter

# Parameters adapted for 200Hz sampling rate
PARAMS_OPTIMIZED = {
    'lowcut': 0.5,
    'highcut': 20.0,
    'height': 0.27,
    'order': 5,
    'distance_sec': 0.39,  # 最小峰间距（秒）
    'prominence': 0.56,
    'h': 0.005,  # 适配200Hz: 1/200 = 0.005
    'rr_threshold': 0.93,  # RR间期阈值
    'width': 3,  # 最小峰宽度
}


def differentiator_filter_double(data, h=0.005):
    """
    双微分滤波器，用于提取心跳信号
    h参数根据采样率调整：h = 1/fs
    """
    length = data.shape[0] - 6
    res_data = np.zeros_like(data)
    
    if length > 0:
        res_data[3:length+3] = data[0+3:length+3] * 4.0 + \
                               (data[1+3:length+1+3] + data[-1+3:length-1+3]) - \
                               2.0 * (data[2+3:length+2+3] + data[-2+3:length-2+3]) - \
                               (data[3+3:length+3+3] + data[-3+3:length-3+3])
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
    diff_sig = differentiator_filter_double(phase, h=PARAMS_OPTIMIZED['h'])
    
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
    distance = int(PARAMS_OPTIMIZED['distance_sec'] * fs)
    height_threshold = PARAMS_OPTIMIZED['height'] * np.max(np.abs(sig))
    
    peaks, properties = find_peaks(
        sig, 
        height=height_threshold, 
        distance=distance,
        prominence=PARAMS_OPTIMIZED['prominence'],
        width=PARAMS_OPTIMIZED['width']
    )
    
    return peaks, properties


def analyze_heart_rhythm(peaks, fs=200):
    """
    分析心律，检测心率和早搏
    """
    result = {
        'hr': np.nan,
        'premature': False,
        'rr_intervals': [],
        'peaks_count': len(peaks)
    }
    
    if len(peaks) < 2:
        return result
    
    # 计算RR间期（秒）
    rr_intervals = np.diff(peaks) / fs
    result['rr_intervals'] = rr_intervals.tolist()
    
    # 计算心率
    mean_rr = np.mean(rr_intervals)
    result['hr'] = 60.0 / mean_rr
    
    # 检测早搏（RR间期显著缩短）
    premature_count = np.sum(rr_intervals < PARAMS_OPTIMIZED['rr_threshold'] * mean_rr)
    if premature_count > 0:
        result['premature'] = True
        result['premature_count'] = int(premature_count)
    
    return result


class SCGGradeProcess(multiprocessing.Process):
    """SCG评分与自相关分析处理进程."""
    
    # 滤波参数
    SAMPLING_RATE = 200
    WINDOW_SECONDS = 5 # 窗口长度（秒）
    LOWCUT = 20
    HIGHCUT = 40
    FILTER_ORDER = 4
    
    # 缓冲区参数
    MIN_BUFFER_SIZE = int(SAMPLING_RATE * 1.0) # 至少需要1秒数据
    MAX_BUFFER_SIZE = int(SAMPLING_RATE * WINDOW_SECONDS) # 5秒窗口
    OUTLIER_THRESHOLD = 1500
    TIME_STEP = 0.005
    # Savitzky-Golay 滤波器参数
    # 增加点数可以提高抗噪性，但过大会平滑掉AO/AC峰细节
    # 31点 @ 200Hz = 155ms，适合保留主峰特征同时滤除高频噪声
    SAVGOL_WINDOW = 7 
    SAVGOL_POLYORDER = 3

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

    def _generate_scg_template(self) -> np.ndarray:
        """
        生成高精度 SCG (加速度) 心跳模板.
        基于文献模型 (e.g., IEEE T-BME, EMBC) 优化参数.
        fs = 200Hz
        """
        fs = self.SAMPLING_RATE
        duration = 0.6 # 秒
        t = np.linspace(0, duration, int(fs * duration))
        
        # 优化后的参数 (基于加速度信号)
        # AO Peak (Aortic Opening):
        #   - 频率: 较高 (25-35Hz)
        #   - 位置: ~0.1s (相对于R峰，这里相对于模板开始)
        #   - 幅度: 1.0 (归一化基准)
        ao_center = 0.12
        ao_sigma = 0.015 # 锐利的峰
        ao_freq = 30.0
        ao_wave = 1.0 * np.exp(-((t - ao_center)**2) / (2 * ao_sigma**2)) * np.cos(2 * np.pi * ao_freq * (t - ao_center))
        
        # AC Peak (Aortic Closing):
        #   - 频率: 较低 (10-15Hz)
        #   - 位置: AO后约 280-320ms (LVET) -> 0.12 + 0.30 = 0.42s
        #   - 幅度: 0.6-0.8
        ac_center = 0.42
        ac_sigma = 0.025 # 较宽的峰
        ac_freq = 12.0
        ac_wave = 0.7 * np.exp(-((t - ac_center)**2) / (2 * ac_sigma**2)) * np.cos(2 * np.pi * ac_freq * (t - ac_center))
        
        # 组合 AO + AC
        template = ao_wave + ac_wave
        
        # 移除直流分量
        template = template - np.mean(template)
        
        return template

    def _apply_matched_filter(self, signal: np.ndarray) -> np.ndarray:
        """
        应用匹配滤波器 (Matched Filter).
        """
        if len(signal) < self.SAMPLING_RATE:
            return signal
            
        template = self._generate_scg_template()
        
        # 互相关
        filtered = correlate(signal, template, mode='same')
        
        # 能量归一化: 保持与原信号能量一致，避免幅度失真
        if np.std(filtered) > 1e-6:
             filtered = filtered / np.std(filtered) * np.std(signal)
             
        return filtered

    def _compute_derivative_waveform(self, phase_data: np.ndarray) -> np.ndarray:
        """
        计算相位二阶差分 (加速度) 并进行小波去噪 + 匹配滤波.
        
        流程:
        1. Phase -> Acceleration (Savitzky-Golay Differentiator)
           - 使用 Savitzky-Golay 滤波器替代简单的7点差分
           - 优势: 在计算微分的同时进行多项式平滑，利用更多点数(如31点)有效抗噪
        2. Wavelet Denoising (1-40Hz Bandpass)
        3. Matched Filtering (AO/AC Template)
        """
        unwrapped_phase = np.unwrap(phase_data)
        
        # 1. 计算加速度 (Acceleration) - 使用 Savitzky-Golay 微分器
        # deriv=2 表示计算二阶导数(加速度)
        # delta=self.TIME_STEP 用于归一化时间单位
        try:
            acceleration = savgol_filter(
                unwrapped_phase, 
                window_length=self.SAVGOL_WINDOW, 
                polyorder=self.SAVGOL_POLYORDER, 
                deriv=2, 
                delta=self.TIME_STEP,
                mode='interp' # 边界处理：插值
            )
        except Exception as e:
            print(f"Savitzky-Golay failed: {e}, falling back to simple diff")
            # Fallback (simple 2nd diff) if signal too short
            acceleration = np.diff(unwrapped_phase, n=2, prepend=[0,0]) / (self.TIME_STEP**2)

        raw_scg = acceleration
        
        # 2. 小波分解 (Wavelet Decomposition)
        w_family = 'sym8'
        try:
            max_level = pywt.dwt_max_level(len(raw_scg), pywt.Wavelet(w_family).dec_len)
            level = min(8, max_level)
            
            if level < 4:
                return raw_scg
                
            coeffs = pywt.wavedec(raw_scg, w_family, level=level)
            
            # 频段重构: 1Hz - 50Hz (保留 D2-D7)
            # A8 (0-0.39Hz), D8 (0.39-0.78Hz) -> 去除呼吸
            coeffs[0] = np.zeros_like(coeffs[0])
            if level >= 8: coeffs[1] = np.zeros_like(coeffs[1])
            
            # D1 (50-100Hz) -> 去除高频肌电
            if len(coeffs) >= 1:
                coeffs[-1] = np.zeros_like(coeffs[-1])
            
            clean_scg = pywt.waverec(coeffs, w_family)
            if len(clean_scg) > len(raw_scg):
                clean_scg = clean_scg[:len(raw_scg)]
            
            # 3. 匹配滤波 (Matched Filter)
            matched_scg = self._apply_matched_filter(clean_scg)
                
            return matched_scg
            
        except Exception as e:
            print(f"Advanced Denoising Failed: {e}")
            return raw_scg

    def _compute_score_and_fft(self, signal: np.ndarray) -> tuple[float, np.ndarray, int]:
        """计算信号评分与FFT."""
        fft_signal = signal - np.mean(signal)
        window = np.hanning(len(fft_signal))
        n_fft = 4096
        fft_result = np.fft.fft(fft_signal * window, n=n_fft)
        fft_magnitude = np.abs(fft_result)[:n_fft//2]
        if len(fft_signal) > 0:
            fft_magnitude = fft_magnitude / len(fft_signal) * 2
            
        idx_20hz = int(20 * n_fft / self.SAMPLING_RATE)
        energy_spectrum = fft_magnitude ** 2
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
        complex_sum = np.sum(radar_data[:, :, final_bin_idx], axis=1) # (N,) 复数数据
        
        # 信号处理
        processed_sig = process_radar_realtime(complex_sum)
        
        # 峰值检测
        peaks, _ = detect_peaks_realtime(processed_sig, self.SAMPLING_RATE)
        
        # 心律分析
        rhythm_result = analyze_heart_rhythm(peaks, self.SAMPLING_RATE)
        
        return rhythm_result

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
        
        # 由于使用 Savitzky-Golay，边界处理较好，不需要特别丢弃最后几个点
        # 但为了保险，仍取最新的有效数据（倒数第1个即可，或者倒数第2个）
        if len(scg_waveform) >= 1:
            latest_value = scg_waveform[-1] 
        else:
            latest_value = 0.0
            
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
