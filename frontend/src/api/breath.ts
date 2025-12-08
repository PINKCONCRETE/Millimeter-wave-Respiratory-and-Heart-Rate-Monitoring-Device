import httpClient, { type ApiResponse } from '@/utils/request'

// 定义接口返回数据类型
interface WaveformData {
  uid: string;
  breath_waveform: number[];
  is_in_bed: boolean;
}

interface RingData {
  uid: string;
  breath_ring_x: number[];
  breath_ring_y: number[];
}

interface WarningData {
  uid: string;
  breath_warning_id: number;
}

/**
 * 获取呼吸波形数据
 * @param id 用户ID
 * @returns Promise 包含波形数据的响应
 */
export function getBWaveform(id: string): Promise<ApiResponse<WaveformData>> {
  return httpClient.get<WaveformData>(`/br/getWaveform/uid/${id}`);
}

/**
 * 获取呼吸环形图数据
 * @param id 用户ID
 * @returns Promise 包含环形图数据的响应
 */
export function getBRingform(id: string): Promise<ApiResponse<RingData>> {
  return httpClient.get<RingData>(`/br/getRing/uid/${id}`);
}

/**
 * 获取呼吸警告信息
 * @param id 用户ID
 * @returns Promise 包含警告信息的响应
 */
export function getWarning(id: string): Promise<ApiResponse<WarningData>> {
  return httpClient.get<WarningData>(`/br/getWarning/uid/${id}`);
}