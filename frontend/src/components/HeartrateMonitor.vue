<template>
  <div class="root-container" :class="{ expanded: isExpanded, collapsed: !isExpanded }">
    <div class="monitor-container" :class="{ expanded: isExpanded, collapsed: !isExpanded }">
      <div class="chart-header">
        <div class="chart-title-group">
          <div @click="toggle" class="toggle-btn">
            <svg
              :class="['triangle-icon', isExpanded ? 'triangle-down' : 'triangle-right']"
              width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"
            >
              <polygon points="5,4 11,4 8,10" :fill="isExpanded ? '#666' : '#666'" style="stroke:none;" />
            </svg>
          </div>
          <h3 class="section-title">心率监测</h3>
        </div>
        <div class="status-text" :class="statusClass">
          <span class="status-text-label">心跳次数: </span>{{ heartRateText }}
        </div>
      </div>
      <div v-if="isExpanded" ref="chartRef" class="chart-container"></div>
    </div>
  </div>
</template>


<script setup lang="ts" name="HeartrateMonitor">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getHrWaveform } from '@/api/heart'
import { convertTimestampToTimeHM } from '@/utils/timestamp'
import { calculateEchartsFontSize, calculateEchartsLineWidth } from '@/utils/echarts'
import { generateHeartRateMockData } from '@/utils/mocks/HeartrateMock'

// Props 定义
const props = defineProps<{
  userId?: string
  isInBed: boolean
}>()

// 路由信息
const route = useRoute()
const userId = computed(() => props.userId || route.params.userId as string)

// 状态定义
const isExpanded = ref(true)
const tooltip = ref('每秒心脏跳动的次数， 60-100为正常')
const heartRate = ref(1)
const chartRef = ref<HTMLElement | null>(null)
const chartData = ref<(number | null)[]>([])
const timeStamps = ref<number[]>([])
const intervalId = ref<number | null>(null)
// 折叠按钮切换
const toggle = () => {
  isExpanded.value = !isExpanded.value
}

let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

// 计算属性
const statusClass = computed(() => {
  return {
    'status-normal': heartRate.value <= 100 && heartRate.value >= 60,
    'status-abnormal': heartRate.value > 100 || heartRate.value < 60,
    'status-dirty': heartRate.value === -1 || heartRate.value === -2,
  }
})
const heartRateText = computed(() => {
  if (heartRate.value !== -1 && heartRate.value !== -2) {
    return `${heartRate.value} 次/分钟`
  }
  return '未检测到心跳'
})

// 更新图表数据，只显示当前时间到前10000秒区间
const updateChart = async () => {
  try {
    const res = await getHrWaveform(userId.value)
    if (!res?.data) return

    const heartWaveformTmp = res.data.heart_waveform
    const timeStampTmp = res.data.time_stamp
    console.log('Fetched heart waveform data:', heartWaveformTmp)
    console.log('Fetched time stamp data:', timeStampTmp)
    // 如果离床，清空图表数据并更新图表
    if (!props.isInBed) {
      chartData.value = []
      timeStamps.value = []
      heartRate.value = -1
      if (chart) {
        chart.clear()
        chart.setOption(getChartOption([], []))
      }
      return
    }

    // 1. 计算时间区间
    const now = Math.floor(Date.now() / 1000)
    const startTime = now - 10000
    const endTime = now
    // 只保留在区间内的点，并四舍五入到秒
    const filtered: { t: number, v: number }[] = []
    for (let i = 0; i < timeStampTmp.length; i++) {
      const t = Math.round(timeStampTmp[i])
      if (t >= startTime && t <= endTime) {
        filtered.push({ t, v: heartWaveformTmp[i] })
      }
    }
    // 横轴为实际采样点时间，纵轴为实际心率
    const xAxisData: (string|null)[] = []
    const displayData: (number|null)[] = []
    for (let i = 0; i < filtered.length; i++) {
      const cur = filtered[i]
      const prev = filtered[i - 1]
      // 判断与前一个点的时间间隔
      if (i > 0 && cur.t - prev.t > 7.5) {
        // 插入null断线
        xAxisData.push(null)
        displayData.push(null)
      }
      xAxisData.push(convertTimestampToTimeHM(cur.t))
      displayData.push((cur.v === -1 || cur.v === -2) ? null : cur.v)
    }

    // 4. 计算最新心率
    let lastValid = null
    for (let i = displayData.length - 1; i >= 0; i--) {
      if (displayData[i] !== null) {
        lastValid = displayData[i]
        break
      }
    }
    heartRate.value = lastValid !== null ? lastValid : -1

    chartData.value = displayData
    timeStamps.value = filtered.map(item => item.t)

    if (chart) {
      chart.clear()
      chart.setOption(getChartOption(displayData, xAxisData))
    }
  } catch (error) {
    console.error('Error fetching latest heart rate data:', error)
  }
}

