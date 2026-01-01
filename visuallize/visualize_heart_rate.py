"""毫米波雷达综合可视化脚本 (SCG波形 + 心率 + 暂停功能).

集成 visualize_grade_all.py 的多Bin SCG波形显示
和 visualize_heart_rate.py 的心率趋势显示。
支持暂停/继续功能。
"""
import sys
import time
import threading
from collections import deque
from queue import Queue, Empty
from pathlib import Path
import copy

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_rader import MMWRadarThread
from src.mmw_processor import MMWProcessorThread
from src.mmw_heart_rate import MMWHeartRateThread

# ==========================================
# 1. 复制并修改 MultiBinGradeProcessor
# ==========================================
class MultiBinGradeProcessor(MMWProcessorThread):
    """多Bin评分处理线程."""
    
    def _generate_new_scg_point(self) -> None:
        """重写生成函数，输出所有Bin的数据及评分."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        fft_data = np.array(self._frame_buffer)
        
        scg_values = []
        scores = []
        
        for bin_idx in range(self._bins_per_channel):
            phase_data = self._extract_phase(fft_data, bin_idx)
            scg_waveform = self._compute_derivative_waveform(phase_data)
            outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
            scg_waveform[outlier_idx] = 0.0
            
            latest_value = scg_waveform[-4]
            scg_values.append(float(latest_value))
            
            score = self._compute_score(scg_waveform)
            scores.append(score)
            
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
            
        result = {
            "type": "scg",
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
        try:
            signal = signal - np.mean(signal)
            window = np.hanning(len(signal))
            n_fft = 4096
            fft_result = np.fft.fft(signal * window, n=n_fft)
            fft_magnitude = np.abs(fft_result)
            fft_magnitude = fft_magnitude[:n_fft//2]
            
            energy_spectrum = fft_magnitude ** 2
            total_energy = np.sum(energy_spectrum)
            
            if total_energy <= 0:
                return 0.0
                
            idx_20hz = int(20 * n_fft / 200)
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            
            return low_freq_energy / total_energy
        except Exception:
            return 0.0

# ==========================================
# 2. 数据分发线程
# ==========================================
class DataDispatcher(threading.Thread):
    """将雷达数据分发给SCG处理器和心率处理器."""
    def __init__(self, input_queue, queues_out):
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.queues_out = queues_out
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.input_queue.get(timeout=1.0)
                for q in self.queues_out:
                    q.put(data)
            except Empty:
                continue
            except Exception as e:
                print(f"Dispatcher error: {e}")

    def stop(self):
        self.running = False

# ==========================================
# 3. 综合可视化器
# ==========================================
class CombinedVisualizer:
    """综合可视化器 (SCG + Heart Rate)."""

    def __init__(self, window_size: int = 1000, bins_num: int = 10, hr_history_size: int = 50) -> None:
        self.window_size = window_size
        self.bins_num = bins_num
        self.hr_history_size = hr_history_size
        
        # SCG 数据
        self.scg_data = [deque(maxlen=window_size) for _ in range(bins_num)]
        self.time_data = deque(maxlen=window_size)
        self.scores = [0.0] * bins_num
        self.max_bin = 0
        self.offset = 0
        
        # 心率数据
        self.hr_history = deque(maxlen=hr_history_size)
        self.current_hr = 0.0
        self.hr_status = "waiting"
        
        # 暂停状态
        self.is_paused = False
        
        # 创建图形
        self.figs = []
        self.axes_list = []
        self.lines = []
        self.score_texts = []
        
        # Figure 1: Bins 0-4
        fig1, axes1 = plt.subplots(5, 1, figsize=(8, 10), sharex=True)
        fig1.canvas.manager.set_window_title("SCG Waveforms (Bins 0-4)")
        self.figs.append(fig1)
        self.axes_list.extend(axes1.flatten() if isinstance(axes1, np.ndarray) else [axes1])

        # Figure 2: Bins 5-9
        fig2, axes2 = plt.subplots(5, 1, figsize=(8, 10), sharex=True)
        fig2.canvas.manager.set_window_title("SCG Waveforms (Bins 5-9)")
        self.figs.append(fig2)
        self.axes_list.extend(axes2.flatten() if isinstance(axes2, np.ndarray) else [axes2])
        
        # Figure 3: Heart Rate Trend
        fig3, ax3 = plt.subplots(figsize=(8, 4))
        fig3.canvas.manager.set_window_title("Heart Rate Trend")
        self.figs.append(fig3)
        self.hr_ax = ax3
        
        # 初始化 SCG 线条和文本
        colors = plt.cm.jet(np.linspace(0, 1, bins_num))
        self.default_colors = colors
        
        for i in range(bins_num):
            ax = self.axes_list[i]
            line, = ax.plot([], [], color=colors[i], linewidth=1)
            self.lines.append(line)
            ax.grid(True, alpha=0.3)
            ax.set_ylabel(f"Bin {i}", fontsize=9)
            
            score_text = ax.text(
                0.98, 0.90, "Score: 0",
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="right",
                fontsize=10,
                fontweight='bold',
                color='red',
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "none"}
            )
            self.score_texts.append(score_text)

        self.axes_list[4].set_xlabel("Time (s)")
        self.axes_list[9].set_xlabel("Time (s)")
        
        # 初始化心率图
        self.hr_ax.set_title("Heart Rate Trend", fontsize=12)
        self.hr_ax.set_xlabel("Measurements")
        self.hr_ax.set_ylabel("BPM")
        self.hr_ax.set_ylim(40, 160)
        self.hr_ax.grid(True, alpha=0.3)
        self.hr_line, = self.hr_ax.plot([], [], "r-o", linewidth=2)
        self.hr_text = self.hr_ax.text(0.02, 0.9, "HR: --", transform=self.hr_ax.transAxes, fontsize=14, fontweight='bold')
        
        # 添加暂停按钮 (在 Figure 3 上)
        self.pause_ax = fig3.add_axes([0.8, 0.02, 0.1, 0.075])
        self.pause_btn = Button(self.pause_ax, 'Pause')
        self.pause_btn.on_clicked(self.toggle_pause)
        
        # 状态文本
        self.status_text = self.axes_list[0].text(
            0.02, 0.95, "", transform=self.axes_list[0].transAxes,
            verticalalignment="top", fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5}
        )

    def toggle_pause(self, event):
        self.is_paused = not self.is_paused
        self.pause_btn.label.set_text('Resume' if self.is_paused else 'Pause')

    def update_scg(self, res: dict):
        if self.is_paused: return
        
        scg_values = res["scg_values"]
        scores = res["scores"]
        timestamp = res["timestamp"]
        
        for i, val in enumerate(scg_values):
            if i < len(self.scg_data):
                self.scg_data[i].append(val)
        
        self.time_data.append(timestamp)
        self.scores = scores
        self.max_bin = res.get("max_bin", 0)
        self.offset = res.get("offset", 0)

    def update_hr(self, res: dict):
        if self.is_paused: return
        
        hr = res.get("heart_rate", 0)
        self.current_hr = hr
        self.hr_status = res.get("status", "unknown")
        if hr > 0:
            self.hr_history.append(hr)

    def _update_scg_fig(self, start_idx, end_idx):
        if not self.time_data:
            return self.lines[start_idx:end_idx]
            
        times = np.array(self.time_data)
        artists = []
        
        for i in range(start_idx, end_idx):
            line = self.lines[i]
            ax = self.axes_list[i]
            text = self.score_texts[i]
            
            # 高亮最大Bin
            if i == self.max_bin:
                line.set_color('red')
                line.set_linewidth(2)
                text.set_color('red')
            else:
                line.set_color(self.default_colors[i])
                line.set_linewidth(1)
                text.set_color('gray')
            
            if len(self.scg_data[i]) > 0:
                data = np.array(self.scg_data[i])
                line.set_data(times, data)
                
                y_min, y_max = data.min(), data.max()
                margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
                ax.set_ylim(y_min - margin, y_max + margin)
                
            ax.set_xlim(times[0], times[-1] + 0.1)
            text.set_text(f"Score: {int(self.scores[i]*100)}")
            
            artists.append(line)
            artists.append(text)
            
        return artists

    def update_fig1(self, frame):
        if self.is_paused: return self.lines[0:5] + self.score_texts[0:5] + [self.status_text]
        
        artists = self._update_scg_fig(0, 5)
        
        status_str = f"Max Bin: {self.max_bin}\nOffset: {self.offset}\nHR: {self.current_hr:.1f} bpm"
        self.status_text.set_text(status_str)
        artists.append(self.status_text)
        return tuple(artists)

    def update_fig2(self, frame):
        if self.is_paused: return self.lines[5:10] + self.score_texts[5:10]
        return tuple(self._update_scg_fig(5, 10))

    def update_fig3(self, frame):
        if self.is_paused: return [self.hr_line, self.hr_text]
        
        if len(self.hr_history) > 0:
            self.hr_line.set_data(range(len(self.hr_history)), list(self.hr_history))
            self.hr_ax.set_xlim(0, max(len(self.hr_history), self.hr_history_size))
        
        self.hr_text.set_text(f"HR: {self.current_hr:.1f} bpm ({self.hr_status})")
        color = "green" if 60 <= self.current_hr <= 100 else "red"
        self.hr_text.set_color(color)
        
        return [self.hr_line, self.hr_text]

    def start_animations(self):
        anim1 = FuncAnimation(self.figs[0], self.update_fig1, interval=50, blit=True, cache_frame_data=False)
        anim2 = FuncAnimation(self.figs[1], self.update_fig2, interval=50, blit=True, cache_frame_data=False)
        anim3 = FuncAnimation(self.figs[2], self.update_fig3, interval=100, blit=True, cache_frame_data=False)
        return [anim1, anim2, anim3]

def main():
    print("启动综合可视化 (SCG + Heart Rate)...")
    
    # 队列
    radar_queue = Queue()
    scg_input_queue = Queue()
    hr_input_queue = Queue()
    
    # 结果队列
    scg_output_queue = Queue()
    # HR线程直接通过回调更新? 或者也用队列
    # MMWHeartRateThread 支持 callback. 
    # 为了统一，我们可以用 callback 把结果放入一个公共结果队列，或者直接更新 visualizer.
    # 但 visualizer 在主线程，callback 在子线程，直接更新 visualizer 数据结构（deques）是线程安全的吗？
    # deque 是线程安全的 (GIL)。
    # 但为了架构清晰，我们用 Queue 传递结果到主线程 loop.
    viz_queue = Queue()
    
    def scg_callback(res): # 不适用，MultiBinGradeProcessor 把结果放入 output_queue
        pass
        
    def hr_callback(res):
        res["type"] = "hr"
        viz_queue.put(res)

    # 线程
    dispatcher = DataDispatcher(radar_queue, [scg_input_queue, hr_input_queue])
    
    radar_thread = MMWRadarThread(
        output_queue=radar_queue,
        serial_port="COM7", 
        serial_baudrate=921600
    )
    
    scg_processor = MultiBinGradeProcessor(
        input_queue=scg_input_queue,
        output_queue=scg_output_queue
    )
    
    hr_processor = MMWHeartRateThread(
        input_queue=hr_input_queue,
        callback=hr_callback
    )
    
    # 可视化
    viz = CombinedVisualizer()
    
    # 启动
    radar_thread.start()
    dispatcher.start()
    scg_processor.start()
    hr_processor.start()
    
    # 动画更新包装
    # 我们需要在主线程消费 scg_output_queue 和 viz_queue (HR结果)
    # 可以在 animation update 函数中消费
    
    def consume_queues():
        # 消费 SCG
        while not scg_output_queue.empty():
            try:
                res = scg_output_queue.get_nowait()
                viz.update_scg(res)
            except Empty:
                break
        
        # 消费 HR
        while not viz_queue.empty():
            try:
                res = viz_queue.get_nowait()
                viz.update_hr(res)
            except Empty:
                break
                
    original_update1 = viz.update_fig1
    def wrapped_update1(frame):
        consume_queues()
        return original_update1(frame)
    viz.update_fig1 = wrapped_update1
    
    anims = viz.start_animations()
    
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping...")
        dispatcher.stop()
        scg_processor.stop()
        hr_processor.stop()
        radar_thread.stop()
        # join...

if __name__ == "__main__":
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    main()
