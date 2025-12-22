"""SCG最佳Bin评分与自相关可视化脚本.

显示当前评分最高的Bin的SCG波形、FFT频谱及其周期互相关矩阵。
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

from src.mmw_rader import MMWRadarThread
from src.mmw_scg_grade import SCGGradeProcessor


class SCGBestBinVisualizer:
    """SCG最佳Bin可视化器."""

    def __init__(self, window_size: int = 1000) -> None:
        self.window_size = window_size
        
        # 数据缓冲区
        self.scg_data = deque(maxlen=window_size)
        self.time_data = deque(maxlen=window_size)
        self.corr_data = np.zeros(window_size) # 自相关数据
        
        # 状态
        self.max_bin = 0
        self.offset = 0
        self.score = 0.0
        self.start_time = time.time()
        
        # 创建图形
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 8))
        self.fig.canvas.manager.set_window_title("SCG Best Bin Grade Visualization")
        
        # 子图3: 互相关矩阵 (新窗口)
        self.fig2, self.ax3 = plt.subplots(figsize=(6, 5))
        self.fig2.canvas.manager.set_window_title("Best Bin Cycle Correlation Matrix")
        self.im = self.ax3.imshow([[0]], cmap='coolwarm', vmin=-1, vmax=1, aspect='auto')
        self.ax3.set_title("Cycle-to-Cycle Correlation")
        self.ax3.set_xlabel("Cycle Index")
        self.ax3.set_ylabel("Cycle Index")
        self.cbar = self.fig2.colorbar(self.im, ax=self.ax3)

        # 子图1: SCG波形 (滚动)
        self.line_scg, = self.ax1.plot([], [], 'b-', linewidth=1, label='SCG')
        self.ax1.set_title("SCG Waveform (Best Score Bin)", fontsize=12)
        self.ax1.set_ylabel("Amplitude")
        self.ax1.grid(True, alpha=0.3)
        self.ax1.legend(loc='upper right')
        
        # 状态文本
        self.status_text = self.ax1.text(
            0.02, 0.95, "",
            transform=self.ax1.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=10,
        )
        
        # 分数大字显示 (右上角)
        self.score_text = self.ax1.text(
            0.95, 0.95, "",
            transform=self.ax1.transAxes,
            verticalalignment="top",
            horizontalalignment="right",
            fontsize=24,
            fontweight='bold',
            color='red',
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "red"}
        )
        
        # 子图2: FFT频谱 (实时刷新)
        self.line_fft, = self.ax2.plot([], [], 'r-', linewidth=1.5, label='FFT Spectrum')
        self.ax2.set_title("FFT Spectrum", fontsize=12)
        self.ax2.set_xlabel("Frequency (Hz)")
        self.ax2.set_ylabel("Magnitude")
        self.ax2.set_ylim(0, 1.0) # 初始范围，会自适应
        self.ax2.set_xlim(0, 100)  # 显示0-100Hz范围
        self.ax2.grid(True, alpha=0.3)
        self.ax2.legend(loc='upper right')
        
        # 频率轴 (Fs=200Hz, 默认 N=4096)
        self.fs = 200
        self.n_fft = 4096 # 默认值，会根据数据更新
        self.freqs = np.linspace(0, self.fs/2, self.n_fft // 2)

    def update_data(self, scg_value: float, fft_data: list[float], timestamp: float, max_bin: int, offset: int, n_fft: int = 4096, score: float = 0.0, corr_matrix: list[list[float]] = None) -> None:
        """更新数据."""
        self.scg_data.append(scg_value)
        self.time_data.append(timestamp)
        self.fft_data = np.array(fft_data)
        self.max_bin = max_bin
        self.offset = offset
        self.score = score
        if corr_matrix and len(corr_matrix) > 0:
            self.corr_matrix = np.array(corr_matrix)
        
        # 如果FFT点数变化，更新频率轴
        if n_fft != self.n_fft:
            self.n_fft = n_fft
            self.freqs = np.linspace(0, self.fs/2, self.n_fft // 2)

    def update_plot(self, frame: int) -> tuple:
        """更新图形."""
        if not self.time_data:
            return self.line_scg, self.line_fft, self.status_text

        # 更新SCG波形
        times = np.array(self.time_data)
        scg = np.array(self.scg_data)
        
        self.line_scg.set_data(times, scg)
        self.ax1.set_xlim(times[0], times[-1] + 0.1)
        
        # SCG Y轴自适应
        if len(scg) > 10:
            y_min, y_max = scg.min(), scg.max()
            margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            self.ax1.set_ylim(y_min - margin, y_max + margin)

        # 更新FFT
        if hasattr(self, 'fft_data') and len(self.fft_data) > 0:
            # 确保频率轴长度匹配
            if len(self.fft_data) == len(self.freqs):
                self.line_fft.set_data(self.freqs, self.fft_data)
                
                # Y轴自适应
                max_mag = np.max(self.fft_data)
                if max_mag > 0:
                    self.ax2.set_ylim(0, max_mag * 1.2)
            else:
                # 重新计算频率轴
                freqs = np.linspace(0, 100, len(self.fft_data))
                self.line_fft.set_data(freqs, self.fft_data)
                
                # Y轴自适应
                max_mag = np.max(self.fft_data)
                if max_mag > 0:
                    self.ax2.set_ylim(0, max_mag * 1.2)
        
        # 更新文本
        status_str = (
            f"Best Bin: {self.max_bin}\n"
            f"Offset: {self.offset}\n"
            f"Buffer: {len(self.scg_data)}"
        )
        self.status_text.set_text(status_str)
        
        # 更新大字分数
        score_val = int(self.score * 100)
        self.score_text.set_text(f"Score: {score_val}")
        
        # 更新互相关矩阵
        if hasattr(self, 'corr_matrix') and self.corr_matrix is not None:
            self.im.set_data(self.corr_matrix)
            # 自动调整范围
            n = self.corr_matrix.shape[0]
            self.im.set_extent([-0.5, n-0.5, n-0.5, -0.5]) # 调整坐标轴
            self.ax3.set_xlim(-0.5, n-0.5)
            self.ax3.set_ylim(n-0.5, -0.5)

        return self.line_scg, self.line_fft, self.status_text, self.score_text, self.im

def main():
    print("=" * 60)
    print("SCG Best Bin Grade Visualization")
    print("=" * 60)
    
    # 配置
    serial_port = "COM7"
    baudrate = 921600
    
    # 队列
    data_queue = Queue()
    output_queue = Queue()
    
    # 可视化器
    visualizer = SCGBestBinVisualizer()
    
    # 数据更新闭包
    def update_from_queue():
        count = 0
        while not output_queue.empty() and count < 20:
            try:
                res = output_queue.get_nowait()
                visualizer.update_data(
                    scg_value=res["scg_value"],
                    fft_data=res["fft_magnitude"],
                    timestamp=res["timestamp"],
                    max_bin=res["max_bin"],
                    offset=res.get("offset", 0),
                    n_fft=res.get("n_fft", 4096),
                    score=res.get("score", 0.0),
                    corr_matrix=res.get("corr_matrix", [])
                )
                count += 1
            except Exception:
                break

    # 包装动画函数
    original_update = visualizer.update_plot
    def wrapped_update(frame):
        update_from_queue()
        return original_update(frame)
    visualizer.update_plot = wrapped_update

    # 启动线程
    radar_thread = MMWRadarThread(
        output_queue=data_queue,
        serial_port=serial_port,
        serial_baudrate=baudrate
    )
    
    # 使用 SCGGradeProcessor (已包含Best Bin选择逻辑)
    processor_thread = SCGGradeProcessor(
        input_queue=data_queue,
        output_queue=output_queue
    )
    
    print("Starting threads...")
    radar_thread.start()
    processor_thread.start()
    
    # 启动动画
    anim = FuncAnimation(
        visualizer.fig,
        visualizer.update_plot,
        interval=50,
        blit=True,
        cache_frame_data=False
    )
    
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping...")
        processor_thread.stop()
        radar_thread.stop()
        processor_thread.join(timeout=1)
        radar_thread.join(timeout=1)

if __name__ == "__main__":
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    main()
