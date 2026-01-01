"""
File: heart_rate_processing.py

Description:
This script processes heart rate signals for preprocessing, autocorrelation calculation, 
heart rate (HR), and heart rate variability (HRV) analysis. It includes functions to extract 
phase information, filter signals, and evaluate signal quality.

Change Log:
- Initial version with heart rate signal processing functions.
- Added support for multi-channel data and bin quality evaluation.
- Improved peak detection and HRV calculation logic.
- Translated all comments into English.
"""

import math
import time
import numpy as np
from scipy.signal import butter, filtfilt, lfilter
from scipy.signal import find_peaks


class HeartRateProcessor:
    """
    A class for processing heart rate signals, including preprocessing, 
    autocorrelation calculation, and HR/HRV analysis.
    """
    def __init__(self, pos_node):
        """
        Initialize the processor.
        Args:
            pos_node (list): Signal data after differential filtering.
        """
        self.pos_node = pos_node
        self.pre_node = []  # Data after outlier removal
        self.norm_node = []  # Normalized data
        self.filtered_data = [] # Filtered data
        self.autocorrelation_result = []  # Autocorrelation results
        self.sn_res = [] 
        self.R_ind_list = []  # R peak indices
        self.max_peak = float('-inf')
        self.peak_index = None  # Index of the maximum peak
        self.current_hr = 60  # Current heart rate, init for 60
        self.last_hr = 60  # Last heart rate, init for 60
        self.status = "failed"  # Initial status
        self.filtered_square_data = []
        self.ibi_list = []

    def preprocess(self):
        """Data preprocessing: Remove outliers and normalize the signal."""

        if not any(self.pos_node):
            print("Error: 差分数据为空!")
            return

        if len(self.pos_node) > 1000:
            self.pos_node = self.pos_node[:1000]
        self.pre_node = [0 if abs(x) > 1500 else x for x in self.pos_node]
        # self.pre_node = [x for x in self.pos_node if abs(x) <= 1500]

        if not any(self.pre_node):
            print("Error: pre node 为空!")
            return

        max_val = max([abs(x) for x in self.pre_node])
        if max_val == 0:
            print("Error: maxVal 为0 !!!.")
            return
        self.norm_node = [x / max_val for x in self.pre_node]

    def calculate_autocorrelation(self):
        """Calculate and normalize the signal's autocorrelation."""
        
        N = len(self.norm_node)
        if N == 0:
            print("Error: Normalized data is empty!")
            return

        energy = sum(x**2 for x in self.norm_node) / N
        self.autocorrelation_result = [
            sum(self.norm_node[i] * self.norm_node[i + lag] for i in range(N - lag)) / ((N - lag) * energy)
            for lag in range(N)
        ]

    def autocorrelation(self):
        """
        Calculate the autocorrelation of the signal.
        param: 
            signal: one-dimensional array or time series of input.
        return: array of autocorrelation values
        """
        signal = self.norm_node
        n = len(signal)
        mean = np.mean(signal)
        var = np.var(signal)
        autocorr = np.correlate(signal - mean, signal - mean, mode='full') / (var * n)
        self.autocorrelation_result = autocorr[n-1:] 

    def find_peak(self):
        """Find the most significant peak in the autocorrelation (lag 100~200)."""
        
        # peaks = {}
        # for i in range(99, 200):  # Search for peaks between indices 100 and 200 (corresponding to heart rates of 60-120 bpm)
        #     if (i > 0 and i < len(self.autocorrelation_result) - 1 and
        #         self.autocorrelation_result[i] > self.autocorrelation_result[i - 1] and self.autocorrelation_result[i] > self.autocorrelation_result[i + 1]):
        #         peaks[i] = self.autocorrelation_result[i]

        # if not peaks:
        #     print("Error: No peaks found in the specified range!")

        # # Find the maximum peak
        # for index, value in peaks.items():
        #     if value > self.max_peak:
        #         self.max_peak = value
        #         self.peak_index = index + 1

        # Search for peaks between indices 100 and 200 (corresponding to heart rates of 60-120 bpm)
        # Search for peaks between indices 80 and 300 (corresponding to heart rates of 40-150 bpm)

        start, end = 90, 240
        sub_range = self.autocorrelation_result[start:end + 1]
        max_value = np.max(sub_range)  # 最大峰值
        max_index = np.argmax(sub_range) + start  # 转换为全局索引

        self.max_peak = max_value
        self.peak_index = max_index + 1

    def is_peak(self, index):
        """Check if the given index represents a peak."""
        return (
            index > 0 and index < len(self.autocorrelation_result) - 1 and
            self.autocorrelation_result[index] > self.autocorrelation_result[index - 1] and
            self.autocorrelation_result[index] > self.autocorrelation_result[index + 1]
        )

    def calculate_heart_rate(self, threshold, sampling_interval):
        """
        Calculate heart rate based on autocorrelation peaks.
        Args:
            threshold (float): Peak threshold.
            sampling_interval (float): Sampling interval in seconds.
        """
        # print("Starting heart rate calculation...")
        # print(f"Threshold: {threshold}, Sampling interval: {sampling_interval}")
        # self.preprocess()
        try:
            if not any(self.norm_node):
                print("Error: Preprocessing failed, no normalized data.")
                return
            try:
                self.autocorrelation()
            except Exception as e:
                print('自相关报错')
                print(e)

            if not any(self.autocorrelation_result):
                print("Error: Autocorrelation calculation failed, no results.")
                return
        except Exception as e:
            print('any error')
            print(e)

        try:
            self.find_peak()
        except Exception as e:
            print('find peaks 报错')
            print(e)
        if self.peak_index and self.autocorrelation_result[self.peak_index] > threshold:
            self.current_hr = 60 / (sampling_interval * (self.peak_index + 1))
            self.last_hr = self.current_hr
            self.status = "succeeded"
        else:
            self.current_hr = -1
            self.status = "failed"

    def calculate_hrv(self, fs):
        """
        Calculate heart rate variability (HRV).
        Args:
            sampling_interval (float): Sampling interval in seconds.
        """
        sampling_interval = 1 / fs
        # self.preprocess()
        try:
            self.filter_data(fs)
        except Exception as e:
            print('filter data error')
            print(e)
        try:
            self.shannon()
        except Exception as e:
            print('shannon error!')
            print(e)
        try:
            final_peaks = self.detect_peaks_2(self.filtered_data)
            # final_peaks = self.detect_peaks()
            # final_peaks, _ = find_peaks(self.norm_node, height=0.3, distance=fs / 2)
        except Exception as e:
            print('detect peaks error!')
            print(e)
            final_peaks = []
        try:
            rr_intervals = self.detect_rr_intervals(final_peaks, sampling_interval)  # e.g [0.8, 0.9, 1.2, 1.0, 1.1]
        except Exception as e:
            print('detect rr intervals error!')
            print(e)
            rr_intervals = []
        N = len(rr_intervals)  # RR intervals
        if not N:
            mean_rr = 0
            sum_square_rr = 0
        else:
            mean_rr = np.mean(rr_intervals)  #  mean of RR intervals
            sum_square_rr = np.sum(np.array(rr_intervals) ** 2)  # sum square
            self.ibi_list = rr_intervals * 1000 # [897, 965, 1000]
        return mean_rr, sum_square_rr, N
    
    def filter_data(self, fs):
        # 设计带通滤波器
        lowcut = 20  # 带通滤波器的低频截止频率
        highcut = 40  # 带通滤波器的高频截止频率
        order = 4  # 滤波器阶数
        b, a = butter(order, [lowcut / (fs / 2), highcut / (fs / 2)], btype='band', analog=False)

        # 应用带通滤波器
        # filtered_signal = lfilter(b, a, self.norm_node)
        filtered_signal = filtfilt(b, a, self.norm_node)
        max_val = max([abs(x) for x in filtered_signal])
        if max_val == 0:
            print("Error: maxVal 为0 !!!.")
            return
        self.filtered_data = [x / max_val for x in filtered_signal]
    
    def detect_peaks(self):

        # 参数设置
        sample_points = len(self.filtered_square_data)  # 样本点数
        y = self.filtered_square_data  # 输入信号
        threshold = 0.3  # 阈值
        window_size = 200  # 窗口大小
        ignore_interval = 100  # 忽略峰值前后100ms内的点（假设采样率为1000Hz，100ms对应100个点）
        peak_indices = []  # 存储峰值点的索引

        # 循环检测峰值
        for i in range(0, sample_points, window_size):
            # 确定当前窗口范围
            window_start = i
            window_end = min(i + window_size, len(y))
            
            # 提取当前窗口内的数据
            window_data = y[window_start:window_end]
            
            # 找到窗口内大于阈值的最大峰值
            max_val = np.max(window_data)
            max_index = np.argmax(window_data)
            if max_val > threshold:
                # 转换为全局索引
                global_max_index = window_start + max_index
                
                # 检查是否在忽略范围内
                if not peak_indices or all(abs(global_max_index - np.array(peak_indices)) > ignore_interval):
                    # 标记峰值
                    peak_indices.append(global_max_index)

        # 标记前后100ms-200ms内的最大值为峰值
        search_range = 100  # 区间大小
        final_peaks = peak_indices.copy()  # 初始化最终峰值索引为初步检测到的峰值

        for peak_index in peak_indices:
            # 左侧100ms ~ 200ms区间
            start_index_left = max(peak_index - ignore_interval - search_range, 0)
            end_index_left = max(peak_index - ignore_interval, 0)
            if end_index_left > start_index_left:
                max_value = np.max(y[start_index_left:end_index_left])
                max_index = np.argmax(y[start_index_left:end_index_left])
                left_peak_index = start_index_left + max_index
                
                if max_value > threshold:
                    # 判断该点是否与已检测到的峰值相邻
                    if not final_peaks or all(abs(left_peak_index - np.array(final_peaks)) > ignore_interval):
                        final_peaks.append(left_peak_index)
            
            # 右侧100ms ~ 200ms区间
            start_index_right = min(peak_index + ignore_interval, len(y))
            end_index_right = min(peak_index + ignore_interval + search_range, len(y))
            if end_index_right > start_index_right:
                max_value = np.max(y[start_index_right:end_index_right])
                max_index = np.argmax(y[start_index_right:end_index_right])
                right_peak_index = start_index_right + max_index
                
                if max_value > threshold:
                    # 判断该点是否与已检测到的峰值相邻
                    if not final_peaks or all(abs(right_peak_index - np.array(final_peaks)) > ignore_interval):
                        final_peaks.append(right_peak_index)

        # 去重并排序
        final_peaks = np.unique(final_peaks)
        final_peaks = np.sort(final_peaks)  # 确保最终峰值索引是有序的

        return final_peaks

    def detect_peaks_2(self, filtered_data):
        # 参数设置
        sample_points = len(filtered_data)  # 样本点数
        y = filtered_data  # 输入信号
        peak_indices_1 = []  # 存储峰值点的索引
        peak_indices_2 = []
        peak_indices_3 = []
        peak_indices_4 = []
        peak_indices_5 = []
        final_peaks = []
        # 第一步：找到所有的局部最大值索引作为峰值
        if y[0] > y[1]:
            peak_indices_1.append(0)
        for i in range(1, sample_points-1):
            if y[i] >= y[i-1] and y[i] >= y[i+1]:
                peak_indices_1.append(i)
        if y[sample_points-2] < y[sample_points-1]:
            peak_indices_1.append(sample_points-1)
        # print('1', peak_indices_1)
        # 第二步：基于第一步找到最大值索引 [1 - 5] [0 - 4] [1 - 3]
        if y[peak_indices_1[0]] > y[peak_indices_1[1]]:
            peak_indices_2.append(peak_indices_1[0])
        for i in range(1, len(peak_indices_1) - 1):
            index = peak_indices_1[i]
            index_b = peak_indices_1[i - 1]
            index_a = peak_indices_1[i + 1]
            if y[index] >= y[index_b] and y[index] >= y[index_a]:
                peak_indices_2.append(index)
        if y[peak_indices_1[len(peak_indices_1) - 2]] < y[peak_indices_1[len(peak_indices_1) - 1]]:
            peak_indices_2.append(peak_indices_1[-1])
        # print('2:', peak_indices_2)
        # # 根据相位幅度调整心跳幅度
        # for i in range(len(peak_indices_2)):
        #     index = peak_indices_2[i]
        #     if 0.08 < y[index] < 0.15 and phase_info[index] <= 0.3:
        #         y[index] += 0.1

        # 第三步：基于第二步筛选满足阈值的索引
        for i in range(len(peak_indices_2)):
            index = peak_indices_2[i]
            # if i == 0 and y[index] >= 0.4:
            #     peak_indices_3.append(index)
            if y[index] >= 0.3:
                peak_indices_3.append(index)
        # print('3:', peak_indices_3)
        # 第四步：将两个index之间介于1-30的index取第一个
        j = 0
        while j < len(peak_indices_3) - 1:
            index = peak_indices_3[j]
            index_a = peak_indices_3[j + 1]

            # print("index, index_a", index, index_a)

            # 检查两个索引之间的差值是否在1到40之间
            if 1 <= index_a - index <= 40:
                # 选择较大的y值对应的索引
                if y[index_a] >= y[index]:
                    select_index = index_a
                else:
                    select_index = index
                j += 1
                peak_indices_4.append(select_index)

            else:
                # 如果不满足条件，直接添加当前索引
                peak_indices_4.append(index)
            j += 1

        # 检查最后一个索引是否需要添加
        if len(peak_indices_3) > 0 and peak_indices_3[-1] not in peak_indices_4 and peak_indices_3[-1] - peak_indices_4[-1] > 40:
            peak_indices_4.append(peak_indices_3[-1])

        # print('4:', peak_indices_4)
        # 第五步：基于第四步判断，若两两index之间介于40-100则取第一个index
        j = 0
        while j <= len(peak_indices_4) - 2:
            index = peak_indices_4[j]
            index_a = peak_indices_4[j + 1]
            # print(index, index_a)
            if j == 0:
                if not 40 <= index_a - index <= 80:  # 解决第二心音判定为peak的问题
                    j = j + 1
                    continue
            if 1 <= index_a - index <=80:
                j = j + 1   # 跳过下个peak
                if j == len(peak_indices_4) - 1:
                    peak_indices_5.append(index)
                    break 
            peak_indices_5.append(index)
            j = j + 1
            if j == len(peak_indices_4) - 1:
                peak_indices_5.append(peak_indices_4[j])
                break
        # peak_indices_5 = peak_indices_5[::-1]
        # if y[peak_indices_5[-1]] <= 0.5:
        #     peak_indices_5.pop()
        # peak_indices_5 = peak_indices_5[::-1]
        # print("5", peak_indices_5)

        final_peaks = peak_indices_5.copy()
        return final_peaks

    def detect_rr_intervals(self, final_peaks, sampling_interval):
        """Detect RR intervals."""
        # Implement peak detection logic here
        rrt_li = [] # R-R interval list
        # 计算相邻峰值索引之间的间隔
        if len(final_peaks) > 1:
            peaks_intervals = np.diff(final_peaks)  # 计算相邻元素的差值
            # 剔除大于240和小于100的间隔 (对应心率为50和120)
            filtered_intervals = peaks_intervals[(peaks_intervals >= 100) & (peaks_intervals <= 240)]
            # # test
            # # 文件路径
            # file_path = "data.npy"

            # # 打开文件以追加模式
            # with open(file_path, "ab") as f:
            #     np.save(f, filtered_intervals)
        else:
            filtered_intervals = np.array([])  # 如果峰值数量不足2个，返回空数组
        rrt_li = filtered_intervals * sampling_interval # 采样间隔时间为0.005s
        return rrt_li
    
    def shannon(self):
        # # If the autocorrelation peak value is greater than 0.2, it is considered a relatively good signal waveform
        # if self.max_peak > 0.2:

        # Iterate through normalized node values
        for node in self.filtered_data:
            if node:
                # Compute squared value of the node
                # d1 = node * node
                d1 = node
                # # Compute fourth power of the node
                # d3 = d1 * d1
                # # Compute Shannon entropy value for the node and append to results
                # d4 = -1 * d3 * node * math.log(d3 * abs(node))
            else:
                d1 = 0
            self.filtered_square_data.append(d1)

        # win_size = 100   # Set window size
        # threshold = 0.08 # Set threshold value
        # id = 0  # Initialize window number
        # peaks = {} # Dictionary to store peaks

        # # Iterate through the Shannon entropy results
        # for i in range(len(self.sn_res)):
        #     # Check if the current index belongs to the same window
        #     if i // win_size == id:
        #         # If the Shannon result exceeds the threshold, store it as a peak
        #         if self.sn_res[i] > threshold:
        #             peaks[i] = self.sn_res[i]
        #     else:
        #         # When moving to the next window, find the maximum peak in the previous window
        #         if peaks:
        #             self.R_ind_list.append(max(peaks, key=peaks.get))
        #         id += 1  # Increment window number
        #         peaks = {} # Reset peaks dictionary
        #         # Check the current value for the new window
        #         if self.sn_res[i] > threshold:
        #             peaks[i] = self.sn_res[i]
        # # else:
        # #     # If the peak value is not satisfactory, clear the Rin_list
        # #     self.R_ind_list = []

    @staticmethod
    def variance(data):
        """Calculate the variance of a dataset."""
        mean = sum(data) / len(data)
        return sum((x - mean)**2 for x in data) / len(data)

