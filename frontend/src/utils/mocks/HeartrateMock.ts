import { da } from "element-plus/es/locales.mjs"

export const generateHeartRateMockData = () => {
  const mockHeartRateData: number[] = []
  const mockTimeStamps: number[] = []
  const now = Math.floor(Date.now() / 1000)
  
  // 生成30个数据点，每10秒一个点（5分钟数据）
  for (let i = 0; i < 30; i++) {
    const timestamp = now - (29 - i) * 10 // 10秒间隔
    mockTimeStamps.push(timestamp)
    
    // 模拟心率数据：正常范围60-100 bpm，有自然波动
    const baseHeartRate = 75 // 基础心率
    const timeVariation = Math.sin(i * 0.1) * 8 // 时间趋势波动
    const randomVariation = (Math.random() - 0.5) * 12 // 随机波动
    const activitySpike = i > 15 && i < 20 ? 15 : 0 // 模拟活动峰值
    
    const heartRateValue = baseHeartRate + timeVariation + randomVariation + activitySpike
    const clampedValue = Math.max(50, Math.min(120, heartRateValue))
    
    // 偶尔插入异常值模拟检测失败
    const shouldBeInvalid = Math.random() < 0.10 // 10%概率
    mockHeartRateData.push(shouldBeInvalid ? 10 : Math.round(clampedValue))
  }
  
  return {
    data: {
      heart_waveform: mockHeartRateData,
      time_stamp: mockTimeStamps,
      is_in_bed: true
    }
  }
}