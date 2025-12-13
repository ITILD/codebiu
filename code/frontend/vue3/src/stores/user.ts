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
    persist: true,
  },
)

export { UserStore }
