<template>
  <div w-full m-10>
    <section class="hero-section">
      <h2>欢迎来到网站首页</h2>
      <p>首页示例，您可以通过顶部导航栏切换到服务器管理页面。</p>
      <RouterLink to="/_server" class="btn-primary">前往服务器管理</RouterLink>
    </section>

    <section class="features-section">
      <h3>主要功能</h3>
      <div class="features-grid">
        <div class="feature-card">
          <h4>简单易用</h4>
          <p>直观的界面设计，让您轻松上手。</p>
        </div>
        <div class="feature-card">
          <h4>服务器管理</h4>
          <p>查看和管理您的服务器资源。</p>
        </div>
        <div class="feature-card">
          <h4>响应式设计</h4>
          <p>在各种设备上都能获得良好的体验。</p>
        </div>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<style scoped>
.home-page {
  max-width: 1000px;
  margin: 0 auto;
}

.hero-section {
  text-align: center;
  padding: 3rem 0;
  margin-bottom: 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px;
}

.hero-section h2 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.hero-section p {
  font-size: 1.2rem;
  margin-bottom: 2rem;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.btn-primary {
  display: inline-block;
  background-color: #ffffff;
  color: #667eea;
  padding: 0.8rem 1.5rem;
  border-radius: 4px;
  text-decoration: none;
  font-weight: bold;
  transition: all 0.3s;
}

.btn-primary:hover {
  background-color: #f8f9fa;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.features-section {
  margin-top: 3rem;
}

.features-section h3 {
  text-align: center;
  font-size: 1.8rem;
  margin-bottom: 2rem;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.feature-card {
  background-color: #f8f9fa;
  padding: 2rem;
  border-radius: 8px;
  text-align: center;
  transition: transform 0.3s, box-shadow 0.3s;
}

.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
}

.feature-card h4 {
  color: #4a6fa5;
  margin-bottom: 0.8rem;
  font-size: 1.2rem;
}
</style>
