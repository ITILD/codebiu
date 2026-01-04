import { createI18n } from 'vue-i18n'

//语言对照
const languageObj = {
  // 支持的语言
  languageTypeArray: ['zh', 'ja', 'en'],
  languageTypeFullArray: ['简体中文', '日本語', 'English'],
  language: ['语言选择', '言語選択', 'language selection'],
  theme: ['主题', 'テーマ', 'theme'],
  dark: ['暗', 'ダーク', 'dark'],
  light: ['明', '明るい', 'light'],
  autoSys: ['跟随系统', 'システムに従う', 'follow system'],
  auto: ['自动', '自動', 'auto'],
  home: ['首页', 'ホーム', 'home'],
  about: ['关于', 'アバウト', 'about'],
  titleDemo: ['标题', 'タイトル', 'title'],
  // 首页
  username: ['用户名', 'ユーザー名', 'username'],
  email: ['邮箱', 'メール', 'email'],
  sign_in: ['登录', 'ログイン', 'sign in'],
  sign_up: ['注册', '登録する', 'sign up'],
  back_to_login: ['返回登录', 'ログインに戻る', 'back to login'],
  search:['搜索', 'サーチ', 'search'],
  // 后台管理
  admin: ['后台管理', '管理画面', 'admin'],
} as Record<string, string[]>
// 语言对照选择格式
const languageOptions: {
  value: string
  label: string
}[] = []
// todo 根据ip地址或者定位，自动选择语言
const i18n = createI18n({
  //
  legacy: false,
  // 'zh'
  locale: languageObj.languageTypeArray[0],
  fallbackLocale: languageObj.languageTypeArray[0],
  messages: {}
})
for (let index = 0; index < languageObj.languageTypeArray.length; index++) {
  const languageType = languageObj.languageTypeArray[index]
  const thisLanguageTypeObj = {} as Record<string, string>
  // 循环 languageObj
  for (const key in languageObj) {
    thisLanguageTypeObj[key] = languageObj[key][index]
  }
  // 设置i18n对应语言
  i18n.global.setLocaleMessage(languageType, thisLanguageTypeObj)

  // 设置语言类别对照
  languageOptions.push({
    value: languageType,
    label: languageObj.languageTypeFullArray[index]
  })
}


export { i18n, languageOptions }