####################
# external methods #
####################

def differentiator_filter_double(data, h):
    """
    Perform a second-order differentiator filter.
    Args:
        data (numpy.ndarray): Input signal data.
        h (float): Sampling interval.
    Returns:
        numpy.ndarray: Filtered data.
    """
    length = data.shape[0] - 6
    data_ans = data * 0.0
    res_data = data[3:length+3] * 4.0 + \
               (data[4:length+4] + data[2:length+2]) - \
               2.0 * (data[5:length+5] + data[1:length+1]) - \
               (data[6:length+6] + data[:length])
    res_data = res_data / 16.0 / h / h
    data_ans[3:-3] = res_data
    return data_ans

def estimate_quality(sig, fs=200):
    """
    Evaluate the quality of a phase signal within a bin based on frequency domain energy.
    Higher concentration in the target frequency range (10-25 breaths per minute) indicates better quality.
    """
    freqs = np.fft.rfftfreq(len(sig), d=1/fs)
    fft_vals = np.abs(np.fft.rfft(sig))

    lower_bound = 10 / 60
    upper_bound = 25 / 60
    band_indices = (freqs >= lower_bound) & (freqs <= upper_bound)
    band_energy = np.sum(fft_vals[band_indices]**2)
    total_energy = np.sum(fft_vals**2)
    quality = band_energy / total_energy if total_energy > 0 else 0
    return quality

