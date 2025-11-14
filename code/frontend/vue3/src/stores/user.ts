const UserStore = defineStore('user', () => {
  const userState = ref({
    img: null,
    loginState: false,
    userId: null,
    userName: '游客'
  })

  return { userState }
})

export { UserStore }
