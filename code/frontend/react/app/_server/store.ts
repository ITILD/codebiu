import { create } from 'zustand';

interface ServerState {
  activeMenuKey: string;
  setActiveMenuKey: (key: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}

export const useServerStore = create<ServerState>((set) => ({
  activeMenuKey: '/_server',
  setActiveMenuKey: (key) => set({ activeMenuKey: key }),
  collapsed: true,
  setCollapsed: (collapsed) => set({ collapsed }),
}));