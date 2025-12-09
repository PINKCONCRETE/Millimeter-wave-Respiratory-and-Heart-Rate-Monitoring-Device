<template>
  <div class="root-container" :class="{ expanded: isExpanded, collapsed: !isExpanded }">
    <div class="monitor-container" :class="{ expanded: isExpanded, collapsed: !isExpanded }">
      
      <!-- 状态区 -->
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
          <h3 class="section-title">呼吸监测</h3>
        </div>
        <div class="status-section">
          <!-- 呼吸暂停状态 -->
          <div class="status-item" v-if="isInBed && breathWarningId === 21">
              <img src="/breath_imgs/breath_hold.svg" alt="呼吸暂停" class="status-icon status-active" />
              <h3 class="status-text-active">呼吸暂停</h3>
          </div>

          <!-- 通气阻塞状态 -->
          <div class="status-item" v-if="isInBed && breathWarningId === 22">
              <img src="/breath_imgs/lung.svg" alt="通气阻塞" class="status-icon status-active" />
              <h3 class="status-text-active">通气阻塞</h3>
          </div>

          <!-- 正常状态 -->
          <div class="status-item" v-if="isInBed && breathWarningId === 0">
              <h3 class="status-text-normal">呼吸正常</h3>
          </div>

          <!-- 离床状态 -->
          <div class="status-item" v-if="!isInBed">
            <h3 class="status-text-out-of-bed">已离床</h3>
          </div>
        </div>
      </div>

      <!-- 图表区 -->
      <div v-if="isExpanded" class="charts-section">
        <div class="waveform-container">
          <div class="chart-container">
            <div class="sub-chart-title-container">
              <h3 class="sub-chart-title">呼吸波形</h3>
            </div>
            <div ref="waveformChartRef" class="sub-chart-container" />
          </div>
        </div>

        <div class="ring-container">
          <div class="chart-container">
            <div class="sub-chart-title-container">
              <h3 class="sub-chart-title">流速-容量环</h3>
              <div class="info-icon-ring" @mouseover="showRingInfo = true" @mouseleave="showRingInfo = false">i</div>
              <div v-if="showRingInfo" class="tooltip-ring">
                自主呼吸的流速容量环是测量呼吸功能的图，显示气流速度和容量关系，包括呼气和吸气两部分。
              </div>
            </div>
            <div ref="ringChartRef" class="sub-chart-container" />
          </div>
        </div>
      </div>

      <!-- ...已移除 chart-note 区域... -->
    </div>
  </div>
</template>

<script setup lang="ts" name="BreathMonitor">
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getBWaveform, getBRingform, getWarning } from '@/api/breath'
import { calculateEchartsFontSize, calculateEchartsLineWidth } from '@/utils/echarts'
import { BarChart } from 'echarts/charts'
import { MAX_SAFE_INTEGER } from 'echarts/types/src/util/number.js'
import { log } from 'echarts/types/src/util/log.js'

// 路由信息
const route = useRoute()
const userId = computed(() => route.params.userId as string)

// 状态定义
const isExpanded = ref(true)
const waveformChartRef = ref<HTMLElement | null>(null)
const ringChartRef = ref<HTMLElement | null>(null)
const waveformData = ref<number[]>([])
const ringData = ref<{ breath_ring_x: number[], breath_ring_y: number[] }>({
  breath_ring_x: [],
  breath_ring_y: []
})
const showRingInfo = ref(false)
const showApneaInfo = ref(false)
const showObstructionInfo = ref(false)
const breathWarningId = ref(0)
const isInBed = ref(true)
const intervalId = ref<number | null>(null)
const waveformQueue = ref<number[]>([])
const waveformDisplayData = ref<number[]>([])
const waveformFetchIntervalId = ref<number | null>(null)
const waveformProcessIntervalId = ref<number | null>(null)

