"""毫米波人体存在检测模块.

基于FFT能量幅度和峰值强度进行人体存在判断。
改编自 human_check_old.py，集成到流水线架构中。
"""

import copy
import multiprocessing
import time
from collections import deque
from queue import Empty
from typing import Any

import numpy as np


class HumanCheckBase:
    """人体检测基类."""

    def __init__(self) -> None:
        self._last_offset = 0
        self._has_human = False

    def reset(self) -> None:
        pass

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        if self._last_offset != offset:
            self.reset()
            self._has_human = True
        self._last_offset = offset
        return self._has_human

    def has_human(self) -> bool:
        return self._has_human


class HumanCheckByWave(HumanCheckBase):
    """基于FFT波动幅度进行人体检测."""

    BINS_PER_CHANNEL = 10
    NEAR_PEAK_RANGE = 5

    def __init__(
        self,
        accumulate_frame_count: int = 100,
        tollerence_frame_count: int = 30,
        tollerence: float = 0.05,
    ) -> None:
        super().__init__()
        self._base_energies = [3001.0] * self.BINS_PER_CHANNEL
        self._accumulated_count = 0
        self._exception_count = 0

        self.accumulate_frame_count = accumulate_frame_count
        self.tollerence_frame_count = tollerence_frame_count
        self.tollerence = tollerence

    def reset(self) -> None:
        self._base_energies = [3001.0] * self.BINS_PER_CHANNEL
        self._accumulated_count = 0
        self._exception_count = 0

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        super().do_human_check(energies, offset)
        need_reset_base = False
        is_exception = False

        if offset < self.NEAR_PEAK_RANGE:
            for bin in range(offset, self.NEAR_PEAK_RANGE):
                base = self._base_energies[bin - offset]
                energy = energies[bin - offset]
                diff = energy - base
                if base > 3000.0 and abs(diff / base) > self.tollerence:
                    is_exception = True
                    break

        start_bin = self.NEAR_PEAK_RANGE if offset < self.NEAR_PEAK_RANGE else offset
        peak = max(energies[start_bin - offset :])
        for bin in range(start_bin, offset + self.BINS_PER_CHANNEL):
            energy = energies[bin - offset]
            if energy > peak * 0.5:
                base = self._base_energies[bin - offset]
                diff = energy - base
                if base > 3000.0 and abs(diff / base) > self.tollerence:
                    is_exception = True
                    break

        if is_exception:
            self._exception_count += 1

        self._accumulated_count += 1

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
    """基于FFT峰值强度进行人体检测."""

    BINS_PER_CHANNEL = 10
    PEAK_THRESHOLD = [
        79350.0,
        109245.0,
        120000.0,
        117750.0,
        90450.0,  # 0-4
        72600.0,
        69000.0,
        66000.0,
        63000.0,
        61500.0,  # 5-9
        58500.0,
        55500.0,
        52500.0,
        49500.0,
        46500.0,  # 10-14
        45000.0,
        43500.0,
        42000.0,
        40500.0,
        39000.0,  # 15-19
        37500.0,
        36000.0,
        34500.0,
        33000.0,
        31500.0,  # 20-24
        30000.0,
        28500.0,
        27000.0,
        25500.0,
        24000.0,  # 25-29
        22500.0,
        21000.0,
        19500.0,
        18000.0,
        16500.0,  # 30-34
        16500.0,
        16500.0,
        16500.0,
        15000.0,
        15000.0,  # 35-39
        15000.0,
        15000.0,
        15000.0,
        15000.0,
        15000.0,  # 40-44
    ]

    def __init__(self, accumulate_count: int = 100, threshold_count: int = 80) -> None:
        super().__init__()
        self.accumulate_count = accumulate_count
        self.threshold_count = threshold_count
        self.cache: deque[bool] = deque(maxlen=accumulate_count)
        self.frame_count = 0
        self.over_count = 0

    def reset(self) -> None:
        self.cache = deque(maxlen=self.accumulate_count)
        self.over_count = 0
        self.frame_count = 0

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        super().do_human_check(energies, offset)

        over_threshold = False
        for bin_idx in range(offset, offset + self.BINS_PER_CHANNEL):
            if (
                bin_idx < len(self.PEAK_THRESHOLD)
                and energies[bin_idx - offset] > self.PEAK_THRESHOLD[bin_idx]
            ):
                over_threshold = True
                break

        if over_threshold:
            self.cache.append(True)
            self.over_count += 1
        else:
            self.cache.append(False)

        self.frame_count += 1
        if self.frame_count == self.accumulate_count:
            self._has_human = self.over_count >= self.threshold_count
            original = self.cache.popleft()
            self.frame_count -= 1
            if original:
                self.over_count -= 1

        return self._has_human


