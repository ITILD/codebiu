<template>
    <!-- server 页-->
    <!-- 内容 -->
    <div flex w-full>
        <!-- 左侧菜单 -->
        <el-menu h-full :default-active="routerStore.routerPath.now" :router="true" overflow-y-auto
            :collapse="isCollapse" :class="!isCollapse ? 'w-60' : ''" @select="handleSelect">
            <!-- Logo 区域（折叠时隐藏文字） -->
            <div flex items-center justify-between p-3 border-b h-12>
                <div flex items-center transition-all duration-300 ease-in-out>
                    <transition name="fade" mode="out-in">
                        <span v-if="!isCollapse" class="pl-4 text-xl font-bold whitespace-nowrap">Server State</span>
                    </transition>
                </div>
                <el-button transition-all duration-300 hover:scale-110 @click="isCollapse = !isCollapse"
                    :icon="isCollapse ? DArrowRight : DArrowLeft" plain />
            </div>
            <!-- 菜单项 -->
            <template v-for="item in menuItems" :key="item.index">
                <el-menu-item v-if="!item.children" :index="item.index" :disabled="item.disabled">
                    <el-icon v-if="item.icon">
                        <component :is="item.icon" />
                    </el-icon>
                    <template #title>{{ item.title }}</template>
                </el-menu-item>

                <el-sub-menu v-else :index="item.index">
                    <template #title>
                        <el-icon v-if="item.icon">
                            <component :is="item.icon" />
                        </el-icon>
                        <span>{{ item.title }}</span>
                    </template>

                    <template v-for="child in item.children" :key="child.index">
                        <el-menu-item v-if="!child.children" :index="child.index" :disabled="child.disabled">
                            {{ child.title }}
                        </el-menu-item>

                        <el-sub-menu v-else :index="child.index">
                            <template #title>{{ child.title }}</template>
                            <el-menu-item v-for="grandChild in child.children" :key="grandChild.index"
                                :index="grandChild.index" :disabled="grandChild.disabled">
                                {{ grandChild.title }}
                            </el-menu-item>
                        </el-sub-menu>
                    </template>
                </el-sub-menu>
            </template>
        </el-menu>
        <!-- 右侧菜单 -->
        <div flex-1 min-w-0 overflow-auto>
            <!-- flex剩余 -->
            <router-view class="w-full h-full"></router-view>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import {
    Document,
    Menu,
    Location,
    Setting,
    DArrowRight,
    DArrowLeft
} from '@element-plus/icons-vue'
import { RouterStore } from '@/stores/router'

// 初始化路由存储
const routerStore = RouterStore()

// 菜单折叠状态
const isCollapse = ref(true)

// 菜单项配置
const menuItems = ref([
    {
        index: '/_server',
        icon: Location,
        title: 'Overview',
        disabled: false,
        children: null
    },
    {
        index: '/db',
        title: 'DataBase',
        icon: Setting,
        children: [
            {
                index: '/_server/database/overview',
                title: 'overview',
                disabled: false,
                children: null
            },
            {
                index: '/_server/database/template',
                title: 'template',
                disabled: false,
                children: null
            }
        ]
    },
    {
        index: '/ai',
        title: 'AI',
        icon: Setting,
        children: [
            {
                index: '/_server/ai/ocr',
                title: 'ocr',
                disabled: false,
                children: null
            }
        ]
    },
    {
        index: '/_server/test',
        title: 'test',
        icon: Menu,
        disabled: false,
        children: null
    },
    {
        index: '4',
        title: 'no_page',
        icon: Document,
        disabled: false,
        children: null
    },
    {
        index: '5',
        title: 'disabled',
        icon: Document,
        disabled: true,
        children: null
    }
])

// 菜单选择处理
const handleSelect = (index: string) => {
    console.log('选中菜单:', index)
}
</script>

<style scoped>
/* 使用CSS类替代属性选择器以确保兼容性 */
:deep(.el-menu) {
    height: 100%;
}
</style>
