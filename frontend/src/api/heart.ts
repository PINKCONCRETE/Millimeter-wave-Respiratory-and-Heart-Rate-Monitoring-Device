import httpClient, { type ApiResponse } from '@/utils/request'

// 定义接口返回数据类型
interface WaveformData {
  uid: string;
  scg_waveform: number[];
  isArrhythmia: number;
  is_in_bed: boolean;
}

interface HeartRateWaveformData {
  uid: string;
  heart_waveform: number[];
  is_in_bed: boolean;
  time_stamp: number[];
}

interface LatestHeartRateData {
  uid: string;
  timestamp: string;
  heart_rate: number;
}

interface StressData {
  uid: string;
  timestamp: string;
  stress_index: number;
  stress_level: string;
}

interface BrHistoryData {
  uid: string;
  data: {
    timestamp: string;
    respiratory_rate: number;
  }[];
}

/**
 * 获取心律波形数据
 * @param id 用户ID
 * @returns Promise 包含心律波形数据的响应
 */
export function getWaveform(id: string): Promise<ApiResponse<WaveformData>> {
  return httpClient.get<WaveformData>(`/arr/getWaveform/uid/${id}`);
}

/**
 * 获取心率波形数据
 * @param id 用户ID
 * @returns Promise 包含心率波形数据的响应
 */
export function getHrWaveform(id: string): Promise<ApiResponse<HeartRateWaveformData>> {
  return httpClient.get<HeartRateWaveformData>(`/hr/getWaveform/uid/${id}`);
}

/**
 * 获取最新的心率数据
 * @param id 用户ID
 * @returns Promise 包含最新心率数据的响应
 */
export function getLatestHrWave(id: string): Promise<ApiResponse<LatestHeartRateData>> {
  return httpClient.get<LatestHeartRateData>(`/hr/getOneWave/uid/${id}`);
}

/**
 * 获取压力指数数据
 * @param id 用户ID
 * @returns Promise 包含压力指数数据的响应
 */
export function getStress(id: string): Promise<ApiResponse<StressData>> {
  return httpClient.get<StressData>(`/hr/getStress/uid/${id}`);
}

/**
 * 获取历史呼吸数据
 * @param uid 用户ID
 * @param startTime 开始时间
 * @param endTime 结束时间
 * @returns Promise 包含历史呼吸数据的响应
 */
export function postBrData(
  uid: string, 
  startTime: string, 
  endTime: string
): Promise<ApiResponse<BrHistoryData>> {
  return httpClient.post<BrHistoryData>('/history/br/getBrData', {
    uid: uid,
    start_time: startTime,
    end_time: endTime
  });
}