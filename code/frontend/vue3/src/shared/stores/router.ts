const RouterStore = defineStore('Router', () => {
  const routerPath = ref({
    // 当前路由
    now: '/',
  })

  const setRouterPath = (path: string) => {
    routerPath.value.now = path
  }

  return { routerPath,setRouterPath }
})

export { RouterStore }
