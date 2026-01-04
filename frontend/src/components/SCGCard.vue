<template>
  <el-card class="box-card" shadow="hover" :body-style="{ padding: '0px', flex: 1, display: 'flex', flexDirection: 'column' }">
    <template #header>
      <div class="card-header">
        <div class="header-left">
            <span class="title">SCG Real-time Monitor</span>
        </div>
        <div class="controls" style="display: flex; align-items: center; gap: 10px; margin-left: 20px;">
            <div class="control-group">
                <span style="font-size: 12px; margin-right: 5px;">Window:</span>
                <el-select v-model="windowSize" size="small" style="width: 80px" @change="handleWindowResize">
                    <el-option label="5s" :value="1000" />
                    <el-option label="10s" :value="2000" />
                    <el-option label="20s" :value="4000" />
                    <el-option label="40s" :value="8000" />
                </el-select>
            </div>
            <div class="control-group" style="display: flex; align-items: center;">
                <span style="font-size: 12px; margin-right: 5px;">Y-Axis:</span>
                <el-switch 
                    v-model="autoScaleY" 
                    size="small"
                    active-text="Auto" 
                    inactive-text="Manual" 
                />
                <div v-if="!autoScaleY" style="display: flex; align-items: center; margin-left: 5px;">
                    <el-input-number v-model="manualYMin" size="small" :step="0.1" controls-position="right" style="width: 80px" />
                    <span style="margin: 0 5px">-</span>
                    <el-input-number v-model="manualYMax" size="small" :step="0.1" controls-position="right" style="width: 80px" />
                </div>
            </div>
        </div>
        <div class="stats" style="margin-left: auto;">
            <el-tag size="small" type="primary">Bin: {{ currentBin }}</el-tag>
            <el-tag size="small" type="primary" style="margin-left: 8px">Score: {{ currentScore.toFixed(1) }}</el-tag>
            <el-tag size="small" type="info" style="margin-left: 8px">Buffer: {{ bufferSize }}</el-tag>
            <el-tag size="small" type="success" style="margin-left: 8px">Backend: {{ fps }}</el-tag>
            <el-tag size="small" type="warning" style="margin-left: 8px">UI: {{ uiFps }}</el-tag>
            <el-tag size="small" :type="status === 'Active' ? 'success' : 'warning'" style="margin-left: 8px">{{ status }}</el-tag>
        </div>
      </div>
    </template>
    <div class="chart-content">
      <div ref="chartRef" class="chart-div"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type SCGData, type FPSData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const chartRef = ref<HTMLElement | null>(null);
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
const BUFFER_LIMIT = 10000; // Keep more data in buffer than displayed
let dataBuffer: number[] = []; // Circular buffer for display
let pendingData: number[] = []; // Temporary buffer for incoming data
let animationFrameId: number | null = null;
let lastUiFpsTime = Date.now();
let uiFrameCount = 0;
let hasNewData = false;

const initChart = () => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value);
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
  }
};

const handleWindowResize = () => {
    // Reset or adjust chart if needed when window size changes
    // Usually renderLoop will handle it, but we might want to update xAxis max immediately
    if (chartInstance) {
        chartInstance.setOption({
            xAxis: { max: windowSize.value }
        });
    }
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
      // Append pending data to buffer
      dataBuffer.push(...pendingData);
      pendingData = []; // Clear pending buffer

      // Maintain buffer limit (keep enough history)
      if (dataBuffer.length > BUFFER_LIMIT) {
          dataBuffer = dataBuffer.slice(dataBuffer.length - BUFFER_LIMIT);
      }
      
      bufferSize.value = dataBuffer.length;
  }

  if ((hasNewData || !autoScaleY.value) && chartInstance) { // Also update if Y-axis mode changes (implied by reactivity or check)
    if (!props.isInBed) {
         // Handle in watcher
    } else {
        // Slice data for display based on windowSize
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
  initChart();
  window.addEventListener('resize', handleResize);
  
  // Start render loop
  renderLoop();
  
  setupIPCListeners({
    onSCG: (data: SCGData) => {
      // Handle incremental updates
      if (typeof data.scg_value === 'number') {
          updateChart(data.scg_value);
          status.value = 'Active';
          if (data.max_bin !== undefined) currentBin.value = data.max_bin;
          if (data.score !== undefined) currentScore.value = data.score;
      } 
      // Fallback for legacy full waveform (though backend is updated)
      else if (data.scg_waveform && data.scg_waveform.length > 0) {
          // If we receive a full waveform, we might just take the last point?
          // Or if it's the first frame, take all?
          // For safety, let's just take the last point if we are in incremental mode.
          // But wait, if backend sends full array every time, taking last point is correct for incremental display.
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

<style scoped>
.box-card { height: 100%; display: flex; flex-direction: column; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: bold; font-size: 18px; }
.chart-content { flex: 1; min-height: 0; padding: 10px; }
.chart-div { width: 100%; height: 100%; }
.stats { display: flex; align-items: center; }
</style>
