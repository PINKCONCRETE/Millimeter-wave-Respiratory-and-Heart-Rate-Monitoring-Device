<template>
  <el-card class="box-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">呼吸监测</span>
        <div class="status-badges">
          <el-tag :type="isInBed ? 'success' : 'info'" size="small">{{ isInBed ? '在床' : '离床' }}</el-tag>
          <el-tag v-if="warningId !== 0" type="danger" size="small" style="margin-left: 5px">
            {{ getWarningText(warningId) }}
          </el-tag>
        </div>
      </div>
    </template>
    <div class="chart-content">
      <div class="metric-value">
        <span class="number">{{ respiratoryRate.toFixed(1) }}</span>
        <span class="unit">BPM</span>
      </div>
      <div ref="chartRef" class="chart-div"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type BreathData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const warningId = ref(0);
const respiratoryRate = ref(0);
let waveformBuffer: number[] = [];

const initChart = () => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value);
    chartInstance.setOption({
      grid: { top: 10, right: 10, bottom: 20, left: 40 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [], show: false },
      yAxis: { 
        type: 'value', 
        scale: true,
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#409EFF', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0.05)' }
          ])
        },
        animation: false
      }]
    });
  }
};

const updateChart = () => {
  if (chartInstance && waveformBuffer.length > 0) {
    if (!props.isInBed) {
        chartInstance.setOption({ series: [{ data: [] }] });
        return;
    }
    chartInstance.setOption({
      xAxis: { data: Array.from({ length: waveformBuffer.length }, (_, i) => i) },
      series: [{ data: waveformBuffer }]
    });
  }
};

const getWarningText = (id: number) => {
  if (id === 21) return '呼吸暂停';
  if (id === 22) return 'COPD风险';
  return '未知';
};

// Resize chart on window resize
const handleResize = () => chartInstance?.resize();

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
  
  setupIPCListeners({
    onBreath: (data: BreathData) => {
      waveformBuffer = data.displacement;
      warningId.value = data.warning_id;
      respiratoryRate.value = data.respiratory_rate;
      updateChart();
    }
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});

// Watch isInBed to clear chart if needed immediately
watch(() => props.isInBed, (newVal) => {
    if (!newVal && chartInstance) {
        chartInstance.setOption({ series: [{ data: [] }] });
    }
});
</script>

<style scoped>
.box-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-weight: bold;
  font-size: 16px;
}
.chart-content {
  position: relative;
  height: 250px;
}
.metric-value {
  position: absolute;
  top: 0;
  left: 10px;
  z-index: 10;
  background: rgba(255,255,255,0.8);
  padding: 2px 5px;
  border-radius: 4px;
}
.number {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}
.unit {
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}
.chart-div {
  width: 100%;
  height: 100%;
}
</style>
