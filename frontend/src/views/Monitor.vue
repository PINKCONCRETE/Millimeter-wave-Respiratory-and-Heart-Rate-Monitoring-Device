<template>
  <div class="monitor-container">
    <div class="header">
      <div v-if="!isPortrait" class="mode-switch">
        <button :class="{active: mode==='grid'}" @click="mode='grid'">2x2模式</button>
        <button :class="{active: mode==='main-slave'}" @click="mode='main-slave'">1+3模式</button>
      </div>
      <h1 class="title">毫米波无感健康检测</h1>
      <div class="time-display">
        <div class="date">{{ currentDate }}</div>
        <div class="time">{{ currentTime }}</div>
        <span v-if="!isInBed" class="bed-status">已离开</span>
      </div>
    </div>
    <!-- 竖屏单列模式 -->
    <div v-if="isPortrait" class="portrait-container">
      <div class="portrait-item"><HeartbeatMonitor :userId="userId" /></div>
      <div class="portrait-item"><HeartrateMonitor :userId="userId" /></div>
      <div class="portrait-item"><BreathMonitor :userId="userId" /></div>
      <div class="portrait-item"><HRVMonitor :userId="userId" /></div>
    </div>
    <!-- 横屏2×2模式 -->
    <div v-else-if="mode==='grid'" class="grid-container">
      <div class="grid-item"><HeartbeatMonitor :userId="userId" /></div>
      <div class="grid-item"><HeartrateMonitor :userId="userId" /></div>
      <div class="grid-item"><BreathMonitor :userId="userId" /></div>
      <div class="grid-item"><HRVMonitor :userId="userId" /></div>
    </div>
    <!-- 横屏1+3模式 -->
    <div v-else class="main-slave-container">
      <div class="main-panel">
        <component :is="getComponent(mainType)" :userId="userId" />
      </div>
      <div class="slave-panel">
        <div
          v-for="item in slaveList"
          :key="item.type"
          class="slave-item"
          @click="switchMain(item.type)"
        >
          <component :is="item.component" :userId="userId" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'
import HeartbeatMonitor from '@/components/HeartbeatMonitor.vue'
import HeartrateMonitor from '@/components/HeartrateMonitor.vue'
import BreathMonitor from '@/components/BreathMonitor.vue'
import HRVMonitor from '@/components/HRVMonitor.vue'
import { getBWaveform } from '@/api/breath'

const userId = ref<string | null>(null)
const currentDate = ref('')
const currentTime = ref('')
const isInBed = ref(true)
const isPortrait = ref(false)
let timer: number | null = null
let bedStatusTimer: number | null = null

const mode = ref<'grid' | 'main-slave'>('grid')
const mainType = ref<'HeartrateMonitor' | 'HeartbeatMonitor' | 'BreathMonitor' | 'HRVMonitor'>('HeartbeatMonitor')

const monitorList = [
  { type: 'HeartrateMonitor', label: '心电监测', component: HeartrateMonitor },
  { type: 'HeartbeatMonitor', label: '心率监测', component: HeartbeatMonitor },
  { type: 'BreathMonitor', label: '呼吸监测', component: BreathMonitor },
  { type: 'HRVMonitor', label: 'HRV监测', component: HRVMonitor }
]

const getComponent = (type: string) => {
  return monitorList.find(item => item.type === type)?.component
}

const slaveList = computed(() =>
  monitorList.filter(item => item.type !== mainType.value)
)

const switchMain = (type: string) => {
  mainType.value = type as any
}

const route = useRoute()
userId.value = route.params.userId as string

