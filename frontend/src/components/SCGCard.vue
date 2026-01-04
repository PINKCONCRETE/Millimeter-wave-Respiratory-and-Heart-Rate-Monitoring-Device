<template>
  <BaseChartCard
    title="SCG Real-time Monitor"
    :window-size="windowSize"
    :auto-scale-y="autoScaleY"
    :manual-y-min="manualYMin"
    :manual-y-max="manualYMax"
    @update:window-size="windowSize = $event"
    @update:auto-scale-y="autoScaleY = $event"
    @update:manual-y-min="manualYMin = $event"
    @update:manual-y-max="manualYMax = $event"
    @chart-ready="initChart"
  >
    <template #stats>
        <el-tag size="small" type="primary">Bin: {{ currentBin }}</el-tag>
        <el-tag size="small" type="primary" style="margin-left: 8px">Score: {{ currentScore.toFixed(1) }}</el-tag>
        <el-tag size="small" type="info" style="margin-left: 8px">Buffer: {{ bufferSize }}</el-tag>
        <el-tag size="small" type="success" style="margin-left: 8px">Backend: {{ fps }}</el-tag>
        <el-tag size="small" type="warning" style="margin-left: 8px">UI: {{ uiFps }}</el-tag>
        <el-tag size="small" :type="status === 'Active' ? 'success' : 'warning'" style="margin-left: 8px">{{ status }}</el-tag>
    </template>
    <template #extra-controls>
        <!-- Any extra controls for SCG specific? None for now -->
    </template>
  </BaseChartCard>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type SCGData, type FPSData } from '../utils/ipc';
import BaseChartCard from './BaseChartCard.vue';

const props = defineProps<{
  isInBed: boolean
}>();

let chartInstance: echarts.ECharts | null = null;
const fps = ref(0);
const uiFps = ref(0);
const bufferSize = ref(0);
const status = ref('Waiting...');
const currentBin = ref(0);
const currentScore = ref(0.0);

// Control variables
const windowSize = ref(4000);
const autoScaleY = ref(true);
const manualYMin = ref(-1.0);
const manualYMax = ref(1.0);

// Performance optimization: Render loop variables
const BUFFER_LIMIT = 10000;
let dataBuffer: number[] = [];
let pendingData: number[] = [];
let animationFrameId: number | null = null;
let lastUiFpsTime = Date.now();
let uiFrameCount = 0;
let hasNewData = false;

const initChart = (div: HTMLElement) => {
    chartInstance = echarts.init(div);
    chartInstance.setOption({
      grid: { top: 30, right: 20, bottom: 20, left: 50 },
      tooltip: { trigger: 'axis' },
      xAxis: { 
          type: 'category', 
          data: [], 
          show: false,
          min: 0,
          max: windowSize.value 
      },
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
        lineStyle: { color: '#E6A23C', width: 2 },
        areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(230,162,60,0.3)' },
            { offset: 1, color: 'rgba(230,162,60,0.05)' }
          ])
        },
        animation: false
      }],
      animation: false
    });
};

// Watch window size to update chart
watch(windowSize, (newVal) => {
    if (chartInstance) {
        chartInstance.setOption({
            xAxis: { max: newVal }
        });
    }
});

const renderLoop = () => {
  const now = Date.now();
  uiFrameCount++;
  
  if (now - lastUiFpsTime >= 1000) {
    uiFps.value = uiFrameCount;
    uiFrameCount = 0;
    lastUiFpsTime = now;
  }

  // Process pending data
  if (pendingData.length > 0) {
      hasNewData = true;
      dataBuffer.push(...pendingData);
      pendingData = [];

      if (dataBuffer.length > BUFFER_LIMIT) {
          dataBuffer = dataBuffer.slice(dataBuffer.length - BUFFER_LIMIT);
      }
      bufferSize.value = dataBuffer.length;
  }

  if ((hasNewData || !autoScaleY.value) && chartInstance) {
    if (!props.isInBed) {
         // Handle in watcher
    } else {
        const displayData = dataBuffer.slice(-windowSize.value);
        const xData = Array.from({ length: displayData.length }, (_, i) => i);
        
        const yAxisOption = autoScaleY.value ? {
            scale: true,
            min: null,
            max: null
        } : {
            scale: false,
            min: manualYMin.value,
            max: manualYMax.value
        };

        chartInstance.setOption({
            xAxis: { 
                data: xData,
                max: windowSize.value
            },
            yAxis: yAxisOption,
            series: [{ data: displayData }]
        });
        hasNewData = false;
    }
  }

  animationFrameId = requestAnimationFrame(renderLoop);
};

const updateChart = (value: number) => {
  pendingData.push(value);
};

const handleResize = () => chartInstance?.resize();

onMounted(() => {
  window.addEventListener('resize', handleResize);
  renderLoop();
  
  setupIPCListeners({
    onSCG: (data: SCGData) => {
      if (typeof data.scg_value === 'number') {
          updateChart(data.scg_value);
          status.value = 'Active';
          if (data.max_bin !== undefined) currentBin.value = data.max_bin;
          if (data.score !== undefined) currentScore.value = data.score;
      } 
      else if (data.scg_waveform && data.scg_waveform.length > 0) {
          updateChart(data.scg_waveform[data.scg_waveform.length - 1]);
          status.value = 'Active';
          if (data.max_bin !== undefined) currentBin.value = data.max_bin;
          if (data.score !== undefined) currentScore.value = data.score;
      }
    },
    onFPS: (data: FPSData) => {
        fps.value = data.fps;
    }
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
  }
});

watch(() => props.isInBed, (newVal) => {
    if (!newVal) {
        if (chartInstance) chartInstance.setOption({ series: [{ data: [] }] });
        status.value = 'No Human';
        dataBuffer = [];
        pendingData = [];
    } else {
        status.value = 'Waiting...';
    }
});
</script>