// 获取图表选项
const getChartOption = (displayData: (number | null)[], xAxisData: string[]) => {
  const fontSize = calculateEchartsFontSize(chartRef.value, 0.9) // 获取字体大小
  const lineWidth = calculateEchartsLineWidth(chartRef.value, 0.8) // 获取线宽
  const mainLineColor = 'rgb(255,68,68)'

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0,0,0,0.7)',
      textStyle: { color: '#fff' },
      borderColor: 'rgba(255,255,255,0.2)'
    },
    grid: {
      left: '5%',     // 左边距
      right: '5%',    // 右边距
      top: '20%',     // 上边距
      bottom: '5%',  // 下边距
      containLabel: true  // 自动调整以包含标签
    },
    xAxis: {
      show: true,
      position: 'bottom',
      type: 'category',
      data: xAxisData,
      axisLabel: {
        show: true,
        interval: Math.floor(xAxisData.length / 5),
        textStyle: {
          color: '#666',
          fontSize: fontSize
        }
      },
      axisTick: {
        alignWithLabel: true,
        length: lineWidth*2
      },
      axisLine: {
        lineStyle: {
          color: '#666',
          width: lineWidth*0.5
        }
      },
    },
    yAxis: {
      type: 'value',
      name: 'Bpm',
      min: 0,
      show: true,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#e0e0e0',
          type: 'solid',
          width: lineWidth*0.5,
        }
      },
      axisLine: {
        lineStyle: {
          color: '#666',
          width: lineWidth*0.5
        }
      },
    },
    series: props.isInBed ? [
      {
        name: 'Heart Rate',
        type: 'line',
        showSymbol: false,
        data: displayData,
        connectNulls: false,
        animation: false,
        animationDuration: 5000,
        animationEasing: 'linear',
        lineStyle: {
          color: mainLineColor,
          width: lineWidth,
          shadowBlur: Math.max(3, lineWidth * 0.8),
          shadowColor: mainLineColor + '40',
          shadowOffsetX: Math.max(1, lineWidth * 0.1),
          shadowOffsetY: Math.max(1, lineWidth * 0.1),        
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgb(255, 105, 180)'
            },
            {
              offset: 1,
              color: 'rgb(255, 240, 245)'
            }
          ])
        },
        itemStyle: {
          color: 'rgb(255, 105, 180)'
        }
      }
    ] : []
  }
}

// 启动定时更新
const startUpdatingChart = () => {
  intervalId.value = window.setInterval(() => {
    updateChart()
  }, 5000)
}

// 调整图表大小
const resizeChart = () => {
  if (chart) {
    chart.resize()
  }
}

// 监听展开状态变化
watch(isExpanded, async (newVal) => {
  if (newVal) {
    await nextTick()
    if (chartRef.value) {
      if (chart) chart.dispose()
      chart = echarts.init(chartRef.value)
      if (chartData.value.length > 0) {
        chart.setOption(getChartOption(
          chartData.value.map(rate => rate === -1 || rate === -2 ? null : rate),
          timeStamps.value.map(point => convertTimestampToTimeHM(point))
        ))
      }
      if (resizeObserver) resizeObserver.disconnect()
      resizeObserver = new ResizeObserver(() => {
        resizeChart()
      })
      resizeObserver.observe(chartRef.value)
    }
  } else {
    if (chart) {
      chart.dispose()
      chart = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }
}, { immediate: true })

// 生命周期钩子
onMounted(async () => {
  updateChart() // 使用模拟数据
  startUpdatingChart()
  // 图表初始化由 watch 统一处理
})

onBeforeUnmount(() => {
  if (chart) {
    chart.dispose()
    chart = null
  }
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})
</script>

<style scoped>
/* 根容器：居中 + 灰底 */
.root-container {
  width: 100%;
  /* height: 100vh; */
  height: auto;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f0f4f8;
  font-family: 'Arial', sans-serif;
  /* min-height: 10vh; */
}

/* 白色内容卡片 */
.monitor-container {
  width: 100%;
  height: auto;
  /* height: 100%; */
  background: #fff;
  border-radius: 0.625em;
  box-shadow: 0 0.125em 0.25em rgba(0, 0, 0, 0.1);
  padding: 0.625em;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: 0.625em;
  /* min-height: fit-content; */
}

.root-container.expanded {
  height: 100vh;
  /* height: auto; */
}
.root-container.collapsed {
  height: auto;
}

.monitor-container.expanded {
  height: 100%;
  /* height: auto; */
}
.monitor-container.collapsed {
  height: auto;     /* 跟随内容 */
}

/* 标题区：左边时间信息 + 右边状态 */
.chart-header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 1% 2%;
  /* flex: 2; */
}

