const UserStore = defineStore(
  'user',
  () => {
    const userState = ref({
      img: null,
      isLogin: false,
      userId: null,
      userName: '游客',
    })

    return { userState }
  },
  {
    // 启用持久化
    persist: true,
  },
)

export { UserStore }