const updateTime = () => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const weekday = weekdays[now.getDay()]
  currentDate.value = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekday}`
  currentTime.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
}

const checkOrientation = () => {
  isPortrait.value = window.innerHeight > window.innerWidth
}

const handleOrientationChange = () => {
  // 延迟一点检查，确保orientation change完成
  setTimeout(() => {
    checkOrientation()
  }, 100)
}

const checkBedStatus = async () => {
  try {
    if (userId.value) {
      const res = await getBWaveform(userId.value)
      if (res && res.data) {
        isInBed.value = res.data.is_in_bed
      }
    }
  } catch (error) {
    console.error('获取离床状态失败:', error)
  }
}

const startCheckingBedStatus = () => {
  checkBedStatus()
  bedStatusTimer = window.setInterval(() => {
    checkBedStatus()
  }, 5000)
}

onMounted(() => {
  updateTime()
  timer = window.setInterval(() => {
    updateTime()
  }, 1000)
  startCheckingBedStatus()
  
  // 初始检查屏幕方向
  checkOrientation()
  
  // 监听窗口大小变化和方向变化
  window.addEventListener('resize', handleOrientationChange)
  window.addEventListener('orientationchange', handleOrientationChange)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (bedStatusTimer) {
    clearInterval(bedStatusTimer)
    bedStatusTimer = null
  }
  
  // 移除事件监听器
  window.removeEventListener('resize', handleOrientationChange)
  window.removeEventListener('orientationchange', handleOrientationChange)
})
</script>

<style scoped>
/* 主容器 */
.monitor-container {
  width: 100%;
  height: 100vh;
  padding: 2%;
  box-sizing: border-box;
  background-color: #f0f4f8;
  display: flex;
  flex-direction: column;
}

/* 头部区域 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 0 auto 20px;
  padding: 10px 20px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: calc(100% - 40px);
  max-width: 2000px;
  box-sizing: border-box;
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin-right: 16px;
}

.mode-switch button {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #ddd;
  background: #f8f9fa;
  cursor: pointer;
  font-size: 14px;
}

.mode-switch button.active {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.title {
  font-size: 1.5rem;
  color: #333;
  margin: 0 auto;
  font-weight: bold;
  flex: 1;
  text-align: center;
}

.time-display {
  min-width: 200px;
  text-align: right;
  display: flex;
  align-items: center;
  gap: 10px;
}

.date {
  font-size: 0.875rem;
  color: #666;
  margin-bottom: 4px;
}

.time {
  font-size: 1.25rem;
  color: #333;
  font-weight: bold;
}

.bed-status {
  color: #ff4d4f;
  font-size: 0.875rem;
  font-weight: bold;
  padding: 2px 8px;
  border-radius: 4px;
  background-color: rgba(255, 77, 79, 0.1);
}

/* 竖屏布局 */
.portrait-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: calc(100vh - 120px);
  width: calc(100% - 40px);
  max-width: 2000px;
  margin: 0 auto;
  overflow-y: auto;
}

.portrait-item {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  position: relative;
  /* height: 300px; */
  height: auto;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

/* 网格布局 */
.grid-container {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(300px, 1fr);
  gap: 20px;
  height: calc(100vh - 120px);
  width: calc(100% - 40px);
  max-width: 2000px;
  margin: 0 auto;
}

.grid-item {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  position: relative;
  min-height: 350px;
  display: flex;
  flex-direction: column;
}

/* 主从布局 */
.main-slave-container {
  display: flex;
  height: calc(100vh - 120px);
  width: calc(100% - 40px);
  max-width: 2000px;
  margin: 0 auto;
  gap: 20px;
}

.main-panel {
  flex: 2;
  min-width: 0;
  min-height: 0;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-size: 1.2rem;
}

.slave-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
  min-height: 0;
  font-size: 0.9rem;
}

.slave-item {
  flex: 1;
  min-height: 0;
  min-width: 0;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
  cursor: pointer;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 响应式设计 - 中等屏幕 */
@media screen and (max-width: 1200px) {
  .grid-container {
    grid-auto-rows: minmax(250px, 1fr);
    gap: 15px;
  }
  
  .grid-item {
    min-height: 250px;
  }
  
  .main-slave-container { 
    flex-direction: column; 
  }
  
  .main-panel, .slave-panel { 
    width: 100%; 
  }
  
  .slave-panel { 
    flex-direction: row; 
    gap: 10px; 
  }
  
  .slave-item { 
    flex: 1; 
  }
}

/* 响应式设计 - 小屏幕 */
@media screen and (max-width: 768px) {
  .header {
    flex-direction: column;
    padding: 10px;
    gap: 10px;
  }
  
  .title {
    margin-bottom: 10px;
    font-size: 1.2rem;
  }
  
  .time-display {
    width: 100%;
    justify-content: center;
  }
  
  .portrait-container {
    gap: 15px;
    width: calc(100% - 20px);
  }
  
  .portrait-item {
    height: 350px;
  }
  
  .grid-container {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 100vh;
  }
  
  .grid-item {
    min-height: 400px;
    height: auto;
  }
  
  .main-slave-container {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }
  
  .main-panel, .slave-panel {
    width: 100%;
    min-height: 0;
  }
  
  .slave-panel {
    flex-direction: row;
    gap: 10px;
  }
  
  .slave-item {
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
}

/* 响应式设计 - 超小屏幕 */
@media screen and (max-width: 480px) {
  .monitor-container {
    padding: 10px;
  }
  
  .portrait-container {
    gap: 10px;
    width: calc(100% - 20px);
  }
  
  .portrait-item {
    /* height: 320px; */
    height: auto;
  }
  
  .grid-container {
    gap: 10px;
    width: calc(100% - 20px);
  }
  
  .main-slave-container {
    gap: 10px;
    width: calc(100% - 10px);
  }
}

/* 屏幕方向 - 竖屏 */
@media screen and (orientation: portrait) {
  .portrait-container {
    height: calc(100vh - 100px);
  }
  
  .portrait-item {
    /* height: 280px; */
    height: auto;
    /* margin-bottom: 10px; */
    max-height: 30vh;
  }
  
  .header {
    padding: 8px 15px;
  }
  
  .title {
    font-size: 1.1rem;
  }
}

/* 屏幕方向 - 横屏低高度 */
@media screen and (orientation: landscape) and (max-height: 600px) {
  .grid-container {
    grid-auto-rows: minmax(200px, 1fr);
  }
  
  .grid-item {
    min-height: 200px;
  }
  
  .main-slave-container {
    height: calc(100vh - 80px);
  }
}

/* 大屏幕优化 */
@media screen and (min-width: 2000px) {
  .grid-container {
    max-width: 2400px;
  }
  
  .grid-item {
    min-height: 500px;
  }
  
  .main-slave-container {
    max-width: 2400px;
  }
  
  .main-panel, .slave-panel {
    min-height: 500px;
  }
}
</style>