.chart-title-group {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex: 1 1 0%;
  min-width: 0;
}

/* 折叠按钮 - 默认隐藏 */
.toggle-btn {
  display: none;
  padding: 0;
  background: none;
  border: none;
  border-radius: 0.25em;
  cursor: pointer;
  font-size: 1em;
  transition: background 0.3s;
  user-select: none;
  align-items: center;
  justify-content: center;
  height: 2em;
  width: 2em;
}

.triangle-icon {
  display: inline-block;
  vertical-align: middle;
  transition: transform 0.2s;
  width: 1em;
  height: 1em;
}
.triangle-down {
  transform: rotate(0deg);
}
.triangle-right {
  transform: rotate(-90deg);
}


.toggle-btn:hover {
  background-color: #e9ecef;
  color: #333;
}

.toggle-btn:active {
  background-color: #dee2e6;
  transform: scale(0.98);
}
.section-title {
  font-size: 1.5em;
  color: #2c3e50;
  letter-spacing: 0.03em;
  margin-bottom: 0;
  margin-top: 1%;
  padding-left: 1%;
  white-space: nowrap;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status-text {
  font-size: 1em;
  font-weight: bold;
  transition: color 0.3s ease;
  background-color: #f8f9fa;
  padding: 1%;
  margin-right: 1vw;
  border-radius: 0.3125em;
  border: #a3a3a3 0.0625em;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}
.status-text-label {
  color: #2c3e50c4;
  margin-right: 0.1em;
}
.status-normal {
  color: #2ecc71;
}
.status-abnormal {
  color: #e74c3c;
}
.status-dirty {
  color: #808080;
}

/* 图表区域 */
.chart-container {
  width: 100%;
  height: 100%;
  flex: 10;
  border-radius: 1.2em;
  overflow: hidden;
  box-shadow: 
    0 0.25em 0.5em rgba(0, 0, 0, 0.1),
    inset 0 0.0625em 0.125em rgba(255, 255, 255, 0.1)
    ;
  transition: all 0.3s ease;
  font-size: 1em;
  padding-bottom: 1vh;
  display: block;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .chart-header {
    margin: 0.5% 1%;
  }
  
  .section-title {
    font-size: 1.2em;
  }
  
  .status-text {
    font-size: 0.8em;
    padding: 0.8%;
  }
}

@media (max-width: 768px) {
  .monitor-container {
    padding: 0.3em;
  }
  /* 只在移动端竖屏时显示折叠按钮 */
  .toggle-btn {
    display: flex;
  }
  .chart-header {
    margin: 0.5% 0;
  }
  .section-title {
    font-size: 1.1em;
  }
  .status-text {
    font-size: 0.8em;
    padding: 0.8% 1%;
    border-radius: 0.25em;
  }
  .status-text-label {
    font-size: 0.8em;
  }
  .chart-container {
    height: 20vh;
    border-radius: 0.8em;
  }
}

/* 横屏专用样式 */
@media screen and (orientation: landscape) and (max-height: 600px) {
  /* 横屏时隐藏折叠按钮 */
  .toggle-btn {
    display: none !important;
  }
  
  .chart-header {
    margin: 0.5% 1%;
  }
  
  .section-title {
    font-size: 1.1em;
  }
  
  .chart-container {
    height: 85vh;
  }
}
</style>