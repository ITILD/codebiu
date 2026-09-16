/**
 * 游戏最高分 composable: 以 localStorage 持久化每个游戏的本地最好成绩
 * 共用方: 三个游戏页(实时刷新) / 游戏大厅卡片(展示各游戏最高分)
 */
import { ref } from 'vue'

/** 存储键前缀(与后端无关, 纯前端本地成绩) */
const KEY_PREFIX = 'arcade:best:'

/**
 * 读取/提交指定游戏的最高分
 * @param key 游戏标识(如 'tetris')
 */
export function useBest(key: string) {
  const best = ref(Number(localStorage.getItem(KEY_PREFIX + key) || 0))

  /** 提交一次成绩, 刷新时返回 true(用于"新纪录"提示) */
  function submit(score: number): boolean {
    if (score <= best.value) return false
    best.value = score
    localStorage.setItem(KEY_PREFIX + key, String(score))
    return true
  }

  return { best, submit }
}
