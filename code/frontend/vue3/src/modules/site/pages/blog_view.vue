<template>
  <div class="p-4 md:p-6 w-full">
    <div class="flex flex-col lg:flex-row gap-4 items-start">
      <!-- 主内容区: 文章列表 / 阅读视图 -->
      <div class="w-full min-w-0 flex-1">
        <!-- 阅读视图: 点击文章进入 -->
        <article v-if="reading" class="rounded-xl border border-note bg-note-card shadow-note p-5 md:p-8">
          <el-button size="small" text :icon="ArrowLeft" @click="closeRead">返回列表</el-button>
          <h1 class="mt-3 text-2xl font-bold text-note">{{ reading.title }}</h1>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-note-sub">
            <el-tag v-if="reading.category" size="small" effect="plain">{{ reading.category }}</el-tag>
            <span>{{ formatDateTime(reading.updated_at) }}</span>
            <span v-if="reading.source_type === 'url'" class="flex items-center gap-1">
              <i class="i-ep-link" /> 外链文章
            </span>
          </div>
          <el-divider />

          <!-- 外链文章: 跳转卡片 -->
          <div
            v-if="reading.source_type === 'url'"
            class="rounded-lg border border-dashed border-note-green bg-note-tint/50 p-4 text-center"
          >
            <p class="text-sm text-note-sub">本文为外部链接文章</p>
            <p class="mt-1 truncate text-xs text-note-green">{{ reading.url }}</p>
            <el-button class="mt-3" type="primary" plain @click="openUrl(reading.url)">
              访问原文 <i class="i-ep-top-right ml-1" />
            </el-button>
          </div>
          <!-- markdown 正文渲染 -->
          <MarkdownView v-else :content="reading.content" class="mt-4" />
        </article>

        <!-- 列表视图: 已发布文章卡片流 -->
        <template v-else>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-lg font-bold text-note">博文</h2>
            <el-input
              v-model="keyword"
              placeholder="搜索文章..."
              clearable
              class="max-w-[220px]"
              :prefix-icon="Search"
              @input="debouncedFetch"
            />
          </div>

          <div v-loading="loading" class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              v-for="post in posts"
              :key="post.id"
              type="button"
              class="rounded-xl border border-note bg-note-card shadow-note p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md"
              @click="openRead(post)"
            >
              <div class="flex items-center gap-2">
                <h3 class="truncate text-base font-bold text-note">{{ post.title }}</h3>
                <i v-if="post.source_type === 'url'" class="i-ep-link shrink-0 text-note-green" />
              </div>
              <p class="mt-1.5 text-sm text-note-sub line-clamp-2">
                {{ post.source_type === 'url' ? post.url : excerpt(post.content, 120) }}
              </p>
              <div class="mt-2 flex items-center gap-2 text-xs text-note-sub/80">
                <el-tag v-if="post.category" size="small" effect="plain">{{ post.category }}</el-tag>
                <span>{{ formatDate(post.updated_at) }}</span>
              </div>
            </button>
          </div>
          <el-empty v-if="!loading && posts.length === 0" description="暂无已发布文章" />

          <!-- 加载更多 -->
          <div v-if="hasMore" class="mt-4 text-center">
            <el-button :loading="loadingMore" plain @click="loadMore">加载更多</el-button>
          </div>
        </template>
      </div>

      <!-- 右上角备忘日历 + 记账迷你卡: 桌面侧栏(sticky), 移动端抽屉 -->
      <aside class="hidden lg:block w-[360px] shrink-0 sticky top-20 space-y-4">
        <MemoCalendar />
        <LedgerMiniCard />
      </aside>
    </div>

    <!-- 移动端浮动按钮 → 日历抽屉 -->
    <el-button
      class="lg:hidden fixed bottom-6 right-6 z-50!"
      type="primary"
      circle
      size="large"
      :icon="Calendar"
      @click="calendarDrawer = true"
    />
    <!-- append-to-body 避免父容器 transform/overflow 影响弹出层; 手机按屏宽自适应 -->
    <el-drawer
      v-model="calendarDrawer"
      title="备忘日历"
      :size="isMd ? '440px' : '94%'"
      append-to-body
    >
      <div class="space-y-4">
        <MemoCalendar />
        <LedgerMiniCard />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Calendar, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useDebounceFn } from '@vueuse/core'
import { listPublishedPosts } from '../api/blog'
import type { BlogPost } from '../types/blog'
import { excerpt } from '../composables/useCalendar'
import MarkdownView from '../components/MarkdownView.vue'
import MemoCalendar from '../components/MemoCalendar.vue'
import LedgerMiniCard from '../components/LedgerMiniCard.vue'
import { useResponsive } from '@/common/composables/useResponsive'

// 响应式断点(手机抽屉宽度自适应)
const { isMd } = useResponsive()

// 列表状态
const posts = ref<BlogPost[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const keyword = ref('')
const loading = ref(false)
const loadingMore = ref(false)

const hasMore = computed(() => posts.value.length < total.value)

// 拉取已发布文章(page=1 重新加载; 追加模式用于加载更多)
async function fetchPosts(append = false) {
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const resp = await listPublishedPosts({
      page: page.value,
      size: pageSize,
      keyword: keyword.value.trim() || undefined,
    })
    posts.value = append ? [...posts.value, ...resp.items] : resp.items
    total.value = resp.total
  } catch (error) {
    console.error('获取文章列表失败:', error)
    ElMessage.error('获取文章列表失败，请重试')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const debouncedFetch = useDebounceFn(() => {
  page.value = 1
  fetchPosts()
}, 300)

function loadMore() {
  page.value += 1
  fetchPosts(true)
}

// 阅读视图(支持 ?id= 直接定位文章)
const route = useRoute()
const router = useRouter()
const reading = ref<BlogPost | null>(null)

/** 移动端日历/记账抽屉开关 */
const calendarDrawer = ref(false)

async function openRead(post: BlogPost) {
  reading.value = post
  // 同步 URL 查询参数, 便于分享/刷新定位
  await router.replace({ query: { id: post.id } })
}

function closeRead() {
  reading.value = null
  router.replace({ query: {} })
}

/** 外链文章跳转(新窗口) */
function openUrl(url: string | null) {
  if (url) window.open(url, '_blank', 'noopener')
}

const formatDate = (v: string) => new Date(v).toLocaleDateString('zh-CN')
const formatDateTime = (v: string) => new Date(v).toLocaleString('zh-CN')

onMounted(async () => {
  fetchPosts()
  // URL 带 id 时直接进入阅读视图
  const id = route.query.id as string | undefined
  if (id) {
    try {
      const { getBlogPost } = await import('../api/blog')
      reading.value = await getBlogPost(id)
    } catch {
      // 文章不可见/不存在时保持列表视图
    }
  }
})
</script>
