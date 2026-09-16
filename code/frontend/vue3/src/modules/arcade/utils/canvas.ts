/**
 * 画布工具: 游戏页共用的高清 canvas 初始化
 * 共用方: 俄罗斯方块 / 贪吃蛇 / 打砖块 / 游戏大厅像素预览
 */

/**
 * 按设备像素比初始化画布, 返回以逻辑像素绘图的 2D 上下文
 * @param canvas 画布元素
 * @param w 逻辑宽度
 * @param h 逻辑高度
 */
export function setupCanvas(canvas: HTMLCanvasElement, w: number, h: number): CanvasRenderingContext2D {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.round(w * dpr)
  canvas.height = Math.round(h * dpr)
  const ctx = canvas.getContext('2d')!
  // 后续绘制一律使用逻辑像素, 由变换矩阵负责放大, 保证高分屏清晰
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return ctx
}
