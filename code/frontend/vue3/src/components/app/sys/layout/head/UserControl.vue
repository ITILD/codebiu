<template>
  <div>
    <CollapseBase :buttonList = "buttonList">
      <li my-1 mb-3>
        <div mini-text-center-between h-12>
          <!-- 名字 邮箱 -->
          <div flex items-center h-full>
            <UserLogin m-2 w-12 h-full />
            <div text-deep-1>
              <div text-lg font-5>Name User</div>
              <div text-sm font-100 text-deep-5>**@***.com</div>
            </div>
          </div>
          <!-- 关闭 -->
          <button w-14 h-full rounded-full bg-deep-2 hover:bg-deep-3
            @click="sysStyle.isUserControlShow = false">×</button>
        </div>
      </li>
    </CollapseBase>
  </div>
</template>

<script setup lang="ts">
import SettingSVG from '@/components/miniUI/miniSvg/SettingSVG.vue'
// 显隐控制
import { SysSettingStore } from '@/stores/sys'
const router = useRouter()
const sysSettingStore = SysSettingStore()
const sysStyle = sysSettingStore.sysStyle
const closeUserControlShow = () => sysStyle.isUserControlShow = false

const openSysSettingShow = () => {
  sysSettingStore.isSysSettingShow = true
  closeUserControlShow()
}

// 两级父子对象
const buttonList = ref([{
  name: '项目列表1',
  icon: SettingSVG,
  clickFuc: (item: { isShow: boolean }) => { item.isShow = !item.isShow },
  isShow: false,
  child: [
    { name: '项目列表1-1', icon: null, url: '/' },
    {
      name: '项目列表1-2', icon: null, url: '/'
    }
  ]
},
{
  name: '后台管理',
  icon: SettingSVG,
  url: '/_server',
  clickFuc: () => {
    router.push('/_server')
  }
},
{
  name: '开发测试',
  icon: SettingSVG,
  url: '/_dev',
  clickFuc: () => {
    router.push('/_dev')
  }
},
{
  name: '博客记录',
  icon: SettingSVG,
  url: '/blog',
  clickFuc: () => {
    router.push('/blog')
  }
},
{
  name: '设置',
  icon: SettingSVG,
  clickFuc: openSysSettingShow
}
])
</script>

<style></style>
