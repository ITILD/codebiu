import { create } from 'zustand';

// 服务器管理状态接口
interface ServerState {
  activeMenuKey: string;
  setActiveMenuKey: (key: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  serverInfo: {
    cpu: number;
    memory: number;
    disk: string;
    uptime: string;
  };
  updateServerInfo: (info: Partial<ServerState['serverInfo']>) => void;
}

// 服务器管理 Store
export const useServerStore = create<ServerState>((set) => ({
  activeMenuKey: '/server',
  setActiveMenuKey: (key) => set({ activeMenuKey: key }),
  collapsed: true,
  setCollapsed: (collapsed) => set({ collapsed }),
  serverInfo: {
    cpu: 0,
    memory: 0,
    disk: '0GB / 0TB',
    uptime: '0小时',
  },
  updateServerInfo: (info) => set((state) => ({
    serverInfo: { ...state.serverInfo, ...info }
  })),
}));