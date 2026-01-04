<template>
  <el-card class="box-card">
    <template #header>
      <div class="card-header">
        <span>呼吸监测</span>
      </div>
    </template>
    <div class="chart-container">
      <div ref="waveformChart" style="width: 100%; height: 300px;"></div>
    </div>
    <div class="status-container">
      <el-tag :type="isInBed ? 'success' : 'info'">{{ isInBed ? '在床' : '离床' }}</el-tag>
      <el-tag v-if="warningId !== 0" type="danger" style="margin-left: 10px">
        {{ getWarningText(warningId) }}
      </el-tag>
      <span style="margin-left: 20px">呼吸率: {{ respiratoryRate.toFixed(1) }} BPM</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type BreathData, type HumanCheckData } from '../utils/ipc';

const props = defineProps<{
  uid: number
}>();

const waveformChart = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const isInBed = ref(true);
const warningId = ref(0);
const respiratoryRate = ref(0);

// Buffer for smooth display
const MAX_POINTS = 200;
let waveformBuffer: number[] = [];

const initChart = () => {
  if (waveformChart.value) {
    chartInstance = echarts.init(waveformChart.value);
    chartInstance.setOption({
      title: { text: '呼吸波形' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [], show: false },
      yAxis: { 
        type: 'value', 
        scale: true, // Auto-scale
        splitLine: { show: true }
      },
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#409EFF' },
        animation: false
      }],
      animation: false
    });
  }
};

const updateChart = () => {
  if (chartInstance && waveformBuffer.length > 0) {
    if (!isInBed.value) {
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
  if (id === 21) return '呼吸暂停警告';
  if (id === 22) return 'COPD风险';
  return '未知警告';
};

onMounted(() => {
  initChart();
  
  // Setup IPC listeners
  setupIPCListeners({
    onBreath: (data: BreathData) => {
      // Assuming data.displacement contains a chunk of new points or the latest window
      // The Python code sends the last 200 points. Let's just use them directly.
      waveformBuffer = data.displacement;
      warningId.value = data.warning_id;
      respiratoryRate.value = data.respiratory_rate;
      updateChart();
    },
    onHumanCheck: (data: HumanCheckData) => {
        isInBed.value = (data.status === 'presence');
    }
  });
});

onUnmounted(() => {
  chartInstance?.dispose();
});
</script>

<style scoped>
.chart-container {
  margin-bottom: 20px;
}
.status-container {
  display: flex;
  align-items: center;
}
</style>
