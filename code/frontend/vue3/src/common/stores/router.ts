/**
 * 全局路由状态:记录当前路由路径,供面包屑/菜单高亮等组件消费
 */
const RouterStore = defineStore('Router', () => {
  const routerPath = ref({
    // 当前路由
    now: '/',
  })

  /** 更新当前路由路径(路由守卫中调用) */
  const setRouterPath = (path: string) => {
    routerPath.value.now = path
  }

  return { routerPath,setRouterPath }
})

export { RouterStore }
