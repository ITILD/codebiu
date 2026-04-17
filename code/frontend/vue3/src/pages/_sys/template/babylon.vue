<template>
  <!-- 场景-->
  <div w-200 h-200 overflow-hidden relative bg-blue>
    <div id="canvasP" w-full h-full absolute>
      <canvas id="glDom" w-full h-full></canvas>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import {
  Scene,
} from 'babylonjs'
// img
import { BaseScene } from './babylon-start-page/BaseScene'
let scene: Scene | undefined
let baseScene: BaseScene
// 创建一个56个三维数组
const faces:number[][] = []
// 初始化56个三维数组
for (let i = 0; i < 56; i++) {
  faces.push([0, 0, 0])
}
// vue
onMounted(() => {
  initMap()
  // 每秒更新一次数组值
  updateInterval = window.setInterval(updateFaces, 1000)
})
const initMap = () => {
  baseScene = new BaseScene('glDom')
  baseScene.observeInit('canvasP')
  scene = baseScene.scene
  // 初始化时调用 initPoints 方法创建点
  baseScene.initPoints(faces)
}

// 数组值每秒随机变化
let updateInterval: number

// 随机更新数组值的函数
const updateFaces = () => {
  for (let i = 0; i < faces.length; i++) {
    faces[i] = [
      Math.random(),
      Math.random(),
      Math.random()
    ]
  }
  // 更新点
  baseScene.updatePoints(faces)
}

onBeforeUnmount(() => {
  // 清理定时器
  clearInterval(updateInterval)
  if (scene) {
    scene.dispose()
  }
})
</script>

<style scoped></style>
