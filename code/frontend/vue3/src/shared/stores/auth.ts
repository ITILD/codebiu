import type { AuthResponse } from '@/types/authorization/auth'
import { defineStore } from 'pinia'
import { getUserPermissions } from '@/api/authorization/auth'

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

/** 权限状态初始值(未登录/未拉取) */
const createInitialPermState = () => ({
  /** 角色绑定,按域分组,如 { "*": ["admin"], "main": ["main_viewer"] } */
  roles: {} as Record<string, string[]>,
  /** 权限码列表,全局管理员为 ["*"] */
  permissions: [] as string[],
})

const useAuthStore = defineStore(
  'auth',
  () => {
    // ✅ 直接使用 reactive 风格（Pinia 默认支持）
    const authState = ref(createInitialAuthState())
    // 当前用户角色与权限码(me_permissions 接口拉取)
    const permState = ref(createInitialPermState())

    const setAuthState = (newState: AuthResponse) => {
      Object.assign(authState.value, newState)
    }
    /**
     * 初始化或重置用户信息为初始状态
     */
    const initAuthState = () => {
      setAuthState(createInitialAuthState())
      resetPermState()
    }

    /**
     * 拉取当前用户的角色与权限码并缓存(登录后调用)
     */
    const fetchPermissions = async () => {
      if (!authState.value.user.id) return
      try {
        const res = await getUserPermissions()
        permState.value.roles = res.roles || {}
        permState.value.permissions = res.permissions || []
      } catch (error) {
        console.error('拉取用户权限失败:', error)
      }
    }

    /** 重置权限状态(登出时调用) */
    const resetPermState = () => {
      permState.value = createInitialPermState()
    }

    return {
      authState,
      permState,
      initAuthState,
      setAuthState,
      fetchPermissions,
      resetPermState,
    }
  },
  {
    persist: true, // 现在 authState 是普通对象，可安全持久化
  },
)
export { useAuthStore }
