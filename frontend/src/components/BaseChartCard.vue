<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';

interface StatItem {
    label: string;
    value: string | number;
    type: 'success' | 'warning' | 'info' | 'danger' | 'primary';
}

const props = withDefaults(defineProps<{
    title: string;
    stats?: StatItem[];
    initialWindowSeconds?: number;
    showWindowControl?: boolean;
    showYAxisControl?: boolean;
    defaultYMin?: number;
    defaultYMax?: number;
}>(), {
    stats: () => [],
    initialWindowSeconds: 10,
    showWindowControl: false,
    showYAxisControl: true,
    defaultYMin: -1.0,
    defaultYMax: 1.0
});

const emit = defineEmits<{
    (e: 'init', instance: echarts.ECharts): void;
    (e: 'window-change', seconds: number): void;
    (e: 'y-axis-change', auto: boolean, min: number, max: number): void;
    (e: 'reset-y-axis'): void;
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const internalWindowSize = ref(props.initialWindowSeconds || 10);
const autoScaleY = ref(true);
const manualYMin = ref(props.defaultYMin ?? -1.0);
const manualYMax = ref(props.defaultYMax ?? 1.0);

const initChart = () => {
    if (chartRef.value) {
        chartInstance = echarts.init(chartRef.value);
        emit('init', chartInstance);
        
        // Resize observer
        const resizeObserver = new ResizeObserver(() => {
            chartInstance?.resize();
        });
        resizeObserver.observe(chartRef.value);
        
        onUnmounted(() => {
            resizeObserver.disconnect();
            chartInstance?.dispose();
        });
    }
};

const handleWindowChange = (val: number | undefined) => {
    if (val) emit('window-change', val);
};

const handleYAxisChange = () => {
    emit('y-axis-change', autoScaleY.value, manualYMin.value, manualYMax.value);
};

const resetYAxis = () => {
    manualYMin.value = props.defaultYMin ?? -1.0;
    manualYMax.value = props.defaultYMax ?? 1.0;
    handleYAxisChange();
    emit('reset-y-axis');
};

onMounted(() => {
    initChart();
});
</script>

<template>
  <el-card class="box-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div class="header-left">
            <span class="title">{{ title }}</span>
        </div>
        <div class="controls">
            <div class="control-group" v-if="showWindowControl">
                <el-tooltip content="Display Window Size (seconds)" placement="top">
                    <el-input-number 
                        v-model="internalWindowSize" 
                        size="small" 
                        :min="1" 
                        :step="1" 
                        controls-position="right" 
                        class="window-input"
                        @change="handleWindowChange"
                    />
                </el-tooltip>
            </div>
            <div class="control-group" v-if="showYAxisControl">
                <el-tooltip content="Auto Scale Y-Axis" placement="top">
                    <el-switch 
                        v-model="autoScaleY" 
                        size="small"
                        active-text="Auto" 
                        inactive-text="Man" 
                        inline-prompt
                        class="y-axis-switch"
                        @change="handleYAxisChange"
                    />
                </el-tooltip>
                <div v-if="!autoScaleY" class="manual-y-controls">
                    <el-input-number v-model="manualYMin" size="small" :step="0.1" controls-position="right" class="y-input" @change="handleYAxisChange" placeholder="Min"/>
                    <span class="separator">-</span>
                    <el-input-number v-model="manualYMax" size="small" :step="0.1" controls-position="right" class="y-input" @change="handleYAxisChange" placeholder="Max"/>
                    <el-button size="small" circle icon="Refresh" @click="resetYAxis" title="Reset Default" class="reset-btn" />
                </div>
            </div>
        </div>
        <div class="stats">
            <slot name="stats-extra"></slot>
            <el-tag v-for="stat in stats" :key="stat.label" size="small" :type="stat.type" class="stat-tag">
                {{ stat.label }}: {{ stat.value }}
            </el-tag>
        </div>
      </div>
    </template>
    <div class="chart-content">
      <div ref="chartRef" class="chart-div"></div>
    </div>
  </el-card>
</template>

<style scoped>
.box-card {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.box-card :deep(.el-card__body) {
    padding: 0px;
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left {
    display: flex;
    align-items: center;
}

.title {
    font-weight: bold;
}

.controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: 20px;
}

.control-group {
    display: flex;
    align-items: center;
}

.window-input {
    width: 70px;
}

.y-axis-switch {
    --el-switch-on-color: #13ce66;
    margin-right: 5px;
}

.manual-y-controls {
    display: flex;
    align-items: center;
    gap: 4px;
}

.y-input {
    width: 60px;
}

.separator {
    color: #909399;
}

.reset-btn {
    margin-left: 2px;
}

.stats {
    margin-left: auto;
    display: flex;
    align-items: center;
}

.stat-tag {
    margin-left: 8px;
}

.chart-content {
    flex: 1;
    min-height: 0;
}

.chart-div {
    width: 100%;
    height: 100%;
}
</style>
