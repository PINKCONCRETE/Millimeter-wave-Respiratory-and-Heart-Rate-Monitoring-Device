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
          <h2 class="section-title">
            心率变异性 (HRV)
            <div class="info-icon-container" 
                 @mouseover="showHRVInfo = true" 
                 @mouseleave="showHRVInfo = false">
              <div class="info-icon"
                   @touchstart="toggleHRVInfo"
                   @click="toggleHRVInfo">
                <span style="font-size: 0.8em;">i</span>
              </div>
            </div>
          </h2>
        </div>
        <div class="status-text">
          <span class="status-text-label">当前HRV值: </span><span class="status-text-content">{{ stressValue }}</span>
        </div>
      </div>
      <div v-if="isExpanded" ref="chartRef" class="chart-container"></div>
      <!-- 提示框在容器内悬浮显示，不挤压图表 -->
      <div v-if="showHRVInfo" class="sdnn-info-box" 
           @click.stop
           @mouseover="showHRVInfo = true"
           @mouseleave="showHRVInfo = false">
        <div class="close-btn" @click="showHRVInfo = false">×</div>
        <h2>HRV是指心跳间隔（RR间期）的微小波动</h2>
        <h3>SDNN（标准差）：</h3>
        <p>单位为毫秒（ms），表示RR间期(心跳间隔)的标准差。</p>
        <h4>SDNN参考范围:</h4>
        <ul>
          <li><strong>高水平（> 100 ms）：</strong> 良好的心血管健康</li>
          <li><strong>中等水平（50–100 ms）：</strong> 正常范围</li>
          <li><strong>低水平（< 50 ms）：</strong> 潜在健康风险</li>
        </ul>
      </div>
    </div>
  </div>
</template>


<script setup lang="ts" name="HRVMonitor">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getHrvData } from '@/api/history'
import { convertTimestampToTimeHM } from '@/utils/timestamp'
import { calculateEchartsFontSize, calculateEchartsLineWidth } from '@/utils/echarts'
import { generateMockData } from '@/utils/mocks/HRVMock'
// 使用本地时区格式化时间
import { formatTimestampToLocalDateTime } from '@/utils/timestamp'

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
const showHRVInfo = ref(false)
const stressValue = ref('0')
const chartRef = ref<HTMLElement | null>(null)
const intervalId = ref<number | null>(null)
const chartData = ref<(number | null)[]>([])
const timeStamps = ref<number[]>([])

let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

// 折叠按钮切换
const toggle = () => {
  isExpanded.value = !isExpanded.value
}

// 切换HRV信息显示状态
const toggleHRVInfo = () => {
  showHRVInfo.value = !showHRVInfo.value
}

// 使用模拟数据的函数
const useMockData = () => {
  const { mockData, mockTimestamps } = generateMockData()
  
  chartData.value = mockData
  timeStamps.value = mockTimestamps
  // 模拟在床状态已由父组件 props 提供
  
  // 设置当前HRV值
  const lastValidValue = [...mockData].reverse().find(v => v !== null)
  stressValue.value = lastValidValue == null ? '/' : lastValidValue.toString()
  
  if (chart) {
    chart.clear()
    chart.setOption(getChartOption(mockData, mockTimestamps.map(convertTimestampToTimeHM)))
  }
}


// 更新图表数据
const updateChart = async () => {
  try {
    const now = Math.floor(Date.now() / 1000)
    const tenMinAgo = now - 10 * 60
    const endTime = now
    const startTime = tenMinAgo

    const res = await getHrvData({
      uid: userId.value,
      start_time: formatTimestampToLocalDateTime(startTime),
      end_time: formatTimestampToLocalDateTime(endTime),
    })
    if (res?.code === 20000 && res.data) {
      chartData.value = res.data.hrv_data.map((v: number) => v === -1 ? null : v)
      timeStamps.value = res.data.time_stamp

      // HRV值显示
      const lastValidValue = [...chartData.value].reverse().find(v => v !== null)
      stressValue.value = lastValidValue == null ? '/' : Math.round(lastValidValue).toString()

      if (chart) {
        chart.clear()
        chart.setOption(getChartOption(chartData.value, timeStamps.value.map(convertTimestampToTimeHM)))
      }
    }
  } catch (error) {
    console.error('Error updating HRV chart:', error)
  }
}

