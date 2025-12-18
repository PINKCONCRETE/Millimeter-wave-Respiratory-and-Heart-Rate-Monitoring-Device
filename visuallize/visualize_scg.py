"""毫米波SCG数据实时可视化脚本.

使用matplotlib实时显示SCG波形，支持滑动窗口显示（默认1000个数据点）。
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

from src.mmw_processor import MMWProcessorThread  # noqa: E402
from src.mmw_rader import MMWRadarThread  # noqa: E402


class MultiBinSCGVisualizer:
    """多Bin毫米波SCG数据实时可视化器.

    使用两个Figure（每个包含5个子图）显示所有10个Bin的SCG波形。

    Attributes:
        window_size: 滑动窗口大小（数据点数）
        scg_data: SCG数据缓冲区列表 (10个deque)
        time_data: 时间戳缓冲区
    """

    def __init__(self, window_size: int = 1000, bins_num: int = 10) -> None:
        """初始化可视化器.

        Args:
            window_size: 滑动窗口大小（默认1000个数据点）
            bins_num: Bin的数量
        """
        self.window_size = window_size
        self.bins_num = bins_num
        self.scg_data = [deque(maxlen=window_size) for _ in range(bins_num)]
        self.time_data = deque(maxlen=window_size)

        # 创建2个图形，每个5个子图
        self.figs = []
        self.axes_list = []
        
        # Figure 1: Bins 0-4
        fig1, axes1 = plt.subplots(5, 1, figsize=(10, 10), sharex=True)
        fig1.canvas.manager.set_window_title("SCG Bins 0-4")
        self.figs.append(fig1)
        if isinstance(axes1, np.ndarray):
            self.axes_list.extend(axes1.flatten())
        else:
            self.axes_list.append(axes1)

        # Figure 2: Bins 5-9
        fig2, axes2 = plt.subplots(5, 1, figsize=(10, 10), sharex=True)
        fig2.canvas.manager.set_window_title("SCG Bins 5-9")
        self.figs.append(fig2)
        if isinstance(axes2, np.ndarray):
            self.axes_list.extend(axes2.flatten())
        else:
            self.axes_list.append(axes2)

        # 初始化所有子图的线条
        self.lines = []
        colors = plt.cm.jet(np.linspace(0, 1, bins_num))
        
        for i in range(bins_num):
            if i >= len(self.axes_list):
                break
                
            ax = self.axes_list[i]
            line, = ax.plot([], [], color=colors[i], linewidth=1)
            self.lines.append(line)
            
            ax.grid(True, alpha=0.3)
            ax.set_ylabel(f"Bin {i}", fontsize=10)
            
            # 设置标题
            if i == 0:
                ax.set_title("SCG Waveforms (Bins 0-4)", fontsize=12, fontweight="bold")
            elif i == 5:
                ax.set_title("SCG Waveforms (Bins 5-9)", fontsize=12, fontweight="bold")

        # 设置共同的X轴标签
        self.axes_list[4].set_xlabel("时间 (秒)", fontsize=10)
        self.axes_list[9].set_xlabel("时间 (秒)", fontsize=10)

        # 状态信息文本 (图1)
        self.status_text = self.axes_list[0].text(
            0.02, 0.95, "",
            transform=self.axes_list[0].transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=9,
        )

        # 状态信息文本 (图2)
        self.status_text2 = self.axes_list[5].text(
            0.02, 0.95, "",
            transform=self.axes_list[5].transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=9,
        )

        # 统计信息
        self.data_point_count = 0
        self.start_time = time.time()
        self.data_start_timestamp = 0.0
        self.data_end_timestamp = 0.0
        self.offset = 0
        self.max_bin = 0
        self.default_colors = colors

    def update_data(self, scg_values: list[float], timestamp: float, offset: int = 0, max_bin: int = 0) -> None:
        """更新数据缓冲区."""
        if self.data_point_count == 0:
            self.data_start_timestamp = timestamp
        
        self.data_end_timestamp = timestamp
        self.offset = offset
        self.max_bin = max_bin
        
        for i, val in enumerate(scg_values):
            if i < len(self.scg_data):
                self.scg_data[i].append(val)
                
        self.time_data.append(timestamp)
        self.data_point_count += 1

    def _update_fig(self, frame: int, start_idx: int, end_idx: int, status_text=None) -> tuple:
        """通用更新函数."""
        if len(self.time_data) == 0:
            artists = [self.lines[i] for i in range(start_idx, end_idx)]
            if status_text:
                artists.append(status_text)
            return tuple(artists)

        time_array = np.array(self.time_data)
        x_min = time_array[0]
        x_max = time_array[-1]
        
        artists = []
        
        # 更新该范围内的所有子图
        for i in range(start_idx, end_idx):
            if i >= len(self.lines):
                break
                
            line = self.lines[i]
            ax = self.axes_list[i]
            
            # 高亮最大能量Bin
            if i == self.max_bin:
                line.set_color('red')
                line.set_linewidth(2)
            else:
                line.set_color(self.default_colors[i])
                line.set_linewidth(1)
            
            if len(self.scg_data[i]) > 0:
                scg_array = np.array(self.scg_data[i])
                line.set_data(time_array, scg_array)
                
                # Y轴自适应
                y_min, y_max = scg_array.min(), scg_array.max()
                y_range = y_max - y_min
                if y_range > 0:
                    margin = 0.1 * y_range
                    ax.set_ylim(y_min - margin, y_max + margin)
                else:
                    ax.set_ylim(-100, 100)
            
            # X轴随时间滚动
            ax.set_xlim(x_min, x_max)
            artists.append(line)

        # 更新状态文本
        if status_text:
            elapsed = time.time() - self.start_time
            data_duration = self.data_end_timestamp - self.data_start_timestamp
            
            status_str = (
                f"Points: {len(self.time_data)}\n"
                f"Duration: {data_duration:.1f}s\n"
                f"Offset: {self.offset}\n"
                f"Max Bin: {self.max_bin}"
            )
            status_text.set_text(status_str)
            artists.append(status_text)
            
        return tuple(artists)

    def update_plot_fig1(self, frame: int) -> tuple:
        """更新图1 (Bins 0-4)."""
        return self._update_fig(frame, 0, 5, self.status_text)

    def update_plot_fig2(self, frame: int) -> tuple:
        """更新图2 (Bins 5-9)."""
        return self._update_fig(frame, 5, 10, self.status_text2)

    def start_animations(self, interval: int = 50) -> list[FuncAnimation]:
        """启动两个动画."""
        anim1 = FuncAnimation(
            self.figs[0],
            self.update_plot_fig1,
            interval=interval,
            blit=True,
            cache_frame_data=False,
        )
        anim2 = FuncAnimation(
            self.figs[1],
            self.update_plot_fig2,
            interval=interval,
            blit=True,
            cache_frame_data=False,
        )
        return [anim1, anim2]


class MultiBinProcessorThread(MMWProcessorThread):
    """多Bin处理线程，输出所有10个Bin的SCG数据."""
    
    def _generate_new_scg_point(self) -> None:
        """重写生成函数，输出所有Bin的数据."""
        if self._generated_scg_points == 0:
            print(f"缓冲区已满（{len(self._frame_buffer)}帧），开始多Bin输出模式...")

        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        # 转换为numpy数组
        fft_data = np.array(self._frame_buffer)
        
        # 计算能量最大的Bin
        max_bin_idx = self._find_max_energy_bin(fft_data)
        
        scg_values = []
        
        # 遍历所有Bin
        for bin_idx in range(self._bins_per_channel):
            # 提取相位
            phase_data = self._extract_phase(fft_data, bin_idx)
            # 计算导数
            scg_waveform = self._compute_derivative_waveform(phase_data)
            # 过滤异常值
            outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
            scg_waveform[outlier_idx] = 0.0
            
            # 取最新的值（倒数第4个，因为7点差分）
            latest_value = scg_waveform[-4]
            scg_values.append(float(latest_value))
            
        # 输出结果
        result = {
            "frame_idx": self._generated_scg_points,
            "scg_values": scg_values,
            "timestamp": self._generated_scg_points * self.TIME_STEP,
            "offset": self._current_offset,
            "max_bin": max_bin_idx
        }
        self._output_queue.put(result)
        
        self._generated_scg_points += 1


def main() -> None:
    """主函数：初始化并启动SCG实时可视化系统."""
    print("=" * 60)
    print("SCG数据实时可视化")
    print("=" * 60)

    # 配置参数
    serial_port = "/dev/ttyACM1"
    baudrate = 921600
    channel_num = 8
    bins_per_channel = 10
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
    visualizer = MultiBinSCGVisualizer(window_size=window_size, bins_num=bins_per_channel)

    # 数据回调函数（从输出队列读取）
    def update_from_queue() -> None:
        """从输出队列批量读取数据并更新可视化."""
        count = 0
        while not output_queue.empty() and count < 50:  # 每次最多处理50个点
            try:
                result = output_queue.get_nowait()
                scg_values = result["scg_values"]
                timestamp = result["timestamp"]
                offset = result.get("offset", 0)
                max_bin = result.get("max_bin", 0)
                visualizer.update_data(scg_values, timestamp, offset, max_bin)
                count += 1
            except Exception:
                break

    # 修改 update_plot_fig1 以从队列读取数据
    original_update_fig1 = visualizer.update_plot_fig1
    def wrapped_update_fig1(frame: int) -> tuple:
        update_from_queue()
        return original_update_fig1(frame)
    
    visualizer.update_plot_fig1 = wrapped_update_fig1

    # 创建雷达线程
    print("\n初始化雷达线程...")
    radar_thread = MMWRadarThread(
        output_queue=data_queue,
        serial_port=serial_port,
        serial_baudrate=baudrate,
        channel_num=channel_num,
        bins_per_channel=bins_per_channel,
    )

    # 创建处理线程
    print("初始化处理线程...")
    processor_thread = MultiBinProcessorThread(
        input_queue=data_queue,
        output_queue=output_queue,
        channel_num=channel_num,
        bins_per_channel=bins_per_channel,
        buffer_size=buffer_size,
    )

    # 启动线程
    print("\n启动数据采集和处理流水线...")
    radar_thread.start()
    processor_thread.start()

    print("启动可视化界面...")
    print("关闭窗口以停止程序\n")

    # 启动动画
    animations = visualizer.start_animations(interval=50)

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
        print(f"  可视化数据点: {len(visualizer.time_data)}")
        print("=" * 60)


if __name__ == "__main__":
    # 设置matplotlib中文支持
    # plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    # plt.rcParams["axes.unicode_minus"] = False

    main()
