import { create } from 'zustand';

// 用户状态接口
interface UserState {
  user: {
    id: string;
    name: string;
    email: string;
    avatar: string;
    role: 'admin' | 'user' | 'guest';
  } | null;
  isAuthenticated: boolean;
  login: (userData: UserState['user']) => void;
  logout: () => void;
  updateProfile: (userData: Partial<UserState['user']>) => void;
}

// 用户 Store - 演示用户状态管理
export const useUserStore = create<UserState>((set) => ({
  user: null,
  isAuthenticated: false,
  login: (userData) => set({ 
    user: userData, 
    isAuthenticated: true 
  }),
  logout: () => set({ 
    user: null, 
    isAuthenticated: false 
  }),
  updateProfile: (userData) => set((state) => ({
    user: state.user ? { ...state.user, ...userData } : null
  })),
}));