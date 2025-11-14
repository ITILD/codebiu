<template>
  <div>
    <h1>测试基础引入内容</h1>
    <br />
    <el-button type="primary" @click="showMessage">测试element-plus自动引入组件和api</el-button>
    <div w-70 bg-blue-300 hover:bg-blue-200>测试unocss+tailwindcss样式引入</div>
    <i-ep-edit /><i-vscode-icons-file-type-tsconfig />

    <!-- 使用 el-icon 为 SVG 图标提供属性 -->


    <!-- 或者独立使用它，不从父级获取属性 -->
    <Edit />
    <el-icon>
      <i-ep-upload-filled />
    </el-icon>
    <el-icon>
      <i-ep-edit />
    </el-icon>
  </div>
</template>
<script setup lang="ts">
// 测试自动引入
const showMessage = () => {
  ElMessage.success('自动引入Element Plus api成功！')
}
</script>

<style></style>
