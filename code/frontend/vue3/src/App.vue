<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <!-- Suspense 非正常结构 弹窗类 控制类 异步加载-->
  <Suspense>
    <template #default>
      <div h-screen flex flex-col>
        <SysHeader h-20 md:h-14 bg-deep-1 z-11 shadow />
        <main flex flex-1>
          <RouterView />
        </main>
        <SysFooter mx-auto w-full p-2 lg:py-2 bg-deep-0 z-10 />
      </div>
    </template>
    <template #fallback>
      <div>Loading...</div>
    </template>
  </Suspense>
</template>

<style></style>
