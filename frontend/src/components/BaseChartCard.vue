<template>
  <el-card class="box-card" shadow="hover" :body-style="{ padding: '0px', flex: 1, display: 'flex', flexDirection: 'column' }">
    <template #header>
      <div class="card-header">
        <div class="header-left">
            <span class="title">{{ title }}</span>
        </div>
        <div class="controls" style="display: flex; align-items: center; gap: 10px; margin-left: 20px;">
            <div class="control-group">
                <span style="font-size: 12px; margin-right: 5px;">Window:</span>
                <el-input-number 
                    v-model="localWindowSize" 
                    size="small" 
                    :step="1000" 
                    :min="1000" 
                    style="width: 100px" 
                    @change="handleWindowChange"
                    controls-position="right"
                >
                    <template #suffix>ms</template>
                </el-input-number>
            </div>
            <div class="control-group" style="display: flex; align-items: center;">
                <span style="font-size: 12px; margin-right: 5px;">Y-Axis:</span>
                <el-switch 
                    v-model="localAutoScaleY" 
                    size="small"
                    active-text="Auto" 
                    inactive-text="Manual" 
                    @change="handleAutoScaleChange"
                />
                <div v-if="!localAutoScaleY" style="display: flex; align-items: center; margin-left: 5px;">
                    <el-input-number v-model="localManualYMin" size="small" :step="0.1" controls-position="right" style="width: 70px" @change="handleRangeChange" />
                    <span style="margin: 0 5px">-</span>
                    <el-input-number v-model="localManualYMax" size="small" :step="0.1" controls-position="right" style="width: 70px" @change="handleRangeChange" />
                </div>
            </div>
            <slot name="extra-controls"></slot>
        </div>
        <div class="stats" style="margin-left: auto;">
            <slot name="stats"></slot>
        </div>
      </div>
    </template>
    <div class="chart-content">
      <div ref="chartDiv" class="chart-div"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

const props = defineProps<{
  title: string;
  windowSize: number;
  autoScaleY: boolean;
  manualYMin: number;
  manualYMax: number;
}>();

const emit = defineEmits<{
  (e: 'update:windowSize', value: number): void;
  (e: 'update:autoScaleY', value: boolean): void;
  (e: 'update:manualYMin', value: number): void;
  (e: 'update:manualYMax', value: number): void;
  (e: 'chart-ready', div: HTMLElement): void;
}>();

const localWindowSize = ref(props.windowSize);
const localAutoScaleY = ref(props.autoScaleY);
const localManualYMin = ref(props.manualYMin);
const localManualYMax = ref(props.manualYMax);
const chartDiv = ref<HTMLElement | null>(null);

watch(() => props.windowSize, (val) => localWindowSize.value = val);
watch(() => props.autoScaleY, (val) => localAutoScaleY.value = val);
watch(() => props.manualYMin, (val) => localManualYMin.value = val);
watch(() => props.manualYMax, (val) => localManualYMax.value = val);

const handleWindowChange = (val: number) => emit('update:windowSize', val);
const handleAutoScaleChange = (val: boolean) => emit('update:autoScaleY', val);
const handleRangeChange = () => {
    emit('update:manualYMin', localManualYMin.value);
    emit('update:manualYMax', localManualYMax.value);
};

onMounted(() => {
    if (chartDiv.value) {
        emit('chart-ready', chartDiv.value);
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
  height: 30px; 
}
.header-left {
  display: flex;
  align-items: center;
}
.title {
  font-weight: bold;
  font-size: 16px;
}
.chart-content {
  flex: 1;
  min-height: 0; 
  position: relative;
}
.chart-div {
  width: 100%;
  height: 100%;
}
.stats {
    display: flex;
    align-items: center;
}
</style>
