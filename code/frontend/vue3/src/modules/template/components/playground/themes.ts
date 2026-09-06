/**
 * 组件选型主题注册表
 * 每个主题通过一组 CSS 变量覆盖 Element Plus 皮肤(主色/圆角/字体/背景/边框),
 * 由 ThemeShowcase 在根容器注入, 整页组件自动换肤; 新增主题只需在此追加一项。
 */

/** 主题定义 */
export interface PlaygroundTheme {
  /** 主题唯一键 */
  key: string
  /** 主题名(导航/卡片标题) */
  name: string
  /** 主题描述 */
  desc: string
  /** 主题页路由路径 */
  path: string
  /** 主题根容器注入的 CSS 变量(覆盖 Element Plus) */
  vars: Record<string, string>
  /** 主题根容器附加类(底色/文字/装饰) */
  rootClass: string
  /** 主题横幅附加类 */
  bannerClass: string
  /** 卡片预览色板(主题选择卡上的色块) */
  colors: string[]
}

/** 商务风: 藏蓝主色 + 小圆角 + 冷灰界面, 正式克制 */
const business: PlaygroundTheme = {
  key: 'business',
  name: '商务风',
  desc: '藏蓝主色、小圆角、冷灰底色，正式克制的办公风格。',
  path: '/template/playground/business',
  vars: {
    // 主色(藏蓝)及明暗梯度
    '--el-color-primary': '#1e40af',
    '--el-color-primary-dark-2': '#18338c',
    '--el-color-primary-light-3': '#6279c7',
    '--el-color-primary-light-5': '#8fa0d7',
    '--el-color-primary-light-7': '#bcc6e7',
    '--el-color-primary-light-8': '#d2d9ef',
    '--el-color-primary-light-9': '#e9ecf7',
    // 功能色梯度
    '--el-color-success': '#15803d',
    '--el-color-success-dark-2': '#116631',
    '--el-color-success-light-3': '#4f9e6e',
    '--el-color-success-light-5': '#85bfa0',
    '--el-color-success-light-7': '#b8d9c6',
    '--el-color-success-light-8': '#d0e6d9',
    '--el-color-success-light-9': '#e8f3ec',
    '--el-color-warning': '#b45309',
    '--el-color-warning-dark-2': '#904307',
    '--el-color-warning-light-3': '#c67c3b',
    '--el-color-warning-light-5': '#d69c6f',
    '--el-color-warning-light-7': '#e6bda3',
    '--el-color-warning-light-8': '#eed4c1',
    '--el-color-warning-light-9': '#f6eadf',
    '--el-color-danger': '#b91c1c',
    '--el-color-danger-dark-2': '#941616',
    '--el-color-danger-light-3': '#c74b4b',
    '--el-color-danger-light-5': '#d98080',
    '--el-color-danger-light-7': '#eab5b5',
    '--el-color-danger-light-8': '#f2cfcf',
    '--el-color-danger-light-9': '#f9e8e8',
    '--el-color-info': '#475569',
    '--el-color-info-dark-2': '#394454',
    '--el-color-info-light-3': '#6f7d8f',
    '--el-color-info-light-5': '#97a1af',
    '--el-color-info-light-7': '#bfc6d0',
    '--el-color-info-light-8': '#d4d9df',
    '--el-color-info-light-9': '#e9ecf0',
    // 文字 / 背景 / 边框 / 填充
    '--el-text-color-primary': '#1f2937',
    '--el-text-color-regular': '#4b5563',
    '--el-text-color-secondary': '#6b7280',
    '--el-bg-color': '#ffffff',
    '--el-bg-color-overlay': '#ffffff',
    '--el-bg-color-page': '#f4f6f9',
    '--el-border-color': '#d5dbe3',
    '--el-border-color-light': '#e3e8ef',
    '--el-border-color-lighter': '#eef1f5',
    '--el-border-color-extra-light': '#f5f7fa',
    '--el-fill-color': '#f0f2f5',
    '--el-fill-color-dark': '#ebeef2',
    '--el-fill-color-light': '#f5f7fa',
    '--el-fill-color-lighter': '#fafbfc',
    '--el-fill-color-blank': '#ffffff',
    // 圆角 / 字体 / 开关激活色
    '--el-border-radius-base': '3px',
    '--el-border-radius-small': '2px',
    '--el-font-family': "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    '--el-switch-on-color': '#1e40af',
  },
  rootClass: 'bg-[#f4f6f9] text-[#1f2937]',
  bannerClass: 'bg-[#1e40af] text-white',
  colors: ['#1e40af', '#ffffff', '#f4f6f9', '#1f2937'],
}

