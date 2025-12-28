"""毫米波人体检测实时可视化脚本.

使用matplotlib实时显示人体检测状态、能量波动和检测率趋势。
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
from matplotlib.patches import Circle

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_human_check import MMWHumanCheckThread  # noqa: E402
from src.mmw_rader import MMWRadarThread  # noqa: E402

# 处理中文和负号显示问题
# plt.rcParams["font.sans-serif"] = ["SimHei"]  # 中文字体
# plt.rcParams["axes.unicode_minus"] = False  # 负号显示


class HumanCheckVisualizer:
    """毫米波人体检测实时可视化器.

    使用matplotlib动画实时显示人体检测状态和统计信息。

    Attributes:
        history_size: 历史记录长度

    """

    def __init__(self, history_size: int = 200) -> None:
        """初始化可视化器.

        Args:
            history_size: 历史记录长度（默认200帧）

        """
        self.history_size = history_size

        # 检测历史数据
        self.detection_history = deque(maxlen=history_size)
        self.time_history = deque(maxlen=history_size)

        # 检测率历史
        self.detection_rate_history = deque(maxlen=history_size)

        # offset历史（窗口偏移）
        self.offset_history = deque(maxlen=history_size)

        # 当前状态
        self.current_has_human = False
        self.current_detection_rate = 0.0
        self.current_offset = 0
        self.frame_count = 0

        # 统计计数
        self.total_detected = 0
        self.total_frames = 0

        # 初始化图形
        self.fig = None
        self.axes = []
        self.lines = []
        self.patches = []
        self.text_objects = []

        # 时间基准
        self.start_time = time.time()

    def _init_plot(self) -> None:
        """初始化matplotlib图形和子图."""
        self.fig = plt.figure(figsize=(14, 10))
        self.fig.suptitle("毫米波人体检测实时监测", fontsize=16, fontweight="bold")

        # 使用GridSpec创建复杂布局
        gs = GridSpec(3, 2, figure=self.fig, hspace=0.3, wspace=0.3)

        # 子图1: 检测状态指示器 (占据左上)
        ax1 = self.fig.add_subplot(gs[0, 0])
        ax1.set_title("人体检测状态", fontsize=12)
        ax1.set_xlim(-1.5, 1.5)
        ax1.set_ylim(-1.5, 1.5)
        ax1.set_aspect("equal")
        ax1.axis("off")

        # 创建状态指示圆圈
        circle = Circle((0, 0), 1.0, color="gray", alpha=0.3)
        ax1.add_patch(circle)
        text_status = ax1.text(
            0,
            0,
            "未检测",
            fontsize=20,
            ha="center",
            va="center",
            fontweight="bold",
        )

        # 子图2: 检测率趋势 (占据右上)
        ax2 = self.fig.add_subplot(gs[0, 1])
        ax2.set_title("检测率趋势", fontsize=12)
        ax2.set_xlabel("时间 (s)")
        ax2.set_ylabel("检测率 (%)")
        ax2.set_ylim(0, 100)
        ax2.grid(True, alpha=0.3)
        (line2,) = ax2.plot([], [], "b-", linewidth=2, label="检测率")
        ax2.axhline(y=50, color="orange", linestyle="--", alpha=0.5, label="50%阈值")
        ax2.legend(loc="upper right", fontsize=8)

        # 子图3: 检测历史时间线 (占据中间两列)
        ax3 = self.fig.add_subplot(gs[1, :])
        ax3.set_title("检测历史时间线", fontsize=12)
        ax3.set_xlabel("时间 (s)")
        ax3.set_ylabel("检测到人体")
        ax3.set_ylim(-0.5, 1.5)
        ax3.grid(True, alpha=0.3, axis="x")
        (line3,) = ax3.plot([], [], "go-", markersize=4, linewidth=1.5, label="检测结果")
        ax3.legend(loc="upper right", fontsize=8)
        ax3.set_yticks([0, 1])
        ax3.set_yticklabels(["无", "有"])

        # 子图4: Offset变化 (占据左下)
        ax4 = self.fig.add_subplot(gs[2, 0])
        ax4.set_title("检测窗口Offset", fontsize=12)
        ax4.set_xlabel("时间 (s)")
        ax4.set_ylabel("Offset")
        ax4.grid(True, alpha=0.3)
        (line4,) = ax4.plot([], [], "m-", linewidth=2, label="Offset")
        ax4.legend(loc="upper right", fontsize=8)

        # 子图5: 统计信息文本显示 (占据右下)
        ax5 = self.fig.add_subplot(gs[2, 1])
        ax5.axis("off")
        ax5.set_title("统计信息", fontsize=12)

        # 创建文本对象
        text_current = ax5.text(0.1, 0.85, "", fontsize=11, verticalalignment="top")
        text_rate = ax5.text(0.1, 0.70, "", fontsize=11, verticalalignment="top")
        text_total = ax5.text(0.1, 0.55, "", fontsize=11, verticalalignment="top")
        text_frames = ax5.text(0.1, 0.40, "", fontsize=11, verticalalignment="top")
        text_offset = ax5.text(0.1, 0.25, "", fontsize=11, verticalalignment="top")
        text_uptime = ax5.text(0.1, 0.10, "", fontsize=11, verticalalignment="top")

        self.axes = [ax1, ax2, ax3, ax4, ax5]
        self.lines = [line2, line3, line4]
        self.patches = [circle]
        self.text_objects = [text_status, text_current, text_rate, text_total, text_frames, text_offset, text_uptime]

    def _update_plot(self, frame: int) -> list:
        """更新图形数据（matplotlib动画回调）.

        Args:
            frame: 动画帧编号

        Returns:
            更新的artist对象列表

        """
        current_time = time.time() - self.start_time

        # 更新状态指示器
        if self.current_has_human:
            self.patches[0].set_color("green")
            self.patches[0].set_alpha(0.7)
            self.text_objects[0].set_text("检测到人体")
            self.text_objects[0].set_color("green")
        else:
            self.patches[0].set_color("red")
            self.patches[0].set_alpha(0.3)
            self.text_objects[0].set_text("无人")
            self.text_objects[0].set_color("red")

        # 更新检测率趋势
        if len(self.detection_rate_history) > 0:
            self.lines[0].set_data(
                list(self.time_history),
                [rate * 100 for rate in self.detection_rate_history],
            )
            self.axes[1].set_xlim(
                max(0, list(self.time_history)[-1] - 30),
                max(30, list(self.time_history)[-1]),
            )

        # 更新检测历史时间线
        if len(self.detection_history) > 0:
            self.lines[1].set_data(
                list(self.time_history),
                [1 if d else 0 for d in self.detection_history],
            )
            self.axes[2].set_xlim(
                max(0, list(self.time_history)[-1] - 30),
                max(30, list(self.time_history)[-1]),
            )

        # 更新Offset变化
        if len(self.offset_history) > 0:
            self.lines[2].set_data(list(self.time_history), list(self.offset_history))
            self.axes[3].set_xlim(
                max(0, list(self.time_history)[-1] - 30),
                max(30, list(self.time_history)[-1]),
            )
            if len(self.offset_history) > 0:
                self.axes[3].set_ylim(
                    min(self.offset_history) - 1,
                    max(self.offset_history) + 1,
                )

        # 更新统计信息文本
        status_text = "有人" if self.current_has_human else "无人"
        self.text_objects[1].set_text(f"当前状态: {status_text}")
        self.text_objects[2].set_text(f"实时检测率: {self.current_detection_rate * 100:.1f}%")

        if self.total_frames > 0:
            overall_rate = (self.total_detected / self.total_frames) * 100
            self.text_objects[3].set_text(f"总体检测率: {overall_rate:.1f}%")
        else:
            self.text_objects[3].set_text("总体检测率: 0.0%")

        self.text_objects[4].set_text(f"接收帧数: {self.total_frames}")
        self.text_objects[5].set_text(f"当前Offset: {self.current_offset}")
        self.text_objects[6].set_text(f"运行时间: {current_time:.1f}s")

        return self.lines + self.patches + self.text_objects

    def update_data(self, result: dict) -> None:
        """更新可视化数据.

        Args:
            result: 包含检测结果的字典

        """
        current_time = time.time() - self.start_time

        # 提取数据
        has_human = result.get("has_human", False)
        detection_rate = result.get("detection_rate", 0.0)
        offset = result.get("offset", 0)
        frame_count = result.get("frame_count", 0)

        # 更新当前状态
        self.current_has_human = has_human
        self.current_detection_rate = detection_rate
        self.current_offset = offset
        self.frame_count = frame_count

        # 更新历史记录
        self.detection_history.append(has_human)
        self.time_history.append(current_time)
        self.detection_rate_history.append(detection_rate)
        self.offset_history.append(offset)

        # 更新统计
        self.total_frames += 1
        if has_human:
            self.total_detected += 1

        # 控制台输出
        if self.total_frames % 10 == 0:
            status = "✓ 有人" if has_human else "✗ 无人"
            print(
                f"[{current_time:.1f}s] {status} | "
                f"检测率: {detection_rate * 100:.1f}% | "
                f"Offset: {offset} | "
                f"帧数: {frame_count}"
            )

    def start(
        self,
        serial_port: str = "/dev/ttyACM1",
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

        # 启动人体检测线程
        human_check_thread = MMWHumanCheckThread(
            input_queue=data_queue,
            callback=self.update_data,
        )

        radar_thread.start()
        human_check_thread.start()

        print("人体检测可视化已启动，按Ctrl+C停止...")
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
            human_check_thread.stop()
            print("人体检测可视化已停止")


if __name__ == "__main__":
    # 创建并启动可视化器
    visualizer = HumanCheckVisualizer(history_size=200)

    # 启动（需要根据实际情况修改串口名称）
    visualizer.start(
        serial_port="COM7",
        serial_baudrate=921600,
    )
