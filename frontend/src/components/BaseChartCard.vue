<template>
  <el-card class="box-card" shadow="hover" :body-style="{ padding: '0px', flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }">
    <template #header>
      <div class="card-header">
        <div class="header-left">
            <span class="title">{{ title }}</span>
        </div>
        <div class="controls" style="display: flex; align-items: center; gap: 10px; margin-left: 20px;">
            <div class="control-group" v-if="showWindowControl">
                <span style="font-size: 12px; margin-right: 5px;">Window(s):</span>
                <el-input-number 
                    v-model="internalWindowSize" 
                    size="small" 
                    :min="1" 
                    :step="1" 
                    controls-position="right" 
                    style="width: 80px" 
                    @change="handleWindowChange"
                />
            </div>
            <div class="control-group" style="display: flex; align-items: center;" v-if="showYAxisControl">
                <span style="font-size: 12px; margin-right: 5px;">Y:</span>
                <el-switch 
                    v-model="autoScaleY" 
                    size="small"
                    active-text="Auto" 
                    inactive-text="Man" 
                    @change="handleYAxisChange"
                />
                <div v-if="!autoScaleY" style="display: flex; align-items: center; margin-left: 5px;">
                    <el-input-number v-model="manualYMin" size="small" :step="0.1" controls-position="right" style="width: 70px" @change="handleYAxisChange" />
                    <span style="margin: 0 5px">-</span>
                    <el-input-number v-model="manualYMax" size="small" :step="0.1" controls-position="right" style="width: 70px" @change="handleYAxisChange" />
                </div>
            </div>
        </div>
        <div class="stats" style="margin-left: auto; display: flex; align-items: center;">
            <slot name="stats-extra"></slot>
            <el-tag v-for="stat in stats" :key="stat.label" size="small" :type="stat.type" style="margin-left: 8px">
                {{ stat.label }}: {{ stat.value }}
            </el-tag>
        </div>
      </div>
    </template>
    <div class="chart-content" style="flex: 1; min-height: 0;">
      <div ref="chartRef" class="chart-div" style="width: 100%; height: 100%;"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';

interface StatItem {
    label: string;
    value: string | number;
    type: 'success' | 'warning' | 'info' | 'danger' | 'primary';
}

const props = defineProps<{
    title: string;
    stats?: StatItem[];
    initialWindowSeconds?: number;
    showWindowControl?: boolean;
    showYAxisControl?: boolean;
}>();

const emit = defineEmits<{
    (e: 'init', instance: echarts.ECharts): void;
    (e: 'window-change', seconds: number): void;
    (e: 'y-axis-change', auto: boolean, min: number, max: number): void;
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const internalWindowSize = ref(props.initialWindowSeconds || 10);
const autoScaleY = ref(true);
const manualYMin = ref(-1.0);
const manualYMax = ref(1.0);

const initChart = () => {
    if (chartRef.value) {
        chartInstance = echarts.init(chartRef.value);
        emit('init', chartInstance);
        
        // Resize observer
        const resizeObserver = new ResizeObserver(() => {
            chartInstance?.resize();
        });
        resizeObserver.observe(chartRef.value);
    }
};

const handleWindowChange = () => {
    emit('window-change', internalWindowSize.value);
};

const handleYAxisChange = () => {
    emit('y-axis-change', autoScaleY.value, manualYMin.value, manualYMax.value);
};

onMounted(() => {
    initChart();
});

onUnmounted(() => {
    chartInstance?.dispose();
});

defineExpose({
    chartInstance
});
</script>

<style scoped>
.box-card {
  height: 100%;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 24px; /* Compact header */
}
.title {
    font-weight: bold;
    font-size: 14px;
}
.chart-content {
    padding: 10px;
}
</style>