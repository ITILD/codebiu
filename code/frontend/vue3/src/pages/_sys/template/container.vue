<template>
  <div flex>
    <div class="w-1/3 h-1/3" bg-gray-900 flex p-1>
      <!-- left: 1/3 -->
      <div class="w-1/3" bg-gray-100>Left Panel</div>

      <!-- right: 剩余 2/3 -->
      <div flex-1 bg-gray-200>Right Panel (auto fills remaining space)</div>
    </div>

    <div class="w-1/3 h-1/3" bg-gray-900 flex p-1>
      <!-- left: 1/3 -->
      <div class="w-1/3" bg-gray-100>Left Panel</div>

      <!-- right: 剩余 2/3 -->
      <div flex-1 bg-gray-200 flex flex-col>
        <!-- up: 9/10 -->
        <div class="h-9/10" bg-gray-300>Up Panel (9/10)</div>

        <!-- down: 剩余 1/10 -->
        <div flex-1 bg-gray-400>Down Panel (1/10)</div>
      </div>
    </div>
    <!-- <div class="w-1/3 h-1/3" bg-gray-900>
      <el-container>
        <el-header bg-gray-100>Header</el-header>
        <el-main bg-gray-200>Main</el-main>
      </el-container>
    </div> -->
  </div>
</template>
