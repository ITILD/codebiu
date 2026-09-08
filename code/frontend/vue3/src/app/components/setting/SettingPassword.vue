<template>
  <div class="max-w-[520px]">
    <h3 class="text-lg font-bold text-note mb-1">修改密码</h3>
    <p class="text-sm text-note-sub mb-5">需验证旧密码；修改成功后建议在其他设备重新登录。</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" label-position="left">
      <el-form-item label="旧密码" prop="old_password">
        <el-input v-model="form.old_password" type="password" show-password placeholder="请输入当前密码" />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="form.new_password" type="password" show-password placeholder="至少6位" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirm_password">
        <el-input v-model="form.confirm_password" type="password" show-password placeholder="再次输入新密码" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSubmit">确认修改</el-button>
        <el-button @click="formRef?.resetFields()">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { changeMyPassword } from '@/modules/authorization/api/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

const formRef = ref<FormInstance>()
const saving = ref(false)
const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

// 确认密码一致性校验(自定义校验器)
const rules: FormRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少6位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.new_password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    saving.value = true
    await changeMyPassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码修改成功')
    formRef.value?.resetFields()
  } catch (error) {
    console.error('修改密码失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '修改密码失败')
  } finally {
    saving.value = false
  }
}
</script>
