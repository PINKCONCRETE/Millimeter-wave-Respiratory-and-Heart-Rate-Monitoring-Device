<template>
  <el-container class="layout-container">
    <el-header style="background-color: #545c64; color: white; display: flex; align-items: center;">
      <h2>毫米波生命体征监测系统</h2>
      <div style="flex-grow: 1;"></div>
      <el-input-number v-model="uid" :min="0" label="用户ID" size="small" />
    </el-header>
    
    <el-main>
      <el-row :gutter="20">
        <el-col :span="12">
          <BreathMonitor :uid="uid" />
        </el-col>
        <el-col :span="12">
          <HeartMonitor :uid="uid" />
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import BreathMonitor from './components/BreathMonitor.vue';
import HeartMonitor from './components/HeartMonitor.vue';

const uid = ref(0);
</script>

<style>
body {
  margin: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  background-color: #f0f2f5;
}
.layout-container {
  height: 100vh;
}
</style>