class HumanCheck:
    """综合人体检测器."""

    def __init__(self) -> None:
        self.check_by_verysmallwave = HumanCheckByWave(
            accumulate_frame_count=100,
            tollerence_frame_count=5,
            tollerence=0.005,
        )
        self.check_by_smallwave = HumanCheckByWave(
            accumulate_frame_count=200,
            tollerence_frame_count=30,
            tollerence=0.05,
        )
        self.check_by_bigwave = HumanCheckByWave(
            accumulate_frame_count=200,
            tollerence_frame_count=10,
            tollerence=0.10,
        )
        self.check_by_peak = HumanCheckByPeak(
            accumulate_count=200,
            threshold_count=10,
        )
        self._has_human = False

    def do_human_check(self, energies: list[float], offset: int) -> bool:
        self.check_by_verysmallwave.do_human_check(energies, offset)
        self.check_by_smallwave.do_human_check(energies, offset)
        self.check_by_bigwave.do_human_check(energies, offset)
        self.check_by_peak.do_human_check(energies, offset)

        res_list = [
            self.check_by_smallwave.has_human(),
            self.check_by_bigwave.has_human(),
            self.check_by_peak.has_human(),
        ]

        if sum(res_list) > 1:
            self._has_human = True
        else:
            self._has_human = False

        # Debug printing every 100 calls or so (not ideal here, but good for now)
        # We can't easily count here without self state.
        return self._has_human


class MMWHumanCheckProcess(multiprocessing.Process):
    """毫米波人体检测进程（消费者）.

    从雷达进程的队列中获取FFT数据，实时判断是否有人存在。
    使用能量波动和峰值强度的综合判断方法。
    """

    def __init__(
        self,
        input_queue: multiprocessing.Queue,
        output_queue: Any = None,
        channel_num: int = 8,
        bins_per_channel: int = 10,
    ) -> None:
        super().__init__()
        self.daemon = True

        self._input_queue = input_queue
        self._output_queue = output_queue or multiprocessing.Queue()
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel

        self._stop_event = multiprocessing.Event()

    def run(self) -> None:
        """主循环."""
        print("人体检测进程已启动...")

        self._human_checker = HumanCheck()
        self._received_channels = 0
        self._completed_frames = 0
        self._has_human = False
        self._start_time = time.time()
        self._current_frame_build = None
        self._current_offset = 0
        self._detection_history = deque(maxlen=100)

        last_fps_time = time.time()
        last_fps_frame_count = 0
        try:
            while not self._stop_event.is_set():
                try:
                    frame_data = self._input_queue.get(timeout=1.0)
                    self._process_single_frame(frame_data)

                    now = time.time()
                    if now - last_fps_time >= 1.0:
                        fps = (self._completed_frames - last_fps_frame_count) / (
                            now - last_fps_time
                        )
                        print(f"[HumanCheck] FPS: {fps:.1f}")
                        last_fps_frame_count = self._completed_frames
                        last_fps_time = now
                except Empty:
                    continue
                except Exception as e:
                    print(f"人体检测异常: {e}")
        except KeyboardInterrupt:
            print("\n人体检测进程收到停止信号")
        finally:
            print("人体检测进程已停止")

    def stop(self) -> None:
        self._stop_event.set()

    def _process_single_frame(self, frame_data: dict[str, Any]) -> None:
        channel_id = frame_data.get("channel_id")
        data = frame_data.get("data")

        if channel_id is None or data is None:
            return

        self._received_channels += 1
        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=complex)

        if channel_id == 0:
            self._current_offset = frame_data.get("offset", 0)
            self._current_frame_build = np.zeros(
                (self._channel_num, self._bins_per_channel), dtype=complex
            )
            self._current_frame_build[channel_id] = data
        elif self._current_frame_build is not None:
            self._current_frame_build[channel_id] = data
        else:
            return

        if (
            channel_id == self._channel_num - 1
            and self._current_frame_build is not None
        ):
            self._completed_frames += 1

            energies = np.sum(np.abs(self._current_frame_build), axis=0).tolist()
            has_human = self._human_checker.do_human_check(
                energies, self._current_offset
            )

            # Debug log every 200 frames (approx 10s at 20Hz)
            if self._completed_frames % 200 == 0:
                print(
                    f"[HumanCheck] Status: {'Normal' if has_human else 'Away'} | "
                    f"S-Wave: {self._human_checker.check_by_smallwave.has_human()} | "
                    f"B-Wave: {self._human_checker.check_by_bigwave.has_human()} | "
                    f"Peak: {self._human_checker.check_by_peak.has_human()}"
                )

            self._has_human = has_human
            self._detection_history.append(has_human)

            result = {
                "type": "human_check_data",
                "has_human": self._has_human,
                "frame_count": self._completed_frames,
                "offset": self._current_offset,
                "detection_rate": sum(self._detection_history)
                / len(self._detection_history)
                if self._detection_history
                else 0.0,
            }

            if not self._output_queue.full():
                self._output_queue.put(result)
