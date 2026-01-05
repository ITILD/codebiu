<template>
  <el-dialog v-model="visible" :title="$t('sign_in')" :width="dialogWidth" :modal="true" :close-on-click-modal="true"
    draggable @close="handleClose">
    <template #header="{  titleId, titleClass }">
      <div flex justify-between items-center>
        <span :id="titleId" :titleClass>{{ $t('sign_in') }}</span>

      </div>
    </template>

    <div p-10px>
      <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top"
        @submit.prevent="handleLogin">
        <el-form-item :label="$t('username')" prop="username">
          <el-input v-model="loginForm.username" :placeholder="$t('username')" autocomplete="username" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" autocomplete="current-password"
            show-password />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" w-full :loading="loading" @click="handleLogin">
            {{ $t('sign_in') }}
          </el-button>
        </el-form-item>
      </el-form>

      <div text-center mt-20px>
        <el-button type="info" link @click="handleSignUp">
          {{ $t('sign_up') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { loginUser } from '@/api/authorization/auth'
import type {
  AuthLoginRequest,
  AuthResponse,
} from '@/types/authorization/auth';


// 定义组件属性
const props = defineProps<{
  modelValue: boolean
}>()

// 定义事件发射
const emit = defineEmits<{
  'update:modelValue': [boolean]
  'login':  [AuthResponse]
  'register': []
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
        // 准备登录数据
        const loginData: AuthLoginRequest = {
          username: loginForm.username,
          password: loginForm.password
        }
        // 调用登录API
        const authResponse: AuthResponse = await loginUser(loginData)
        // 发射登录事件
        emit('login', authResponse)
        handleClose()
      } catch (error: unknown) {
        debugger
        console.error('登录失败:', error)
        // 添加错误提示
        ElMessage.error((error as { message?: string }).message || '登录失败，请检查用户名和密码')
      } finally {
        loading.value = false
      }
    }
  })
}

// 处理切换到注册
const handleSignUp = () => {
  handleClose()
  emit('register')
}


</script>

<style scoped></style>
