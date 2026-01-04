<template>
  <el-card class="box-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">心率监测</span>
        <el-tag :type="isArrhythmia === 0 ? 'success' : 'danger'" size="small">
          {{ isArrhythmia === 0 ? '心律正常' : '心律异常' }}
        </el-tag>
      </div>
    </template>
    <div class="chart-content">
      <div class="metric-value">
        <span class="number">{{ currentHeartRate }}</span>
        <span class="unit">BPM</span>
      </div>
      <div ref="chartRef" class="chart-div"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type HeartRateData, type SCGData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const currentHeartRate = ref(0);
const isArrhythmia = ref(0);
const hrHistory: {time: number, value: number}[] = [];

const initChart = () => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value);
    chartInstance.setOption({
      grid: { top: 10, right: 10, bottom: 20, left: 40 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'time', show: true, axisLabel: { show: true, formatter: '{HH}:{mm}:{ss}' } },
      yAxis: { 
        type: 'value', 
        scale: true, 
        min: 40,
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#F56C6C', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(245,108,108,0.3)' },
            { offset: 1, color: 'rgba(245,108,108,0.05)' }
          ])
        },
        animation: false
      }]
    });
  }
};

const updateChart = () => {
  if (chartInstance) {
    if (!props.isInBed) return;
    const points = hrHistory.map(item => [item.time, item.value]);
    chartInstance.setOption({
      series: [{ data: points }]
    });
  }
};

const handleResize = () => chartInstance?.resize();

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
  
  setupIPCListeners({
    onHeartRate: (data: HeartRateData) => {
      if (!props.isInBed) return;
      
      currentHeartRate.value = data.heart_rate;
      
      const now = Date.now();
      hrHistory.push({ time: now, value: data.heart_rate });
      
      // Keep last 5 mins
      if (hrHistory.length > 300) hrHistory.shift();
      while(hrHistory.length > 0 && now - hrHistory[0].time > 300000) {
        hrHistory.shift();
      }
      
      updateChart();
    },
    onSCG: (data: SCGData) => {
        // Arrhythmia data comes with SCG
        isArrhythmia.value = data.isArrhythmia;
    }
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});

watch(() => props.isInBed, (newVal) => {
    if (!newVal && chartInstance) {
         // Optionally clear
    }
});
</script>

<style scoped>
.box-card { height: 100%; display: flex; flex-direction: column; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: bold; font-size: 16px; }
.chart-content { position: relative; height: 250px; }
.metric-value { position: absolute; top: 0; left: 10px; z-index: 10; background: rgba(255,255,255,0.8); padding: 2px 5px; border-radius: 4px; }
.number { font-size: 24px; font-weight: bold; color: #303133; }
.unit { font-size: 12px; color: #909399; margin-left: 4px; }
.chart-div { width: 100%; height: 100%; }
</style>
