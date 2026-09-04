<template>
  <div p-4 md:p-6>
    <h2 text-xl font-bold mb-4>模板示例概览</h2>
    <el-row :gutter="16">
      <el-col v-for="item in templates" :key="item.path" :xs="24" :sm="12" :md="8" :lg="6" mb-4>
        <el-card shadow="hover" cursor-pointer @click="router.push(item.path)">
          <div flex flex-col items-center p-4>
            <el-icon :size="32" mb-3 :class="item.color">
              <component :is="item.icon" />
            </el-icon>
            <span font-semibold>{{ item.title }}</span>
            <span text-xs text-gray-400 mt-1>{{ item.desc }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import { Files, Grid, Camera, Box } from '@element-plus/icons-vue'

const router = useRouter()

const templates = [
  { path: '/_sys/template/template', title: '模板管理', desc: 'CRUD 表格示例', icon: markRaw(Files), color: 'text-blue-500' },
  { path: '/_sys/template/container', title: '布局容器', desc: 'Flex 布局示例', icon: markRaw(Grid), color: 'text-green-500' },
  { path: '/_sys/template/mediapipe_face', title: '人脸识别', desc: 'MediaPipe 视觉', icon: markRaw(Camera), color: 'text-orange-500' },
  { path: '/_sys/template/babylon', title: 'Babylon 3D', desc: '3D 场景示例', icon: markRaw(Box), color: 'text-purple-500' },
]
</script>
