"""毫米波呼吸信号处理模块.

基于相位信息提取呼吸波形和呼吸周期（位移-流速循环）。
改编自 breath_old.py，集成到流水线架构中。
"""
import multiprocessing
import time
from collections import deque
from queue import Empty
from typing import Any

import numpy as np
from scipy import signal


class MMWBreathProcess(multiprocessing.Process):
    """毫米波呼吸信号处理进程（消费者）.

    从雷达进程的队列中获取FFT数据，实时生成呼吸波形和呼吸周期信息。
    使用相位展开、基线漂移去除、滑动窗口平滑等算法。

    Attributes:
        channel_num: 通道数量（默认8）
        bins_per_channel: 每个通道的频率bin数量（默认10）
        buffer_size: 数据缓冲区大小（默认1000帧，5秒数据）

    """

    # 算法常量
    SAMPLING_RATE = 200  # 采样率 200Hz
    BUFFER_TIME = 5  # 缓冲区时长（秒）
    BASELINE_WIN_LEN = 5  # 基线漂移去除窗口长度（秒）
    SMOOTH_WIN_LEN = 1.7  # 平滑窗口长度（秒）
    PEAK_MIN_DISTANCE = 0.3  # 峰值最小间隔（秒）

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: Any = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        buffer_size: int = 1000,
    ) -> None:
        """初始化呼吸处理进程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的呼吸信息（可选）
            channel_num: 通道数量（默认8）
            bins_per_channel: 每个通道的频率bin数量（默认10）
            buffer_size: 数据缓冲区大小（默认1000帧）

        """
        super().__init__()
        self.daemon = True

        self._input_queue = input_queue
        self._output_queue = output_queue or multiprocessing.Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._buffer_size = buffer_size
        
        self._stop_event = multiprocessing.Event()

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("呼吸处理进程已启动...")
        
        # 初始化进程内状态
        self._frame_buffer = deque(maxlen=self._buffer_size)
        self._received_channels = 0
        self._completed_frames = 0
        self._last_completed_frames = 0
        self._generated_breath_cycles = 0
        self._current_target_bin = 0
        self._start_time = time.time()
        
        # 当前帧构建缓冲区
        self._current_frame_build = None
        self._current_frame_id = -1
        self._respiratory_rate = 0.0
        self._warning_id = 0

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
                        # print(f"[Breath] FPS: {fps:.1f}")
                        last_fps_frame_count = self._completed_frames
                        last_fps_time = now
                        
                except Empty:
                    continue
                except Exception as e:
                    print(f"呼吸处理异常: {e}")
                    import traceback
                    traceback.print_exc()
        except KeyboardInterrupt:
            print("\n呼吸处理进程收到停止信号")
        finally:
            print(f"呼吸处理进程已停止，接收 {self._completed_frames} 完整帧")

    def stop(self) -> None:
        """停止进程."""
        self._stop_event.set()

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        """处理单帧数据并更新缓冲区.

        Args:
            frame_data: 包含 'channel_id', 'bins_count', 'data' 的字典
        """
        channel_id = frame_data.get("channel_id")
        data = frame_data.get("data")
        
        if channel_id is None or data is None:
            return
            
        # 确保数据是numpy数组
        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=complex)

        # 简单的帧同步逻辑
        if channel_id == 0:
            self._current_frame_build = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            self._current_frame_build[channel_id] = data
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return # 等待新的帧开始

        # 完整帧接收判断
        if channel_id == self._channel_num - 1 and self._current_frame_build is not None:
            self._completed_frames += 1
            self._frame_buffer.append(self._current_frame_build.copy())
            
            # 实时呼吸波形提取
            if len(self._frame_buffer) >= 200: # 至少1秒数据
                self._extract_breath_waveform()
                
    def _extract_breath_waveform(self) -> None:
        """从缓冲区数据提取呼吸波形."""
        # 1. 获取最近的数据
        data = np.array(self._frame_buffer)
        
        # 2. Bin选择 (能量最大)
        # 每100帧更新一次目标Bin
        if self._completed_frames % 100 == 0:
            energies = np.sum(np.abs(data[:, 0, :]), axis=0)
            self._current_target_bin = np.argmax(energies)
            
        target_bin = self._current_target_bin if 0 <= self._current_target_bin < self._bins_per_channel else 0
        
        # 3. 提取相位
        # 使用通道0 (Old algorithm behavior)
        complex_signal = data[:, 0, target_bin]
        raw_phase = np.angle(complex_signal)
        
        # 4. 高级信号处理 (使用移植的算法)
        # 展开
        unwrap_phase = np.unwrap(raw_phase)
        
        # 去基线漂移 (只对足够长的数据进行)
        if len(unwrap_phase) > self.SAMPLING_RATE * 1:
            corrected_signal = self._remove_baseline_drift(unwrap_phase)
        else:
            corrected_signal = unwrap_phase - np.mean(unwrap_phase)
            
        # 平滑
        if len(corrected_signal) > self.SAMPLING_RATE * 0.5:
             br_signal = self._smooth_signal(corrected_signal)
        else:
             br_signal = corrected_signal
             
        # 翻转 (根据旧代码逻辑)
        br_signal = -br_signal
        
        # 5. 计算流速 (位移的导数)
        flow_rate = np.gradient(br_signal)
        
        # 6. 定期计算呼吸率和检测异常 (每1秒 / 200帧)
        if self._completed_frames % 200 == 0:
            self._warning_id, self._respiratory_rate = self._detect_breath_anomalies(br_signal)
            # print(f"呼吸率: {self._respiratory_rate:.1f} BPM, Warning: {self._warning_id}")

        # 7. 发送数据 (增量发送)
        if len(br_signal) > 0:
            result = {
                "type": "breath_data",
                "frame_idx": self._completed_frames,
                "breath_value": float(br_signal[-1]), # Incremental
                "flow_value": float(flow_rate[-1]),     # Incremental
                "respiratory_rate": round(float(self._respiratory_rate), 1),
                "warning_id": int(self._warning_id)
            }
            
            if not self._output_queue.full():
                try:
                    self._output_queue.put_nowait(result)
                except:
                    pass

    def _remove_baseline_drift(self, signal_data: np.ndarray, win_len: float = 5.0) -> np.ndarray:
        """去除信号的基线漂移."""
        window_size = int(self.SAMPLING_RATE * win_len)
        if window_size > len(signal_data):
            window_size = len(signal_data)
        if window_size % 2 == 0:
            window_size += 1
            
        if window_size < 3:
             return signal_data - np.mean(signal_data)

        pad_width = window_size // 2

        # 反射填充
        padded_signal = np.pad(signal_data, (pad_width, pad_width), mode="reflect")

        # 移动平均计算基线
        baseline = np.convolve(
            padded_signal, np.ones(window_size) / window_size, mode="same"
        )
        baseline = baseline[pad_width:-pad_width]

        # 减去基线
        corrected_signal = signal_data - baseline
        return corrected_signal

    def _smooth_signal(self, signal_data: np.ndarray, win_len: float = 1.7) -> np.ndarray:
        """使用滑动窗口平滑信号."""
        window_size = int(self.SAMPLING_RATE * win_len)
        if window_size > len(signal_data):
            window_size = len(signal_data)
        
        if window_size < 2:
            return signal_data
            
        pad_width = window_size // 2
        
        # 反射填充以避免边缘效应
        padded_signal = np.pad(signal_data, (pad_width, pad_width), mode="reflect")

        smoothed = np.convolve(
            padded_signal, np.ones(window_size) / window_size, mode="same"
        )
        return smoothed[pad_width:-pad_width]

    def _find_peaks_valleys(self, data: np.ndarray, time_valid: float = 0.3) -> tuple[np.ndarray, np.ndarray]:
        """在信号中寻找峰值和谷值."""
        data = np.squeeze(data)
        min_distance = int(time_valid * self.SAMPLING_RATE)
        if min_distance < 1:
            min_distance = 1

        # 寻找谷值（负峰值）
        valleys, _ = signal.find_peaks(-data, distance=min_distance)

        # 寻找峰值
        peaks, _ = signal.find_peaks(data, distance=min_distance)

        return peaks, valleys

    def _detect_breath_anomalies(self, phase_info: np.ndarray) -> tuple[int, float]:
        """检测呼吸异常（呼吸暂停和COPD）."""
        if len(phase_info) == 0:
            return 0, 0.0

        # 1. 检测呼吸暂停：能量过低或幅度过小
        energy_thresh = 0.5
        range_value_thresh = 0.15
        phase_energy = np.sum(np.square(phase_info)) / len(phase_info)
        max_amplitude = np.max(np.abs(phase_info)) if len(phase_info) > 0 else 0

        # 注意：这里的阈值可能需要根据归一化情况调整。
        # 旧代码中未明确归一化，但这里使用了原始相位。
        # 为了安全起见，我们放宽一点或仅在特定条件下触发
        # if phase_energy < energy_thresh or max_amplitude < range_value_thresh:
        #     return 21, 0.0  # 呼吸暂停

        # 2. 计算呼吸参数用于COPD检测
        peaks, valleys = self._find_peaks_valleys(phase_info)

        # 至少需要2个完整周期才能计算参数
        if len(peaks) < 2:
            return 0, 0.0  # 数据不足

        # 对齐峰值和谷值
        if len(valleys) > 0 and peaks[0] > valleys[0]:
            peaks = peaks[1:]

        if len(peaks) < 2:
            return 0, 0.0

        # 计算呼吸率和COPD相关参数
        ti_te_list = []
        duty_cycle_list = []
        t_ptef_te_list = []
        ie_50_list = []
        rr_list = []

        for i in range(len(peaks) - 1):
            if peaks[i] >= len(phase_info) or peaks[i+1] >= len(phase_info):
                continue
                
            single_cycle = -phase_info[peaks[i]:peaks[i+1]]  # 翻转信号以匹配旧算法预期 (吸气为正?)
            # 实际上，phase_info已经是处理过的，如果前面 _extract_breath_waveform 做了 -br_signal
            # 那么这里可能不需要再次负号，或者取决于原始定义的吸气方向。
            # 假设吸气是波峰，呼气是波谷。
            
            cycle_length = len(single_cycle)
            if cycle_length == 0:
                continue

            t_tot = cycle_length / self.SAMPLING_RATE
            peak_idx = np.argmax(single_cycle)
            t_i = peak_idx / self.SAMPLING_RATE
            t_e = t_tot - t_i

            if t_e == 0 or t_tot == 0:
                continue

            ti_te = t_i / t_e
            duty_cycle = t_i / t_tot
            rr = 60 / t_tot

            rr_list.append(rr)
            ti_te_list.append(ti_te)
            duty_cycle_list.append(duty_cycle)
            
            # 简单计算IE50等复杂参数可能出错，这里先只保留基础参数和RR
            # 如果需要严格复刻COPD检测，需要更严谨的流速计算
            
            # 计算流速相关参数
            try:
                derivative = np.gradient(single_cycle)
                t_PTEF = np.argmin(derivative) / self.SAMPLING_RATE - t_tot / 2
                t_ptef_te = t_PTEF / t_e if t_e != 0 else 0
                t_ptef_te_list.append(t_ptef_te)

                # 计算IE50
                mid_inhale = (single_cycle[0] + single_cycle[peak_idx]) / 2
                mid_exhale = (single_cycle[peak_idx] + single_cycle[-1]) / 2
            
                TIF_50_idx = np.where(single_cycle[:peak_idx] >= mid_inhale)[0][0]
                TEF_50_idx = np.where(single_cycle[peak_idx:] <= mid_exhale)[0][0] + peak_idx
                tif_50 = abs(derivative[TIF_50_idx])
                tef_50 = abs(derivative[TEF_50_idx])
                ie_50 = tif_50 / tef_50 if tef_50 != 0 else 0
                ie_50_list.append(ie_50)
            except (IndexError, ValueError):
                continue

        # 计算中位数
        if not ti_te_list:
            return 0, 0.0

        median_ti_te = np.median(ti_te_list)
        median_duty_cycle = np.median(duty_cycle_list)
        median_t_ptef_te = np.median(t_ptef_te_list) if t_ptef_te_list else 0
        median_ie_50 = np.median(ie_50_list) if ie_50_list else 0
        median_rr = np.median(rr_list)

        # 3. COPD判断：至少2个参数异常
        ti_te_flag = 0.4 <= median_ti_te <= 1.2
        duty_cycle_flag = 0.35 <= median_duty_cycle <= 0.55
        t_ptef_te_flag = 0.241 <= median_t_ptef_te <= 0.583
        ie_50_flag = 0.9 <= median_ie_50 <= 1.88

        abnormal_count = sum([
            not ti_te_flag,
            not duty_cycle_flag,
            not t_ptef_te_flag,
            not ie_50_flag
        ])

        if abnormal_count >= 2:
            return 22, median_rr  # COPD

        return 0, median_rr  # 正常
