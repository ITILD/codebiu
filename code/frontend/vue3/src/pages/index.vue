<template>
  <div w-full max-w-5xl mx-auto p-4 md:p-10>
    <section
      text-center
      p-6 md:p-12
      mb-8
      rounded-lg
      bg-gradient-to-br
      from-indigo-500
      to-purple-700
      text-white
    >
      <h2 text-3xl md:text-4xl font-bold mb-4>欢迎来到网站首页</h2>
      <p text-base md:text-lg mb-8 max-w-2xl mx-auto>
        首页示例，您可以通过顶部导航栏切换到服务器管理页面。
      </p>
      <RouterLink
        to="/_sys"
        inline-block
        bg-white
        text-indigo-600
        px-6
        py-3
        rounded
        font-bold
        transition-all
        duration-300
        hover:bg-gray-100
        hover:-translate-y-0.5
        hover:shadow-md
      >
        前往管理后台
      </RouterLink>
    </section>

    <section mt-12>
      <h3 text-center text-2xl md:text-3xl mb-8>主要功能</h3>
      <div grid grid-cols-1 md:grid-cols-3 gap-6>
        <div
          v-for="feature in features"
          :key="feature.title"
          bg-gray-50
          dark:bg-gray-800
          p-8
          rounded-lg
          text-center
          transition-all
          duration-300
          hover:-translate-y-1
          hover:shadow-lg
        >
          <h4 text-blue-700 dark:text-blue-400 mb-3 text-xl font-semibold>
            {{ feature.title }}
          </h4>
          <p text-gray-600 dark:text-gray-300>{{ feature.desc }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
const features = [
  { title: '简单易用', desc: '直观的界面设计，让您轻松上手。' },
  { title: '服务器管理', desc: '查看和管理您的服务器资源。' },
  { title: '响应式设计', desc: '在各种设备上都能获得良好的体验。' },
]
</script>
