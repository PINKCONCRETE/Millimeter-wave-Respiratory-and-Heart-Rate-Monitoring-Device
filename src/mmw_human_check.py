"""毫米波人体存在检测模块.

基于FFT能量幅度和峰值强度进行人体存在判断。
改编自 human_check_old.py，集成到流水线架构中。
"""
import copy
import threading
from collections import deque
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

import numpy as np


class HumanCheckBase:
    """人体检测基类.

    提供基本的offset切换检测和状态管理。

    """

    def __init__(self) -> None:
        """初始化基类."""
        self._last_offset = 0
        self._has_human = False

    def reset(self) -> None:
        """重置检测状态（子类实现）."""
        pass

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        """执行人体检测.

        Args:
            energies: 检测窗口内每个bin的能量强度
            offset: 窗口偏移

        Returns:
            是否检测到人体

        """
        if self._last_offset != offset:
            self.reset()
            self._has_human = True
        self._last_offset = offset
        return self._has_human

    def has_human(self) -> bool:
        """返回当前是否有人."""
        return self._has_human


class HumanCheckByWave(HumanCheckBase):
    """基于FFT波动幅度进行人体检测.

    通过累积一定帧数，判断能量波动是否超过阈值，来判断是否有人。

    Attributes:
        accumulate_frame_count: 需要累积的帧数
        tollerence_frame_count: 允许出现的异常帧数
        tollerence: 能量波动容忍度

    """

    BINS_PER_CHANNEL = 10  # 每个通道的频率bin数量
    NEAR_PEAK_RANGE = 4 #近距离处会有一个伪峰

    def __init__(
        self,
        accumulate_frame_count: int = 100,
        tollerence_frame_count: int = 30,
        tollerence: float = 0.05,
    ) -> None:
        """初始化波动检测器.

        Args:
            accumulate_frame_count: 需要累积的帧数
            tollerence_frame_count: 允许出现的异常帧数
            tollerence: 能量波动容忍度

        """
        super().__init__()
        self._base_energies = [0.0] * self.BINS_PER_CHANNEL
        self._accumulated_count = 0
        self._exception_count = 0

        self.accumulate_frame_count = accumulate_frame_count
        self.tollerence_frame_count = tollerence_frame_count
        self.tollerence = tollerence

    def reset(self) -> None:
        """重置检测状态."""
        self._base_energies = [0.0] * self.BINS_PER_CHANNEL
        self._accumulated_count = 0
        self._exception_count = 0

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        """执行波动检测.

        Args:
            energies: 检测窗口内每个bin的能量强度
            offset: 窗口偏移

        Returns:
            是否检测到人体

        """
        super().do_human_check(energies, offset)

        need_reset_base = False

        #近距离的伪峰中，计算每个bin的能量波动
        is_exception = False
        if offset < self.NEAR_PEAK_RANGE:
            for bin in range(offset, self.NEAR_PEAK_RANGE):
                base = self._base_energies[bin - offset]
                energy = energies[bin - offset]
                diff = energy - base
                if base > 3000. and abs(diff / base) > self.tollerence:
                    is_exception = True
                    break
        
        #从剩余bin中，找出峰值，检测能量波动（只检测强度与峰值的比例大于一定阈值的bin）
        start_bin = self.NEAR_PEAK_RANGE if offset < self.NEAR_PEAK_RANGE else offset
        peak = max(energies[start_bin - offset:])
        for bin in range(start_bin, offset + self.BINS_PER_CHANNEL):
            energy = energies[bin - offset]
            if energy > peak * 0.5:
                base = self._base_energies[bin - offset]
                diff = energy - base
                if base > 3000. and abs(diff / base) > self.tollerence:
                    is_exception = True
                    break

        if is_exception:
            self._exception_count += 1 

        # # 对比信号强度差异
        # for base, energy, bin_idx in zip(
        #     self._base_energies, energies, range(offset, offset + self.BINS_PER_CHANNEL)
        # ):
        #     if base < 0.001:
        #         need_reset_base = True
        #         break
        #     diff = energy - base
        #     # 基准能量大于3000时，判断相对变化是否超过容忍度
        #     if base > 3000.0 and abs(diff / base) > self.tollerence:
        #         self._exception_count += 1
        #         break

        self._accumulated_count += 1

        # 判断是否达到累积帧数或异常帧数阈值
        if (
            self._accumulated_count >= self.accumulate_frame_count
            or self._exception_count >= self.tollerence_frame_count
        ):
            if self._exception_count >= self.tollerence_frame_count:
                self._has_human = True
            else:
                self._has_human = False
            need_reset_base = True

        if need_reset_base:
            self._accumulated_count = 0
            self._exception_count = 0
            self._base_energies = copy.deepcopy(energies)

        return self._has_human


