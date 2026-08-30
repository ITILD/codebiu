// 临时脚本: 排查对话页渲染错误(用后即删)
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
const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
page.on('console', (m) => console.log('[console]', m.type(), m.text().slice(0, 300)))
page.on('pageerror', (e) => console.log('[pageerror]', String(e).slice(0, 300)))
await page.addInitScript((auth) => localStorage.setItem('auth', auth), AUTH)
await page.goto(BASE + '/_sys/rag/conversation', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
const state = await page.evaluate(() => ({
  path: location.pathname,
  bodyChildren: document.body.children.length,
  appHtml: document.querySelector('#app')?.innerHTML?.slice(0, 300),
  mainHtmlLen: document.querySelector('main')?.innerHTML?.length,
}))
console.log(JSON.stringify(state, null, 1))
await browser.close()
