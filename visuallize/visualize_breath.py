"""毫米波呼吸数据实时可视化脚本.

使用matplotlib实时显示呼吸波形和呼吸周期（位移-流速循环）。
"""
import sys
import time
from collections import deque
from pathlib import Path
from queue import Queue

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_breath import MMWBreathThread  # noqa: E402
from src.mmw_rader import MMWRaderThread  # noqa: E402

# 处理中文和负号显示问题
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 中文字体
plt.rcParams["axes.unicode_minus"] = False  # 负号显示

class BreathVisualizer:
    """毫米波呼吸数据实时可视化器.

    使用matplotlib动画实时显示呼吸波形和呼吸周期图。

    Attributes:
        window_size: 呼吸波形滑动窗口大小（数据点数）
        rr_wave_data: 呼吸波形数据缓冲区

    """

    def __init__(self, window_size: int = 1000) -> None:
        """初始化可视化器.

        Args:
            window_size: 滑动窗口大小（默认1000个数据点）

        """
        self.window_size = window_size
        self.rr_wave_data = deque(maxlen=window_size)
        self.time_data = deque(maxlen=window_size)

        # 呼吸周期数据（位移-流速）
        self.displacement = None
        self.flow_rate = None

        # 创建图形：左边呼吸波形，右边呼吸周期
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # 左图：呼吸波形
        (self.line1,) = self.ax1.plot([], [], "g-", linewidth=2)
        self.ax1.set_xlabel("时间 (秒)", fontsize=12)
        self.ax1.set_ylabel("相位值", fontsize=12)
        self.ax1.set_title("实时呼吸波形 (Phase)", fontsize=14, fontweight="bold")
        self.ax1.grid(True, alpha=0.3)

        # 右图：呼吸周期（位移-流速）
        (self.line2,) = self.ax2.plot([], [], "g-", linewidth=3)
        self.ax2.set_xlabel("位移 (Displacement)", fontsize=12)
        self.ax2.set_ylabel("流速 (Flow Rate)", fontsize=12)
        self.ax2.set_title("呼吸周期图", fontsize=14, fontweight="bold")
        self.ax2.grid(True, alpha=0.3)
        self.ax2.set_xlim(-0.1, 1.1)
        self.ax2.set_ylim(-1.2, 1.2)

        # 状态信息
        self.status_text1 = self.ax1.text(
            0.02, 0.98, "", transform=self.ax1.transAxes, verticalalignment="top"
        )
        self.status_text2 = self.ax2.text(
            0.02, 0.98, "", transform=self.ax2.transAxes, verticalalignment="top"
        )

        # 统计信息
        self.frame_count = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.update_count = 0

    def update_rr_wave(self, rr_wave: np.ndarray) -> None:
        """更新呼吸波形数据.

        Args:
            rr_wave: 完整的呼吸波形数组（1000个点）

        """
        self.rr_wave_data = deque(rr_wave, maxlen=self.window_size)
        # 生成时间轴（假设200Hz采样率）
        self.time_data = deque(
            np.arange(len(rr_wave)) / 200.0, maxlen=self.window_size
        )
        self.frame_count += 1
        self.update_count += 1

    def update_breath_cycle(
        self, displacement: np.ndarray | None, flow_rate: np.ndarray | None
    ) -> None:
        """更新呼吸周期数据.

        Args:
            displacement: 位移数组
            flow_rate: 流速数组

        """
        self.displacement = displacement
        self.flow_rate = flow_rate

    def update_plot(self, frame: int) -> tuple:
        """更新图形（matplotlib动画回调）.

        Args:
            frame: 帧编号（未使用）

        Returns:
            更新的图形对象元组

        """
        # 更新左图：呼吸波形
        if len(self.rr_wave_data) > 0:
            time_array = np.array(self.time_data)
            rr_array = np.array(self.rr_wave_data)
            self.line1.set_data(time_array, rr_array)

            # 自动调整坐标轴
            if len(time_array) > 0:
                self.ax1.set_xlim(time_array[0], time_array[-1])
                y_min, y_max = rr_array.min(), rr_array.max()
                margin = (y_max - y_min) * 0.1
                self.ax1.set_ylim(y_min - margin, y_max + margin)

        # 更新右图：呼吸周期
        if self.displacement is not None and self.flow_rate is not None:
            self.line2.set_data(self.displacement, self.flow_rate)

        # 更新状态信息
        current_time = time.time()
        elapsed = current_time - self.start_time
        fps = self.update_count / (current_time - self.last_update_time + 0.001)

        if current_time - self.last_update_time >= 1.0:
            self.status_text1.set_text(
                f"帧数: {self.frame_count}\n"
                f"时间: {elapsed:.1f}s\n"
                f"更新率: {fps:.1f} Hz"
            )
            self.status_text2.set_text(
                f"周期点数: {len(self.displacement) if self.displacement is not None else 0}\n"
                f"最新周期: {self.frame_count}"
            )
            self.update_count = 0
            self.last_update_time = current_time

        return self.line1, self.line2, self.status_text1, self.status_text2

    def start(self) -> None:
        """启动动画显示."""
        ani = FuncAnimation(
            self.fig, self.update_plot, interval=50, blit=True, cache_frame_data=False
        )
        plt.tight_layout()
        plt.show()


