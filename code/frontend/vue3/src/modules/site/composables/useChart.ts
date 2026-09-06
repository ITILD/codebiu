// src/modules/site/composables/useChart.ts —— ECharts 按需注册 + 容器绑定(模块内图表统一入口)
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Ref } from 'vue'

echarts.use([PieChart, BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

/**
 * 图表绑定: 初始化/更新配置/随窗口自适应/组件卸载时销毁
 * @param elRef 图表容器元素引用
 */
export function useChart(elRef: Ref<HTMLElement | null>) {
  let chart: echarts.ECharts | null = null

  /** 渲染/替换配置(notMerge=true, 避免残留旧系列) */
  const render = (option: echarts.EChartsCoreOption) => {
    if (!elRef.value) return
    if (!chart) chart = echarts.init(elRef.value)
    chart.setOption(option, true)
  }

  const resize = () => chart?.resize()

  onMounted(() => window.addEventListener('resize', resize))
  onUnmounted(() => {
    window.removeEventListener('resize', resize)
    chart?.dispose()
    chart = null
  })

  return { render }
}
