import numpy as np
from scipy.signal import butter, filtfilt
from src.mmw_processor import MMWProcessorThread

class SCGGradeProcessor(MMWProcessorThread):
    """SCG评分与自相关分析处理线程.
    
    专注于单通道（最大能量Bin）的SCG提取，并计算其自相关函数。
    同时进行周期分割与相似度矩阵计算。
    """
    
    # 滤波参数 (复用 mmw_heart_rate.py)
    SAMPLING_RATE = 200
    LOWCUT = 20
    HIGHCUT = 40
    FILTER_ORDER = 4

    def _compute_score_and_fft(self, signal: np.ndarray) -> tuple[float, np.ndarray, int]:
        """计算信号评分和FFT频谱.
        
        Returns:
            (score, fft_magnitude, n_fft)
        """
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
        # 归一化
        if len(fft_signal) > 0:
            fft_magnitude = fft_magnitude / len(fft_signal) * 2

        # 计算信号质量分数 (20Hz以下能量占比)
        idx_20hz = int(20 * n_fft / 200)
        
        # 计算能量谱 (幅度的平方)
        energy_spectrum = fft_magnitude ** 2
        total_energy = np.sum(energy_spectrum)
        
        score = 0.0
        if total_energy > 0:
            low_freq_energy = np.sum(energy_spectrum[:idx_20hz])
            score = low_freq_energy / total_energy
            
        return score, fft_magnitude, n_fft

    def _generate_new_scg_point(self) -> None:
        """生成新的SCG点及自相关数据."""
        if len(self._frame_buffer) < self.MIN_BUFFER_SIZE:
            return

        # 转换为numpy数组
        fft_data = np.array(self._frame_buffer)
        
        # 寻找最佳Bin (基于评分，带滞后逻辑)
        # 如果当前没有选中的Bin，或者_current_max_bin无效，则默认为0
        current_selected_bin = self._current_max_bin if 0 <= self._current_max_bin < self._bins_per_channel else 0
        
        best_bin_idx = 0
        max_score = -1.0
        
        # 存储所有Bin的计算结果，以便后续根据选择直接获取
        # 格式: {bin_idx: (score, scg_waveform, fft_mag, n_fft)}
        bin_results = {}
        
        # 遍历所有Bin计算评分
        for bin_idx in range(self._bins_per_channel):
             # 提取相位 -> SCG
             phase_data = self._extract_phase(fft_data, bin_idx)
             scg_waveform = self._compute_derivative_waveform(phase_data)
             
             # 过滤异常值
             outlier_idx = np.abs(scg_waveform) > self.OUTLIER_THRESHOLD
             scg_waveform[outlier_idx] = 0.0
             
             # 计算评分
             score, fft_mag, n_fft = self._compute_score_and_fft(scg_waveform)
             
             bin_results[bin_idx] = (score, scg_waveform, fft_mag, n_fft)
             
             # 记录全局最高分
             if score > max_score:
                 max_score = score
                 best_bin_idx = bin_idx
        
        # 滞后逻辑：
        # 只有当全局最高分比当前选中Bin的分数高出阈值(0.05)时，才切换Bin
        # 否则保持当前Bin不变
        current_bin_score = bin_results[current_selected_bin][0]
        HYSTERESIS_THRESHOLD = 0.05
        
        if max_score > current_bin_score + HYSTERESIS_THRESHOLD:
            final_bin_idx = best_bin_idx
        else:
            final_bin_idx = current_selected_bin
            
        # 使用最终选择的Bin的数据
        score, scg_waveform, fft_magnitude, n_fft = bin_results[final_bin_idx]
        self._current_max_bin = final_bin_idx
        max_bin_idx = final_bin_idx # 兼容变量名
        
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
        # (已在循环中计算最佳Bin的FFT)
        # 7. 计算信号质量分数 (20Hz以下能量占比)
        # (已在循环中计算)

        # 8. 周期分割与互相关矩阵计算
        corr_matrix = []
        if self._generated_scg_points % 20 == 0: # 每20帧(0.1s)计算一次，避免过高负载
             corr_matrix = self._compute_cycle_correlation_matrix(scg_waveform)

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
            "score": score,  # 信号质量分数
            "corr_matrix": corr_matrix # 互相关矩阵
        }
        
        self._output_queue.put(result)
        self._generated_scg_points += 1

    def _compute_cycle_correlation_matrix(self, scg_data: np.ndarray) -> list[list[float]]:
        """计算周期互相关矩阵.
        
        1. 带通滤波 (20-40Hz)
        2. 峰值检测
        3. 切片与重采样
        4. 计算相关系数矩阵
        """
        # 1. 预处理与滤波
        try:
            # 归一化
            max_val = np.max(np.abs(scg_data))
            if max_val == 0: return []
            norm_data = scg_data / max_val
            
            # 滤波
            b, a = butter(
                self.FILTER_ORDER,
                [self.LOWCUT / (self.SAMPLING_RATE / 2), self.HIGHCUT / (self.SAMPLING_RATE / 2)],
                btype='band',
                analog=False
            )
            filtered_data = filtfilt(b, a, norm_data)
            
            # 再次归一化
            max_val = np.max(np.abs(filtered_data))
            if max_val == 0: return []
            filtered_data = filtered_data / max_val
            
        except Exception:
            return []

        # 2. 峰值检测 (复用 heart_rate_old 逻辑)
        peaks = self._detect_peaks_multistep(filtered_data)
        if len(peaks) < 3: # 至少需要3个峰才能形成2个完整周期
            return []
            
        # 3. 切片与重采样
        segments = []
        target_length = 100 # 统一重采样到100点
        
        # 使用峰值间的数据作为周期
        for i in range(len(peaks) - 1):
            start = peaks[i]
            end = peaks[i+1]
            
            # 简单的异常周期过滤 (50bpm -> 240点, 150bpm -> 80点)
            # 既然是SCG，可能包含更多高频成分，这里放宽一点
            if end - start < 40 or end - start > 300:
                continue
                
            # 提取原始SCG数据片段 (注意：使用原始SCG还是滤波后的？通常原始波形包含更多形态信息)
            # 这里我们使用原始SCG数据(scg_data)进行形态比较
            segment = scg_data[start:end]
            
            # 重采样
            x_old = np.linspace(0, 1, len(segment))
            x_new = np.linspace(0, 1, target_length)
            segment_resampled = np.interp(x_new, x_old, segment)
            
            # 归一化片段 (去除幅度差异，只比形状)
            seg_mean = np.mean(segment_resampled)
            seg_std = np.std(segment_resampled)
            if seg_std > 1e-6:
                segment_resampled = (segment_resampled - seg_mean) / seg_std
            else:
                segment_resampled = segment_resampled - seg_mean
                
            segments.append(segment_resampled)
            
        if len(segments) < 2:
            return []
            
        # 4. 计算相关系数矩阵
        n_segs = len(segments)
        matrix = np.zeros((n_segs, n_segs))
        
        for i in range(n_segs):
            for j in range(n_segs):
                # Pearson correlation
                # 由于已经归一化 (mean=0, std=1)，corr = mean(a * b)
                corr = np.mean(segments[i] * segments[j])
                matrix[i, j] = corr
                
        return matrix.tolist()

    def _detect_peaks_multistep(self, filtered_data: np.ndarray) -> np.ndarray:
        """多步骤峰值检测算法 (复用自 mmw_heart_rate.py)."""
        sample_points = len(filtered_data)
        y = filtered_data
        
        # 第一步：找到所有局部最大值
        peak_indices_1 = []
        if sample_points > 1:
            if y[0] > y[1]: peak_indices_1.append(0)
            for i in range(1, sample_points - 1):
                if y[i] >= y[i-1] and y[i] >= y[i+1]:
                    peak_indices_1.append(i)
            if y[sample_points-2] < y[sample_points-1]:
                peak_indices_1.append(sample_points-1)
        
        if len(peak_indices_1) < 2: return np.array([])

        # 第二步：在局部最大值中找更大的峰值
        peak_indices_2 = []
        if len(peak_indices_1) >= 2:
            if y[peak_indices_1[0]] > y[peak_indices_1[1]]:
                peak_indices_2.append(peak_indices_1[0])
            for i in range(1, len(peak_indices_1) - 1):
                index = peak_indices_1[i]
                index_b = peak_indices_1[i - 1]
                index_a = peak_indices_1[i + 1]
                if y[index] >= y[index_b] and y[index] >= y[index_a]:
                    peak_indices_2.append(index)
            if y[peak_indices_1[-2]] < y[peak_indices_1[-1]]:
                peak_indices_2.append(peak_indices_1[-1])

        # 第三步：筛选满足阈值的峰值
        peak_indices_3 = []
        for index in peak_indices_2:
            if y[index] >= 0.3:
                peak_indices_3.append(index)
        
        if len(peak_indices_3) < 2: return np.array([])

        # 第四步：合并间隔1-40的峰值
        peak_indices_4 = []
        j = 0
        while j < len(peak_indices_3) - 1:
            index = peak_indices_3[j]
            index_a = peak_indices_3[j + 1]
            if 1 <= index_a - index <= 40:
                if y[index_a] >= y[index]: select_index = index_a
                else: select_index = index
                j += 1
                peak_indices_4.append(select_index)
            else:
                peak_indices_4.append(index)
            j += 1
        
        if len(peak_indices_3) > 0 and (not peak_indices_4 or peak_indices_3[-1] != peak_indices_4[-1]):
             # 简单处理最后一个点逻辑，确保不漏
             if len(peak_indices_4) == 0 or peak_indices_3[-1] - peak_indices_4[-1] > 40:
                 peak_indices_4.append(peak_indices_3[-1])

        return np.array(peak_indices_4)
