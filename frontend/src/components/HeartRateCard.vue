<template>
  <BaseChartCard
    title="Heart Rate Trend"
    :stats="statsList"
    :show-window-control="false"
    :show-y-axis-control="true"
    @init="onChartInit"
    @y-axis-change="onYAxisChange"
  />
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import BaseChartCard from './BaseChartCard.vue';
import { setupIPCListeners, type HeartRateData, type HumanCheckData } from '../utils/ipc';

const props = defineProps<{
  isInBed: boolean
}>();

const currentHR = ref(0);
const stressLevel = ref('Unknown');
const hasHuman = ref(false);

const statsList = computed(() => [
    { label: 'HR', value: `${currentHR.value} bpm`, type: 'danger' as const },
    { label: 'Stress', value: stressLevel.value, type: 'warning' as const },
    { label: 'Human', value: hasHuman.value ? 'Yes' : 'No', type: hasHuman.value ? 'success' as const : 'info' as const }
]);

// Chart state
let chartInstance: echarts.ECharts | null = null;
const MAX_HISTORY_POINTS = 3600; // Keep 1 hour of data at 1Hz
type DataPoint = { name: string; value: [string, number | null] };
let dataBuffer: DataPoint[] = [];
let isAutoScaleY = true;
let manualYMin = 40;
let manualYMax = 120;

const onChartInit = (instance: echarts.ECharts) => {
    chartInstance = instance;
    
    chartInstance.setOption({
      grid: { top: 30, right: 20, bottom: 20, left: 50 },
      tooltip: { 
          trigger: 'axis',
          formatter: (params: any) => {
              const date = new Date(params[0].value[0]);
              return `${date.toLocaleTimeString()} : ${params[0].value[1]} bpm`;
          }
      },
      xAxis: { 
          type: 'time',
          splitLine: { show: false }
      },
      yAxis: { 
        type: 'value', 
        scale: true,
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [{
        name: 'Heart Rate',
        type: 'line',
        showSymbol: true,
        symbolSize: 4,
        connectNulls: false, // Don't connect points when has_human=0 (null values)
        lineStyle: { color: '#F56C6C', width: 2 },
        itemStyle: { color: '#F56C6C' },
        areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(245,108,108,0.3)' },
            { offset: 1, color: 'rgba(245,108,108,0.05)' }
          ])
        },
        data: []
      }],
      animation: false
    });
};

const onYAxisChange = (auto: boolean, min: number, max: number) => {
    isAutoScaleY = auto;
    manualYMin = min;
    manualYMax = max;
    updateChart();
};

const updateChart = () => {
    if (!chartInstance) return;

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
        yAxis: yAxisOption,
        series: [{ data: dataBuffer }]
    });
};

// IPC Listeners
setupIPCListeners({
    onHeartRate: (data: HeartRateData) => {
        currentHR.value = data.heart_rate;
        stressLevel.value = data.stress_level;
        
        const now = new Date();
        const timestamp = now.toISOString(); // Or formatted string if preferred
        
        // Logic: Y-axis has value only if has_human=1. 
        // If !has_human, we push a null value to break the line? Or just don't push?
        // User said: "纵轴当且仅当has_human=1时才有值，否则没有值"
        // This implies we should record time but with no value, so chart shows a gap.
        
        const value = hasHuman.value ? data.heart_rate : null;
        
        dataBuffer.push({
            name: timestamp,
            value: [timestamp, value]
        });

        if (dataBuffer.length > MAX_HISTORY_POINTS) {
            dataBuffer.shift();
        }

        updateChart();
    },
    onHumanCheck: (data: HumanCheckData) => {
        hasHuman.value = data.has_human;
    }
});
</script>