"""实时雷达心跳分析进程.

独立于 SCG 评分进程，专注于运行 realtime.py 中的核心算法，
以避免阻塞 SCG 波形的实时生成。
"""
import multiprocessing
import time
import numpy as np
from collections import deque
from queue import Empty, Full
from typing import Any
from scipy.signal import find_peaks

# ==================== Configuration ====================
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

# ==================== Signal Processing Functions ====================
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

# ==================== Process Class ====================
class MMWRealtimeAnalysisProcess(multiprocessing.Process):
    """实时心率分析进程."""
    
    SAMPLING_RATE = 200
    MIN_BUFFER_SIZE = 200   # 1秒
    MAX_BUFFER_SIZE = 1000  # 5秒
    ANALYSIS_INTERVAL = 10  # 每10帧(0.05s)分析一次

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: multiprocessing.Queue, # IPC queue
        channel_num: int = 8,
        bins_per_channel: int = 10,
    ) -> None:
        super().__init__()
        self.daemon = True
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._stop_event = multiprocessing.Event()
        
    def run(self) -> None:
        print("实时分析进程已启动...")
        self._frame_buffer = deque(maxlen=self.MAX_BUFFER_SIZE)
        self._current_frame_build = None
        self._completed_frames = 0
        
        # 简单策略：固定选择 Bin 0 (或者之后优化为动态选择)
        # 为了更稳健，我们可以选择 Bin 2-3，通常能量较好
        self._target_bin = 2 
        
        try:
            while not self._stop_event.is_set():
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
                except Exception as e:
                    print(f"实时分析进程异常: {e}")
        finally:
            print("实时分析进程已停止")

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
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return
            
        if channel_id == self._channel_num - 1 and self._current_frame_build is not None:
            self._completed_frames += 1
            
            # 提取目标 Bin 的数据并对所有通道求和 (类似 SCG 逻辑)
            # complex_sum: (N,) -> scalar complex for this frame
            complex_sum = np.sum(self._current_frame_build[:, self._target_bin])
            self._frame_buffer.append(complex_sum)
            
            # 定期运行分析
            if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE and \
               self._completed_frames % self.ANALYSIS_INTERVAL == 0:
                self._run_analysis()

    def _run_analysis(self) -> None:
        # Convert buffer to numpy array
        raw_data = np.array(self._frame_buffer)
        
        # 1. 信号处理
        processed_sig = process_radar_realtime(raw_data)
        
        # 2. 峰值检测
        peaks, _ = detect_peaks_realtime(processed_sig, self.SAMPLING_RATE)
        
        # 3. 心律分析
        rhythm_result = analyze_heart_rhythm(peaks, self.SAMPLING_RATE)
        
        # 4. 发送结果 (处理 NaN)
        hr = rhythm_result['hr']
        if np.isnan(hr) or np.isinf(hr):
            hr = 0.0 # 或者 None/0
        else:
            hr = float(hr)
            
        premature = bool(rhythm_result['premature'])
        
        output_data = {
            "type": "realtime_analysis",
            "realtime_hr": hr,
            "realtime_premature": premature,
            "timestamp": time.time()
        }
        
        try:
            self._output_queue.put_nowait(output_data)
        except Full:
            pass # 队列满则丢弃
