import httpClient, { type ApiResponse } from '@/utils/request'

// 定义接口类型
interface HistoryParams {
  uid: string;
  start_time: string;
  end_time: string;
}

// 呼吸数据接口
interface BrData {
  uid: string;
  data: {
    timestamp: string;
    respiratory_rate: number;
  }[];
}

// 呼吸指数数据接口
interface BrIndexData {
  uid: string;
  br_index: number;
  date: string;
}

// 心率数据接口
interface HeartData {
  uid: string;
  data: {
    timestamp: string;
    heart_rate: number;
  }[];
}

// HRV数据接口
interface HrvData {
  uid: string;
  is_in_bed: boolean;
  time_stamp: number[];
  hrv_data: number[];
}

// 心率统计数据接口
interface HeartStatData {
  uid: string;
  avg_heart_rate: number;
  max_heart_rate: number;
  min_heart_rate: number;
  date: string;
}

// 心律失常统计数据接口
interface ArrCountListData {
  uid: string;
  arr_counts: {
    date: string;
    count: number;
  }[];
  total_count: number;
}


/**
 * 获取呼吸数据
 * @param params - 请求参数
 * @returns Promise 包含呼吸数据的响应
 */
export function getBrData(params: HistoryParams): Promise<ApiResponse<BrData>> {
  return httpClient.post<BrData>('/history/br/getBrData', params);
}

/**
 * 获取呼吸指数
 * @param params - 请求参数
 * @returns Promise 包含呼吸指数的响应
 */
export function getBrindex(params: HistoryParams): Promise<ApiResponse<BrIndexData>> {
  return httpClient.post<BrIndexData>('/history/br/index', params);
}

/**
 * 获取心率数据
 * @param params - 请求参数
 * @returns Promise 包含心率数据的响应
 */
export function getHeartData(params: HistoryParams): Promise<ApiResponse<HeartData>> {
  return httpClient.post<HeartData>('/history/hr/getHeartData', params);
}

/**
 * 获取HRV数据
 * @param params - 请求参数
 * @returns Promise 包含HRV数据的响应
 */
export function getHrvData(params: HistoryParams): Promise<ApiResponse<HrvData>> {
  return httpClient.post<HrvData>('/history/hr/getHrvData', params);
}

/**
 * 获取心率统计数据
 * @param params - 请求参数
 * @returns Promise 包含心率统计数据的响应
 */
export function getstat(params: HistoryParams): Promise<ApiResponse<HeartStatData>> {
  return httpClient.post<HeartStatData>('/history/hr/stat', params);
}

/**
 * 获取心律失常统计列表
 * @param params - 请求参数
 * @returns Promise 包含心律失常统计列表的响应
 */
export function getarr_count_list(params: HistoryParams): Promise<ApiResponse<ArrCountListData>> {
  return httpClient.post<ArrCountListData>('/history/arr/arr_count_list', params);
}