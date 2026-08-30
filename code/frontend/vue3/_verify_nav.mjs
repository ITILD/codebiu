// 临时脚本: 客户端导航进入对话页(模拟真实用户点击菜单)(用后即删)
import { chromium } from '@playwright/test'

const CHROME = 'C:\\Users\\admin\\AppData\\Local\\ms-playwright\\chromium-1217\\chrome-win64\\chrome.exe'
const BASE = 'http://localhost:50002'
const AUTH = JSON.stringify({
  authState: {
    tokens: {
      access: { token: 'x', expires_in: 99999, token_id: null },
      refresh: { token: 'x', expires_in: 99999, token_id: null },
    },
    user: {
      id: 'u1', username: 'tester', password: '', email: '', phone: '',
      nickname: '测试用户', avatar: '', is_active: true, created_at: '', updated_at: '',
    },
    message: '',
  },
})

const browser = await chromium.launch({ executablePath: CHROME })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
page.on('console', (m) => { if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 250)) })
page.on('pageerror', (e) => console.log('[pageerror]', String(e).slice(0, 250)))
await page.addInitScript((auth) => localStorage.setItem('auth', auth), AUTH)

// 1. 先进 /_sys
await page.goto(BASE + '/_sys', { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
// 2. 点击侧栏「知识库问答」菜单(客户端路由, 需先展开分组)
const group = page.locator('.el-sub-menu__title', { hasText: '知识库' }).first()
if (await group.count()) {
  await group.click()
  await page.waitForTimeout(500)
}
const item = page.locator('.el-menu-item', { hasText: '知识库问答' }).first()
if (await item.count()) {
  await item.click()
  await page.waitForTimeout(1500)
  const state = await page.evaluate(() => {
    const main = document.querySelector('main')
    return {
      path: location.pathname,
      hasChat: !!main?.querySelector('.chat-input-card'),
      hasAside: !!main?.querySelector('aside'),
      greeting: main?.querySelector('h2')?.textContent,
      mainLen: main?.innerHTML.length,
    }
  })
  console.log('客户端导航进入:', JSON.stringify(state))
} else {
  console.log('未找到菜单项, 检查菜单文本')
  const texts = await page.evaluate(() => [...document.querySelectorAll('.el-menu-item, .el-sub-menu__title')].map(e => e.textContent?.trim()))
  console.log('菜单项:', JSON.stringify(texts))
}
await browser.close()
