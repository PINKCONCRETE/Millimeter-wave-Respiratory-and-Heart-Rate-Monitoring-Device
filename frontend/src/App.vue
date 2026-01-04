<template>
  <el-container class="layout-container">
    <el-header class="app-header">
      <div class="header-content">
        <h2>毫米波生命体征监测系统</h2>
        <div class="spacer"></div>
        <el-input-number v-model="uid" :min="0" label="用户ID" size="small" />
      </div>
    </el-header>
    
    <el-main class="app-main">
      <div class="single-view">
        <SCGCard :uid="uid" :is-in-bed="isInBed" />
      </div>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import SCGCard from './components/SCGCard.vue';
import { setupIPCListeners, type HumanCheckData } from './utils/ipc';

const uid = ref(0);
const isInBed = ref(true);

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
  padding: 20px;
  background-color: #f0f2f5;
  flex: 1;
  overflow: hidden;
}

.single-view {
  height: 100%;
  width: 100%;
}
</style>