// 图表配置函数
const getChartOption = (displayData: (number | null)[], xAxisData: string[]) => {
  const fontSize = calculateEchartsFontSize(chartRef.value, 0.9) // 获取字体大小
  const lineWidth = calculateEchartsLineWidth(chartRef.value, 0.8) // 获取线宽
  const mainLineColor = 'rgb(139, 92, 246)'

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
      type: 'category',
      data: xAxisData,
      splitLine: {
        show: false
      },
      axisLabel: {
        show: true,
        interval: Math.floor(chartData.value.length / 5),
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
      name: 'SDNN(ms)',
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
    series: props.isInBed ? [{
      name: 'HRV',
      type: 'line',
      data: displayData,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: mainLineColor,
        width: lineWidth,
        shadowBlur: Math.max(3, lineWidth * 0.8),
        shadowColor: mainLineColor + '40',
        shadowOffsetX: Math.max(1, lineWidth * 0.1),
        shadowOffsetY: Math.max(1, lineWidth * 0.1),        
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(139, 92, 246, 0.6)' },
            { offset: 1, color: 'rgba(139, 92, 246, 0)' }
          ]
        }
      },
      itemStyle: {
        color: '#8B5CF6'
      }
    }] : []
  }
}

// 启动定时更新
const startUpdatingChart = () => {
  intervalId.value = window.setInterval(() => {
    updateChart()
    // useMockData() // 使用模拟数据
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
        chart.setOption(getChartOption(chartData.value, timeStamps.value.map(convertTimestampToTimeHM)))
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
  await updateChart()
  // useMockData() // 使用模拟数据

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
  position: relative; /* 添加相对定位作为参考点 */
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
  position: relative; /* 添加相对定位，作为绝对定位的参考 */
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

/* 标题区 */
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
.status-text-content {
  color: #8B5CF6;
  margin-left: 0.25em;
}
.status-text-label {
  color: #2c3e50c4;
  margin-right: 0.1em;
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

/* 小提示图标容器 */
.info-icon-container {
  position: relative;
  display: inline-flex;
  align-items: center;
  margin-left: 0.3em;
}

/* 小提示图标 */
.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1em;
  height: 1em;
  border-radius: 50%;
  background-color: #8B5CF6;
  color: #fff;
  font-size: 0.8em;
  cursor: pointer;
  transition: background-color 0.2s;
}

.info-icon:hover {
  background-color: #7c3aed;
}

/* 提示气泡 */
.tooltip {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 10;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 0.75em 1em;
  border-radius: 0.375em;
  max-width: 21.875em;
  font-size: 0.9em;
  line-height: 1.5;
  box-shadow: 0 0.25em 0.75em rgba(0, 0, 0, 0.15);
}

/* SDNN 信息块 */
.sdnn-info-box {
  position: absolute;        /* 绝对定位，相对于 monitor-container */
  top: 50%;                 /* 垂直居中 */
  left: 50%;                /* 水平居中 */
  transform: translate(-50%, -50%); /* 精确居中 */
  z-index: 100;
  box-shadow: 0 0.5em 1.5em rgba(0, 0, 0, 0.25);
  background: #f8f9fa;
  padding: 1em;
  border-radius: 0.5em;
  border-left: 0.25em solid #8B5CF6;
  max-width: 90%;           /* 相对于容器的宽度 */
  max-height: 80%;          /* 相对于容器的高度 */
  overflow-y: auto;         /* 内容过多时滚动 */
}

/* 关闭按钮 */
.close-btn {
  position: absolute;
  top: 0.5em;
  right: 0.5em;
  width: 1.5em;
  height: 1.5em;
  border-radius: 50%;
  background: #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.2em;
  color: #6b7280;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background: #d1d5db;
  color: #374151;
}

.sdnn-info-box h2 {
  font-size: 1.1em;
  margin: 0 0 0.5em 0;
  color: #2c3e50;
}

.sdnn-info-box h3 {
  font-size: 1em;
  margin: 0.5em 0 0.3em 0;
  color: #4b5563;
}

.sdnn-info-box h4 {
  font-size: 0.9em;
  margin: 0.3em 0 0.2em 0;
  color: #4b5563;
}

.sdnn-info-box p {
  font-size: 0.85em;
  margin: 0.2em 0 0.5em 0;
  color: #6b7280;
  line-height: 1.4;
}

.sdnn-info-box ul {
  padding-left: 1.25em;
  margin: 0.3em 0;
}

.sdnn-info-box li {
  font-size: 0.8em;
  margin-bottom: 0.25em;
  color: #6b7280;
  line-height: 1.3;
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
  
  .sdnn-info-box {
    padding: 0.8em;
    max-width: 85%;
  }
  
  .sdnn-info-box h2 {
    font-size: 1em;
  }
  
  .sdnn-info-box h3 {
    font-size: 0.9em;
  }
  
  .sdnn-info-box h4 {
    font-size: 0.8em;
  }
  
  .sdnn-info-box p {
    font-size: 0.75em;
  }
  
  .sdnn-info-box li {
    font-size: 0.7em;
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
  
  .sdnn-info-box {
    padding: 0.6em;
    max-width: 95%;
    max-height: 70%;
  }
  
  .sdnn-info-box h2 {
    font-size: 0.9em;
    margin-bottom: 0.4em;
  }
  
  .sdnn-info-box h3 {
    font-size: 0.8em;
    margin: 0.4em 0 0.2em 0;
  }
  
  .sdnn-info-box h4 {
    font-size: 0.75em;
    margin: 0.2em 0 0.1em 0;
  }
  
  .sdnn-info-box p {
    font-size: 0.7em;
    margin: 0.1em 0 0.3em 0;
  }
  
  .sdnn-info-box ul {
    margin: 0.2em 0;
    padding-left: 1em;
  }
  
  .sdnn-info-box li {
    font-size: 0.65em;
    margin-bottom: 0.2em;
    line-height: 1.2;
  }
  
  .close-btn {
    width: 1.2em;
    height: 1.2em;
    font-size: 1em;
  }
  
  .chart-note {
    font-size: 0.6em;
    padding: 0.2em;
  }
  .heart-status-icon {
    width: 0.4em;
    height: 0.4em;
  }
  .heart-status-text {
    font-size: 0.6em;
    padding: 0.2em 0.4em;
    margin-left: 0.2em;
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
  
  .chart-note {
    margin-top: 0.2em;
    padding: 0.2em;
  }
  
  .sdnn-info-box {
    padding: 0.5em;
    max-width: 95%;
    max-height: 60%;
  }
  
  .sdnn-info-box h2 {
    font-size: 0.8em;
    margin-bottom: 0.3em;
  }
  
  .sdnn-info-box h3 {
    font-size: 0.7em;
    margin: 0.3em 0 0.1em 0;
  }
  
  .sdnn-info-box h4 {
    font-size: 0.65em;
    margin: 0.1em 0;
  }
  
  .sdnn-info-box p {
    font-size: 0.6em;
    margin: 0.1em 0 0.2em 0;
  }
  
  .sdnn-info-box ul {
    margin: 0.1em 0;
    padding-left: 0.8em;
  }
  
  .sdnn-info-box li {
    font-size: 0.55em;
    margin-bottom: 0.1em;
    line-height: 1.1;
  }
  
  .close-btn {
    width: 1em;
    height: 1em;
    font-size: 0.9em;
    top: 0.3em;
    right: 0.3em;
  }
}

</style>
