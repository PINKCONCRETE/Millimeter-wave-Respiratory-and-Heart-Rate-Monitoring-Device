"""毫米波呼吸信号处理模块.

基于相位信息提取呼吸波形和呼吸周期（位移-流速循环）。
改编自 breath_old.py，集成到流水线架构中。
"""
import threading
from collections import deque
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

import numpy as np
from scipy import signal


class MMWBreathThread(threading.Thread):
    """毫米波呼吸信号处理线程（消费者）.

    从雷达线程的队列中获取FFT数据，实时生成呼吸波形和呼吸周期信息。
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
        input_queue: Queue,
        output_queue: Queue | None = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        buffer_size: int = 1000,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """初始化呼吸处理线程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的呼吸信息（可选）
            channel_num: 通道数量（默认8）
            bins_per_channel: 每个通道的频率bin数量（默认10）
            buffer_size: 数据缓冲区大小（默认1000帧）
            callback: 可选回调函数 callback(breath_dict)

        """
        super().__init__(daemon=True)

        self._input_queue = input_queue
        self._output_queue = output_queue or Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._buffer_size = buffer_size
        self._callback = callback

        # 数据缓冲区：存储最近的帧数据
        self._frame_buffer: deque = deque(maxlen=buffer_size)

        # 状态跟踪
        self._received_channels = 0
        self._completed_frames = 0
        self._last_completed_frames = 0
        self._generated_breath_cycles = 0
        self._current_target_bin = 0  # 当前选择的能量最大bin
        self._running = True
        self._start_time = None
        self._last_start_time = None

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("呼吸处理线程已启动...")

        try:
            while self._running:
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
        except KeyboardInterrupt:
            print("\n呼吸处理线程收到停止信号")
        finally:
            self._running = False
            print(f"呼吸处理线程已停止，接收 {self._completed_frames} 完整帧")

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        """处理单帧数据并更新缓冲区.

        Args:
            frame_data: 包含 'channel_id', 'bins_count', 'data' 的字典

        """
        import time

        if self._start_time is None:
            self._start_time = time.time()
            self._last_start_time = self._start_time

        channel_id = frame_data["channel_id"]
        data = np.array(frame_data["data"])

        # 统计接收的通道包数
        self._received_channels += 1

        # 帧同步：通道 0 表示新一轮开始
        if channel_id == 0:
            # 创建新帧
            current_frame = np.zeros(
                (self._channel_num, self._bins_per_channel), dtype=complex
            )
            current_frame[channel_id] = data
            self._frame_buffer.append(current_frame)
        elif len(self._frame_buffer) > 0:
            # 更新当前帧的通道数据
            self._frame_buffer[-1][channel_id] = data
        else:
            return  # 等待通道 0开始

        # 完整帧接收完毕（0-7号通道都收到）
        if channel_id == self._channel_num - 1:
            self._completed_frames += 1

            # 每100帧打印一次统计
            if self._completed_frames % 100 == 0:
                elapsed = time.time() - self._last_start_time
                frame_rate = (self._completed_frames - self._last_completed_frames) / elapsed if elapsed > 0 else 0
                print(
                    f"[呼吸处理] 已接收 {self._completed_frames} 完整帧 | "
                    f"帧率: {frame_rate:.1f} fps | "
                    f"已生成 {self._generated_breath_cycles} 个呼吸周期"
                )
                self._last_completed_frames = self._completed_frames
                self._last_start_time = time.time()

            # 缓冲区满后，尝试生成呼吸信息
            if len(self._frame_buffer) >= self._buffer_size:
                self._generate_breath_info()

    def _generate_breath_info(self) -> None:
        """基于当前缓冲区生成呼吸波形和周期信息."""
        if len(self._frame_buffer) < self._buffer_size:
            return

        # 转换为numpy数组: (samples=1000, channels=8, bins=10)
        fft_data = np.array(self._frame_buffer)

        # 1. 选择能量最大的频率bin（只在通道0中选择）
        target_bin = self._choose_target_bin(fft_data)
        self._current_target_bin = target_bin

        # 2. 提取该bin的相位信息
        raw_phase = self._get_phase_info(fft_data, target_bin)

        # 3. 处理相位信息得到呼吸波形
        phase_info = self._process_phase_info(raw_phase)

        # 4. 提取呼吸周期（位移-流速）
        displacement, flow_rate = self._get_breath_cycle(phase_info)

        # 5. 构造输出结果
        breath_dict = {
            "rr_wave": phase_info,
            "displacement": displacement,
            "flow_rate": flow_rate,
            "target_bin": target_bin,
            "frame_idx": self._completed_frames,
        }

        # 输出到队列
        self._output_queue.put(breath_dict)

        # 调用回调函数
        if self._callback:
            self._callback(breath_dict)

        # 统计
        if displacement is not None and flow_rate is not None:
            self._generated_breath_cycles += 1

    def _choose_target_bin(self, fft_data: np.ndarray) -> int:
        """选择通道0中能量最大的频率bin.

        Args:
            fft_data: 形状为(1000, 8, 10)的数组

        Returns:
            能量最大的bin索引

        """
        # 只使用通道0的数据
        abs_raw_frame = np.abs(fft_data[:, 0, :])
        # 计算每个bin的平均能量
        mean_abs = np.mean(abs_raw_frame, axis=0)
        target_bin = int(np.argmax(mean_abs))
        return target_bin

    def _get_phase_info(self, fft_data: np.ndarray, target_bin: int) -> np.ndarray:
        """提取指定bin的相位信息.

        Args:
            fft_data: 形状为(1000, 8, 10)的数组
            target_bin: 目标bin索引

        Returns:
            相位序列

        """
        # 选择通道0的目标bin数据
        chosen_profile = fft_data[:, 0, target_bin]
        raw_phase = np.angle(chosen_profile)
        return raw_phase

    def _process_phase_info(
        self, raw_phase: np.ndarray, normalize: bool = False
    ) -> np.ndarray:
        """处理相位信息：展开 -> 去基线漂移 -> 平滑 -> 可选归一化.

        Args:
            raw_phase: 原始相位序列
            normalize: 是否归一化

        Returns:
            处理后的呼吸信号

        """
        # 1. 相位展开
        unwrap_phase = np.unwrap(raw_phase)

        # 2. 去除基线漂移
        corrected_signal = self._remove_baseline_drift(unwrap_phase)

        # 3. 滑动窗口平滑
        br_signal = self._smooth_signal(corrected_signal)

        # 4. 翻转并偏移
        br_signal = -br_signal + 1

        # 5. 可选归一化
        if normalize:
            br_signal = (br_signal - np.min(br_signal)) / (
                np.max(br_signal) - np.min(br_signal)
            )

        return br_signal

    def _remove_baseline_drift(
        self, signal_data: np.ndarray, win_len: float = 5.0
    ) -> np.ndarray:
        """去除信号的基线漂移.

        Args:
            signal_data: 输入信号
            win_len: 窗口长度（秒）

        Returns:
            去除基线漂移后的信号

        """
        window_size = int(self.SAMPLING_RATE * win_len)
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

    def _smooth_signal(
        self, signal_data: np.ndarray, win_len: float = 1.7
    ) -> np.ndarray:
        """使用滑动窗口平滑信号.

        Args:
            signal_data: 输入信号
            win_len: 窗口长度（秒）

        Returns:
            平滑后的信号

        """
        window_size = int(self.SAMPLING_RATE * win_len)
        smoothed = np.convolve(
            signal_data, np.ones(window_size) / window_size, mode="same"
        )
        return smoothed

    def _get_breath_cycle(
        self, phase_info: np.ndarray
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """提取最新的呼吸周期（位移和流速）.

        Args:
            phase_info: 处理后的相位信息

        Returns:
            (displacement, flow_rate) 元组，如果无法提取则返回 (None, None)

        """
        # 寻找峰值和谷值
        peaks, valleys = self._find_peaks_valleys(phase_info)

        # 至少需要2个谷值才能提取一个完整周期
        if len(valleys) < 2:
            return None, None

        # 选取最后两个谷值之间的周期
        last_valleys = valleys[-2:]
        cycle_signal = phase_info[last_valleys[0] : last_valleys[1]]

        # 计算梯度（流速）
        derivative = np.gradient(cycle_signal)

        # 归一化位移和流速
        displacement = (cycle_signal - np.min(cycle_signal)) / (
            np.max(cycle_signal) - np.min(cycle_signal)
        )
        flow_rate = derivative / np.max(np.abs(derivative))

        return displacement, flow_rate

    def _find_peaks_valleys(
        self, data: np.ndarray, time_valid: float = 0.3
    ) -> tuple[np.ndarray, np.ndarray]:
        """在信号中寻找峰值和谷值.

        Args:
            data: 输入信号
            time_valid: 峰值间最小时间间隔（秒）

        Returns:
            (peaks, valleys) 元组

        """
        data = np.squeeze(data)
        min_distance = int(time_valid * self.SAMPLING_RATE)

        # 寻找谷值（负峰值）
        valleys, _ = signal.find_peaks(-data, distance=min_distance)

        # 寻找峰值
        peaks, _ = signal.find_peaks(data, distance=min_distance)

        return peaks, valleys

    def stop(self) -> None:
        """停止处理线程."""
        self._running = False

    def get_result(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """从输出队列获取处理结果.

        Args:
            timeout: 超时时间（秒）

        Returns:
            包含呼吸信息的字典，超时返回None

        """
        try:
            return self._output_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_statistics(self) -> dict[str, int | float]:
        """获取处理统计信息."""
        import time

        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "completed_frames": self._completed_frames,
            "received_channels": self._received_channels,
            "generated_breath_cycles": self._generated_breath_cycles,
            "buffer_size": len(self._frame_buffer),
            "max_buffer_size": self._buffer_size,
            "input_queue_size": self._input_queue.qsize(),
            "output_queue_size": self._output_queue.qsize(),
            "current_target_bin": self._current_target_bin,
            "elapsed_time": elapsed,
            "frame_rate": self._completed_frames / elapsed if elapsed > 0 else 0,
        }

    def __repr__(self) -> str:
        """返回对象的字符串表示."""
        return (
            f"MMWBreathThread("
            f"frames={self._completed_frames}, "
            f"breath_cycles={self._generated_breath_cycles}, "
            f"buffer={len(self._frame_buffer)}/{self._buffer_size}, "
            f"running={self._running})"
        )