const WAVEFORM_SAMPLING_RATE = 200
const WAVEFORM_FETCH_INTERVAL = 1000
const WAVEFORM_FETCH_CHUNK_SIZE = 200
const WAVEFORM_PROCESS_INTERVAL = 40
const WAVEFORM_PROCESS_BATCH = 8
const MAX_WAVEFORM_POINTS = 2000

let last_point = 0
let waveformChart: ECharts | null = null
let ringChart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null
let last_time = 0

// 折叠按钮切换
const toggle = () => {
  isExpanded.value = !isExpanded.value
}

// ...已移除 chart-note 相关逻辑...

// 呼吸波形图表配置函数
const getWaveformChartOption = (displayData: number[], xAxisData?: string[]) => {
  const fontSize = calculateEchartsFontSize(waveformChartRef.value, 0.8)
  const lineWidth = calculateEchartsLineWidth(waveformChartRef.value, 1)
  const containerWidth = waveformChartRef.value ? waveformChartRef.value.clientWidth : 0
  const containerHeight = waveformChartRef.value ? waveformChartRef.value.clientHeight : 0
  const samplingRate = WAVEFORM_SAMPLING_RATE
  const xTickInterval = containerWidth < 250 ? samplingRate * 2 : samplingRate
  const ySplitNumber = containerHeight < 250 ? 3 : 5

  const isMobile = window.innerWidth <= 768
  const xAxisName = isMobile ? '' : '时间(s)'
  const yAxisName = isMobile ? '' : '归一化幅度'

  const resolvedXAxisData = xAxisData && xAxisData.length > 0
    ? xAxisData
    : Array.from({ length: displayData.length }, (_, index) => (index / samplingRate).toFixed(2))

  // ========== 新增：动态计算 Y 轴范围 ==========
  const FIXED_Y_MIN = -10;
  const FIXED_Y_MAX = 10;
  const ADAPTIVE_GAP = 0.05; // 自适应时上下预留 5% 空白

  // 过滤无效数据（NaN/undefined），计算有效数据的极值
  const getValidExtremes = (data: number[]) => {
    const validData = data.filter(item => !isNaN(item) && item !== undefined);
    if (validData.length === 0) {
      return { min: FIXED_Y_MIN, max: FIXED_Y_MAX }; // 无数据时默认固定范围
    }
    return {
      min: Math.min(...validData),
      max: Math.max(...validData)
    };
  };

  // 动态判断：超出 ±10 则自适应，否则固定 ±10
  const { min: dataMin, max: dataMax } = getValidExtremes(displayData);
  const isOutOfFixedRange = dataMax > FIXED_Y_MAX || dataMin < FIXED_Y_MIN;

  let yAxisMin = FIXED_Y_MIN;
  let yAxisMax = FIXED_Y_MAX;

  if (isOutOfFixedRange) {
    // 自适应模式：极值 + 预留空白
    const range = dataMax - dataMin;
    yAxisMin = Math.floor(dataMin - range * ADAPTIVE_GAP);
    yAxisMax = Math.floor(dataMax + range * ADAPTIVE_GAP);
  }
  // ========== 动态范围逻辑结束 ==========

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        animation: false
      },
      backgroundColor: 'rgba(0,0,0,0.7)',
      textStyle: { 
        color: '#fff',
        fontSize: fontSize
      },
      borderColor: 'rgba(255,255,255,0.2)'
    },
    grid: {
      left: '3%',
      right: '10%',
      bottom: '15%',
      top: '25%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      min: 0,
      max: MAX_WAVEFORM_POINTS,
      name: xAxisName,
      nameLocation: 'center',
      nameGap: 25,
      nameTextStyle: {
        color: '#666',
        fontSize: fontSize * 0.8
      },
      data: resolvedXAxisData,
      splitLine: {
        show: false
      },
      axisLabel: {
        show: true,
        formatter: (value: string, index: number) => {
          if (index % xTickInterval === 0) {
            return `${(index / samplingRate).toFixed(0)}`
          }
          return ''
        },
        interval: xTickInterval - 1,
        textStyle: {
          color: '#666',
          fontSize: fontSize
        }
      },
      axisTick: {
        show: true,
        interval: (index: number) => index % xTickInterval === 0,
        alignWithLabel: true,
        length: lineWidth * 2
      },
      axisLine: {
        show: true,
        lineStyle: {
          color: '#666',
          width: lineWidth * 0.5
        }
      },
    },
    yAxis: {
      // 替换原来固定的 min/max，使用动态计算的值
      min: yAxisMin,
      max: yAxisMax,
      type: 'value',
      name: yAxisName,
      nameGap: 8,
      nameTextStyle: {
        color: '#666',
        fontSize: fontSize * 0.9
      },
      show: true,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#e0e0e0',
          type: 'solid',
          width: lineWidth * 0.5
        }
      },
      axisLine: {
        show: true,
        lineStyle: {
          color: '#666',
          width: lineWidth * 0.5
        }
      },
      axisTick: {
        show: true,
        length: lineWidth * 2
      },
      axisLabel: {
        textStyle: {
          color: '#666',
          fontSize: fontSize
        },
      },
      splitNumber: ySplitNumber,
      // 保留原有特殊场景的配置（优先级最高，会覆盖上面的 min/max）
      ...(isInBed.value && breathWarningId.value === 21 && false ? {
        min: -1,
        max: 1
      } : {})
    },
    series: !isInBed.value ? [] : [{
      name: '呼吸波形',
      type: 'line',
      data: displayData,
      smooth: true,
      symbol: 'none',
      showSymbol: false,
      animation: false,
      lineStyle: {
        color: '#3B82F6',
        width: lineWidth,
        shadowBlur: Math.max(3, lineWidth * 0.8),
        shadowColor: '#3B82F6' + '40',
        shadowOffsetX: Math.max(1, lineWidth * 0.1),
        shadowOffsetY: Math.max(1, lineWidth * 0.1)
      },
      itemStyle: {
        color: '#3B82F6'
      }
    }]
  }
}

