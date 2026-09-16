<template>
  <div p-4 md:p-6>
    <!-- 水墨页头 -->
    <InkPageHead title="数据库概览" sub="以一页自然笔记, 整理你的数据资产" seal="览" />
    <el-row :gutter="16">
      <el-col v-for="item in tables" :key="item.path" :xs="24" :sm="12" :md="8" mb-4>
        <!-- 无边线纸片: 色差+光晕环成形, hover 抬升(garden PaperCard 纸纤维顶盖) -->
        <div
          class="paper-grain note-glow-hover"
          bg-note-card rounded-2xl p-5 cursor-pointer overflow-hidden
          duration-300 hover:-translate-y-0.5
          @click="router.push(item.path)"
        >
          <div flex items-center gap-3>
            <div flex items-center justify-center w-12 h-12 rounded-xl bg-note-tint shrink-0 :class="item.color">
              <el-icon :size="24">
                <component :is="item.icon" />
              </el-icon>
            </div>
            <div min-w-0>
              <div font-semibold text-note>{{ item.title }}</div>
              <div text-xs text-note-sub mt-0.5>{{ item.desc }}</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import { User, DocumentCopy, Setting } from '@element-plus/icons-vue'

const router = useRouter()

const tables = [
  { path: '/authorization/user', title: '用户数据', desc: '用户信息管理', icon: markRaw(User), color: 'text-[var(--note-green)]' },
  { path: '/main/dict', title: '字段表管理', desc: '数据字典管理', icon: markRaw(Setting), color: 'text-[var(--note-lotus-core)]' },
]
</script>
