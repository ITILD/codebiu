<template>
  <div p-4 flex flex-wrap gap-4>
    <!-- 示例1: 左1/3 + 右2/3 -->
    <div class="w-full md:w-1/3" h-48 bg-gray-900 flex p-1 rounded>
      <div class="w-1/3" bg-gray-100 rounded flex items-center justify-center>Left Panel</div>
      <div flex-1 bg-gray-200 rounded ml-1 flex items-center justify-center>Right Panel</div>
    </div>

    <!-- 示例2: 左1/3 + 右2/3 上下分割 -->
    <div class="w-full md:w-1/3" h-48 bg-gray-900 flex p-1 rounded>
      <div class="w-1/3" bg-gray-100 rounded flex items-center justify-center>Left Panel</div>
      <div flex-1 bg-gray-200 rounded ml-1 flex flex-col>
        <div class="h-[90%]" bg-gray-300 rounded flex items-center justify-center>Up Panel (90%)</div>
        <div flex-1 bg-gray-400 rounded mt-1 flex items-center justify-center>Down Panel (10%)</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
