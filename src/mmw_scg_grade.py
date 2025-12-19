import numpy as np
from src.mmw_processor import MMWProcessorThread

class SCGGradeProcessor(MMWProcessorThread):
    """SCG评分与自相关分析处理线程.
    
    专注于单通道（最大能量Bin）的SCG提取，并计算其自相关函数。
    """

    def _generate_new_scg_point(self) -> None:
        """生成新的SCG点及自相关数据."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        # 转换为numpy数组
        fft_data = np.array(self._frame_buffer)
        
        # 1. 找到能量最大的频率bin
        max_bin_idx = self._find_max_energy_bin(fft_data)
        self._current_max_bin = max_bin_idx

        # 2. 提取相位数据
        phase_data = self._extract_phase(fft_data, max_bin_idx)

        # 3. 计算二阶导数 (SCG)
        scg_waveform = self._compute_derivative_waveform(phase_data)

        # 4. 过滤异常值
        outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
        scg_waveform[outlier_idx] = 0.0
        
        # 取最新的SCG值（用于滚动显示）
        latest_value = scg_waveform[-4]

        # 5. 计算自相关函数 (基于当前1000点的窗口)
        # 标准化
        signal = scg_waveform
        if np.std(signal) > 1e-6:
            signal_norm = (signal - np.mean(signal)) / np.std(signal)
        else:
            signal_norm = signal - np.mean(signal)

        # 计算自相关
        # mode='full' 返回长度为 2*N - 1
        corr = np.correlate(signal_norm, signal_norm, mode='full')
        # 取正半轴 (lag >= 0)
        corr = corr[len(corr)//2:]
        # 归一化 (使得 lag=0 时为 1)
        if len(signal_norm) > 0:
            corr = corr / len(signal_norm)

        # 6. 计算FFT
        # 去除直流分量
        fft_signal = signal - np.mean(signal)
        # 加窗 (Hanning window)
        window = np.hanning(len(fft_signal))
        
        # 使用补零增加FFT点数到4096，获得更平滑的频谱
        n_fft = 4096
        fft_result = np.fft.fft(fft_signal * window, n=n_fft)
        
        # 取模值
        fft_magnitude = np.abs(fft_result)
        # 只取正频率部分 (N/2)
        fft_magnitude = fft_magnitude[:n_fft//2]
        # 归一化 (注意：补零后的幅度归一化仍需除以原始信号长度)
        fft_magnitude = fft_magnitude / len(fft_signal) * 2

        # 7. 计算信号质量分数 (20Hz以下能量占比)
        # Fs = 200Hz, n_fft = 4096
        # 频率分辨率 = 200 / 4096 ~= 0.0488 Hz
        # 20Hz 对应的索引 = 20 / (200/4096) = 409.6 -> 410
        idx_20hz = int(20 * n_fft / 200)
        
        # 计算能量谱 (幅度的平方)
        energy_spectrum = fft_magnitude ** 2
        total_energy = np.sum(energy_spectrum)
        
        score = 0.0
        if total_energy > 0:
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            score = low_freq_energy / total_energy

        # 构造输出
        result = {
            "frame_idx": self._generated_scg_points,
            "scg_value": float(latest_value),
            "autocorrelation": corr.tolist(),
            "fft_magnitude": fft_magnitude.tolist(),
            "timestamp": self._generated_scg_points * self.TIME_STEP,
            "max_bin": max_bin_idx,
            "offset": self._current_offset,
            "n_fft": n_fft, # 传递FFT点数
            "score": score  # 信号质量分数
        }
        
        self._output_queue.put(result)
        self._generated_scg_points += 1
