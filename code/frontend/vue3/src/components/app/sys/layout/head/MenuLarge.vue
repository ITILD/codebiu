<template>
  <!-- 顶部导航栏 -->
  <!-- 启用 vue-router 模式。 启用该模式会在激活导航时以 index 作为 path 进行路由跳转  -->
  <!-- ellipsis 多余子项  collapse外部传入是否水平 -->
  <el-menu :default-active="routerStore.routerPath.now" :router=true :mode="mode ? 'horizontal' : 'vertical'"
    @select="handleSelect" :ellipsis=false>
    <template v-for="item in menuData" :key="item.index">
      <el-menu-item v-if="!item.children" :index="item.index" :disabled="item.disabled">
        {{ item.title }}
      </el-menu-item>

      <el-sub-menu v-else :index="item.index">
        <template #title>{{ item.title }}</template>

        <template v-for="child in item.children" :key="child.index">
          <el-menu-item v-if="!child.children" :index="child.index" :disabled="child.disabled">
            {{ child.title }}
          </el-menu-item>

          <el-sub-menu v-else :index="child.index">
            <template #title>{{ child.title }}</template>
            <el-menu-item v-for="grandChild in child.children" :key="grandChild.index" :index="grandChild.index"
              :disabled="grandChild.disabled">
              {{ grandChild.title }}
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-sub-menu>
    </template>
  </el-menu>
</template>
<script setup lang="ts">
import { RouterStore } from '@/stores/router'
// activeIndex 菜单激活项 routerStore.routerPath.now
const routerStore = RouterStore()
// 外部传入是否水平
defineProps({
  mode: {
    type: Boolean,
    default: true
  }
})

const menuData = [
  {
    index: '/_sys',
    title: 'Sys',
    disabled: false,
    children: null
  },
  {
    index: '/_dev',
    title: 'Dev',
    children: [
      {
        index: '/component_mini',
        title: 'component_mini',
        disabled: false,
        children: null
      },
      {
        index: '/component_lib',
        title: 'component_lib',
        disabled: false,
        children: null
      },
      {
        index: '2-4',
        title: 'item four',
        children: [
          {
            index: '2-4-1',
            title: 'item one',
            disabled: false,
            children: null
          },
          {
            index: '2-4-2',
            title: 'item two',
            disabled: false,
            children: null
          }
        ]
      }
    ]
  },
  {
    index: 'blog',
    title: 'Blog',
    disabled: false,
    children: null
  },
  {
    index: '4',
    title: 'Info',
    disabled: false,
    children: null
  }
]

const handleSelect = (index: string) => {
  console.log('selected:', index)
  // todo 根据目标路径 设置一些主题
}
</script>
<style scoped>
/* menu样式覆盖 */
.el-menu-home {
  /* 背景透明 */
  background-color: transparent;
  /* 去除下方边框阴影 */
  border-bottom: none;
}
</style>
