"""毫米波心率信号处理模块.

基于差分相位信号提取心率信息。
使用峰值检测算法计算心率和心率变异性(HRV)。
改编自 heart_rate_old.py
"""
import threading
from collections import deque
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt


class MMWHeartRateThread(threading.Thread):
    """毫米波心率信号处理线程（消费者）.

    从雷达线程的队列中获取FFT数据，实时生成心率信息。
    直接处理1000帧FFT数据，计算心率和HRV指标。

    Attributes:
        channel_num: 通道数量（默认8）
        bins_per_channel: 每个通道的频率bin数量（默认10）
        buffer_size: 数据缓冲区大小（默认1000帧）

    """

    # 算法常量
    SAMPLING_RATE = 200  # 采样率 200Hz
    TIME_STEP = 0.005  # 采样时间间隔（秒）
    MIN_BUFFER_SIZE = 1000  # 最小缓冲区大小
    OUTLIER_THRESHOLD = 1500  # 异常值阈值
    
    # 带通滤波参数
    LOWCUT = 20  # Hz
    HIGHCUT = 40  # Hz
    FILTER_ORDER = 4

    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue | None = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        buffer_size: int = 1000,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """初始化心率处理线程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的心率信息（可选）
            channel_num: 通道数量（默认8）
            bins_per_channel: 每个通道的频率bin数量（默认10）
            buffer_size: 数据缓冲区大小（默认1000帧）
            callback: 可选回调函数 callback(hr_dict)

        """
        super().__init__(daemon=True)

        self._input_queue = input_queue
        self._output_queue = output_queue or Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._buffer_size = buffer_size
        self._callback = callback

        # 滑动窗口缓冲区
        self._frame_buffer: deque = deque(maxlen=buffer_size)
        
        # 初始化缓冲区为1000个零帧
        if buffer_size == 1000:
            zero_frame = np.zeros((channel_num, bins_per_channel), dtype=complex)
            for _ in range(1000):
                self._frame_buffer.append(zero_frame.copy())

        # 状态跟踪
        self._received_channels = 0
        self._completed_frames = 0
        self._generated_hr_results = 0
        self._current_max_bin = 0  # 当前能量最大bin
        self._running = True
        self._start_time = None

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("心率处理线程已启动...")
        import time
        self._start_time = time.time()

        try:
            while self._running:
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)
                except Empty:
                    continue
                except Exception as e:
                    print(f"处理帧时出错: {e}")
                    continue
        except KeyboardInterrupt:
            print("\n心率处理线程收到停止信号")
        finally:
            self._running = False
            print(f"心率处理线程已停止，接收 {self._completed_frames} 完整帧，生成 {self._generated_hr_results} 个心率结果")

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        """处理单帧数据并更新缓冲区.

        Args:
            frame_data: 包含 'channel_id', 'bins_count', 'data' 的字典

        """
        channel_id = frame_data["channel_id"]
        data = np.array(frame_data["data"])
        
        # 统计接收的通道包数
        self._received_channels += 1
        
        # 帧同步：通道 0 表示新一轮开始
        if channel_id == 0:
            # 创建新帧
            current_frame = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
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
            
            # 每100帧处理一次心率
            if self._completed_frames % 100 == 0:
                import time
                elapsed = time.time() - self._start_time if self._start_time else 0
                frame_rate = self._completed_frames / elapsed if elapsed > 0 else 0
                print(f"[心率] 已接收 {self._completed_frames} 完整帧 | 帧率: {frame_rate:.1f} fps")
            
            # 缓冲区满后，生成心率信息
            if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
                self._calculate_heart_rate()

    def _calculate_heart_rate(self) -> None:
        """基于当前1000帧窗口计算心率和HRV指标."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        try:
            # 转换为numpy数组: (1000, 8, 10)
            fft_data = np.array(self._frame_buffer)

            # 1. 找能量最大的bin（只在通道0中）
            max_idx = 0
            max_val = 0
            for i in range(self._bins_per_channel):
                tmp_val = np.sum(np.abs(fft_data[:, 0, i]))
                if max_val < tmp_val:
                    max_idx = i
                    max_val = tmp_val
            self._current_max_bin = max_idx

            # 2. 提取相位并展开
            phase = np.unwrap(np.angle(fft_data[:, 0, max_idx]))

            # 3. 计算二阶差分（7点加权）
            h = self.TIME_STEP
            length = phase.shape[0] - 6
            diff_data = np.zeros_like(phase)
            res_data = (
                phase[3:length+3] * 4.0 +
                (phase[4:length+4] + phase[2:length+2]) -
                2.0 * (phase[5:length+5] + phase[1:length+1]) -
                (phase[6:length+6] + phase[:length])
            ) / (16.0 * h * h)
            diff_data[3:-3] = res_data

            # 4. 过滤异常值
            st_idx = np.abs(diff_data) > self.OUTLIER_THRESHOLD
            diff_data[st_idx] = 0

            # 5. 预处理：归一化
            if not np.any(diff_data):
                return
            
            max_val = max(abs(x) for x in diff_data)
            if max_val == 0:
                return
            norm_data = diff_data / max_val

            # 6. 带通滤波 20-40Hz
            try:
                b, a = butter(  # type: ignore
                    self.FILTER_ORDER,
                    [self.LOWCUT / (self.SAMPLING_RATE / 2), self.HIGHCUT / (self.SAMPLING_RATE / 2)],
                    btype='band',
                    analog=False
                )
                filtered_data = filtfilt(b, a, norm_data)
                
                # 再次归一化滤波后的数据
                max_val = max(abs(x) for x in filtered_data)
                if max_val == 0:
                    return
                filtered_data = filtered_data / max_val
            except Exception as e:
                print(f"滤波失败: {e}")
                return

            # 7. 检测峰值（使用改进的多步骤算法）
            peaks = self._detect_peaks_multistep(filtered_data)

            if len(peaks) < 2:
                return  # 至少需要2个峰值

            # 8. 计算RR间期（峰值间隔，以秒为单位）
            peaks_intervals = np.diff(peaks)
            # 过滤异常间隔（对应心率40-180 bpm）
            filtered_intervals = peaks_intervals[
                (peaks_intervals >= 100) & (peaks_intervals <= 240)
            ]
            
            if len(filtered_intervals) == 0:
                return

            rr_intervals = filtered_intervals * self.TIME_STEP  # 转换为秒

            # 9. 计算心率
            mean_rr = np.mean(rr_intervals)
            heart_rate = 60.0 / mean_rr  # bpm

            # 10. 计算HRV指标
            N = len(rr_intervals)
            sdnn = float(np.std(rr_intervals) * 1000)  # ms
            
            # RMSSD
            rr_diff = np.diff(rr_intervals)
            rmssd = float(np.sqrt(np.mean(rr_diff ** 2)) * 1000) if len(rr_diff) > 0 else 0.0
            
            # pNN50
            nn50_count = np.sum(np.abs(rr_diff) > 0.05)
            pnn50 = float((nn50_count / len(rr_diff)) * 100) if len(rr_diff) > 0 else 0.0

            # IBI数据（毫秒）
            ibi_list = (rr_intervals * 1000).tolist()
            ibi_string = ','.join([str(int(ibi)) for ibi in ibi_list])

            # 11. 构造输出结果
            hr_dict = {
                "status": "succeeded",
                "heart_rate": float(heart_rate),
                "rr_intervals": rr_intervals.tolist(),
                "hrv_sdnn": sdnn,
                "hrv_rmssd": rmssd,
                "hrv_pnn50": pnn50,
                "num_rr_intervals": N,
                "mean_rr_interval": float(mean_rr),
                "sum_square_rr": float(np.sum(rr_intervals ** 2)),
                "peak_count": len(peaks),
                "ibi_data": ibi_string,
                "filtered_waveform": filtered_data[-200:].tolist(),  # 最后200个点用于可视化
                "max_bin": self._current_max_bin,
                "frame_idx": self._completed_frames,
                "timestamp": self._completed_frames * self.TIME_STEP,
            }
            
            # 输出到队列
            if not self._output_queue.full():
                self._output_queue.put(hr_dict)
            
            # 调用回调函数
            if self._callback:
                self._callback(hr_dict)
            
            self._generated_hr_results += 1

        except Exception as e:
            print(f"计算心率时出错: {e}")
            import traceback
            traceback.print_exc()

    def _detect_peaks_multistep(self, filtered_data: np.ndarray) -> np.ndarray:
        """多步骤峰值检测算法（基于 heart_rate_old.py 的 detect_peaks_2）.

        Args:
            filtered_data: 滤波后的归一化数据

        Returns:
            峰值索引数组

        """
        sample_points = len(filtered_data)
        y = filtered_data
        
        # 第一步：找到所有局部最大值
        peak_indices_1 = []
        if y[0] > y[1]:
            peak_indices_1.append(0)
        for i in range(1, sample_points - 1):
            if y[i] >= y[i-1] and y[i] >= y[i+1]:
                peak_indices_1.append(i)
        if y[sample_points-2] < y[sample_points-1]:
            peak_indices_1.append(sample_points-1)
        
        if len(peak_indices_1) < 2:
            return np.array([])

        # 第二步：在局部最大值中找更大的峰值
        peak_indices_2 = []
        if y[peak_indices_1[0]] > y[peak_indices_1[1]]:
            peak_indices_2.append(peak_indices_1[0])
        for i in range(1, len(peak_indices_1) - 1):
            index = peak_indices_1[i]
            index_b = peak_indices_1[i - 1]
            index_a = peak_indices_1[i + 1]
            if y[index] >= y[index_b] and y[index] >= y[index_a]:
                peak_indices_2.append(index)
        if y[peak_indices_1[-2]] < y[peak_indices_1[-1]]:
            peak_indices_2.append(peak_indices_1[-1])

        # 第三步：筛选满足阈值的峰值
        peak_indices_3 = []
        for index in peak_indices_2:
            if y[index] >= 0.3:
                peak_indices_3.append(index)
        
        if len(peak_indices_3) < 2:
            return np.array([])

        # 第四步：合并间隔1-40的峰值，取较大者
        peak_indices_4 = []
        j = 0
        while j < len(peak_indices_3) - 1:
            index = peak_indices_3[j]
            index_a = peak_indices_3[j + 1]
            
            if 1 <= index_a - index <= 40:
                # 选择较大的值
                if y[index_a] >= y[index]:
                    select_index = index_a
                else:
                    select_index = index
                j += 1
                peak_indices_4.append(select_index)
            else:
                peak_indices_4.append(index)
            j += 1
        
        # 检查最后一个索引
        if len(peak_indices_3) > 0 and peak_indices_3[-1] not in peak_indices_4:
            if len(peak_indices_4) == 0 or peak_indices_3[-1] - peak_indices_4[-1] > 40:
                peak_indices_4.append(peak_indices_3[-1])

        # 第五步：处理间隔40-80的峰值
        peak_indices_5 = []
        j = 0
        while j <= len(peak_indices_4) - 2:
            index = peak_indices_4[j]
            index_a = peak_indices_4[j + 1]
            
            if j == 0:
                if not 40 <= index_a - index <= 80:
                    j += 1
                    continue
            
            if 1 <= index_a - index <= 80:
                j += 1
                if j == len(peak_indices_4) - 1:
                    peak_indices_5.append(index)
                    break
            
            peak_indices_5.append(index)
            j += 1
            
            if j == len(peak_indices_4) - 1:
                peak_indices_5.append(peak_indices_4[j])
                break

        return np.array(peak_indices_5)

    def stop(self) -> None:
        """停止处理线程."""
        self._running = False

    def get_result(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """从输出队列获取处理结果.

        Args:
            timeout: 超时时间（秒）

        Returns:
            包含心率信息的字典，超时返回None

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
            "generated_hr_results": self._generated_hr_results,
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
            f"MMWHeartRateThread("
            f"frames={self._completed_frames}, "
            f"hr_results={self._generated_hr_results}, "
            f"running={self._running})"
        )
