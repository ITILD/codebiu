<template>
  <div p-4 md:p-6>
    <h2 text-xl font-bold mb-4>数据库概览</h2>
    <el-row :gutter="16">
      <el-col v-for="item in tables" :key="item.path" :xs="24" :sm="12" :md="8" mb-4>
        <el-card shadow="hover" cursor-pointer @click="router.push(item.path)">
          <div flex items-center gap-3 p-2>
            <el-icon :size="28" :class="item.color">
              <component :is="item.icon" />
            </el-icon>
            <div>
              <div font-semibold>{{ item.title }}</div>
              <div text-xs text-gray-400>{{ item.desc }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import { User, DocumentCopy, Setting } from '@element-plus/icons-vue'

const router = useRouter()

const tables = [
  { path: '/_sys/database/user', title: '用户数据', desc: '用户信息管理', icon: markRaw(User), color: 'text-blue-500' },
  { path: '/_sys/database/dict', title: '字段表管理', desc: '数据字典管理', icon: markRaw(Setting), color: 'text-purple-500' },
]
</script>
