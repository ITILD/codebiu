<template>
  <div w-full max-w-5xl mx-auto p-4 md:p-8>
    <!-- Hero: 自然笔记卡片(苔绿渐变+笔记本格线), 登录态感知 -->
    <section
      relative
      overflow-hidden
      rounded-2xl
      border-note
      bg-note-gradient
      p-8
      md:p-14
      mb-10
    >
      <!-- 笔记本横线纹理 -->
      <div absolute inset-0 note-lined-paper pointer-events-none />
      <!-- 右上角叶片装饰 -->
      <div absolute top-4 right-6 text-4xl md:text-5xl opacity-70 dark:opacity-90 select-none>🌿</div>

      <div relative>
        <!-- 已登录: 时段问候 + 最近访问(仅前台应用页) -->
        <template v-if="isLoggedIn">
          <h1 font-serif text-3xl md:text-5xl font-bold text-note-green mb-3>
            {{ greeting }}，{{ displayName }}
          </h1>
          <p text-base md:text-lg text-note-sub mb-6 max-w-xl leading-relaxed>
            像打理一页自然笔记一样，安放你的数据与灵感。
          </p>

          <!-- 最近访问快捷入口(过滤后台路由, 首页不出现后台相关内容) -->
          <div v-if="recentAppPages.length" mb-2>
            <p text-xs text-note-sub mb-2>最近访问</p>
            <div flex flex-wrap gap-2>
              <RouterLink
                v-for="item in recentAppPages.slice(0, 6)"
                :key="item.path"
                :to="item.path"
                px-3 py-1.5 rounded-full bg-note-card border border-note text-xs md:text-sm text-note hover:border-note-green hover:text-note-green transition-colors
              >
                {{ item.title }}
              </RouterLink>
            </div>
          </div>
        </template>

        <!-- 未登录: 品牌引导 -->
        <template v-else>
          <h1 font-serif text-3xl md:text-5xl font-bold text-note-green mb-4>
            {{ TITLE }}
          </h1>
          <p text-base md:text-lg text-note-sub mb-2 max-w-xl leading-relaxed>
            像打理一页自然笔记一样，安放你的数据与灵感。
          </p>
          <p text-sm md:text-base text-note-sub mb-2 max-w-xl>
            登录后即可使用个人小站、知识库等应用。
          </p>
        </template>
      </div>
    </section>

    <!-- 主应用入口卡(仅前台应用, 从这里直接进入各自页面; 后台管理经头像下拉进入) -->
    <section>
      <div flex items-center gap-2 mb-6>
        <span text-xl>🧭</span>
        <h2 font-serif text-2xl font-semibold text-note>应用</h2>
        <div flex-1 border-b border-dashed border-note />
      </div>

      <div grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5>
        <RouterLink
          v-for="app in visibleApps"
          :key="app.index"
          :to="app.children?.length ? app.children[0].index : app.index"
          bg-note-card
          border
          border-note
          rounded-2xl
          p-7
          transition-all
          duration-300
          hover:-translate-y-1
          hover:shadow-note
          hover:border-note-green
          group
        >
          <div
            flex
            items-center
            justify-center
            w-14
            h-14
            rounded-2xl
            bg-note-tint
            text-note-green
            mb-5
            transition-transform
            duration-300
            group-hover:scale-110
          >
            <el-icon :size="28"><component :is="app.icon" /></el-icon>
          </div>
          <h3 text-xl font-semibold text-note mb-2>{{ app.title }}</h3>
          <p text-sm text-note-sub leading-relaxed>{{ app.desc ?? '进入应用开始使用。' }}</p>
          <!-- 功能速览: 应用内主要页面 -->
          <div v-if="app.children?.length" flex flex-wrap gap-1.5 mt-4>
            <span
              v-for="child in app.children"
              :key="child.index"
              px-2 py-0.5 rounded-full bg-note-tint text-xs text-note-sub
            >
              {{ child.title }}
            </span>
          </div>
        </RouterLink>
      </div>
    </section>

    <!-- 底部小语 -->
    <section mt-12 text-center>
      <p text-sm text-note-sub font-serif italic>
        「 淡淡的绿意，是数据生长的样子 」
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/common/stores/auth'
import { useVisibleApps } from '@/common/composables/useMenu'
import { useRecentPages } from '@/common/composables/useRecentPages'

const TITLE = import.meta.env.VITE_GLOB_APP_TITLE
const router = useRouter()

const authStore = useAuthStore()
const { visibleApps } = useVisibleApps()
const { recentPages } = useRecentPages()

// ===== 登录态与问候 =====
const isLoggedIn = computed(() => Boolean(authStore.authState.user.id))
const displayName = computed(() => authStore.authState.user.nickname || authStore.authState.user.username)

/** 按当前时段返回问候语 */
function greetingByHour(): string {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}
const greeting = ref(greetingByHour())

// ===== 最近访问(仅展示前台应用页, 后台路由不出现在首页) =====
const recentAppPages = computed(() =>
  recentPages.value.filter((item) => !router.resolve(item.path).meta.admin)
)
</script>
