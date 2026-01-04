<template>
  <BaseChartCard
    title="Respiratory Waveform"
    :stats="statsList"
    :initial-window-seconds="20"
    :show-window-control="true"
    :show-y-axis-control="true"
    @init="onChartInit"
    @window-change="onWindowChange"
    @y-axis-change="onYAxisChange"
  />
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import BaseChartCard from './BaseChartCard.vue';
import { setupIPCListeners, type BreathData, type FPSData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const fps = ref(0);
const uiFps = ref(0);
const bufferSize = ref(0);
const status = ref('Waiting...');
const respiratoryRate = ref(0);

const statsList = computed(() => [
    { label: 'RR', value: `${respiratoryRate.value} rpm`, type: 'primary' as const },
    { label: 'Buffer', value: bufferSize.value, type: 'info' as const },
    { label: 'Backend', value: fps.value, type: 'success' as const },
    { label: 'UI', value: uiFps.value, type: 'warning' as const },
    { label: 'Status', value: status.value, type: status.value === 'Active' ? 'success' as const : 'warning' as const }
]);

// Chart state
let chartInstance: echarts.ECharts | null = null;
const SAMPLING_RATE = 20; // 20Hz for Breath
const BUFFER_LIMIT = 2000; // 100 seconds buffer
let dataBuffer: number[] = [];
let pendingData: number[] = [];

// Display control
let currentWindowPoints = 400; // Default 20s * 20Hz
let isAutoScaleY = true;
let manualYMin = -1.0;
let manualYMax = 1.0;

// Render loop
let animationFrameId: number | null = null;
let lastUiFpsTime = Date.now();
let uiFrameCount = 0;
let hasNewData = false;

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
        lineStyle: { color: '#409EFF', width: 2 },
        areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0.05)' }
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
        hasNewData = true;
    }
};

const onYAxisChange = (auto: boolean, min: number, max: number) => {
    isAutoScaleY = auto;
    manualYMin = min;
    manualYMax = max;
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
        hasNewData = false;
    }
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
    onBreath: (data: BreathData) => {
        // Use breath_value (displacement) for waveform
        // data.breath_value is incremental (single float)
        if (typeof data.breath_value === 'number') {
             pendingData.push(data.breath_value);
        } 
        // Fallback for legacy array
        else if (data.displacement && data.displacement.length > 0) {
             pendingData.push(data.displacement[data.displacement.length - 1]);
        }
        
        if (data.respiratory_rate !== undefined) {
            respiratoryRate.value = data.respiratory_rate;
        }
        status.value = 'Active';
    },
    onFPS: (data: FPSData) => {
        // We might want to filter only Breath module FPS here, but currently FPS data is generic
        // Assuming Broadcaster sends FPS for all modules, we might need to check source if available.
        // But for now, just displaying the last received FPS is fine, or update ipc.ts to filter.
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