<template>
  <BaseChartCard
    title="SCG Real-time Monitor"
    :stats="statsList"
    :initial-window-seconds="20"
    :show-window-control="true"
    :show-y-axis-control="true"
    :default-y-min="-1.0"
    :default-y-max="1.0"
    @init="onChartInit"
    @window-change="onWindowChange"
    @y-axis-change="onYAxisChange"
  >
    <!-- <template #stats-extra>
        <el-tag size="small" type="primary">Bin: {{ currentBin }}</el-tag>
        <el-tag size="small" type="primary" style="margin-left: 8px">Score: {{ currentScore.toFixed(1) }}</el-tag>
    </template> -->
  </BaseChartCard>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import BaseChartCard from './BaseChartCard.vue';
import { setupIPCListeners, type SCGData, type FPSData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const fps = ref(0);
const uiFps = ref(0);
const bufferSize = ref(0);
const status = ref('Waiting...');
const currentBin = ref(0);
const currentScore = ref(0.0);
const isPremature = ref(false);

const statsList = computed(() => [
    { label: 'Premature', value: isPremature.value ? 'Yes' : 'No', type: isPremature.value ? 'danger' as const : 'info' as const },
    { label: 'Human', value: props.isInBed ? 'Yes' : 'No', type: props.isInBed ? 'success' as const : 'info' as const },
    { label: 'FPS', value: fps.value, type: 'success' as const }
]);

// Chart state
let chartInstance: echarts.ECharts | null = null;
const SAMPLING_RATE = 200; // 200Hz
const BUFFER_LIMIT = 20000; // 100 seconds buffer
let dataBuffer: number[] = [];
let pendingData: number[] = [];

// Display control
let currentWindowPoints = 4000; // Default 20s * 200Hz
let isAutoScaleY = true;
let manualYMin = -1.0;
let manualYMax = 1.0;

// Render loop
let animationFrameId: number | null = null;
let lastUiFpsTime = Date.now();
let uiFrameCount = 0;
let hasNewData = false;
let lastIsInBed = true;

watch(() => props.isInBed, (newVal) => {
    hasNewData = true; // Force update on state change
});

const onChartInit = (instance: echarts.ECharts) => {
    chartInstance = instance;
    
    chartInstance.setOption({
      grid: { top: 30, right: 20, bottom: 20, left: 50 },
      tooltip: { trigger: 'axis' },
      xAxis: { 
          type: 'category', 
          show: false,
          min: 0,
          max: currentWindowPoints 
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

    startRenderLoop();
};

const onWindowChange = (seconds: number) => {
    currentWindowPoints = seconds * SAMPLING_RATE;
    if (chartInstance) {
        chartInstance.setOption({
            xAxis: { max: currentWindowPoints }
        });
        // Force update immediately
        hasNewData = true;
    }
};

const onYAxisChange = (auto: boolean, min: number, max: number) => {
    isAutoScaleY = auto;
    manualYMin = min;
    manualYMax = max;
    // Force update immediately
    hasNewData = true;
};

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

  if ((hasNewData || !isAutoScaleY) && chartInstance) {
    if (props.isInBed) {
        const displayData = dataBuffer.slice(-currentWindowPoints);
        const xData = Array.from({ length: displayData.length }, (_, i) => i);
        
        const yAxisOption = isAutoScaleY ? {
            scale: true,
            min: null,
            max: null
        } : {
            scale: false,
            min: manualYMin,
            max: manualYMax
        };

        chartInstance.setOption({
            xAxis: { 
                data: xData,
                max: currentWindowPoints
            },
            yAxis: yAxisOption,
            series: [{ data: displayData }]
        });
    } else {
        // Clear chart when not in bed
        chartInstance.setOption({
            series: [{ data: [] }]
        });
    }
    hasNewData = false;
  }

  animationFrameId = requestAnimationFrame(renderLoop);
};

const startRenderLoop = () => {
    if (animationFrameId === null) {
        renderLoop();
    }
};

// IPC Listeners
setupIPCListeners({
    onSCG: (data: SCGData) => {
        // Handle new data point
        if (data.scg_value !== undefined) {
            pendingData.push(data.scg_value);
        } else if (data.scg_waveform && data.scg_waveform.length > 0) {
            // Fallback for full waveform if sent
             pendingData.push(...data.scg_waveform);
        }

        if (data.max_bin !== undefined) currentBin.value = data.max_bin;
        if (data.score !== undefined) currentScore.value = data.score;
    },
    onRealtimeAnalysis: (data: RealtimeAnalysisData) => {
        if (data.realtime_premature !== undefined) isPremature.value = data.realtime_premature;
    },
    onFPS: (data: FPSData) => {
        fps.value = data.fps;
    }
});

onUnmounted(() => {
    if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
});
</script>