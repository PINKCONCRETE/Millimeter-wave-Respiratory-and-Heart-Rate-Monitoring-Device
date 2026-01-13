<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import SCGCard from './components/SCGCard.vue';
import BreathCard from './components/BreathCard.vue';
import HeartRateCard from './components/HeartRateCard.vue';
import HRVCard from './components/HRVCard.vue';
import { setupIPCListeners, type HumanCheckData, type HeartRateData } from './utils/ipc';

const componentMap = {
  scg: SCGCard,
  breath: BreathCard,
  hr: HeartRateCard,
  hrv: HRVCard
};

const getComponent = (id: string) => {
    return componentMap[id as keyof typeof componentMap];
};

const isInBed = ref(true);
const layoutMode = ref('grid');
const focusedId = ref('scg');
const cardOrder = ref(['scg', 'breath', 'hr', 'hrv']);
const currentHeartRate = ref(0);

const layoutClass = computed(() => {
  return {
    'layout-grid': layoutMode.value === 'grid',
    'layout-focus': layoutMode.value === 'focus'
  };
});

const setFocus = (id: string) => {
    // Optional: Clicking still promotes to main in focus mode?
    // Or just let drag handle it.
    // User asked to "change to drag", but keeping click is harmless if it logic matches.
    // Let's make click move the clicked item to position 0 if in focus mode.
    if (layoutMode.value === 'focus') {
        const index = cardOrder.value.indexOf(id);
        if (index !== 0) {
            // Move to front
            const newOrder = [...cardOrder.value];
            newOrder.splice(index, 1);
            newOrder.unshift(id);
            cardOrder.value = newOrder;
        }
    }
    focusedId.value = id;
};

// Drag and Drop Logic
let draggedId: string | null = null;

const onDragStart = (id: string, event: DragEvent) => {
    draggedId = id;
    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
    }
};

const onDrop = (targetId: string) => {
    if (draggedId && draggedId !== targetId) {
        const fromIndex = cardOrder.value.indexOf(draggedId);
        const toIndex = cardOrder.value.indexOf(targetId);
        
        const newOrder = [...cardOrder.value];
        // Swap or move? 
        // Swap is usually more intuitive for a fixed grid.
        newOrder[fromIndex] = targetId;
        newOrder[toIndex] = draggedId;
        
        cardOrder.value = newOrder;
    }
    draggedId = null;
};

onMounted(() => {
    setupIPCListeners({
        onHumanCheck: (data: HumanCheckData) => {
            if (data.has_human !== undefined) isInBed.value = data.has_human;
        },
        onHeartRate: (data: HeartRateData) => {
            currentHeartRate.value = data.heart_rate;
        }
    });
});
</script>

<template>
  <el-container class="layout-container">
    <el-header class="app-header">
      <div class="header-content">
        <div class="heart-rate-display">
          <div class="heart-rate-label">心率</div>
          <div class="heart-rate-value" v-if="isInBed">{{ Math.round(currentHeartRate) }}</div>
          <div class="heart-rate-status" v-else>已离开</div>
          <div class="heart-rate-unit" v-if="isInBed">bpm</div>
        </div>
        <h2>毫米波生命体征监测系统</h2>
        <div class="spacer"></div>
        <div class="layout-controls">
          <el-radio-group v-model="layoutMode" size="small">
            <el-radio-button label="grid">2x2 Grid</el-radio-button>
            <el-radio-button label="focus">1+3 Focus</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-header>
    
    <el-main class="app-main">
      <div class="dashboard-grid" :class="layoutClass">
        <div v-for="(id, index) in cardOrder" 
             :key="id"
             class="grid-item" 
             :class="`item-${index + 1}`" 
             draggable="true"
             @dragstart="onDragStart(id, $event)"
             @dragover.prevent
             @drop="onDrop(id)"
             @click="setFocus(id)">
            <component :is="getComponent(id)" :isInBed="isInBed" />
        </div>
      </div>
    </el-main>
  </el-container>
</template>

<style>
/* Global resets if needed */
body {
  margin: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}
</style>

<style scoped>
.layout-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  padding: 0 20px;
  height: 60px;
}

.header-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.spacer {
    flex: 1;
}

.heart-rate-display {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-right: 30px;
}

.heart-rate-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.heart-rate-value {
  font-size: 42px;
  font-weight: 700;
  color: #F56C6C;
  line-height: 1;
  font-family: 'Arial', sans-serif;
  letter-spacing: -1px;
}

.heart-rate-unit {
  font-size: 16px;
  color: #909399;
  font-weight: 500;
}
heart-rate-status {
  font-size: 18px;
  color: #909399;
  font-weight: 500;
}

.
.layout-controls {
  margin-right: 30px;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  flex: 1;
  overflow: hidden; /* Prevent main scroll, grid handles it if needed or fit to screen */
}

.dashboard-grid {
    display: grid;
    gap: 20px;
    height: 100%;
    width: 100%;
    /* Default Grid: 2x2 */
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    grid-template-areas: 
        "item1 item2"
        "item3 item4";
    transition: all 0.5s ease;
}

/* 2x2 Layout */
.layout-grid .item-1 { grid-area: item1; }
.layout-grid .item-2 { grid-area: item2; }
.layout-grid .item-3 { grid-area: item3; }
.layout-grid .item-4 { grid-area: item4; }

/* Focus Layout: 1 Large on Left, 3 Small on Right */
.layout-focus {
    grid-template-columns: 3fr 1fr;
    grid-template-rows: 1fr 1fr 1fr;
    grid-template-areas: 
        "main side1"
        "main side2"
        "main side3";
}

.layout-focus .item-1 { grid-area: main; }
.layout-focus .item-2 { grid-area: side1; }
.layout-focus .item-3 { grid-area: side2; }
.layout-focus .item-4 { grid-area: side3; }

.grid-item {
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
    overflow: hidden;
    height: 100%; /* Fill grid cell */
    transition: all 0.5s ease; /* Smooth transition for position changes */
    cursor: grab;
}

.grid-item:active {
    cursor: grabbing;
}
</style>