def main() -> None:
    """主函数：启动呼吸数据采集和可视化."""
    print("=" * 60)
    print("毫米波呼吸信号实时可视化")
    print("=" * 60)

    # 配置参数
    serial_port = "COM7"
    baudrate = 921600
    channel_num = 8  # 8个通道
    bins_per_channel = 10  # 每个通道的频率bin数量
    buffer_size = 1000  # 滑动窗口大小（1000帧 = 5秒）
    window_size = 1000  # 显示窗口大小（1000个数据点）

    print("\n配置信息:")
    print(f"  串口: {serial_port}")
    print(f"  波特率: {baudrate}")
    print(f"  通道数: {channel_num}")
    print(f"  每通道bin数: {bins_per_channel}")
    print(f"  缓冲区大小: {buffer_size} 帧")
    print(f"  显示窗口: {window_size} 点")

    # 创建队列
    data_queue = Queue()
    output_queue = Queue()

    # 创建可视化器
    print("\n初始化可视化器...")
    visualizer = BreathVisualizer(window_size=window_size)

    # 数据回调函数（从输出队列读取）
    def update_from_queue() -> None:
        """从输出队列批量读取数据并更新可视化."""
        count = 0
        while not output_queue.empty() and count < 10:  # 每次最多处理10个
            try:
                result = output_queue.get_nowait()
                rr_wave = result["rr_wave"]
                displacement = result["displacement"]
                flow_rate = result["flow_rate"]

                # 更新可视化
                visualizer.update_rr_wave(rr_wave)
                visualizer.update_breath_cycle(displacement, flow_rate)

                count += 1
            except Exception as e:
                print(f"更新可视化时出错: {e}")
                break

    # 修改update_plot以从队列读取
    original_update = visualizer.update_plot

    def wrapped_update(frame: int) -> tuple:
        update_from_queue()
        return original_update(frame)

    visualizer.update_plot = wrapped_update

    # 创建雷达线程
    print("\n初始化雷达线程...")
    radar_thread = MMWRaderThread(
        output_queue=data_queue,
        serial_port=serial_port,
        serial_baudrate=baudrate,
        channel_num=channel_num,
        bins_per_channel=bins_per_channel,
    )

    # 创建呼吸处理线程
    print("初始化呼吸处理线程...")
    breath_thread = MMWBreathThread(
        input_queue=data_queue,
        output_queue=output_queue,
        channel_num=channel_num,
        bins_per_channel=bins_per_channel,
        buffer_size=buffer_size,
    )

    # 启动线程
    print("\n启动数据采集和处理流水线...")
    radar_thread.start()
    breath_thread.start()

    print("启动可视化界面...")
    print("关闭窗口以停止程序\n")

    try:
        # 启动可视化（这会阻塞直到窗口关闭）
        visualizer.start()
    except KeyboardInterrupt:
        print("\n\n收到停止信号")
    finally:
        # 停止线程
        print("正在停止线程...")
        breath_thread.stop()

        # 等待线程结束
        radar_thread.join(timeout=2.0)
        breath_thread.join(timeout=2.0)

        # 打印最终统计
        print("\n最终统计:")
        breath_stats = breath_thread.get_statistics()
        print(f"  接收帧数: {breath_stats['completed_frames']}")
        print(f"  生成呼吸周期: {breath_stats['generated_breath_cycles']}")
        print(f"  平均帧率: {breath_stats['frame_rate']:.2f} fps")

        print("\n程序结束")


if __name__ == "__main__":
    main()