// 呼吸容量环图表配置函数
const getRingChartOption = (seriesData: [number, number][], shouldShowData: boolean) => {
  const fontSize = calculateEchartsFontSize(ringChartRef.value, 0.8)
  const lineWidth = calculateEchartsLineWidth(ringChartRef.value, 1)
  const containerWidth = ringChartRef.value ? ringChartRef.value.clientWidth : 0
  const containerHeight = ringChartRef.value ? ringChartRef.value.clientHeight : 0
  const samplingRate = 100
  const xTickInterval = containerWidth < 250 ? samplingRate * 2 : samplingRate
  const yTickInterval = containerHeight < 250 ? 2 : 1
  const xSplitNumber = containerWidth < 250 ? 4 : 5
  const ySplitNumber = containerHeight < 250 ? 3 : 5

  const isMobile = window.innerWidth <= 768
  const xAxisName = isMobile ? '' : '时间(s)'
  const yAxisName = isMobile ? '' : '归一化幅度'

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        animation: false
      },
      backgroundColor: 'rgba(0,0,0,0.7)',
      textStyle: { 
        color: '#fff',
        fontSize: fontSize
      },
      borderColor: 'rgba(255,255,255,0.2)'
    },
    grid: {
      left: '3%',
      right: '5%',
      bottom: '15%',
      top: '25%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 1.01,
      name: xAxisName,
      nameLocation: 'center',
      nameGap: 25,
      nameTextStyle: {
        color: '#666',
        fontSize: fontSize * 0.8
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#e0e0e0',
          type: 'solid',
          width: lineWidth * 0.5
        }
      },
      axisLine: {
        show: true,
        lineStyle: {
          color: '#666',
          width: lineWidth * 0.5
        }
      },
      axisTick: {
        show: true,
        length: lineWidth * 2
      },
      axisLabel: {
        textStyle: {
          color: '#666',
          fontSize: fontSize
        },
      },
      splitNumber: xSplitNumber,
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      nameGap: 8,
      nameTextStyle: {
        color: '#666',
        fontSize: fontSize * 0.9,
      },
      show: true,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#e0e0e0',
          type: 'solid',
          width: lineWidth * 0.5
        }
      },
      axisLine: {
        show: true,
        lineStyle: {
          color: '#666',
          width: lineWidth * 0.5
        }
      },
      axisTick: {
        show: true,
        length: lineWidth * 2
      },
      axisLabel: {
        textStyle: {
          color: '#666',
          fontSize: fontSize
        },
      },
      splitNumber: ySplitNumber,
    },
    series: shouldShowData ? [{
      name: '呼吸环',
      type: 'line',
      data: seriesData,
      smooth: true,
      symbol: 'none',
      showSymbol: false,
      lineStyle: {
        color: '#F59E0B',
        width: lineWidth,
        shadowBlur: Math.max(3, lineWidth * 0.8),
        shadowColor: '#F59E0B' + '40',
        shadowOffsetX: Math.max(1, lineWidth * 0.1),
        shadowOffsetY: Math.max(1, lineWidth * 0.1)
      },
      itemStyle: {
        color: '#F59E0B'
      },
      animation: true,
      animationDuration: 10000,
      animationEasing: 'linear',
    }] : []
  }
}

