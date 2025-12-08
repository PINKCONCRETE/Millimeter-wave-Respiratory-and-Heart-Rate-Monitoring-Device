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
          <h3 class="section-title">心律失常监测</h3>
        </div>
        <div class="status-text" :class="statusClass">
          <span class="status-text-label">心律状态: </span><span class="status-text-content">{{ statusText }}</span>
        </div>
      </div>
      <div v-if="isExpanded" ref="chartRef" class="chart-container"></div>
    </div>
  </div>
</template>

<script setup lang="ts" name="HeartbeatMonitor">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getWaveform } from '@/api/heart'
import { calculateEchartsFontSize, calculateEchartsLineWidth } from '@/utils/echarts'

// 路由信息
const route = useRoute()
const userId = computed(() => route.params.userId as string)

// 状态定义
const isExpanded = ref(true)
const tooltip = ref('这是心律')
const status = ref(1)
const chartRef = ref<HTMLElement | null>(null)
const intervalId = ref<number | null>(null)
const currentIndex = ref(0)
const nodeText = ref('常见的窦性心律失常')
const chartData = ref<number[]>([])
const isInBed = ref<boolean | null>(null)



let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null
var displayData = [] as number[]
// 计算属性
const statusText = computed(() => {
  if (isInBed.value === false) {
    return '已离开'
  }
  if (status.value === -1) {
    return '脏数据'
  }
  return `${status.value === 0 ? '正常' : '不正常'}`
})

const statusClass = computed(() => {
  if (isInBed.value === false) {
    return 'status-out-of-bed'
  }
  if (status.value === -1) {
    return 'status-dirty'
  }
  return status.value === 0 ? 'status-normal' : 'status-abnormal'
})

// 图表配置函数
const getChartOption = () => {
  const fontSize = calculateEchartsFontSize(chartRef.value, 1) // 获取字体大小
  const lineWidth = calculateEchartsLineWidth(chartRef.value, 1) // 获取线宽
  const mainLineColor = status.value === -1 ? '#808080' : (status.value === 0 ? '#4CAF50' : '#FF0000')
  return {
    tooltip: {
      trigger: 'axis'
    },
    grid: {
      left: '2%',     // 左边距
      right: '12%',    // 右边距
      top: '2%',     // 上边距
      bottom: '10%',  // 下边距
      containLabel: true  // 自动调整以包含标签
    },
    xAxis: {
      show: true,
      position: 'bottom',
      type: 'category',
      data: Array.from({ length: 1000 + 1 }, (_, index) => index),
      axisLabel: {
        formatter: (value: number) => {
          if (value % 200 === 0) {
            return `${value / 200}s`
          }
          return ''
        },
        interval: 199,
        fontSize: fontSize,  // 设置X轴标签字体大小
        fontWeight: 'normal',  // 字体粗细
        color: '#666'  // 字体颜色
      },
      axisTick: {
        show: true,
        interval: (index: number) => {
          return index % 200 === 0 ? 1 : 0
        }
      },
      axisLine: {
        show: true
      },
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: !isInBed.value ? [] : [{
      type: 'line',
      data: displayData,
      // animationDuration: 5000,
      // animationEasing: 'linear',
      animation: false,
      lineStyle: {
        color: mainLineColor,
        width: lineWidth,
        shadowBlur: Math.max(3, lineWidth * 0.8),
        shadowColor: mainLineColor + '40',
        shadowOffsetX: Math.max(1, lineWidth * 0.1),
        shadowOffsetY: Math.max(1, lineWidth * 0.1),
      },
    }]
  }
}

// 更新图表数据
const dataQueue = ref<number[]>([])
const dataFetchingLoop = async () => {
  try {
    const res = await getWaveform(userId.value)
    console.log("HeartbeatMonitor waveform data:", res);
    if (res?.data) {
      const min = Math.min(...res.data.scg_waveform)
      const newWaveform = res.data.scg_waveform.map(item => item - min)
      dataQueue.value.push(...newWaveform)
      status.value = res.data.isArrhythmia
      isInBed.value = res.data.is_in_bed
    }
  } catch (error) {
    console.error('Error fetching heart rate data:', error)
  }
}

const dataProcessingLoop = () => {
  if (dataQueue.value.length >= 8) {
    const dataPoints = dataQueue.value.splice(0, 8)
    displayData.push(...dataPoints)
    if (displayData.length > 1000) {
      displayData = []
    }
    if (chart) {
      chart.clear()
      chart.setOption(getChartOption())
    }
  }
}

// 启动定时更新
const startUpdatingChart = () => {
  intervalId.value = window.setInterval(dataFetchingLoop, 1000)
  window.setInterval(dataProcessingLoop, 40) // 25Hz
}

// 调整图表大小
const resizeChart = () => {
  if (chart) {
    chart.resize()
  }
}

const toggle = () => {
  isExpanded.value = !isExpanded.value
}

// 初始化图表
const initChart = async () => {
  if (chartRef.value && isExpanded.value) {
    if (chart) {
      chart.dispose()
    }
    chart = echarts.init(chartRef.value)
    
    // 设置 ResizeObserver
    if (resizeObserver) {
      resizeObserver.disconnect()
    }
    resizeObserver = new ResizeObserver(() => {
      resizeChart()
    })
    resizeObserver.observe(chartRef.value)
    
    // 更新图表数据
    if (chartData.value.length > 0) {
      chart.setOption(getChartOption())
    }
  }
}

// 监听展开状态变化
watch(isExpanded, async (newVal) => {
  if (newVal) {
    // 展开时需要等待 DOM 更新完成
    await nextTick()
    await initChart()
  } else {
    // 收起时清理图表实例
    if (chart) {
      chart.dispose()
      chart = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
    }
  }
}, { immediate: true }) // 组件挂载时立即执行一次


// 生命周期钩子
onMounted(async () => {
  await dataFetchingLoop()
  startUpdatingChart()
  
  // 图表初始化由 watch 统一处理
})

onBeforeUnmount(() => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
  
  if (chart) {
    chart.dispose()
    chart = null
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
.status-out-of-bed {
  color: #FFA500;
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
  .chart-title-group {
    gap: 0.2em;
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