"""
毫米波雷达数据处理模块
实现生产者-消费者模型的实时SCG波形生成
"""
import threading
from queue import Queue, Empty
from typing import Optional, Callable, Dict, Any
from collections import deque
import numpy as np


class MMWProcessorThread(threading.Thread):
    """
    毫米波雷达数据处理线程（消费者）
    
    从雷达线程的队列中获取FFT数据，实时生成SCG波形。
    使用7点加权差分算法计算相位的二阶导数。
    
    Attributes:
        bin_num: bin数量（通道数）
        dlc: 每帧的复数数量（频率bin数）
        buffer_size: 滑动窗口大小（帧数）
    """
    
    # 算法常量
    TIME_STEP = 0.005  # 采样时间间隔（秒）
    MIN_BUFFER_SIZE = 7  # 7点差分算法需要的最小样本数
    OUTLIER_THRESHOLD = 1500  # 异常值阈值
    DIFFERENTIAL_WEIGHT = 16.0  # 差分公式分母权重
    
    def __init__(
        self,
        input_queue: Queue,
        output_queue: Optional[Queue] = None,
        bin_num: int = 8,
        dlc: int = 10,
        buffer_size: int = 50,
        callback: Optional[Callable[[np.ndarray, int], None]] = None
    ) -> None:
        """
        初始化处理线程
        
        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的SCG波形
            bin_num: bin数量（默认8）
            dlc: 每帧复数数量（默认10）
            buffer_size: 滑动窗口大小（默认50帧）
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
        
        # 状态跟踪
        self._processed_frames = 0
        self._current_max_bin = 0  # 当前能量最大的bin编号
        self._running = True
        
    def run(self) -> None:
        """主循环：从队列消费数据并处理"""
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
            print(f"处理线程已停止，共处理 {self._processed_frames} 帧")
    
    def _process_single_frame(self, frame_data: Dict[str, Any]) -> None:
        """
        处理单帧数据并更新缓冲区
        
        Args:
            frame_data: 包含 'bin_id', 'dlc', 'data' 的字典
        """
        bin_id = frame_data['bin_id']
        data = np.array(frame_data['data'])
        
        # 帧同步：bin 0 表示新一轮开始
        if bin_id == 0:
            if not self._frame_buffer:
                print("接收到第一帧数据，Bin 0")
            
            current_frame = np.zeros((self._bin_num, self._dlc), dtype=complex)
            current_frame[bin_id] = data
            self._frame_buffer.append(current_frame)
        elif self._frame_buffer:
            self._frame_buffer[-1][bin_id] = data
        else:
            return  # 等待bin 0开始
        
        # 完整帧接收完毕（0-7号bin都收到），立即处理
        if bin_id == self._bin_num - 1 and len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
            self._try_generate_waveform()
    
    def _try_generate_waveform(self) -> None:
        """每收到完整一帧（8个bin）就生成一个SCG数据点"""
        buffer_len = len(self._frame_buffer)
        
        # 首次处理提示
        if self._processed_frames == 0:
            print(f"开始处理数据，缓冲区已有: {buffer_len} 帧")
        
        # 生成单个SCG数据点
        scg_value = self._generate_single_scg_point()
        if scg_value is None:
            return
        
        # 输出单个数据点
        result = {
            'frame_idx': self._processed_frames,
            'scg_value': scg_value,
            'timestamp': self._processed_frames * self.TIME_STEP
        }
        self._output_queue.put(result)
        
        if self._callback:
            self._callback(np.array([scg_value]), self._processed_frames)
        
        self._processed_frames += 1
        
        # 定期打印进度（每100帧）
        if self._processed_frames % 100 == 0:
            print(f"已处理 {self._processed_frames} 帧...")
    
    def _generate_single_scg_point(self) -> Optional[float]:
        """
        生成单个SCG数据点（针对最新帧）
        
        算法步骤：
        1. 找到能量最大的频率bin
        2. 提取相位并unwrap展开
        3. 使用7点加权差分计算最新点的二阶导数
        4. 过滤异常值
        
        Returns:
            单个SCG值，失败返回None
        """
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return None
        
        # 转换为numpy数组: (samples, bins, dlc)
        fft_data = np.array(self._frame_buffer)
        
        # 找能量最大的频率bin
        max_bin_idx = self._find_max_energy_bin(fft_data)
        
        # 提取相位数据
        phase_data = self._extract_phase(fft_data, max_bin_idx)
        
        # 计算最新点的二阶导数（使用7点差分）
        scg_value = self._compute_latest_derivative(phase_data)
        
        # 过滤异常值
        if abs(scg_value) > self.OUTLIER_THRESHOLD:
            scg_value = 0.0
        
        return scg_value
    
    def _find_max_energy_bin(self, fft_data: np.ndarray) -> int:
        """找到能量最大的频率bin索引"""
        energies = [np.sum(np.abs(fft_data[:, 0, i])) for i in range(fft_data.shape[-1])]
        max_bin_idx = int(np.argmax(energies))
        self._current_max_bin = max_bin_idx  # 保存当前最大能量bin编号
        return max_bin_idx
    
    def _extract_phase(self, fft_data: np.ndarray, bin_idx: int) -> np.ndarray:
        """提取相位并展开（避免2π跳变）"""
        return np.unwrap(np.angle(fft_data[:, 0, bin_idx]))
    
    def _compute_latest_derivative(self, phase_data: np.ndarray) -> float:
        """
        计算最新点的7点加权二阶导数
        
        使用缓冲区中最后7个点计算中心点（第4个点，即最新点周围）的导数
        公式: f''(x) ≈ [4f(x) + f(x+1) + f(x-1) - 2f(x+2) - 2f(x-2) - f(x+3) - f(x-3)] / (16h²)
        
        Args:
            phase_data: 相位数据序列
            
        Returns:
            最新点的二阶导数值
        """
        n = len(phase_data)
        if n < self.MIN_BUFFER_SIZE:
            return 0.0
        
        h_squared = self.TIME_STEP ** 2
        
        # 使用最后7个点，计算中心点（索引-4，即倒数第4个）的导数
        # 这样可以使用完整的7点公式
        i = n - 4  # 中心点位置
        
        result = (
            phase_data[i] * 4.0 +
            (phase_data[i+1] + phase_data[i-1]) -
            2.0 * (phase_data[i+2] + phase_data[i-2]) -
            (phase_data[i+3] + phase_data[i-3])
        ) / (self.DIFFERENTIAL_WEIGHT * h_squared)
        
        return float(result)
    
    def stop(self) -> None:
        """停止处理线程"""
        self._running = False
    
    def get_result(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        从输出队列获取处理结果
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            包含 'frame_idx', 'scg_value', 'timestamp' 的字典
        """
        try:
            return self._output_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def get_statistics(self) -> Dict[str, int]:
        """获取处理统计信息"""
        return {
            'processed_frames': self._processed_frames,
            'buffer_size': len(self._frame_buffer),
            'max_buffer_size': self._buffer_size,
            'input_queue_size': self._input_queue.qsize(),
            'output_queue_size': self._output_queue.qsize(),
            'current_max_bin': self._current_max_bin
        }
    
    def __repr__(self) -> str:
        """返回对象的字符串表示"""
        return (
            f"MMWProcessorThread("
            f"processed={self._processed_frames}, "
            f"buffer={len(self._frame_buffer)}/{self._buffer_size}, "
            f"running={self._running})"
        )