/** 哈利波特: 羊皮纸底 + 鎏金主色 + 衬线字体, 魔法复古风 */
const harryPotter: PlaygroundTheme = {
  key: 'harry_potter',
  name: '哈利波特',
  desc: '羊皮纸底、鎏金主色、衬线字体，魔法世界的复古风格。',
  path: '/template/playground/harry_potter',
  vars: {
    // 主色(鎏金)及明暗梯度
    '--el-color-primary': '#b08d3e',
    '--el-color-primary-dark-2': '#8d6e2c',
    '--el-color-primary-light-3': '#c9ab63',
    '--el-color-primary-light-5': '#d8c391',
    '--el-color-primary-light-7': '#e7d9bd',
    '--el-color-primary-light-8': '#efe5cf',
    '--el-color-primary-light-9': '#f7f0e2',
    // 功能色梯度(格林芬多红 / 斯莱特林绿)
    '--el-color-success': '#2d5a3d',
    '--el-color-success-dark-2': '#244831',
    '--el-color-success-light-3': '#5b8069',
    '--el-color-success-light-5': '#8aa694',
    '--el-color-success-light-7': '#b8ccbf',
    '--el-color-success-light-8': '#cfe0d5',
    '--el-color-success-light-9': '#e7f0ea',
    '--el-color-warning': '#a0621a',
    '--el-color-warning-dark-2': '#804e15',
    '--el-color-warning-light-3': '#b78140',
    '--el-color-warning-light-5': '#cd9f6f',
    '--el-color-warning-light-7': '#e0bd9f',
    '--el-color-warning-light-8': '#ead1ba',
    '--el-color-warning-light-9': '#f4e6d5',
    '--el-color-danger': '#8b1a1a',
    '--el-color-danger-dark-2': '#6f1515',
    '--el-color-danger-light-3': '#a34141',
    '--el-color-danger-light-5': '#b97070',
    '--el-color-danger-light-7': '#d0a0a0',
    '--el-color-danger-light-8': '#dcbcbc',
    '--el-color-danger-light-9': '#eed9d9',
    '--el-color-info': '#57534e',
    '--el-color-info-dark-2': '#46423e',
    '--el-color-info-light-3': '#7d7872',
    '--el-color-info-light-5': '#a3a09b',
    '--el-color-info-light-7': '#c9c6c2',
    '--el-color-info-light-8': '#dcdad7',
    '--el-color-info-light-9': '#efedeb',
    // 文字 / 背景 / 边框 / 填充(羊皮纸色系)
    '--el-text-color-primary': '#3b2f2f',
    '--el-text-color-regular': '#57493f',
    '--el-text-color-secondary': '#7d6b57',
    '--el-bg-color': '#faf4e2',
    '--el-bg-color-overlay': '#faf4e2',
    '--el-bg-color-page': '#f3ead3',
    '--el-border-color': '#c9b382',
    '--el-border-color-light': '#d8c69f',
    '--el-border-color-lighter': '#e7dbbd',
    '--el-border-color-extra-light': '#f0e7d2',
    '--el-fill-color': '#f0e6c8',
    '--el-fill-color-dark': '#e8dbb9',
    '--el-fill-color-light': '#f4ecd6',
    '--el-fill-color-lighter': '#f9f3e4',
    '--el-fill-color-blank': '#faf4e2',
    // 圆角 / 字体 / 开关激活色
    '--el-border-radius-base': '2px',
    '--el-border-radius-small': '2px',
    '--el-font-family': "Georgia, 'Times New Roman', 'STZhongsong', 'KaiTi', serif",
    '--el-switch-on-color': '#b08d3e',
  },
  rootClass: 'bg-[#f3ead3] text-[#3b2f2f] border border-[#c9b382]',
  bannerClass: 'bg-[#2a1d10] text-[#e3c36b] border border-[#c9b382]',
  colors: ['#b08d3e', '#faf4e2', '#f3ead3', '#3b2f2f'],
}

