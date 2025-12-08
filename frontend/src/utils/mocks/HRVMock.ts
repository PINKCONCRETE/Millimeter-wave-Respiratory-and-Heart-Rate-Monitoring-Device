
// 生成模拟数据的函数
export const generateMockData = () => {
  const mockData: (number | null)[] = []
  const mockTimestamps: number[] = []
  const now = Math.floor(Date.now() / 1000)
  
  // 生成10分钟的数据，每30秒一个点（20个数据点）
  for (let i = 0; i < 20; i++) {
    const timestamp = now - (19 - i) * 30 // 30秒间隔
    mockTimestamps.push(timestamp)
    
    // 模拟HRV数据：正常范围50-120ms，有一些波动
    const baseValue = 75 // 基础值
    const variation = Math.sin(i * 0.3) * 20 + Math.random() * 15 - 7.5
    const hrvValue = Math.max(20, Math.min(150, baseValue + variation))
    
    // 偶尔插入null值模拟数据缺失
    mockData.push(Math.random() > 0.05 ? Math.round(hrvValue) : null)
  }
  
  return { mockData, mockTimestamps }
}

