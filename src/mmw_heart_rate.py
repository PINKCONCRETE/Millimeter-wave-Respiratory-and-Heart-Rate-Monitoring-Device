"""毫米波心率信号处理模块.

基于差分相位信号提取心率信息。
使用峰值检测算法计算心率和心率变异性(HRV)。
改编自 heart_rate_old.py
"""
import multiprocessing
import time
from collections import deque
from queue import Empty
from typing import Any, List, Union

import numpy as np
from src.heart_rate_processor import calculate_heart_rate


class MMWHeartRateProcess(multiprocessing.Process):
    """毫米波心率信号处理进程（消费者）.

    从雷达进程的队列中获取FFT数据，实时生成心率信息。
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

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: Any = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        buffer_size: int = 1000,
    ) -> None:
        """初始化心率处理进程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送处理后的心率信息（可选）
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

    def _calculate_stress_metrics(self, ibi_list: Union[List[float], np.ndarray]) -> tuple[float, float, float, float, float, float, int, float, str]:
        """计算HRV(SDNN, RMSSD, pNN50)和压力指数.
        
        Returns:
            sdnn, rmssd, pnn50, mean_rr, sum_square_rr, stress_index, num_rr, hrv_sdnn (duplicate for compat), stress_level
        """
        # Fix: handle numpy array truth value ambiguity by checking len directly
        if len(ibi_list) < 2:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, "低"
            
        # HRV Calculation
        ibi_array = np.array(ibi_list)
        # Convert to seconds for standard HRV metrics calculation (if inputs are in ms)
        # Usually ibi_list from processor is in ms.
        rr_intervals_s = ibi_array / 1000.0
        
        # 1. SDNN (ms)
        sdnn = float(np.std(rr_intervals_s) * 1000)
        
        # 2. RMSSD (ms)
        rr_diff = np.diff(rr_intervals_s)
        rmssd = float(np.sqrt(np.mean(rr_diff ** 2)) * 1000)
        
        # 3. pNN50 (%)
        nn50_count = np.sum(np.abs(rr_diff) > 0.05)
        pnn50 = float((nn50_count / len(rr_diff)) * 100)
        
        # 4. Mean RR (ms)
        mean_rr = float(np.mean(ibi_array))
        
        # 5. Sum Square RR (ms^2) - from old code logic, though unit is ambiguous there, assuming raw sum of squares
        # Old code: sum_square_rr = result["sum_square_RR"] which came from processor.
        # But here we calculate from ibi_list directly to be safe or use processor output if available.
        # Let's calculate it here to be consistent.
        sum_square_rr = float(np.sum(ibi_array ** 2))
        
        num_rr = len(ibi_list)

        # Stress Index (Baevsky)
        # SI = AMo / (2 * Mo * MxDMn)
        # AMo: Mode amplitude (%)
        # Mo: Mode (s)
        # MxDMn: Variation range (s)
        
        # Convert to ms for histogram if not already
        if np.mean(ibi_array) < 2.0: # Likely seconds
             ibi_ms = ibi_array * 1000
        else:
             ibi_ms = ibi_array
             
        # Histogram with 50ms bins
        bins = np.arange(0, 2000, 50)
        hist, bin_edges = np.histogram(ibi_ms, bins=bins)
        
        max_bin_idx = np.argmax(hist)
        mo_ms = (bin_edges[max_bin_idx] + bin_edges[max_bin_idx+1]) / 2
        amo = (hist[max_bin_idx] / len(ibi_ms)) * 100
        mxdmn_ms = np.max(ibi_ms) - np.min(ibi_ms)
        
        if mo_ms > 0 and mxdmn_ms > 0:
            si = amo / (2 * (mo_ms/1000) * (mxdmn_ms/1000))
        else:
            si = 0
            
        # Stress Level
        if si < 50:
            level = "低"
        elif si < 150:
            level = "正常"
        elif si < 500:
            level = "中"
        else:
            level = "高"
            
        return sdnn, rmssd, pnn50, mean_rr, sum_square_rr, si, num_rr, sdnn, level

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("心率处理进程已启动...")
        
        # 初始化进程内状态
        self._frame_buffer = deque(maxlen=self._buffer_size)
        
        # 初始化缓冲区为1000个零帧
        if self._buffer_size == 1000:
            zero_frame = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            for _ in range(1000):
                self._frame_buffer.append(zero_frame.copy())

        self._received_channels = 0
        self._completed_frames = 0
        self._last_completed_frames = 0
        self._generated_hr_results = 0
        self._current_max_bin = 0
        self._start_time = time.time()
        self.last_heart_rate = 0
        self.final_heart_rate = 0
        
        self._current_frame_build = None

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
                        print(f"[HeartRate] FPS: {fps:.1f}")
                        last_fps_frame_count = self._completed_frames
                        last_fps_time = now
                        
                except Empty:
                    continue
                except Exception as e:
                    print(f"心率处理异常: {e}")
        except KeyboardInterrupt:
            print("\n心率处理进程收到停止信号")
        finally:
            print(f"心率处理进程已停止，接收 {self._completed_frames} 完整帧")

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

        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=complex)
        
        self._received_channels += 1
        
        if channel_id == 0:
            self._current_frame_build = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            self._current_frame_build[channel_id] = data
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return

        if channel_id == self._channel_num - 1 and self._current_frame_build is not None:
            self._completed_frames += 1
            self._frame_buffer.append(self._current_frame_build.copy())
            
            # 每1000帧处理一次
            if self._completed_frames % 1000 == 0:
                current_time = time.time()
                elapsed = current_time - self._start_time if self._start_time else 0
                frame_rate = (self._completed_frames - self._last_completed_frames) / elapsed if elapsed > 0 else 0
                print(f"[心率] 已接收 {self._completed_frames} 完整帧 | 帧率: {frame_rate:.1f} fps")
                self._last_completed_frames = self._completed_frames
                self._start_time = current_time
                
                if len(self._frame_buffer) >= self.MIN_BUFFER_SIZE:
                    self._calculate_heart_rate()

    def _calculate_heart_rate(self) -> None:
        """基于当前1000帧窗口计算心率."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        try:
            fft_data = np.array(self._frame_buffer)
            result = calculate_heart_rate(fft_data)
            
            if result["status"] == "failed":
                self.final_heart_rate = self.last_heart_rate
            else: 
                self.last_heart_rate = self.final_heart_rate
                self.final_heart_rate = result["heart_rate"]
            
            # Calculate HRV and Stress
            sdnn, rmssd, pnn50, mean_rr, sum_square_rr, stress_index, num_rr, hrv_sdnn, stress_level = self._calculate_stress_metrics(result.get("ibi_list", []))

            # 构造输出结果
            hr_dict = {
                "type": "heart_rate_data",
                "status": result["status"],
                "heart_rate": float(self.final_heart_rate),
                "hrv_sdnn": sdnn,
                "hrv_rmssd": rmssd,
                "hrv_pnn50": pnn50,
                "mean_rr_interval": mean_rr,
                "sum_square_rr": sum_square_rr,
                "num_rr_intervals": num_rr,
                "stress_index": stress_index,
                "stress_level": stress_level,
                "frame_idx": self._completed_frames,
                "timestamp": self._completed_frames * self.TIME_STEP,
                "method": "old_algorithm_ported"
            }
            
            if not self._output_queue.full():
                self._output_queue.put(hr_dict)
            
            self._generated_hr_results += 1

        except Exception as e:
            print(f"计算心率时出错: {e}")