def find_target_bin(rp, fs=200):
    """
    Finds the best bin and channel with the highest signal quality.

    Args:
        rp (numpy.ndarray): Multi-channel range profile data.
        fs (int): Sampling rate, default is 200 Hz.

    Returns:
        tuple: Best bin index and channel index.
    """

    best_quality_bin = -1
    best_bin_idx = -1
    # ============================================================================================================================
    # removed, too slow
    # chan_idx_for_find_bin = 0
    # for bin_idx in range(rp.shape[1]):
    #     phase = extract_phase(rp, channel_idx=chan_idx_for_find_bin, bin_idx=bin_idx)
    #     quality = estimate_quality(phase, fs)

    #     if quality > best_quality_bin:
    #         best_quality_bin = quality
    #         best_bin_idx = bin_idx

    # best_quality_channel = -1
    # best_channel_idx = -1

    # for channel_idx in range(rp.shape[0]):
    #     phase = extract_phase(rp, channel_idx=channel_idx, bin_idx=best_bin_idx)
    #     quality = estimate_quality(phase, fs)

    #     if quality > best_quality_channel:
    #         best_quality_channel = quality
    #         best_channel_idx = channel_idx
    # ============================================================================================================================
    
    # average multi channel. 
    fused_rp = np.mean(rp, axis=0)

    # find bin with max abs variance.
    amplitude_variances = np.var(np.abs(fused_rp), axis=1)
    
    max_variance_index = np.argmax(amplitude_variances)
    max_variance_value = amplitude_variances[max_variance_index]


    return max_variance_index

