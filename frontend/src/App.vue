<template>
  <el-container class="layout-container">
    <el-header class="app-header">
      <div class="header-content">
        <h2>毫米波生命体征监测系统</h2>
        <div class="spacer"></div>
        <div class="layout-controls" style="margin-right: 20px;">
          <el-radio-group v-model="layoutMode" size="small">
            <el-radio-button label="grid">2x2 Grid</el-radio-button>
            <el-radio-button label="focus">1+3 Focus</el-radio-button>
          </el-radio-group>
        </div>
        <el-input-number v-model="uid" :min="0" label="用户ID" size="small" />
      </div>
    </el-header>
    
    <el-main class="app-main">
      <div class="dashboard-grid" :class="layoutClass">
        <div class="grid-item" 
             :class="getItemClass('scg')" 
             draggable="true"
             @dragstart="onDragStart('scg', $event)"
             @dragover.prevent
             @drop="onDrop('scg')"
             @click="setFocus('scg')">
            <SCGCard :isInBed="isInBed" />
        </div>
        <div class="grid-item" 
             :class="getItemClass('breath')" 
             draggable="true"
             @dragstart="onDragStart('breath', $event)"
             @dragover.prevent
             @drop="onDrop('breath')"
             @click="setFocus('breath')">
            <BreathCard :isInBed="isInBed" />
        </div>
        <div class="grid-item" 
             :class="getItemClass('hr')" 
             draggable="true"
             @dragstart="onDragStart('hr', $event)"
             @dragover.prevent
             @drop="onDrop('hr')"
             @click="setFocus('hr')">
            <HeartRateCard :isInBed="isInBed" />
        </div>
        <div class="grid-item" 
             :class="getItemClass('hrv')" 
             draggable="true"
             @dragstart="onDragStart('hrv', $event)"
             @dragover.prevent
             @drop="onDrop('hrv')"
             @click="setFocus('hrv')">
            <HRVCard :isInBed="isInBed" />
        </div>
      </div>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import SCGCard from './components/SCGCard.vue';
import BreathCard from './components/BreathCard.vue';
import HeartRateCard from './components/HeartRateCard.vue';
import HRVCard from './components/HRVCard.vue';
import { setupIPCListeners, type HumanCheckData } from './utils/ipc';

const uid = ref(0);
const isInBed = ref(true);
const layoutMode = ref('grid');
const focusedId = ref('scg');
const cardOrder = ref(['scg', 'breath', 'hr', 'hrv']);

const layoutClass = computed(() => {
  return {
    'layout-grid': layoutMode.value === 'grid',
    'layout-focus': layoutMode.value === 'focus'
  };
});

const getItemClass = (id: string) => {
    // Both modes now rely on cardOrder to determine position
    const index = cardOrder.value.indexOf(id);
    return `item-${index + 1}`;
};

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
};

const draggedId = ref<string | null>(null);

const onDragStart = (id: string, event: DragEvent) => {
    draggedId.value = id;
    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        // Optional: set drag image
    }
};

const onDrop = (targetId: string) => {
    if (draggedId.value && draggedId.value !== targetId) {
        const fromIndex = cardOrder.value.indexOf(draggedId.value);
        const toIndex = cardOrder.value.indexOf(targetId);
        
        if (fromIndex !== -1 && toIndex !== -1) {
            // Swap positions
            const newOrder = [...cardOrder.value];
            newOrder[fromIndex] = targetId;
            newOrder[toIndex] = draggedId.value;
            cardOrder.value = newOrder;
        }
    }
    draggedId.value = null;
};

onMounted(() => {
  setupIPCListeners({
    onHumanCheck: (data: HumanCheckData) => {
      isInBed.value = data.has_human;
    }
  });
});
</script>

<style>
body {
  margin: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  background-color: #f0f2f5;
  height: 100%;
  overflow: hidden;
}

.layout-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background-color: #545c64;
  color: white;
  padding: 0 20px;
  height: 60px;
}

.header-content {
  height: 100%;
  display: flex;
  align-items: center;
}

.spacer {
  flex-grow: 1;
}

.app-main {
  padding: 10px;
  background-color: #f0f2f5;
  flex: 1;
  overflow: hidden;
}

.dashboard-grid {
    display: grid;
    gap: 10px;
    height: 100%;
    width: 100%;
    transition: all 0.3s ease;
}

/* 2x2 Grid Layout */
.dashboard-grid.layout-grid {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    grid-template-areas: 
        "item1 item2"
        "item3 item4";
}

/* 1+3 Focus Layout */
.dashboard-grid.layout-focus {
    grid-template-columns: 2fr 1fr;
    grid-template-rows: 1fr 1fr 1fr;
    grid-template-areas: 
        "item1 item2"
        "item1 item3"
        "item1 item4";
}

.grid-item {
    height: 100%;
    width: 100%;
    min-height: 0; /* Prevent overflow */
    min-width: 0;
    transition: all 0.3s ease;
    cursor: pointer;
}

.item-1 { grid-area: item1; }
.item-2 { grid-area: item2; }
.item-3 { grid-area: item3; }
.item-4 { grid-area: item4; }

</style>