const buildWaveformXAxisData = (pointCount: number) => {
  return Array.from({ length: pointCount }, (_, index) => (index / WAVEFORM_SAMPLING_RATE).toFixed(2))
}

const renderWaveformChart = () => {
  if (!waveformChart) {
    return
  }
  const xAxisData = buildWaveformXAxisData(waveformDisplayData.value.length)
  waveformChart.clear()
  waveformChart.setOption(getWaveformChartOption(waveformDisplayData.value, xAxisData))
}

const normalizeWaveformSamples = (samples: number[]) => {
  if (!samples.length) {
    return samples
  }
  const min = Math.min(...samples)
  return samples.map(item => item - min)
}

const setFlatWaveform = (value: number) => {
  waveformQueue.value = []
  waveformDisplayData.value = new Array(MAX_WAVEFORM_POINTS).fill(value)
  renderWaveformChart()
}

const handleSpecialWaveformStates = () => {
  if (!isInBed.value) {
    setFlatWaveform(0)
    return true
  }
  if (breathWarningId.value === 21 && false) {
    setFlatWaveform(0.5)
    return true
  }
  return false
}

const trimWaveformChunk = (samples: number[]) => {
  if (!samples.length) {
    return []
  }
  if (samples.length <= WAVEFORM_FETCH_CHUNK_SIZE) {
    return samples
  }
  return samples.slice(-WAVEFORM_FETCH_CHUNK_SIZE)
}

const appendWaveformData = (dataPoints: number[]) => {
  if (!dataPoints.length) {
    return
  }
  waveformDisplayData.value = waveformDisplayData.value.concat(dataPoints)
  if (waveformDisplayData.value.length > MAX_WAVEFORM_POINTS) {
    waveformDisplayData.value = waveformDisplayData.value.slice(-MAX_WAVEFORM_POINTS)
  }
  renderWaveformChart()
}

