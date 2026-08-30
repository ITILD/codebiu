<template>
  <div w-full>
    <!-- 管理后台内容容器(侧边栏已全局化于 App.vue, 高度由文档流决定)
         注意: 注释必须写在根元素内部 —— 模板顶层注释会使组件成为
         Fragment 多根, 与 App.vue 的路由 Transition 冲突导致页面空白 -->
    <RouterView />
  </div>
</template>

<script lang="ts" setup>
// 全局布局说明:
// 吸顶导航(SysHeader)与左侧模块列表(SysSidebar)在 App.vue 中全局渲染,
// 此组件仅作为 /_sys 嵌套路由的内容承载容器, 页面随文档流自然滚动。
</script>
