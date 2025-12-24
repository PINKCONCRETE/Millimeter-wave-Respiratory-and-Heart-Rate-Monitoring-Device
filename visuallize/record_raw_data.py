"""带原始数据录制功能的多Bin评分可视化脚本.

显示所有10个Bin的SCG波形及其质量评分，并提供按钮录制原始十六进制数据。
"""
import sys
import time
import datetime
import threading
from collections import deque
from pathlib import Path
from queue import Queue

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_rader import MMWRadarThread
from src.mmw_processor import MMWProcessorThread


class MultiBinGradeProcessor(MMWProcessorThread):
    """多Bin评分处理线程."""
    
    def _generate_new_scg_point(self) -> None:
        """重写生成函数，输出所有Bin的数据及评分."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        # 转换为numpy数组
        fft_data = np.array(self._frame_buffer)
        
        scg_values = []
        scores = []
        
        # 遍历所有Bin
        for bin_idx in range(self._bins_per_channel):
            # 1. 提取相位
            phase_data = self._extract_phase(fft_data, bin_idx)
            # 2. 计算导数 (SCG波形)
            scg_waveform = self._compute_derivative_waveform(phase_data)
            # 3. 过滤异常值
            outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
            scg_waveform[outlier_idx] = 0.0
            
            # 取最新的值
            latest_value = scg_waveform[-4]
            scg_values.append(float(latest_value))
            
            # 4. 计算评分 (20Hz以下能量占比)
            score = self._compute_score(scg_waveform)
            scores.append(score)
            
        # 更新逻辑：选择评分最高的Bin作为Max Bin (带滞后)
        current_selected_bin = self._current_max_bin if 0 <= self._current_max_bin < self._bins_per_channel else 0
        
        max_score_idx = int(np.argmax(scores))
        max_score = scores[max_score_idx]
        current_bin_score = scores[current_selected_bin]
        
        HYSTERESIS_THRESHOLD = 0.05
        
        if max_score > current_bin_score + HYSTERESIS_THRESHOLD:
            final_bin_idx = max_score_idx
        else:
            final_bin_idx = current_selected_bin
            
        max_bin_idx = final_bin_idx
        self._current_max_bin = final_bin_idx
            
        # 输出结果
        result = {
            "frame_idx": self._generated_scg_points,
            "scg_values": scg_values,
            "scores": scores,
            "timestamp": self._generated_scg_points * self.TIME_STEP,
            "offset": self._current_offset,
            "max_bin": max_bin_idx
        }
        self._output_queue.put(result)
        
        self._generated_scg_points += 1

    def _compute_score(self, signal: np.ndarray) -> float:
        """计算信号质量评分."""
        try:
            # 去除直流
            signal = signal - np.mean(signal)
            # 加窗
            window = np.hanning(len(signal))
            # FFT (补零到4096)
            n_fft = 4096
            fft_result = np.fft.fft(signal * window, n=n_fft)
            # 幅度谱
            fft_magnitude = np.abs(fft_result)
            fft_magnitude = fft_magnitude[:n_fft//2]
            
            # 计算能量
            energy_spectrum = fft_magnitude ** 2
            total_energy = np.sum(energy_spectrum)
            
            if total_energy <= 0:
                return 0.0
                
            # 计算20Hz以下能量
            idx_20hz = int(20 * n_fft / 200)
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            
            return low_freq_energy / total_energy
        except Exception:
            return 0.0


class RecorderVisualizer:
    """带录制功能的多Bin评分可视化器."""

    def __init__(self, radar_thread: MMWRadarThread, window_size: int = 1000, bins_num: int = 10) -> None:
        self.radar_thread = radar_thread
        self.window_size = window_size
        self.bins_num = bins_num
        self.scg_data = [deque(maxlen=window_size) for _ in range(bins_num)]
        self.time_data = deque(maxlen=window_size)
        
        # 状态
        self.scores = [0.0] * bins_num
        self.max_bin = 0
        self.offset = 0
        self.start_time = time.time()
        self.data_start_timestamp = 0.0
        self.data_end_timestamp = 0.0
        
        # 录制状态
        self.is_recording = False
        self.record_file = None
        
        # 创建2个图形
        self.figs = []
        self.axes_list = []
        self.score_texts = []
        
        # Figure 1: Bins 0-4
        fig1, axes1 = plt.subplots(5, 1, figsize=(10, 10), sharex=True)
        fig1.canvas.manager.set_window_title("SCG Scores Bins 0-4 (Recorder)")
        self.figs.append(fig1)
        if isinstance(axes1, np.ndarray):
            self.axes_list.extend(axes1.flatten())
        else:
            self.axes_list.append(axes1)

        # Figure 2: Bins 5-9
        fig2, axes2 = plt.subplots(5, 1, figsize=(10, 10), sharex=True)
        fig2.canvas.manager.set_window_title("SCG Scores Bins 5-9")
        self.figs.append(fig2)
        if isinstance(axes2, np.ndarray):
            self.axes_list.extend(axes2.flatten())
        else:
            self.axes_list.append(axes2)

        # 初始化线条和文本
        self.lines = []
        colors = plt.cm.jet(np.linspace(0, 1, bins_num))
        self.default_colors = colors
        
        for i in range(bins_num):
            if i >= len(self.axes_list): break
                
            ax = self.axes_list[i]
            line, = ax.plot([], [], color=colors[i], linewidth=1)
            self.lines.append(line)
            
            ax.grid(True, alpha=0.3)
            ax.set_ylabel(f"Bin {i}", fontsize=10)
            
            # 分数显示 (右上角)
            score_text = ax.text(
                0.98, 0.90, "Score: 0",
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="right",
                fontsize=14,
                fontweight='bold',
                color='red',
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "none"}
            )
            self.score_texts.append(score_text)

        # X轴标签
        self.axes_list[4].set_xlabel("Time (s)")
        self.axes_list[9].set_xlabel("Time (s)")
        
        # 状态文本 (Figure 1)
        self.status_text1 = self.axes_list[0].text(
            0.02, 0.95, "",
            transform=self.axes_list[0].transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=9,
        )

        # 状态文本 (Figure 2)
        self.status_text2 = self.axes_list[5].text(
            0.02, 0.95, "",
            transform=self.axes_list[5].transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=9,
        )
        
        # 添加录制按钮 (在 Figure 1 顶部)
        # 调整第一个子图的位置，为按钮腾出空间
        # fig1.subplots_adjust(top=0.9)
        self.ax_btn = fig1.add_axes([0.7, 0.95, 0.2, 0.04]) # [left, bottom, width, height]
        self.btn_record = Button(self.ax_btn, 'Start Recording', color='lightgreen', hovercolor='0.975')
        self.btn_record.on_clicked(self.toggle_recording)
        
        # 录制状态文本
        self.record_status_text = fig1.text(0.5, 0.97, "Recording: Stopped", ha='center', va='center', fontsize=12, color='black')

    def toggle_recording(self, event):
        """切换录制状态"""
        if not self.is_recording:
            # 开始录制
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"record_{timestamp}.txt"
            filepath = Path(__file__).parent.parent / "record_raw_data" / filename
            
            try:
                self.record_file = open(filepath, "w")
                self.radar_thread.set_raw_file(self.record_file)
                self.is_recording = True
                
                # 更新UI
                self.btn_record.label.set_text("Stop Recording")
                self.btn_record.color = 'salmon'
                self.btn_record.hovercolor = 'red'
                self.record_status_text.set_text(f"Recording: {filename}")
                self.record_status_text.set_color('red')
                self.record_status_text.set_weight('bold')
                
            except Exception as e:
                print(f"Failed to start recording: {e}")
        else:
            # 停止录制
            self.radar_thread.set_raw_file(None)
            if self.record_file:
                self.record_file.close()
                self.record_file = None
            self.is_recording = False
            
            # 更新UI
            self.btn_record.label.set_text("Start Recording")
            self.btn_record.color = 'lightgreen'
            self.btn_record.hovercolor = '0.975'
            self.record_status_text.set_text("Recording: Stopped")
            self.record_status_text.set_color('black')
            self.record_status_text.set_weight('normal')

    def update_data(self, scg_values: list[float], scores: list[float], timestamp: float, offset: int, max_bin: int) -> None:
        """更新数据."""
        if not self.time_data:
            self.data_start_timestamp = timestamp
            
        self.data_end_timestamp = timestamp
        self.offset = offset
        self.max_bin = max_bin
        self.scores = scores
        
        for i, val in enumerate(scg_values):
            if i < len(self.scg_data):
                self.scg_data[i].append(val)
                
        self.time_data.append(timestamp)

    def _update_fig(self, frame: int, start_idx: int, end_idx: int, status_text=None) -> tuple:
        """通用更新函数."""
        if not self.time_data:
            artists = [self.lines[i] for i in range(start_idx, end_idx)]
            artists.extend([self.score_texts[i] for i in range(start_idx, end_idx)])
            if status_text: artists.append(status_text)
            return tuple(artists)

        times = np.array(self.time_data)
        artists = []
        
        for i in range(start_idx, end_idx):
            if i >= len(self.lines): break
                
            line = self.lines[i]
            ax = self.axes_list[i]
            text = self.score_texts[i]
            
            # 高亮最大能量Bin
            if i == self.max_bin:
                line.set_color('red')
                line.set_linewidth(2)
                text.set_color('red')
                text.set_fontweight('bold')
            else:
                line.set_color(self.default_colors[i])
                line.set_linewidth(1)
                text.set_color('gray')
                text.set_fontweight('normal')
            
            # 更新波形
            if len(self.scg_data[i]) > 0:
                data = np.array(self.scg_data[i])
                line.set_data(times, data)
                
                # Y轴自适应
                y_min, y_max = data.min(), data.max()
                margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
                ax.set_ylim(y_min - margin, y_max + margin)
            
            # X轴滚动
            ax.set_xlim(times[0], times[-1] + 0.1)
            
            # 更新分数
            score_val = int(self.scores[i] * 100)
            text.set_text(f"Score: {score_val}")
            
            artists.append(line)
            artists.append(text)

        # 更新状态文本
        if status_text:
            status_str = (
                f"Max Bin: {self.max_bin}\n"
                f"Offset: {self.offset}\n"
                f"Points: {len(self.time_data)}"
            )
            status_text.set_text(status_str)
            artists.append(status_text)
            
        return tuple(artists)

    def update_plot_fig1(self, frame: int) -> tuple:
        return self._update_fig(frame, 0, 5, self.status_text1)

    def update_plot_fig2(self, frame: int) -> tuple:
        return self._update_fig(frame, 5, 10, self.status_text2)

    def start_animations(self, interval: int = 50) -> list[FuncAnimation]:
        anim1 = FuncAnimation(self.figs[0], self.update_plot_fig1, interval=interval, blit=True, cache_frame_data=False)
        anim2 = FuncAnimation(self.figs[1], self.update_plot_fig2, interval=interval, blit=True, cache_frame_data=False)
        return [anim1, anim2]


def main():
    print("=" * 60)
    print("Multi-Bin SCG Grade Visualization with Raw Data Recording")
    print("=" * 60)
    
    # 配置
    serial_port = "COM7"
    baudrate = 921600
    
    # 队列
    data_queue = Queue()
    output_queue = Queue()
    
    # 启动线程
    radar_thread = MMWRadarThread(
        output_queue=data_queue,
        serial_port=serial_port,
        serial_baudrate=baudrate
    )
    
    processor_thread = MultiBinGradeProcessor(
        input_queue=data_queue,
        output_queue=output_queue
    )
    
    # 可视化器 (传入 radar_thread 以控制录制)
    visualizer = RecorderVisualizer(radar_thread)
    
    # 数据更新闭包
    def update_from_queue():
        count = 0
        while not output_queue.empty() and count < 50:
            try:
                res = output_queue.get_nowait()
                visualizer.update_data(
                    scg_values=res["scg_values"],
                    scores=res["scores"],
                    timestamp=res["timestamp"],
                    offset=res.get("offset", 0),
                    max_bin=res.get("max_bin", 0)
                )
                count += 1
            except Exception:
                break

    # 包装动画函数
    original_update1 = visualizer.update_plot_fig1
    def wrapped_update1(frame):
        update_from_queue()
        return original_update1(frame)
    visualizer.update_plot_fig1 = wrapped_update1
    
    print("Starting threads...")
    radar_thread.start()
    processor_thread.start()
    
    # 启动动画
    animations = visualizer.start_animations(interval=50)
    
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
        
        # 确保文件关闭
        if visualizer.record_file:
            visualizer.record_file.close()

if __name__ == "__main__":
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    main()