/** 数字花园: 草木绿主色 + 米纸底色 + 衬线字体, Brad Woods 数字花园可视化技巧演示 */
const bradGarden: PlaygroundTheme = {
  key: 'brad_garden',
  name: '数字花园',
  desc: '草木绿主色、米纸底色、纸张质感，汇集 blend-modes/3D/描线等可视化技巧的温室。',
  path: '/template/playground/brad_garden',
  vars: {
    // 主色(草木绿)及明暗梯度
    '--el-color-primary': '#4a7c59',
    '--el-color-primary-dark-2': '#3b6447',
    '--el-color-primary-light-3': '#6f9579',
    '--el-color-primary-light-5': '#93b39b',
    '--el-color-primary-light-7': '#bcd2c2',
    '--el-color-primary-light-8': '#d3e2d7',
    '--el-color-primary-light-9': '#eaf2ec',
    // 功能色梯度(苔绿 / 麦黄 / 陶红)
    '--el-color-success': '#2f7d4f',
    '--el-color-success-dark-2': '#26643f',
    '--el-color-success-light-3': '#589671',
    '--el-color-success-light-5': '#8ab498',
    '--el-color-success-light-7': '#b8d2c0',
    '--el-color-success-light-8': '#cfe2d5',
    '--el-color-success-light-9': '#e6f0e9',
    '--el-color-warning': '#b08a3e',
    '--el-color-warning-dark-2': '#8d6e31',
    '--el-color-warning-light-3': '#c2a468',
    '--el-color-warning-light-5': '#d3bd8f',
    '--el-color-warning-light-7': '#e3d5b4',
    '--el-color-warning-light-8': '#ede2cb',
    '--el-color-warning-light-9': '#f6f0e2',
    '--el-color-danger': '#a35454',
    '--el-color-danger-dark-2': '#824343',
    '--el-color-danger-light-3': '#b87676',
    '--el-color-danger-light-5': '#cd9898',
    '--el-color-danger-light-7': '#e0baba',
    '--el-color-danger-light-8': '#ebcfcf',
    '--el-color-danger-light-9': '#f5e5e5',
    '--el-color-info': '#6e7566',
    '--el-color-info-dark-2': '#585e52',
    '--el-color-info-light-3': '#8b9184',
    '--el-color-info-light-5': '#a8ada2',
    '--el-color-info-light-7': '#c5c8c0',
    '--el-color-info-light-8': '#d8dad4',
    '--el-color-info-light-9': '#eaebe6',
    // 文字 / 背景 / 边框 / 填充(米纸色系)
    '--el-text-color-primary': '#33392f',
    '--el-text-color-regular': '#4d5548',
    '--el-text-color-secondary': '#79806f',
    '--el-bg-color': '#faf8f1',
    '--el-bg-color-overlay': '#faf8f1',
    '--el-bg-color-page': '#f2efe6',
    '--el-border-color': '#cfc9b8',
    '--el-border-color-light': '#dcd7c8',
    '--el-border-color-lighter': '#e8e4d8',
    '--el-border-color-extra-light': '#f0ede4',
    '--el-fill-color': '#f0ede2',
    '--el-fill-color-dark': '#e8e4d6',
    '--el-fill-color-light': '#f3f0e7',
    '--el-fill-color-lighter': '#f8f5ee',
    '--el-fill-color-blank': '#faf8f1',
    // 圆角 / 字体 / 开关激活色
    '--el-border-radius-base': '4px',
    '--el-border-radius-small': '3px',
    '--el-font-family': "Georgia, 'Noto Serif SC', 'STZhongsong', 'KaiTi', serif",
    '--el-switch-on-color': '#4a7c59',
  },
  rootClass: 'bg-[#f2efe6] text-[#33392f] border border-[#cfc9b8]',
  bannerClass: 'bg-[#2f3a2c] text-[#e4ecd8] border border-[#cfc9b8]',
  colors: ['#4a7c59', '#faf8f1', '#f2efe6', '#33392f'],
}

/** 全部可选主题(新增主题在此追加) */
export const playgroundThemes: PlaygroundTheme[] = [business, harryPotter, bradGarden]
