<template>
  <el-dialog
    v-model="visible"
    :title="$t('sign_in')"
    :width="dialogWidth"
    :modal="true"
    draggable
    class="login-dialog"
    @close="handleClose"
  >
    <!-- 自定义头部以实现拖拽功能 -->
    <template #header="{ close, titleId, titleClass }">
      <div 
        class="dialog-header draggable-area" 
        @mousedown="startDrag"
        style="cursor: move; user-select: none;"
      >
        <span :id="titleId" :class="titleClass">{{ $t('sign_in') }}</span>
        <button class="el-dialog__headerbtn" @click="close" aria-label="Close">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </template>
    
    <div class="login-form">
      <el-form 
        ref="loginFormRef" 
        :model="loginForm" 
        :rules="loginRules" 
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item :label="$t('username')" prop="username">
          <el-input 
            v-model="loginForm.username" 
            :placeholder="$t('username')" 
            autocomplete="username"
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="请输入密码" 
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="w-full" 
            :loading="loading" 
            @click="handleLogin"
          >
            {{ $t('sign_in') }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <el-button type="info" link @click="handleRegister">
          {{ $t('sign_up') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, defineProps, defineEmits, onUnmounted } from 'vue'
import { Close } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'

// 定义组件属性
const props = defineProps<{
  modelValue: boolean
}>()

// 定义事件发射
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'login', userInfo: { username: string }): void
  (e: 'register'): void
}>()

// 控制弹窗显示
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 登录表单引用
const loginFormRef = ref<FormInstance>()

// 加载状态
const loading = ref(false)

// 登录表单数据
const loginForm = reactive({
  username: '',
  password: '',
  remember: false
})

// 表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

// 对话框宽度
const dialogWidth = ref('400px')

// 拖拽相关变量
let isDragging = false
let dragOffset = { x: 0, y: 0 }

// 开始拖拽
const startDrag = (e: MouseEvent) => {
  // 确保只在标题栏上按下鼠标左键才开始拖拽
  if (e.button !== 0) return
  
  isDragging = true
  const dialog = document.querySelector('.login-dialog .el-dialog') as HTMLElement
  if (!dialog) return
  
  // 获取对话框当前位置
  const rect = dialog.getBoundingClientRect()
  dragOffset = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  }
  
  // 添加全局事件监听器
  document.addEventListener('mousemove', handleDrag)
  document.addEventListener('mouseup', stopDrag)
  
  // 防止文本选择
  e.preventDefault()
}

// 处理拖拽
const handleDrag = (e: MouseEvent) => {
  if (!isDragging) return
  
  const dialog = document.querySelector('.login-dialog .el-dialog') as HTMLElement
  if (!dialog) return
  
  // 计算新的位置
  const x = e.clientX - dragOffset.x
  const y = e.clientY - dragOffset.y
  
  // 设置位置
  dialog.style.position = 'fixed'
  dialog.style.left = `${x}px`
  dialog.style.top = `${y}px`
  dialog.style.transform = 'none' // 移除原有的transform
}

// 停止拖拽
const stopDrag = () => {
  isDragging = false
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭弹窗
const handleClose = () => {
  visible.value = false
  // 重置表单
  loginFormRef.value?.resetFields()
}

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // 模拟登录请求
        await new Promise(resolve => setTimeout(resolve, 1000))
        // 发射登录事件
        emit('login', { username: loginForm.username })
        handleClose()
      } catch (error) {
        console.error('登录失败:', error)
      } finally {
        loading.value = false
      }
    }
  })
}

// 处理注册
const handleRegister = () => {
  handleClose()
  emit('register')
}

// 组件卸载时清理事件监听器
onUnmounted(() => {
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)
})
</script>

<style scoped>
.login-dialog :deep(.el-dialog) {
  border-radius: 8px;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.login-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.login-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.login-form {
  padding: 10px 0;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
}

/* 暗色主题适配 */
.dark .login-dialog :deep(.el-dialog) {
  background: rgba(30, 30, 30, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dark .login-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
</style>