<template>
  <el-card class="box-card">
    <template #header>
      <div class="card-header">
        <span>心率与SCG监测</span>
      </div>
    </template>
    
    <div class="chart-container">
      <h3>心率趋势</h3>
      <div ref="heartChart" style="width: 100%; height: 250px;"></div>
    </div>

    <div class="chart-container">
      <h3>SCG波形</h3>
      <div ref="scgChart" style="width: 100%; height: 250px;"></div>
    </div>

    <div class="status-container">
      <el-tag :type="isArrhythmia === 0 ? 'success' : 'danger'">
        {{ isArrhythmia === 0 ? '心律正常' : '心律失常风险' }}
      </el-tag>
      <el-statistic title="当前压力指数" :value="stressIndex" :precision="1" style="margin-left: 20px" />
      <el-tag :type="getStressType(stressLevel)" style="margin-left: 10px">{{ stressLevel }}</el-tag>
      <span style="margin-left: 20px; font-weight: bold; font-size: 1.2em">
        实时心率: {{ currentHeartRate }} BPM
      </span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import { setupIPCListeners, type HeartRateData, type SCGData, type HumanCheckData } from '../utils/ipc';

const props = defineProps<{
  uid: number
}>();

const heartChart = ref<HTMLElement | null>(null);
const scgChart = ref<HTMLElement | null>(null);
let heartInstance: echarts.ECharts | null = null;
let scgInstance: echarts.ECharts | null = null;

const isInBed = ref(true); // Default to true or wait for check
const isArrhythmia = ref(0);
const stressIndex = ref(0);
const stressLevel = ref('低');
const currentHeartRate = ref(0);

// Heart Rate History Buffer
const hrHistory: {time: number, value: number}[] = [];

const initCharts = () => {
  if (heartChart.value) {
    heartInstance = echarts.init(heartChart.value);
    heartInstance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', scale: true, name: 'BPM', min: 40 }, // Dynamic scale
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#F56C6C' }
      }],
      animation: false
    });
  }

  if (scgChart.value) {
    scgInstance = echarts.init(scgChart.value);
    scgInstance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [], show: false },
      yAxis: { type: 'value', scale: true }, // Dynamic scale
      series: [{
        data: [],
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#E6A23C' }
      }],
      animation: false
    });
  }
};

const updateHeartChart = () => {
  if (heartInstance) {
    if (!isInBed.value) {
         // Clear chart or show empty
         // heartInstance.setOption({ series: [{ data: [] }] });
         return; 
    }
    const points = hrHistory.map(item => [item.time, item.value]);
    heartInstance.setOption({
      series: [{ data: points }]
    });
  }
};

const getStressType = (level: string) => {
  if (level === '低') return 'success';
  if (level === '中') return 'warning';
  return 'danger';
};

onMounted(() => {
  initCharts();
  
  setupIPCListeners({
    onHeartRate: (data: HeartRateData) => {
      if (!isInBed.value) return;

      currentHeartRate.value = data.heart_rate;
      stressIndex.value = data.stress_index;
      stressLevel.value = data.stress_level;
      
      // Update history
      const now = Date.now();
      hrHistory.push({ time: now, value: data.heart_rate });
      // Keep last 5 minutes (300 seconds)
      if (hrHistory.length > 300) {
        hrHistory.shift();
      }
      
      // Filter out old points
      while(hrHistory.length > 0 && now - hrHistory[0].time > 300000) {
        hrHistory.shift();
      }
      
      updateHeartChart();
    },
    onSCG: (data: SCGData) => {
      if (!isInBed.value) {
          if (scgInstance) scgInstance.setOption({ series: [{ data: [] }] });
          return;
      }

      isArrhythmia.value = data.isArrhythmia;
      
      if (scgInstance && data.scg_waveform) {
        const xData = Array.from({ length: data.scg_waveform.length }, (_, i) => i);
        scgInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: data.scg_waveform }]
        });
      }
    },
    onHumanCheck: (data: HumanCheckData) => {
        isInBed.value = (data.status === 'presence');
    }
  });
});

onUnmounted(() => {
  heartInstance?.dispose();
  scgInstance?.dispose();
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