class HumanCheckByPeak(HumanCheckBase):
    """基于FFT峰值强度进行人体检测.

    通过判断FFT峰值是否超过预设阈值，来判断是否有人。

    Attributes:
        accumulate_count: 累积帧数
        threshold_count: 超过阈值的帧数阈值

    """

    BINS_PER_CHANNEL = 10  # 每个通道的频率bin数量

    # 峰值阈值表（45个bin的阈值）
    PEAK_THRESHOLD = [
        52900.0, 72830.0, 80000.0, 78500.0, 60300.0,  # 0-4
        48400.0, 46000.0, 44000.0, 42000.0, 41000.0,  # 5-9
        39000.0, 37000.0, 35000.0, 33000.0, 31000.0,  # 10-14
        30000.0, 29000.0, 28000.0, 27000.0, 26000.0,  # 15-19
        25000.0, 24000.0, 23000.0, 22000.0, 21000.0,  # 20-24
        20000.0, 19000.0, 18000.0, 17000.0, 16000.0,  # 25-29
        15000.0, 14000.0, 13000.0, 12000.0, 11000.0,  # 30-34
        11000.0, 11000.0, 11000.0, 10000.0, 10000.0,  # 35-39
        10000.0, 10000.0, 10000.0, 10000.0, 10000.0,  # 40-44
    ]

    def __init__(self, accumulate_count: int = 100, threshold_count: int = 80) -> None:
        """初始化峰值检测器.

        Args:
            accumulate_count: 累积帧数
            threshold_count: 超过阈值的帧数阈值

        """
        super().__init__()
        self.accumulate_count = accumulate_count
        self.threshold_count = threshold_count
        self.cache: deque[bool] = deque(maxlen=accumulate_count)
        self.frame_count = 0
        self.over_count = 0  # 超过阈值的帧数

    def reset(self) -> None:
        """重置检测状态."""
        self.cache = deque(maxlen=self.accumulate_count)
        self.over_count = 0
        self.frame_count = 0

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        """执行峰值检测.

        Args:
            energies: 检测窗口内每个bin的能量强度
            offset: 窗口偏移

        Returns:
            是否检测到人体

        """
        super().do_human_check(energies, offset)

        over_threshold = False
        for bin_idx in range(offset, offset + self.BINS_PER_CHANNEL):
            # 检查当前bin的能量是否超过对应的阈值
            if energies[bin_idx - offset] > self.PEAK_THRESHOLD[bin_idx]:
                over_threshold = True
                break

        if over_threshold:
            self.cache.append(True)
            self.over_count += 1
        else:
            self.cache.append(False)

        # 累积足够帧数后，重新确定是否有人
        self.frame_count += 1
        if self.frame_count == self.accumulate_count:
            self._has_human = self.over_count >= self.threshold_count
            # 移出最早的那一帧
            original = self.cache.popleft()
            self.frame_count -= 1
            if original:
                self.over_count -= 1

        return self._has_human


class HumanCheck:
    """综合人体检测器.

    结合波动检测和峰值检测，实现更可靠的人体存在判断。

    """

    def __init__(self) -> None:
        """初始化综合检测器."""
        # 关注是否有大量微动
        self.check_by_smallwave = HumanCheckByWave(
            accumulate_frame_count=200,
            tollerence_frame_count=20,
            tollerence=0.02,
        )
        # 关注是否有少量大动
        self.check_by_bigwave = HumanCheckByWave(
            accumulate_frame_count=200,
            tollerence_frame_count=10,
            tollerence=0.10,
        )
        # 关注峰值是否足够强
        self.check_by_peak = HumanCheckByPeak(
            accumulate_count=200,
            threshold_count=10,
        )
        self._has_human = False

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        """执行综合人体检测.

        Args:
            energies: 检测窗口内每个bin的能量强度
            offset: 窗口偏移

        Returns:
            是否检测到人体

        """
        self.check_by_smallwave.do_human_check(energies, offset)
        self.check_by_bigwave.do_human_check(energies, offset)
        self.check_by_peak.do_human_check(energies, offset)

        res_list = [
            self.check_by_smallwave.has_human(),
            self.check_by_bigwave.has_human(),
            self.check_by_peak.has_human(),
        ]
        
        print(res_list)
        # 三种检测方法中有两种或以上判断有人，则认为有人
        if sum(res_list) > 1:
        # if res_list[1]:
            self._has_human = True
        else:
            self._has_human = False

        return self._has_human

    def has_human(self) -> bool:
        """返回当前是否有人."""
        return self._has_human