const waveProcessingLoop = () => {
  if (handleSpecialWaveformStates()) {
    return
  }
  if (waveformQueue.value.length < WAVEFORM_PROCESS_BATCH) {
    return
  }
  if (waveformDisplayData.value.length >= MAX_WAVEFORM_POINTS) {
    if (waveformChart) {
      waveformChart.clear()
      waveformDisplayData.value = []
      waveformChart.setOption(getWaveformChartOption(waveformDisplayData.value))
    }
    return
  }
  const chunkSize = Math.min(WAVEFORM_PROCESS_BATCH, waveformQueue.value.length)
  const dataPoints = waveformQueue.value.splice(0, chunkSize)
  appendWaveformData(dataPoints)
}
let cnt = 0
const waveFetchingLoop = async () => {
  try {
    let res = await getBWaveform(userId.value)
    while(res.data && res.data.timestamp <= last_time)
    {
      res = await getBWaveform(userId.value)
    }
    if(res.data){
      last_time = res.data.timestamp
      console.log("BreathMonitor timestamp:", last_time)
    }
    if (res?.data) {
      if ('is_in_bed' in res.data) {
        isInBed.value = res.data.is_in_bed
      }
      const rawWaveform = Array.isArray(res.data.breath_waveform) ? res.data.breath_waveform : []
      waveformData.value = rawWaveform

      if (handleSpecialWaveformStates()) {
        return
      }

      if (!rawWaveform.length) {
        return
      }
      
      const trimmed = trimWaveformChunk(rawWaveform)
      let first_point = rawWaveform[0]
      if(cnt == 0)
      {
        waveformQueue.value.push(...rawWaveform)
        last_point = rawWaveform[rawWaveform.length - 1]
      }
      else
      {
        const adjustedWaveform = rawWaveform.map(point => (point - first_point + last_point));
        waveformQueue.value.push(...adjustedWaveform)
        last_point = adjustedWaveform[rawWaveform.length - 1];
      }
      cnt += 1
      if(cnt == 10)
      {
        cnt = 0
      }
      // waveformQueue.value.push(...normalizeWaveformSamples(trimmed))
      waveProcessingLoop()
    }
  } catch (error) {
    console.error('Error updating waveform chart:', error)
  }
}

const startWaveformStreaming = async () => {
  if (waveformFetchIntervalId.value === null) {
    await waveFetchingLoop()
    waveformFetchIntervalId.value = window.setInterval(() => {
      waveFetchingLoop()
    }, WAVEFORM_FETCH_INTERVAL)
  }

  if (waveformProcessIntervalId.value === null) {
    waveformProcessIntervalId.value = window.setInterval(() => {
      waveProcessingLoop()
    }, WAVEFORM_PROCESS_INTERVAL)
  }
}

const stopWaveformStreaming = () => {
  if (waveformFetchIntervalId.value !== null) {
    clearInterval(waveformFetchIntervalId.value)
    waveformFetchIntervalId.value = null
  }

  if (waveformProcessIntervalId.value !== null) {
    clearInterval(waveformProcessIntervalId.value)
    waveformProcessIntervalId.value = null
  }
}

// 更新呼吸波形图表数据
const updateWaveform = async () => {
  await waveFetchingLoop()
}

// 更新呼吸环图表数据
const updateRing = async () => {
  try {
    const res = await getBRingform(userId.value)
    if (res?.data) {
      ringData.value = {
        breath_ring_x: res.data.breath_ring_x || [],
        breath_ring_y: res.data.breath_ring_y || []
      }
      
      const shouldShowData = isInBed.value && breathWarningId.value !== 21 && true
      const seriesData = ringData.value.breath_ring_x.map((x, i) => [x, ringData.value.breath_ring_y[i]] as [number, number])
      
      if (ringChart) {
        ringChart.clear()
        ringChart.setOption(getRingChartOption(seriesData, shouldShowData))
      }
    }
  } catch (error) {
    console.error('Error updating ring chart:', error)
  }
}

// 更新警告状态
const updateWarning = async () => {
  try {
    const warningRes = await getWarning(userId.value)
    if (warningRes.data) {
      breathWarningId.value = warningRes.data.breath_warning_id
      // breathWarningId.value = 22
    }
  } catch (error) {
    console.error('Error updating warning:', error)
  }
}

// 更新所有数据
const updateCharts = async () => {
  try {
    await updateWarning()
    await Promise.all([
      updateWaveform(),
      updateRing()
    ])
  } catch (error) {
    console.error('Error updating charts:', error)
  }
}

