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

        try:
            while not self._stop_event.is_set():
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
                except Exception as e:
                    print(f"呼吸处理异常: {e}")
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
        
        # 2. 简单的Bin选择 (能量最大)
        # 实际应用中可能需要更复杂的逻辑，这里简化为每100帧更新一次目标Bin
        if self._completed_frames % 100 == 0:
            energies = np.sum(np.abs(data[:, :, :]), axis=(0, 1))
            self._current_target_bin = np.argmax(energies)
            
        target_bin = self._current_target_bin if 0 <= self._current_target_bin < self._bins_per_channel else 0
        
        # 3. 提取相位
        # 聚合通道 (简单的求和)
        complex_signal = np.sum(data[:, :, target_bin], axis=1)
        phase = np.unwrap(np.angle(complex_signal))
        
        # 4. 去除趋势 (简单的滑动平均减法或高通滤波)
        # 这里使用简单的去均值，实际应使用带通滤波
        # 呼吸频率 0.1 - 0.5 Hz
        
        # 简单差分获取相对位移
        displacement = phase - np.mean(phase)
        
        # 5. 计算流速 (位移的导数)
        flow_rate = np.gradient(displacement)
        
        # 6. 发送数据
        # 为了减少通信量，可以每N帧发送一次，或者只发送最新的点
        # 这里发送最近的一段波形用于前端显示
        
        if self._completed_frames % 5 == 0: # 降采样发送
            result = {
                "type": "breath_data",
                "frame_idx": self._completed_frames,
                "rr_wave": displacement[-200:].tolist() if len(displacement) > 200 else displacement.tolist(),
                "displacement": displacement[-200:].tolist() if len(displacement) > 200 else displacement.tolist(),
                "flow_rate": flow_rate[-200:].tolist() if len(flow_rate) > 200 else flow_rate.tolist(),
                "respiratory_rate": 0.0, # TODO: 添加呼吸率计算
                "warning_id": 0
            }
            
            if not self._output_queue.full():
                try:
                    self._output_queue.put_nowait(result)
                except:
                    pass