def extract_phase(range_profile, channel_idx, bin_idx):
    """
    Extracts the unwrapped phase signal from a specified channel and bin.
    if channel_idx == -1, average all channel signals for phase extraction. 

    Args:
        range_profile (numpy.ndarray): Multi-channel range profile data.
        channel_idx (int): Channel index.
        bin_idx (int): Bin index.

    Returns:
        numpy.ndarray: Phase signal.
    """
    if channel_idx == -1:
        complex_signal = np.mean(range_profile, axis=0)
        complex_signal = complex_signal[bin_idx, :]
    else:
        complex_signal = range_profile[channel_idx, bin_idx, :]
    phase = np.unwrap(np.angle(complex_signal))
    return phase

def get_range_profile(fftData):
    """
    Converts raw FFT data into range profiles without multi-channel fusion.

    Args:
        fftData (list[list[list]]): Complex FFT data.

    Returns:
        numpy.ndarray: Range profiles with shape (channels, bins, samples).
    """
    fftData_np = np.array(fftData, dtype=np.complex128)

    if fftData_np.shape != (1000, 8, 10):
        raise ValueError(f"Input fftData shape is invalid: {fftData_np.shape}. Expected (1000, 8, 10).")

    range_profiles = np.transpose(fftData_np, (1, 2, 0))
    return range_profiles

