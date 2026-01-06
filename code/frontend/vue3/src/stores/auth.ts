import type { AuthResponse } from '@/types/authorization/auth'
import { defineStore } from 'pinia'

const createInitialAuthState = (): AuthResponse => ({
  tokens: {
    access: { token: '', expires_in: 0, token_id: null },
    refresh: { token: '', expires_in: 0, token_id: null },
  },
  user: {
    id: '',
    username: '',
    password: '',
    email: '',
    phone: '',
    nickname: '',
    avatar: '',
    is_active: false,
    created_at: '',
    updated_at: '',
  },
  message: '',
})

const useAuthStore = defineStore(
  'auth',
  () => {
    // ✅ 直接使用 reactive 风格（Pinia 默认支持）
    const authState = ref(createInitialAuthState())

    const setAuthState = (newState: AuthResponse) => {
      Object.assign(authState.value, newState)
    }
    /**
     * 初始化或重置用户信息为初始状态
     */
    const initAuthState = () => {
      setAuthState(createInitialAuthState())
    }

    return { authState, initAuthState, setAuthState }
  },
  {
    persist: true, // 现在 authState 是普通对象，可安全持久化
  },
)
export { useAuthStore }