// 启动定时更新
const startUpdatingCharts = () => {
  intervalId.value = window.setInterval(() => {
    updateCharts()
  }, 10000)
}

// 调整图表大小
const resizeCharts = () => {
  if (waveformChart) {
    waveformChart.resize()
  }
  if (ringChart) {
    ringChart.resize()
  }
}

// 初始化图表
const initCharts = async () => {
  if (isExpanded.value) {
    if (waveformChartRef.value) {
      if (waveformChart) waveformChart.dispose()
      waveformChart = echarts.init(waveformChartRef.value)
    }
    
    if (ringChartRef.value) {
      if (ringChart) ringChart.dispose()
      ringChart = echarts.init(ringChartRef.value)
    }
    
    // 设置 ResizeObserver
    if (resizeObserver) {
      resizeObserver.disconnect()
    }
    resizeObserver = new ResizeObserver(() => {
      resizeCharts()
    })
    
    if (waveformChartRef.value) {
      resizeObserver.observe(waveformChartRef.value)
    }
    if (ringChartRef.value) {
      resizeObserver.observe(ringChartRef.value)
    }
  }
}

watch([isInBed, breathWarningId], () => {
  if (!handleSpecialWaveformStates()) {
    renderWaveformChart()
  }
})

// 监听展开状态变化
watch(isExpanded, async (newVal) => {
  if (newVal) {
    // 展开时需要等待 DOM 更新完成
    await nextTick()
    await initCharts()
    renderWaveformChart()
    // 重新更新图表数据
    if (waveformData.value.length > 0 || ringData.value.breath_ring_x.length > 0) {
      await updateCharts()
    }
  } else {
    // 收起时清理图表实例
    if (waveformChart) {
      waveformChart.dispose()
      waveformChart = null
    }
    if (ringChart) {
      ringChart.dispose()
      ringChart = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }
}, { immediate: true })

// 生命周期钩子
onMounted(async () => {
  await updateCharts()
  startUpdatingCharts()
  await startWaveformStreaming()
  
  // 图表初始化由 watch 统一处理
})

onBeforeUnmount(() => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
  
  if (waveformChart) {
    waveformChart.dispose()
    waveformChart = null
  }
  if (ringChart) {
    ringChart.dispose()
    ringChart = null
  }
  
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  stopWaveformStreaming()
})
</script>

<style scoped>
.root-container {
  width: 100%;
  /* height: 100vh; */
  height: auto;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f0f4f8;
  font-family: 'Arial', sans-serif;
}

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
  gap: 0.625em;
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
.status-section {
  font-size: 1em;
  font-weight: bold;
  transition: color 0.3s ease;
  background-color: #f8f9fa;
  padding: 1%;
  margin-right: 1.5vw;
  border-radius: 0.3125em;
  border: #a3a3a3 0.0625em;
  box-shadow: 0 0.125em 0.25em rgba(0, 0, 0, 0.15);
  max-width: fit-content;
  white-space: nowrap;
}
.status-item {
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  gap: 0.5em;
  flex-shrink: 0;
}
.status-icon {
  width: 1.75em;
  height: 1.75em;
  transition: transform 0.3s ease;
  margin-right: 0.5em;
  flex-shrink: 0;
}
.status-icon.status-active {
  filter: brightness(0) saturate(100%) invert(18%) sepia(98%) saturate(7040%) hue-rotate(358deg) brightness(100%) contrast(106%);
  animation: pulse 2s infinite;
}
.status-text-active {
  color: #EF4444;
  font-weight: bold;
  font-size: 1em;
  margin: 0;
}
.status-text-normal {
  color: #10B981;
  font-weight: bold;
  font-size: 1em;
  margin: 0;
}
.status-text-out-of-bed {
  color: #F59E0B;
  font-weight: bold;
  font-size: 1em;
  margin: 0;
}