def list_to_string(lst):
    # 如果输入是 NumPy 数组，先将其转换为普通列表
    if isinstance(lst, np.ndarray):
        lst = lst.tolist()
        lst = [int(ibi) for ibi in lst]
    # 如果列表为空，直接返回空字符串
    if not lst:
        return ''
    # 将列表中的数字转换为字符串，并用逗号连接
    return ','.join(map(str, lst))

def save_fftData(file_path, new_data):

    # 加载现有的npy文件
    try:
        existing_data = np.load(file_path)
    except FileNotFoundError:
        existing_data = np.array([])  # 如果文件不存在，初始化为空数组

    # 检查现有数据和新数据的形状是否兼容
    if existing_data.size == 0:
        updated_data = new_data
    else:
        updated_data = np.concatenate((existing_data, new_data), axis=0)

    # 保存更新后的数据
    np.save(file_path, updated_data)


def calculate_heart_rate(fftData):
    """
    Main function: Processes heart rate data and outputs results as a dictionary.

    Args:
        fftData (list[list[list]]): Complex FFT data.

    Returns:
        dict: A dictionary containing the status, heart rate, and HRV metrics.
    """
    try:
        # save_fftData(file_path = "rpdata.npy", new_data = fftData)

        # a = time.time()
        fs=200
        

        # Generate range profiles
        rp = get_range_profile(fftData)

        # Find the target bin in Channel 0 based on max energy
        max_idx = 0
        max_val = 0
        # fftData shape: (samples, channels, bins)
        for i in range(fftData.shape[-1]):
            tmp_val = np.sum(np.abs(fftData[:, 0, i]))
            if max_val < tmp_val:
                max_idx = i
                max_val = tmp_val
        
        target_bin_idx = max_idx
        
        # Extract phase from Channel 0, Max Bin
        phase = np.unwrap(np.angle(fftData[:, 0, target_bin_idx]))

        # Apply the double differentiator filter to the phase signal
        data_ans = differentiator_filter_double(phase, 0.005)

        st_idx = (np.abs(data_ans) > 1500).nonzero()
        data_ans[st_idx] = 0

        # Initialize the heart rate processor
        processor = HeartRateProcessor(data_ans)    # data_ans是差分滤波
        try:
            processor.preprocess()
        except Exception as e:
            print('preprocess error.')
            print(e)
        
        # Calculate heart rate
        try:
            fs_jz = 1 / 206
            processor.calculate_heart_rate(threshold=0.10, sampling_interval = fs_jz)
        except Exception as e:
            print('心率计算报错')
            print(e)
        # Calculate HRV metrics
        try:
            mean_rr, sum_square_rr, N = processor.calculate_hrv(fs)
        except Exception as e:
            print('hrv计算报错')
            print(e)

        try:
            ibi_data = list_to_string(processor.ibi_list)
        except Exception as e:
            print(111)

        if processor.status == 'failed':
            mean_rr = 0
            sum_square_rr = 0
            N = 0
            ibi_data = ''
        
        # Compile results into a dictionary
        results = {
            "status": processor.status,
            "heart_rate": processor.current_hr,
            "num_RR_interval": N,
            "mean_RR_interval": mean_rr,
            "sum_square_RR": sum_square_rr,
            "ibi_data": ibi_data,
            "ibi_list": processor.ibi_list,
            "filtered_waveform": processor.norm_node,
            "max_bin": target_bin_idx
        }
        # print(time.time() - a)
        return results
    except Exception as e:
        print('hr报错：')
        print(e)

# data = np.load('../tmp.npy')
# print(calculate_heart_rate(data))

# def calculate_heart_rate(fftData):
#         results = {
#             "status": 'succeeded',
#             "heart_rate": 60,
#             "num_RR_interval": 5,
#             "mean_RR_interval": 0.8,
#             "sum_square_RR": 1.2,
#             "ibi_data": [800, 750, 600, 780]
#         }
#         # print(time.time() - a)
#         return results
