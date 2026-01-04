"""毫米波雷达数据处理模块 (多进程版).

实现SCG波形生成算法，使用7点加权差分计算相位二阶导数。
重构为 multiprocessing.Process.
"""
import multiprocessing
from collections import deque
from queue import Empty
from typing import Any

import numpy as np


class MMWSCGProcess(multiprocessing.Process):
    """毫米波雷达数据处理进程（消费者）.

    从雷达进程的队列中获取FFT数据，实时生成SCG波形。
    使用7点加权差分算法计算相位的二阶导数。
    只使用通道0的数据进行处理。
    """

    # 算法常量
    TIME_STEP = 0.005  # 采样时间间隔（秒）
    MIN_BUFFER_SIZE = 1000  # 批处理需要的最小样本数（1000帧）
    OUTLIER_THRESHOLD = 1500  # 异常值阈值
    DIFFERENTIAL_WEIGHT = 16.0  # 差分公式分母权重

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: Any = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        buffer_size: int = 1000,
    ) -> None:
        super().__init__()
        self.daemon = True

        self._input_queue = input_queue
        # 如果没有提供输出队列，创建一个（注意：在多进程中，通常由外部传入Queue）
        self._output_queue = output_queue or multiprocessing.Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._buffer_size = buffer_size

        # 状态跟踪变量将在 run() 中初始化，因为它们不能在进程间共享
        self._frame_buffer = None
        self._running = True

    def run(self) -> None:
        """进程主循环."""
        print("SCG 处理进程已启动 (PID: %s)..." % self.pid)
        import time

        # 初始化进程内状态
        self._frame_buffer = deque(maxlen=self._buffer_size)
        if self._buffer_size == 1000:
             # 创建零值帧：(8 channels, 10 bins) 复数零矩阵
            zero_frame = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            for _ in range(1000):
                self._frame_buffer.append(zero_frame.copy())
                
        self._received_channels = 0
        self._completed_frames = 0
        self._last_completed_frames = 0
        self._generated_scg_points = 0
        self._current_max_bin = 0
        self._current_offset = 0
        self._start_time = time.time()
        self._running = True

        try:
            while self._running:
                try:
                    # 从队列获取数据
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
                except Exception as e:
                    print(f"[SCG Process] Error: {e}")
                    continue
        except KeyboardInterrupt:
            print("\nSCG Process received interrupt.")
        finally:
            print(f"SCG Process stopped. Generated {self._generated_scg_points} points.")

    def stop(self) -> None:
        """停止处理 (在父进程调用，通过发送信号或terminate)."""
        # Multiprocessing Process cannot be stopped by setting a flag from outside easily
        # unless using a Value/Event. For simplicity, we can rely on terminate()
        # or sending a 'poison pill' in the queue.
        # Here we just implement terminate logic in the manager.
        self.terminate()

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        import time
        
        channel_id = frame_data["channel_id"]
        # Deserialize numpy array if needed (Queue handles pickling)
        data = frame_data["data"] 
        if not isinstance(data, np.ndarray):
             data = np.array(data)

        self._received_channels += 1

        if channel_id == 0:
            if "offset" in frame_data:
                self._current_offset = frame_data["offset"]
            
            # Create new frame
            current_frame = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            current_frame[channel_id] = data
            self._frame_buffer.append(current_frame)
        elif len(self._frame_buffer) > 0:
            self._frame_buffer[-1][channel_id] = data
        else:
            return

        if channel_id == self._channel_num - 1:
            self._completed_frames += 1
            
            if self._completed_frames % 500 == 0:
                # Minimal logging to avoid clutter
                # print(f"[SCG] Processed {self._completed_frames} frames.")
                pass
            
            if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
                self._generate_new_scg_point()

    def _generate_new_scg_point(self) -> None:
        scg_waveform = self._generate_scg_waveform()
        if scg_waveform is None:
            return

        latest_scg_value = scg_waveform[-4]
        
        result = {
            "type": "scg",
            "frame_idx": self._generated_scg_points,
            "value": float(latest_scg_value),
            "timestamp": self._generated_scg_points * self.TIME_STEP
        }
        
        try:
            self._output_queue.put_nowait(result)
        except:
            pass # Drop if full

        self._generated_scg_points += 1

    def _generate_scg_waveform(self) -> np.ndarray | None:
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return None

        fft_data = np.array(self._frame_buffer)
        max_bin_idx = self._find_max_energy_bin(fft_data)
        phase_data = self._extract_phase(fft_data, max_bin_idx)
        scg_waveform = self._compute_derivative_waveform(phase_data)

        outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
        scg_waveform[outlier_idx] = 0.0

        return scg_waveform

    def _find_max_energy_bin(self, fft_data: np.ndarray) -> int:
        energies = [np.sum(np.abs(fft_data[:, 0, i])) for i in range(self._bins_per_channel)]
        max_bin_idx = int(np.argmax(energies))
        self._current_max_bin = max_bin_idx
        return max_bin_idx

    def _extract_phase(self, fft_data: np.ndarray, bin_idx: int) -> np.ndarray:
        return np.unwrap(np.angle(fft_data[:, 0, bin_idx]))

    def _compute_derivative_waveform(self, phase_data: np.ndarray) -> np.ndarray:
        n = phase_data.shape[0]
        h_squared = self.TIME_STEP ** 2
        result = np.zeros_like(phase_data)
        length = n - 6

        result[3:length+3] = (
            phase_data[3:length+3] * 4.0 +
            (phase_data[4:length+4] + phase_data[2:length+2]) -
            2.0 * (phase_data[5:length+5] + phase_data[1:length+1]) -
            (phase_data[6:length+6] + phase_data[:length])
        ) / (self.DIFFERENTIAL_WEIGHT * h_squared)

        return result
