"""毫米波雷达数据处理模块.

实现SCG波形生成算法，使用7点加权差分计算相位二阶导数。
"""
import threading
from collections import deque
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

import numpy as np


class MMWProcessorThread(threading.Thread):
    """毫米波雷达数据处理线程（消费者）.

    从雷达线程的队列中获取FFT数据，实时生成SCG波形。
    使用7点加权差分算法计算相位的二阶导数。

    Attributes:
        bin_num: bin数量（默认8）
        dlc: 每帧的复数数量（默认10）
        buffer_size: 滑动窗口大小（默认50帧）

    """

    # 算法常量
    TIME_STEP = 0.005  # 采样时间间隔（秒）
    MIN_BUFFER_SIZE = 1000  # 批处理需要的最小样本数（1000帧）
    OUTLIER_THRESHOLD = 1500  # 异常值阈值
    DIFFERENTIAL_WEIGHT = 16.0  # 差分公式分母权重

    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue | None = None,
        bin_num: int = 8,
        dlc: int = 10,
        buffer_size: int = 1000,
        callback: Callable[[np.ndarray, int], None] | None = None,
    ) -> None:
        """初始化处理线程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的SCG波形（可选）
            bin_num: bin数量（默认8）
            dlc: 每帧复数数量（默认10）
            buffer_size: 滑动窗口大小（默认1000帧）
            callback: 可选回调函数 callback(waveform, frame_idx)

        """
        super().__init__(daemon=True)

        self._input_queue = input_queue
        self._output_queue = output_queue or Queue()
        self._bin_num = bin_num
        self._dlc = dlc
        self._buffer_size = buffer_size
        self._callback = callback

        # 滑动窗口缓冲区：自动删除旧数据
        self._frame_buffer: deque = deque(maxlen=buffer_size)
        
        # 初始化缓冲区为1000个零帧（用于算法预热，但不输出）
        if buffer_size == 1000:
            # 创建零值帧：(8 bins, 10 dlc) 复数零矩阵
            zero_frame = np.zeros((bin_num, dlc), dtype=complex)
            for _ in range(1000):
                self._frame_buffer.append(zero_frame.copy())

        # 状态跟踪
        self._received_bins = 0  # 接收的bin包数
        self._completed_frames = 0  # 接收的完整帧数（8个bin = 1帧）
        self._generated_scg_points = 0  # 生成的SCG数据点数
        self._current_max_bin = 0  # 当前能量最大的bin编号
        self._running = True
        self._start_time = None

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("数据处理线程已启动...")

        try:
            while self._running:
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
        except KeyboardInterrupt:
            print("\n处理线程收到停止信号")
        finally:
            self._running = False
            print(f"处理线程已停止，接收 {self._completed_frames} 完整帧，生成 {self._generated_scg_points} 个SCG点")

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        """处理单帧数据并更新缓冲区.

        Args:
            frame_data: 包含 'bin_id', 'dlc', 'data' 的字典

        """
        import time
        
        if self._start_time is None:
            self._start_time = time.time()
        
        bin_id = frame_data["bin_id"]
        data = np.array(frame_data["data"])
        
        # 统计接收的bin包数
        self._received_bins += 1
        
        # 帧同步：bin 0 表示新一轮开始
        if bin_id == 0:
            # 首次接收数据提示
            if self._completed_frames == 0 and np.any(data != 0):
                print("接收到第一帧真实数据，Bin 0")

            # 创建新帧（滑动窗口自动删除最旧的帧）
            current_frame = np.zeros((self._bin_num, self._dlc), dtype=complex)
            current_frame[bin_id] = data
            self._frame_buffer.append(current_frame)
        elif len(self._frame_buffer) > 0:
            # 更新当前帧的bin数据
            self._frame_buffer[-1][bin_id] = data
        else:
            return  # 等待bin 0开始

        # 完整帧接收完毕（0-7号bin都收到）
        if bin_id == self._bin_num - 1:
            self._completed_frames += 1
            
            # 每100帧打印一次统计
            if self._completed_frames % 100 == 0:
                elapsed = time.time() - self._start_time
                frame_rate = self._completed_frames / elapsed if elapsed > 0 else 0
                print(f"[处理器] 已接收 {self._completed_frames} 完整帧 | "
                      f"帧率: {frame_rate:.1f} fps | "
                      f"已生成 {self._generated_scg_points} 个SCG点")
            
            # 缓冲区满后，每接收一帧就生成一个新的SCG点
            if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
                self._generate_new_scg_point()

    def _generate_new_scg_point(self) -> None:
        """滑动窗口模式：基于当前1000帧窗口生成最新的SCG点.
        
        工作流程：
        1. 新帧进入窗口，最旧帧自动删除（deque自动处理）
        2. 对整个1000帧窗口进行滤波处理
        3. 只输出对应最新帧的SCG值（窗口中倒数第4个点）
        """
        # 首次处理提示
        if self._generated_scg_points == 0:
            print(f"缓冲区已满（{len(self._frame_buffer)}帧），开始滑动窗口模式...")

        # 基于整个1000帧窗口生成完整波形（滤波处理）
        scg_waveform = self._generate_scg_waveform()
        if scg_waveform is None:
            return

        # 只输出最新的1个数据点（对应刚刚加入的新帧）
        # 由于使用7点差分，最右侧有效点是倒数第4个
        latest_scg_value = scg_waveform[-4]
        
        # 只将新产生的点传入输出队列
        result = {
            "frame_idx": self._generated_scg_points,
            "scg_value": float(latest_scg_value),
            "timestamp": self._generated_scg_points * self.TIME_STEP
        }
        self._output_queue.put(result)

        if self._callback:
            self._callback(np.array([latest_scg_value]), self._generated_scg_points)

        self._generated_scg_points += 1

    def _generate_scg_waveform(self) -> np.ndarray | None:
        """生成1000个SCG数据点（基于1000帧数据）.

        算法步骤：
        1. 找到能量最大的频率bin
        2. 提取相位并unwrap展开
        3. 使用7点加权差分计算所有点的二阶导数
        4. 过滤异常值

        Returns:
            1000个SCG值的数组，失败返回None

        """
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return None

        # 转换为numpy数组: (samples=1000, bins=8, dlc=10)
        fft_data = np.array(self._frame_buffer)

        # 找能量最大的频率bin
        max_bin_idx = self._find_max_energy_bin(fft_data)

        # 提取相位数据
        phase_data = self._extract_phase(fft_data, max_bin_idx)

        # 使用7点加权差分计算所有点的二阶导数
        scg_waveform = self._compute_derivative_waveform(phase_data)

        # 过滤异常值
        outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
        scg_waveform[outlier_idx] = 0.0

        return scg_waveform

    def _find_max_energy_bin(self, fft_data: np.ndarray) -> int:
        """找到能量最大的频率bin索引."""
        # 计算每个频率bin的总能量
        energies = [np.sum(np.abs(fft_data[:, 0, i])) for i in range(fft_data.shape[-1])]
        max_bin_idx = int(np.argmax(energies))
        self._current_max_bin = max_bin_idx  # 保存当前最大能量bin编号
        return max_bin_idx

    def _extract_phase(self, fft_data: np.ndarray, bin_idx: int) -> np.ndarray:
        """提取相位并展开（避免2π跳变）."""
        return np.unwrap(np.angle(fft_data[:, 0, bin_idx]))

    def _compute_derivative_waveform(self, phase_data: np.ndarray) -> np.ndarray:
        """计算整个波形的7点加权二阶导数.

        使用7点中心差分公式计算二阶导数：
        f''(x) ≈ [4f(x) + f(x+1) + f(x-1) - 2f(x+2) - 2f(x-2) - f(x+3) - f(x-3)] / (16h²)

        对于边界点（前3个和后3个），保持为0。

        Args:
            phase_data: 相位数据序列 (1000个点)

        Returns:
            二阶导数波形 (1000个点)

        """
        n = phase_data.shape[0]
        h_squared = self.TIME_STEP ** 2

        # 初始化结果数组为0
        result = np.zeros_like(phase_data)

        # 计算可以应用7点公式的范围（排除边界3个点）
        length = n - 6

        # 使用向量化计算中间部分的二阶导数
        # 中心点从索引3到n-4
        result[3:length+3] = (
            phase_data[3:length+3] * 4.0 +
            (phase_data[4:length+4] + phase_data[2:length+2]) -
            2.0 * (phase_data[5:length+5] + phase_data[1:length+1]) -
            (phase_data[6:length+6] + phase_data[:length])
        ) / (self.DIFFERENTIAL_WEIGHT * h_squared)

        return result

    def stop(self) -> None:
        """停止处理线程."""
        self._running = False

    def get_result(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """从输出队列获取处理结果.

        Args:
            timeout: 超时时间（秒）

        Returns:
            包含 'frame_idx', 'scg_value', 'timestamp' 的字典，超时返回None

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
            "received_bins": self._received_bins,
            "generated_scg_points": self._generated_scg_points,
            "buffer_size": len(self._frame_buffer),
            "max_buffer_size": self._buffer_size,
            "input_queue_size": self._input_queue.qsize(),
            "output_queue_size": self._output_queue.qsize(),
            "current_max_bin": self._current_max_bin,
            "elapsed_time": elapsed,
            "frame_rate": self._completed_frames / elapsed if elapsed > 0 else 0,
        }

    def __repr__(self) -> str:
        """返回对象的字符串表示."""
        return (
            f"MMWProcessorThread("
            f"frames={self._completed_frames}, "
            f"scg_points={self._generated_scg_points}, "
            f"buffer={len(self._frame_buffer)}/{self._buffer_size}, "
            f"running={self._running})"
        )