class MMWHumanCheckThread(threading.Thread):
    """毫米波人体检测线程（消费者）.

    从雷达线程的队列中获取FFT数据，实时判断是否有人存在。
    使用能量波动和峰值强度的综合判断方法。

    Attributes:
        channel_num: 通道数量（默认8）
        bins_per_channel: 每个通道的频率bin数量（默认10）

    """

    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue | None = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """初始化人体检测线程.

        Args:
            input_queue: 输入队列，接收雷达FFT数据
            output_queue: 输出队列，发送检测结果（可选）
            channel_num: 通道数量（默认8）
            bins_per_channel: 每个通道的频率bin数量（默认10）
            callback: 可选回调函数 callback(result_dict)

        """
        super().__init__(daemon=True)

        self._input_queue = input_queue
        self._output_queue = output_queue or Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._callback = callback

        # 人体检测器
        self._human_checker = HumanCheck()

        # 状态跟踪
        self._received_channels = 0
        self._completed_frames = 0
        self._has_human = False
        self._running = True
        self._start_time = None
        
        # 当前帧缓冲（用于累积8个通道的数据）
        self._current_frame = None
        self._current_offset = 0

        # 历史记录
        self._detection_history = deque(maxlen=100)  # 最近100帧检测结果

    def run(self) -> None:
        """主循环：从队列消费数据并处理."""
        print("人体检测线程已启动...")
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
            print("\n接收到中断信号，正在停止...")
        finally:
            print("人体检测线程已停止")

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        """处理单帧FFT数据.

        Args:
            frame_data: 包含FFT数据的字典，格式为 {'channel_id': int, 'data': ndarray, 'offset': int}

        """
        channel_id = frame_data.get("channel_id")
        data = frame_data.get("data")
        
        if channel_id is None or data is None:
            return
        
        # 统计接收的通道包数
        self._received_channels += 1
        
        # 确保数据是ndarray
        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=complex)
        
        # 帧同步：通道 0 表示新一轮开始
        if channel_id == 0:
            # 保存offset
            self._current_offset = frame_data.get("offset", 0)
            # 创建新帧
            self._current_frame = np.zeros((self._channel_num, self._bins_per_channel), dtype=complex)
            self._current_frame[channel_id] = data
        elif self._current_frame is not None:
            # 更新当前帧的通道数据
            self._current_frame[channel_id] = data
        else:
            return  # 等待通道 0开始
        
        # 完整帧接收完毕（0-7号通道都收到）
        if channel_id == self._channel_num - 1 and self._current_frame is not None:
            self._completed_frames += 1
            
            # 计算当前帧每个bin的能量（对所有通道求和）
            # _current_frame shape: (8, 10)
            energies = np.sum(np.abs(self._current_frame), axis=0).tolist()
            
            # 执行人体检测
            has_human = self._human_checker.do_human_check(energies, self._current_offset)
            
            self._has_human = has_human
            self._detection_history.append(has_human)
            
            # 构造输出结果
            result = {
                "has_human": has_human,
                "frame_count": self._completed_frames,
                "offset": self._current_offset,
                "detection_rate": sum(self._detection_history) / len(self._detection_history)
                if self._detection_history
                else 0.0,
            }
            
            # 输出到队列
            if not self._output_queue.full():
                self._output_queue.put(result)
            
            # 调用回调函数
            if self._callback:
                self._callback(result)

    def stop(self) -> None:
        """停止处理线程."""
        self._running = False

    def get_result(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """从输出队列获取检测结果.

        Args:
            timeout: 超时时间（秒）

        Returns:
            包含检测结果的字典，超时返回None

        """
        try:
            return self._output_queue.get(timeout=timeout)
        except Empty:
            return None

    def has_human(self) -> bool:
        """返回当前是否检测到人体."""
        return self._has_human

    def get_statistics(self) -> dict[str, int | float]:
        """获取处理统计信息."""
        import time

        elapsed = time.time() - self._start_time if self._start_time else 0
        detection_rate = (
            sum(self._detection_history) / len(self._detection_history)
            if self._detection_history
            else 0.0
        )

        return {
            "completed_frames": self._completed_frames,
            "received_channels": self._received_channels,
            "has_human": self._has_human,
            "detection_rate": detection_rate,
            "input_queue_size": self._input_queue.qsize(),
            "output_queue_size": self._output_queue.qsize(),
            "elapsed_time": elapsed,
            "frame_rate": self._completed_frames / elapsed if elapsed > 0 else 0,
        }

    def __repr__(self) -> str:
        """返回对象的字符串表示."""
        detection_rate = (
            sum(self._detection_history) / len(self._detection_history)
            if self._detection_history
            else 0.0
        )
        return (
            f"MMWHumanCheckThread("
            f"frames={self._completed_frames}, "
            f"has_human={self._has_human}, "
            f"detection_rate={detection_rate:.1%}, "
            f"running={self._running})"
        )


def check_human(fft_data: np.ndarray, offsets: np.ndarray) -> bool:
    """简化的人体检测接口（兼容旧代码）.

    Args:
        fft_data: FFT数据数组
        offsets: offset数组

    Returns:
        是否检测到人体

    """
    human_checker = HumanCheck()

    for once_fft_data, off in zip(np.abs(fft_data), offsets.tolist()):
        energies = once_fft_data.sum(axis=0).tolist()
        human_checker.do_human_check(energies, off)

    return human_checker.has_human()
