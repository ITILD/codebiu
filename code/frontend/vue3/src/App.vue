<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <Suspense>
    <template #default>
      <div h-screen flex flex-col>
        <SysHeader h-14 md:h-16 bg-deep-1 z-11 shadow shrink-0 />
        <main flex flex-1 min-h-0>
          <RouterView />
        </main>
        <SysFooter mx-auto w-full p-2 lg:py-2 bg-deep-0 z-10 shrink-0 />
      </div>
    </template>
    <template #fallback>
      <div h-screen flex items-center justify-center>
        <el-icon :size="40" class="is-loading">
          <Loading />
        </el-icon>
      </div>
    </template>
  </Suspense>
</template>
