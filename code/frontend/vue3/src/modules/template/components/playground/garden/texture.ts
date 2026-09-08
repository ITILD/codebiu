/**
 * 数字花园演示资源: 程序化噪声纹理 + AI 生成配图
 * 配图统一走 text_to_image 接口按提示词实时生成; 噪声图提供本地 webp 与内联 SVG 两种来源。
 */
import noiseWebp from '@/assets/garden/noise.webp'

/** 单个噪声预设: 展示名 + background-image 可用的 url(...) 值 */
export interface NoisePreset {
  label: string
  url: string
}

/** 内联 SVG feTurbulence 噪声(data URI, 离线可用, 参数可调出不同质感) */
function svgNoise(type: 'fractalNoise' | 'turbulence', freq: string, octaves: number, opacity = 0.55): string {
  const svg =
    `%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='280'%3E` +
    `%3Cfilter id='n'%3E%3CfeTurbulence type='${type}' baseFrequency='${freq}' numOctaves='${octaves}' stitchTiles='stitch'/%3E` +
    `%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E` +
    `%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='${opacity}'/%3E%3C/svg%3E`
  return `url("data:image/svg+xml,${svg}")`
}

/** 可切换的噪声图预设: 本位图颗粒 + 三种 SVG 程序化噪声 */
export const NOISE_PRESETS: NoisePreset[] = [
  { label: '颗粒 webp', url: `url("${noiseWebp}")` },
  { label: '细颗粒', url: svgNoise('fractalNoise', '0.9', 4) },
  { label: '纸纤维', url: svgNoise('fractalNoise', '0.02 0.4', 3) },
  { label: '湍流斑驳', url: svgNoise('turbulence', '0.06', 3, 0.4) },
]

/** 默认噪声: 原 SVG 细颗粒配方(向后兼容旧引用) */
export const NOISE_URL = NOISE_PRESETS[1].url

/** 按提示词生成图片 URL(text_to_image) */
function genImage(prompt: string, size: string): string {
  return `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(prompt)}&image_size=${size}`
}

/** 主演示图: 山湖晨光(双色调 / 半调网点 / 扫描线 / 彩色聚光共用) */
export const mainPhoto = genImage(
  'golden sunrise over misty mountain lake with pine forest, vivid warm and teal colors, fine art landscape photography, highly detailed',
  'landscape_4_3',
)

/** 静物图: 园艺工具(文字环绕排版用) */
export const potPhoto = genImage(
  'vintage brass watering can and terracotta flower pot on wooden garden table, warm sunlight, still life photography',
  'square',
)

/** 视图过渡画廊配图(花园主题) */
export const galleryPhotos = [
  { title: '樱花枝头', src: genImage('cherry blossom branch close-up against soft spring sky, delicate pink petals, shallow depth of field', 'square') },
  { title: '带露蕨叶', src: genImage('lush green fern leaves with morning dew drops, macro photography, forest floor', 'square') },
  { title: '林间蘑菇', src: genImage('red-capped mushroom in mossy forest, fairy tale mood, soft bokeh background', 'square') },
  { title: '花间凤蝶', src: genImage('blue morpho butterfly on lavender flower in garden sunlight, vivid colors', 'square') },
  { title: '睡莲池畔', src: genImage('water lilies on a tranquil garden pond with lotus leaves, soft reflection', 'square') },
  { title: '玻璃温室', src: genImage('sunlit glass greenhouse interior full of lush plants, botanical garden, warm light', 'square') },
]
