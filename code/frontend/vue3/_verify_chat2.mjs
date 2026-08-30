// 临时脚本: 输入激活测试 + 暗色模式(用后即删)
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

// 输入后发送按钮激活
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
  await page.addInitScript((auth) => localStorage.setItem('auth', auth), AUTH)
  await page.goto(BASE + '/_sys/rag/conversation', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await page.fill('main textarea', '测试问题')
  await page.waitForTimeout(300)
  const sendState = await page.evaluate(() => {
    const btn = document.querySelector('main .chat-input-card button')
    return { disabled: btn?.disabled, bg: btn ? getComputedStyle(btn).backgroundColor : null, color: btn ? getComputedStyle(btn).color : null }
  })
  console.log('输入后发送按钮:', JSON.stringify(sendState))
  await page.close()
}

// 暗色模式
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
  await page.addInitScript((auth) => {
    localStorage.setItem('auth', auth)
    localStorage.setItem('sysSetting', JSON.stringify({ sysStyle: { isDark: true } }))
  }, AUTH)
  await page.goto(BASE + '/_sys/rag/conversation', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  const dark = await page.evaluate(() => {
    const main = document.querySelector('main')
    return {
      htmlDark: document.documentElement.classList.contains('dark'),
      chatBg: main ? getComputedStyle(main.firstElementChild).backgroundColor : null,
    }
  })
  console.log('暗色:', JSON.stringify(dark))
  await page.screenshot({ path: '_chat_dark.png' })
  await page.close()
}

await browser.close()
console.log('done')
