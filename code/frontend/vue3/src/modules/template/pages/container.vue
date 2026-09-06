<template>
  <!-- 容器布局示例页: 演示 flex 百分比分割(主题色随 note-* 亮暗自适应) -->
  <div p-4 flex flex-wrap gap-4>
    <!-- 示例1: 左1/3 + 右2/3 -->
    <div class="w-full md:w-1/3" h-48 bg-note-tint flex p-1 rounded border border-note>
      <div class="w-1/3" bg-note-card text-note rounded flex items-center justify-center>Left Panel</div>
      <div flex-1 bg-note-soft text-note rounded ml-1 flex items-center justify-center>Right Panel</div>
    </div>

    <!-- 示例2: 左1/3 + 右2/3 上下分割 -->
    <div class="w-full md:w-1/3" h-48 bg-note-tint flex p-1 rounded border border-note>
      <div class="w-1/3" bg-note-card text-note rounded flex items-center justify-center>Left Panel</div>
      <div flex-1 bg-note-soft rounded ml-1 flex flex-col>
        <div class="h-[90%]" bg-note-card text-note rounded flex items-center justify-center>Up Panel (90%)</div>
        <div flex-1 bg-note-green text-white rounded mt-1 flex items-center justify-center>Down Panel (10%)</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
