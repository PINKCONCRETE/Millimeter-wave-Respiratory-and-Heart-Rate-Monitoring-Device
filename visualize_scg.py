"""
SCG数据实时可视化脚本

使用matplotlib实时显示SCG波形，滑动窗口大小为1000个数据点
"""
import time
from queue import Queue
from collections import deque
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mmw_rader import MMWRaderThread
from mmw_processor import MMWProcessorThread


class SCGVisualizer:
    """SCG数据实时可视化类"""
    
    def __init__(self, window_size: int = 1000):
        """
        初始化可视化器
        
        Args:
            window_size: 滑动窗口大小（数据点数）
        """
        self.window_size = window_size
        self.scg_data = deque(maxlen=window_size)
        self.time_data = deque(maxlen=window_size)
        
        # 创建图形
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.line, = self.ax.plot([], [], 'b-', linewidth=1)
        
        # 设置图形属性
        self.ax.set_xlabel('时间 (秒)', fontsize=12)
        self.ax.set_ylabel('SCG值', fontsize=12)
        self.ax.set_title('实时SCG波形 (滑动窗口)', fontsize=14, fontweight='bold')
        self.ax.grid(True, alpha=0.3)
        
        # 状态信息文本
        self.status_text = self.ax.text(
            0.02, 0.98, '', 
            transform=self.ax.transAxes,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10
        )
        
        # 统计信息
        self.frame_count = 0
        self.start_time = time.time()
        
    def update_data(self, scg_value: float, timestamp: float) -> None:
        """
        更新数据缓冲区
        
        Args:
            scg_value: SCG值
            timestamp: 时间戳
        """
        self.scg_data.append(scg_value)
        self.time_data.append(timestamp)
        self.frame_count += 1
    
    def update_plot(self, frame) -> tuple:
        """
        更新图形（由FuncAnimation调用）
        
        Args:
            frame: 帧编号（由FuncAnimation自动传入）
            
        Returns:
            更新的艺术家对象
        """
        if len(self.scg_data) > 0:
            # 更新线条数据
            time_array = np.array(self.time_data)
            scg_array = np.array(self.scg_data)
            self.line.set_data(time_array, scg_array)
            
            # 动态调整坐标轴
            if len(time_array) > 1:
                self.ax.set_xlim(time_array[0], time_array[-1])
                
                # y轴自适应，留10%余量
                y_min, y_max = scg_array.min(), scg_array.max()
                y_range = y_max - y_min
                if y_range > 0:
                    self.ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
                else:
                    self.ax.set_ylim(-100, 100)
            
            # 更新状态信息
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            
            status_str = (
                f'数据点: {len(self.scg_data)}/{self.window_size}\n'
                f'总帧数: {self.frame_count}\n'
                f'采样率: {fps:.1f} Hz\n'
                f'运行时间: {elapsed:.1f}s'
            )
            self.status_text.set_text(status_str)
        
        return self.line, self.status_text
    
    def start_animation(self, interval: int = 50) -> FuncAnimation:
        """
        启动动画
        
        Args:
            interval: 更新间隔（毫秒）
            
        Returns:
            FuncAnimation对象
        """
        anim = FuncAnimation(
            self.fig, 
            self.update_plot,
            interval=interval,
            blit=True,
            cache_frame_data=False
        )
        return anim


def main():
    """主函数"""
    print("=" * 60)
    print("SCG数据实时可视化")
    print("=" * 60)
    
    # 配置参数
    SERIAL_PORT = "COM7"
    BAUDRATE = 921600
    BIN_NUM = 8
    DLC = 10
    BUFFER_SIZE = 50
    WINDOW_SIZE = 1000  # 可视化窗口大小
    
    print(f"\n配置信息:")
    print(f"  串口: {SERIAL_PORT}")
    print(f"  波特率: {BAUDRATE}")
    print(f"  可视化窗口: {WINDOW_SIZE} 个数据点")
    
    # 创建共享队列
    data_queue = Queue()
    
    # 创建可视化器
    visualizer = SCGVisualizer(window_size=WINDOW_SIZE)
    
    # 数据回调函数
    def data_callback(scg_value, frame_idx):
        """接收处理后的SCG数据"""
        timestamp = frame_idx * 0.005  # 5ms采样间隔
        visualizer.update_data(scg_value[0], timestamp)
    
    # 创建雷达线程
    print("\n初始化雷达线程...")
    radar_thread = MMWRaderThread(
        output_queue=data_queue,
        serial_port=SERIAL_PORT,
        serial_baudrate=BAUDRATE,
        bin_num=BIN_NUM,
        dlc=DLC
    )
    
    # 创建处理线程
    print("初始化处理线程...")
    processor_thread = MMWProcessorThread(
        input_queue=data_queue,
        bin_num=BIN_NUM,
        dlc=DLC,
        buffer_size=BUFFER_SIZE,
        callback=data_callback
    )
    
    # 启动线程
    print("\n启动数据采集和处理流水线...")
    radar_thread.start()
    processor_thread.start()
    
    print("启动可视化界面...")
    print("关闭窗口以停止程序\n")
    
    # 启动动画
    anim = visualizer.start_animation(interval=50)
    
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
        print(f"\n最终统计:")
        print(f"  总处理帧数: {stats['processed_frames']}")
        print(f"  可视化数据点: {len(visualizer.scg_data)}")
        print("=" * 60)


if __name__ == "__main__":
    # 设置matplotlib中文支持
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    main()
