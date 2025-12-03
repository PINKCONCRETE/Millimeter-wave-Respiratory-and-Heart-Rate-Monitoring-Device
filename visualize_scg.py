"""毫米波SCG数据实时可视化脚本.

使用matplotlib实时显示SCG波形，支持滑动窗口显示（默认1000个数据点）。
"""
import time
from collections import deque
from queue import Queue

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from src.mmw_processor import MMWProcessorThread
from src.mmw_rader import MMWRaderThread


class SCGVisualizer:
    """毫米波SCG数据实时可视化器.

    使用matplotlib动画实时显示SCG波形，支持滑动窗口显示。

    Attributes:
        window_size: 滑动窗口大小（数据点数）
        scg_data: SCG数据缓冲区
        time_data: 时间戳缓冲区

    """

    def __init__(self, window_size: int = 1000) -> None:
        """初始化可视化器.

        Args:
            window_size: 滑动窗口大小（默认1000个数据点）

        """
        self.window_size = window_size
        self.scg_data = deque(maxlen=window_size)
        self.time_data = deque(maxlen=window_size)

        # 创建图形
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.line, = self.ax.plot([], [], "b-", linewidth=1)

        # 设置图形属性
        self.ax.set_xlabel("时间 (秒)", fontsize=12)
        self.ax.set_ylabel("SCG值", fontsize=12)
        self.ax.set_title("实时SCG波形 (滑动窗口)", fontsize=14, fontweight="bold")
        self.ax.grid(True, alpha=0.3)

        # 状态信息文本
        self.status_text = self.ax.text(
            0.02, 0.98, "",
            transform=self.ax.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=10,
        )

        # 统计信息
        self.data_point_count = 0
        self.start_time = time.time()
        self.data_start_timestamp = 0.0
        self.data_end_timestamp = 0.0

    def update_data(self, scg_value: float, timestamp: float) -> None:
        """更新数据缓冲区.

        Args:
            scg_value: SCG值
            timestamp: 时间戳

        """
        if self.data_point_count == 0:
            self.data_start_timestamp = timestamp
        
        self.data_end_timestamp = timestamp
        self.scg_data.append(scg_value)
        self.time_data.append(timestamp)
        self.data_point_count += 1

    def update_plot(self, frame: int) -> tuple:
        """更新图形（由FuncAnimation调用）.

        Args:
            frame: 帧编号（由FuncAnimation自动传入）

        Returns:
            更新的艺术家对象元组

        """
        if len(self.scg_data) > 0:
            # 更新线条数据
            time_array = np.array(self.time_data)
            scg_array = np.array(self.scg_data)
            self.line.set_data(time_array, scg_array)

            # 动态调整坐标轴
            if len(time_array) > 1:
                # x轴显示时间（秒）
                x_min = time_array[0]
                x_max = time_array[-1]
                self.ax.set_xlim(x_min, x_max)
                
                # 设置x轴标签格式
                if x_max - x_min > 60:
                    # 如果超过1分钟，显示分钟:秒
                    self.ax.set_xlabel(
                        f"时间 (秒) [{x_min:.1f}s - {x_max:.1f}s]", fontsize=12
                    )
                else:
                    self.ax.set_xlabel("时间 (秒)", fontsize=12)

                # y轴自适应，留10%余量
                y_min, y_max = scg_array.min(), scg_array.max()
                y_range = y_max - y_min
                if y_range > 0:
                    margin = 0.1 * y_range
                    self.ax.set_ylim(y_min - margin, y_max + margin)
                else:
                    self.ax.set_ylim(-100, 100)

            # 更新状态信息
            elapsed = time.time() - self.start_time
            data_duration = self.data_end_timestamp - self.data_start_timestamp

            status_str = (
                f"数据点: {len(self.scg_data)}/{self.window_size}\n"
                f"总数据点: {self.data_point_count}\n"
                f"数据时长: {data_duration:.1f}s\n"
                f"运行时间: {elapsed:.1f}s"
            )
            self.status_text.set_text(status_str)

        return self.line, self.status_text

    def start_animation(self, interval: int = 50) -> FuncAnimation:
        """启动动画.

        Args:
            interval: 更新间隔（毫秒，默认50ms）

        Returns:
            FuncAnimation对象

        """
        return FuncAnimation(
            self.fig,
            self.update_plot,
            interval=interval,
            blit=True,
            cache_frame_data=False,
        )


def main() -> None:
    """主函数：初始化并启动SCG实时可视化系统."""
    print("=" * 60)
    print("SCG数据实时可视化")
    print("=" * 60)

    # 配置参数
    serial_port = "COM7"
    baudrate = 921600
    bin_num = 8
    dlc = 10
    buffer_size = 1000  # 处理缓冲区大小（必须为1000）
    window_size = 1000  # 可视化窗口大小

    print("\n配置信息:")
    print(f"  串口: {serial_port}")
    print(f"  波特率: {baudrate}")
    print(f"  可视化窗口: {window_size} 个数据点")

    # 创建共享队列
    data_queue = Queue()
    output_queue = Queue()

    # 创建可视化器
    visualizer = SCGVisualizer(window_size=window_size)

    # 数据回调函数（从输出队列读取）
    def update_from_queue() -> None:
        """从输出队列批量读取数据并更新可视化."""
        count = 0
        while not output_queue.empty() and count < 50:  # 每次最多处理50个点
            try:
                result = output_queue.get_nowait()
                scg_value = result["scg_value"]
                timestamp = result["timestamp"]
                visualizer.update_data(scg_value, timestamp)
                count += 1
            except Exception:
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
        bin_num=bin_num,
        dlc=dlc,
    )

    # 创建处理线程
    print("初始化处理线程...")
    processor_thread = MMWProcessorThread(
        input_queue=data_queue,
        output_queue=output_queue,
        bin_num=bin_num,
        dlc=dlc,
        buffer_size=buffer_size,
    )

    # 启动线程
    print("\n启动数据采集和处理流水线...")
    radar_thread.start()
    processor_thread.start()

    print("启动可视化界面...")
    print("关闭窗口以停止程序\n")

    # 启动动画
    _ = visualizer.start_animation(interval=50)

    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        print("\n正在关闭...")
        processor_thread.stop()

        # 等待线程结束
        processor_thread.join(timeout=2)
        radar_thread.join(timeout=2)

        # 显示统计信息
        stats = processor_thread.get_statistics()
        print("\n最终统计:")
        print(f"  接收完整帧数: {stats['completed_frames']}")
        print(f"  生成SCG点数: {stats['generated_scg_points']}")
        print(f"  可视化数据点: {len(visualizer.scg_data)}")
        print("=" * 60)


if __name__ == "__main__":
    # 设置matplotlib中文支持
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False

    main()
