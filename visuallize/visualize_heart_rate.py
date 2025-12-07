"""毫米波心率数据实时可视化脚本.

使用matplotlib实时显示滤波后的心率波形、心率趋势和HRV指标。
"""
import sys
import time
from collections import deque
from pathlib import Path
from queue import Queue

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_heart_rate import MMWHeartRateThread  # noqa: E402
from src.mmw_rader import MMWRadarThread  # noqa: E402

# 处理中文和负号显示问题
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 中文字体
plt.rcParams["axes.unicode_minus"] = False  # 负号显示


class HeartRateVisualizer:
    """毫米波心率数据实时可视化器.

    使用matplotlib动画实时显示心率波形、心率趋势和HRV指标。

    Attributes:
        waveform_window_size: 心率波形滑动窗口大小（数据点数）
        hr_history_size: 心率历史记录长度

    """

    def __init__(
        self,
        waveform_window_size: int = 1000,
        hr_history_size: int = 20,
    ) -> None:
        """初始化可视化器.

        Args:
            waveform_window_size: 心率波形滑动窗口大小（默认1000个数据点）
            hr_history_size: 心率历史记录长度（默认20次）

        """
        self.waveform_window_size = waveform_window_size
        self.hr_history_size = hr_history_size

        # 心率波形数据缓冲区（滤波后的归一化数据）
        self.waveform_data = deque(maxlen=waveform_window_size)
        self.waveform_time = deque(maxlen=waveform_window_size)

        # 心率趋势数据
        self.hr_history = deque(maxlen=hr_history_size)
        self.hr_time = deque(maxlen=hr_history_size)

        # HRV指标历史
        self.sdnn_history = deque(maxlen=hr_history_size)
        self.rmssd_history = deque(maxlen=hr_history_size)

        # 当前统计信息
        self.current_hr = 0.0
        self.current_sdnn = 0.0
        self.current_rmssd = 0.0
        self.current_pnn50 = 0.0
        self.peak_count = 0
        self.max_bin = 0
        self.status = "waiting"

        # 初始化图形
        self.fig = None
        self.axes = []
        self.lines = []
        self.text_objects = []

        # 时间基准
        self.start_time = time.time()
        self.frame_count = 0

    def _init_plot(self) -> None:
        """初始化matplotlib图形和子图."""
        self.fig = plt.figure(figsize=(15, 10))
        self.fig.suptitle("毫米波心率实时监测", fontsize=16, fontweight="bold")

        # 使用GridSpec创建复杂布局
        gs = GridSpec(3, 2, figure=self.fig, hspace=0.3, wspace=0.3)

        # 子图1: 滤波后的心率波形 (占据上方两列)
        ax1 = self.fig.add_subplot(gs[0, :])
        ax1.set_title("心率波形（带通滤波 20-40Hz）", fontsize=12)
        ax1.set_xlabel("样本点")
        ax1.set_ylabel("归一化幅度")
        ax1.grid(True, alpha=0.3)
        (line1,) = ax1.plot([], [], "b-", linewidth=1, label="心率波形")
        ax1.legend(loc="upper right")
        ax1.set_ylim(-1, 1)

        # 子图2: 心率趋势
        ax2 = self.fig.add_subplot(gs[1, 0])
        ax2.set_title("心率趋势", fontsize=12)
        ax2.set_xlabel("测量次数")
        ax2.set_ylabel("心率 (bpm)")
        ax2.set_ylim(40, 180)
        ax2.grid(True, alpha=0.3)
        (line2,) = ax2.plot([], [], "r-o", linewidth=2, markersize=4, label="心率")
        ax2.axhline(y=60, color="g", linestyle="--", alpha=0.5, label="正常下限")
        ax2.axhline(y=100, color="orange", linestyle="--", alpha=0.5, label="正常上限")
        ax2.legend(loc="upper right", fontsize=8)

        # 子图3: HRV - SDNN
        ax3 = self.fig.add_subplot(gs[1, 1])
        ax3.set_title("HRV - SDNN (标准差)", fontsize=12)
        ax3.set_xlabel("测量次数")
        ax3.set_ylabel("SDNN (ms)")
        ax3.grid(True, alpha=0.3)
        (line3,) = ax3.plot([], [], "g-o", linewidth=2, markersize=4, label="SDNN")
        ax3.legend(loc="upper right", fontsize=8)

        # 子图4: HRV - RMSSD
        ax4 = self.fig.add_subplot(gs[2, 0])
        ax4.set_title("HRV - RMSSD (均方根)", fontsize=12)
        ax4.set_xlabel("测量次数")
        ax4.set_ylabel("RMSSD (ms)")
        ax4.grid(True, alpha=0.3)
        (line4,) = ax4.plot([], [], "m-o", linewidth=2, markersize=4, label="RMSSD")
        ax4.legend(loc="upper right", fontsize=8)

        # 子图5: 统计信息文本显示
        ax5 = self.fig.add_subplot(gs[2, 1])
        ax5.axis("off")
        ax5.set_title("实时统计信息", fontsize=12)

        # 创建文本对象
        text_status = ax5.text(0.1, 0.95, "", fontsize=10, verticalalignment="top")
        text_hr = ax5.text(0.1, 0.80, "", fontsize=12, verticalalignment="top", fontweight="bold")
        text_sdnn = ax5.text(0.1, 0.65, "", fontsize=10, verticalalignment="top")
        text_rmssd = ax5.text(0.1, 0.50, "", fontsize=10, verticalalignment="top")
        text_pnn50 = ax5.text(0.1, 0.35, "", fontsize=10, verticalalignment="top")
        text_peaks = ax5.text(0.1, 0.20, "", fontsize=10, verticalalignment="top")
        text_bin = ax5.text(0.1, 0.05, "", fontsize=10, verticalalignment="top")

        self.axes = [ax1, ax2, ax3, ax4, ax5]
        self.lines = [line1, line2, line3, line4]
        self.text_objects = [text_status, text_hr, text_sdnn, text_rmssd, text_pnn50, text_peaks, text_bin]

    def _update_plot(self, frame: int) -> list:
        """更新图形数据（matplotlib动画回调）.

        Args:
            frame: 动画帧编号

        Returns:
            更新的artist对象列表

        """
        # 更新心率波形
        if len(self.waveform_data) > 0:
            x_data = list(range(len(self.waveform_data)))
            self.lines[0].set_data(x_data, list(self.waveform_data))
            self.axes[0].set_xlim(0, max(len(self.waveform_data), 200))

        # 更新心率趋势
        if len(self.hr_history) > 0:
            x_data = list(range(len(self.hr_history)))
            self.lines[1].set_data(x_data, list(self.hr_history))
            self.axes[1].set_xlim(-1, max(len(self.hr_history) + 1, 5))

        # 更新SDNN
        if len(self.sdnn_history) > 0:
            x_data = list(range(len(self.sdnn_history)))
            self.lines[2].set_data(x_data, list(self.sdnn_history))
            self.axes[2].set_xlim(-1, max(len(self.sdnn_history) + 1, 5))
            self.axes[2].set_ylim(0, max(max(self.sdnn_history) * 1.2, 100))

        # 更新RMSSD
        if len(self.rmssd_history) > 0:
            x_data = list(range(len(self.rmssd_history)))
            self.lines[3].set_data(x_data, list(self.rmssd_history))
            self.axes[3].set_xlim(-1, max(len(self.rmssd_history) + 1, 5))
            self.axes[3].set_ylim(0, max(max(self.rmssd_history) * 1.2, 100))

        # 更新统计信息文本
        status_color = "green" if self.status == "succeeded" else "red"
        self.text_objects[0].set_text(f"状态: {self.status}")
        self.text_objects[0].set_color(status_color)
        self.text_objects[1].set_text(f"当前心率: {self.current_hr:.1f} bpm")
        self.text_objects[2].set_text(f"SDNN: {self.current_sdnn:.2f} ms")
        self.text_objects[3].set_text(f"RMSSD: {self.current_rmssd:.2f} ms")
        self.text_objects[4].set_text(f"pNN50: {self.current_pnn50:.2f} %")
        self.text_objects[5].set_text(f"峰值数: {self.peak_count}")
        self.text_objects[6].set_text(f"能量最大Bin: {self.max_bin}")

        return self.lines + self.text_objects

    def update_data(self, hr_dict: dict) -> None:
        """更新可视化数据.

        Args:
            hr_dict: 包含心率信息的字典

        """
        # 更新心率波形（最后200个点）
        waveform = hr_dict.get("filtered_waveform", [])
        if len(waveform) > 0:
            self.waveform_data.clear()
            for value in waveform:
                self.waveform_data.append(value)

        # 更新心率和HRV指标
        self.status = hr_dict.get("status", "failed")
        self.current_hr = hr_dict.get("heart_rate", 0.0)
        self.current_sdnn = hr_dict.get("hrv_sdnn", 0.0)
        self.current_rmssd = hr_dict.get("hrv_rmssd", 0.0)
        self.current_pnn50 = hr_dict.get("hrv_pnn50", 0.0)
        self.peak_count = hr_dict.get("peak_count", 0)
        self.max_bin = hr_dict.get("max_bin", 0)

        # 添加到历史记录
        self.hr_history.append(self.current_hr)
        self.sdnn_history.append(self.current_sdnn)
        self.rmssd_history.append(self.current_rmssd)

        self.frame_count += 1

        # 控制台输出
        print(
            f"[测量 {self.frame_count}] 心率: {self.current_hr:.1f} bpm | "
            f"SDNN: {self.current_sdnn:.1f} ms | "
            f"RMSSD: {self.current_rmssd:.1f} ms | "
            f"峰值: {self.peak_count}"
        )

    def start(
        self,
        serial_port: str = "COM7",
        serial_baudrate: int = 921600,
    ) -> None:
        """启动可视化.

        Args:
            serial_port: 串口名称
            serial_baudrate: 串口波特率

        """
        # 创建数据队列
        data_queue = Queue()

        # 初始化图形
        self._init_plot()

        # 启动雷达线程
        print(f"正在连接雷达设备: {serial_port} @ {serial_baudrate} bps")
        radar_thread = MMWRadarThread(
            output_queue=data_queue,
            serial_port=serial_port,
            serial_baudrate=serial_baudrate,
        )

        # 启动心率处理线程
        heart_rate_thread = MMWHeartRateThread(
            input_queue=data_queue,
            buffer_size=1000,
            callback=self.update_data,
        )

        radar_thread.start()
        heart_rate_thread.start()

        print("心率可视化已启动，按Ctrl+C停止...")
        print("-" * 60)

        # 启动动画（必须在self.fig不为None时调用）
        if self.fig is not None:
            ani = FuncAnimation(
                self.fig,
                self._update_plot,
                interval=100,  # 100ms刷新一次
                blit=True,
                cache_frame_data=False,
            )

        try:
            plt.show()
        except KeyboardInterrupt:
            print("\n正在停止...")
        finally:
            heart_rate_thread.stop()
            print("心率可视化已停止")


if __name__ == "__main__":
    # 创建并启动可视化器
    visualizer = HeartRateVisualizer(
        waveform_window_size=1000,  # 心率波形窗口
        hr_history_size=20,  # 心率历史记录
    )

    # 启动（需要根据实际情况修改串口名称）
    visualizer.start(
        serial_port="COM7",
        serial_baudrate=921600,
    )
