<template>
  <el-card class="box-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">HRV趋势 (SDNN)</span>
        <el-tag :type="getStressType(stressLevel)" size="small">压力: {{ stressLevel }}</el-tag>
      </div>
    </template>
    <div class="chart-content">
      <div class="metric-value">
        <span class="number">{{ stressIndex.toFixed(1) }}</span>
        <span class="unit">SI</span>
      </div>
      <div ref="chartRef" class="chart-div"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type HeartRateData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const stressIndex = ref(0);
const stressLevel = ref('低');
const hrvHistory: {time: number, value: number}[] = [];

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
        name: 'ms',
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#67C23A', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103,194,58,0.3)' },
            { offset: 1, color: 'rgba(103,194,58,0.05)' }
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
    const points = hrvHistory.map(item => [item.time, item.value]);
    chartInstance.setOption({
      series: [{ data: points }]
    });
  }
};

const getStressType = (level: string) => {
  if (level === '低') return 'success';
  if (level === '中') return 'warning';
  return 'danger';
};

const handleResize = () => chartInstance?.resize();

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
  
  setupIPCListeners({
    onHeartRate: (data: HeartRateData) => {
      if (!props.isInBed) return;
      
      stressIndex.value = data.stress_index;
      stressLevel.value = data.stress_level;
      
      if (data.hrv > 0) {
        const now = Date.now();
        hrvHistory.push({ time: now, value: data.hrv });
        
        if (hrvHistory.length > 300) hrvHistory.shift();
        while(hrvHistory.length > 0 && now - hrvHistory[0].time > 300000) {
          hrvHistory.shift();
        }
        updateChart();
      }
    }
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
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
