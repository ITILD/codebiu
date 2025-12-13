import { create } from 'zustand';

// 计数器状态接口
interface CounterState {
  count: number;
  increment: () => void;
  decrement: () => void;
  reset: () => void;
  incrementBy: (amount: number) => void;
  decrementBy: (amount: number) => void;
}

// 计数器 Store - 演示基础状态管理
export const useCounterStore = create<CounterState>((set, get) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
  decrement: () => set((state) => ({ count: state.count - 1 })),
  reset: () => set({ count: 0 }),
  incrementBy: (amount: number) => set((state) => ({ count: state.count + amount })),
  decrementBy: (amount: number) => set((state) => ({ count: state.count - amount })),
}));