/* 图表区域 */
.charts-section {
  display: flex;
  gap: 0.8em;
  flex: 10;
  min-height: 0;
  overflow: hidden;
  padding-bottom: 1vh;
  padding-top: 1vh;
  font-size: 1em;
}
.waveform-container {
  flex: 2;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.ring-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0;
  padding-right: 0.3em;
}
.chart-container {
  width: 100%;
  flex: 1;
  min-height: 0;
  border-radius: 1.2em;
  overflow: hidden;
  box-shadow: 
    0 0.25em 0.5em rgba(0, 0, 0, 0.1),
    inset 0 0.0625em 0.125em rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  background: #fff;
  position: relative;
}
.sub-chart-title-container {
  display: flex;
  align-items: center;
  gap: 0.5em;
  position: relative;
  flex-shrink: 0;
  background: rgba(248, 249, 250, 0.8);
  border-bottom: 0.0625em solid rgba(0, 0, 0, 0.1);
}
.sub-chart-title {
  font-size: 0.9em;
  color: #2c3e508e;
  letter-spacing: 0.03em;
  margin: 0;
  padding: 0.75em 1em 0.5em 1em;
  flex-shrink: 0;
  background: rgba(248, 249, 250, 0.8);
  font-weight: 600;
}

/* 环形图信息图标 */
.info-icon-ring {
  width: 1.2em;
  height: 1.2em;
  border-radius: 50%;
  background: #007bff;
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: help;
  font-size: 0.75em;
  font-weight: bold;
  flex-shrink: 0;
  transition: background-color 0.2s ease;
}
.info-icon-ring:hover {
  background-color: #0056b3;
}
.tooltip-ring {
  position: absolute;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 0.5em 0.75em;
  border-radius: 0.375em;
  font-size: 0.6875em;
  z-index: 1000;
  min-width: 15em;
  max-width: 20em;
  white-space: normal;
  top: 100%;
  left: 0;
  margin-top: 0.5em;
  box-shadow: 0 0.25em 0.5em rgba(0, 0, 0, 0.2);
  pointer-events: none;
}
.tooltip-ring::before {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 1em;
  width: 0;
  height: 0;
  border-left: 0.375em solid transparent;
  border-right: 0.375em solid transparent;
  border-bottom: 0.375em solid rgba(0, 0, 0, 0.9);
}

/* 子图表容器 */
.sub-chart-container {
  width: 100%;
  flex: 1;
  min-height: 0;
  position: relative;
  font-size: 1em;
}

/* ...已移除 chart-note 相关样式... */

/* 动画效果 */
@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
  }
}

/* 响应式设计 */
@media (max-width: 75em) { /* 1200px */
  .chart-header {
    margin: 0.5% 1%;
  }
  
  .section-title {
    font-size: 1.2em;
  }
  
  .status-section {
    font-size: 0.9em;
    padding: 0.8%;
  }
  
  .charts-section {
    gap: 1vw;
    padding-bottom: 0.5vh;
    padding-top: 0.5vh;
  }
}

@media (max-width: 48em) { /* 768px */
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
  
  .status-section {
    font-size: 0.8em;
    margin-right: 0;
    padding: 0.8% 1.2%;
  }
  
  .status-text-active,
  .status-text-normal,
  .status-text-out-of-bed {
    font-size: 0.8em;
  }
  
  .status-icon {
    width: 15%;
  }
  
  .charts-section {
    gap: 0.5em;
    height: 20vh;
  }
  
  .waveform-container,
  .ring-container {
    flex: 1;
    min-height: 5%;
  }
  
  .sub-chart-title {
    font-size: 0.8em;
    padding: 0.2em 0.5em;
  }
  
  .chart-note {
    font-size: 0.7em;
    padding: 0.4em;
  }
  
  .breath-status-text {
    font-size: 0.9em;
    padding: 0.25em 0.5em;
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
  
  .charts-section {
    height: 85vh;
  }
  
  .chart-note {
    margin: 0.1em 0em;
    padding: 0em;
  }
}
</style>