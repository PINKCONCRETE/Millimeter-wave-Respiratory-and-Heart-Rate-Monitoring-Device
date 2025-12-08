<script setup lang="ts">
</script>

<template>
  <RouterView />
</template>

<style>
/* 全局样式重置 - 不要加 scoped */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow-x: hidden;
}
</style>
