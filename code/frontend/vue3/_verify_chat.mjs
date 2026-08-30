// 临时脚本: 精确验证对话页(作用域限定在 main 内, 用后即删)
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

// --- 桌面端(精确作用域) ---
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
  page.on('pageerror', (e) => console.log('[pageerror]', String(e).slice(0, 200)))
  await page.addInitScript((auth) => localStorage.setItem('auth', auth), AUTH)
  await page.goto(BASE + '/_sys/rag/conversation', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  const info = await page.evaluate(() => {
    const main = document.querySelector('main')
    const aside = main?.querySelector('aside')
    const inputCard = main?.querySelector('.chat-input-card')
    const textarea = main?.querySelector('textarea')
    const suggestionBtns = main?.querySelectorAll('button:not(.chat-input-card button)')
    const deepThinkBtn = [...(main?.querySelectorAll('header button') || [])].find(b => b.textContent?.includes('深度思考'))
    const sendBtn = inputCard?.querySelector('button')
    return {
      convAsideW: aside ? Math.round(aside.getBoundingClientRect().width) : null,
      inputCardH: inputCard ? Math.round(inputCard.getBoundingClientRect().height) : null,
      textareaPlaceholder: textarea?.placeholder,
      suggestionCount: suggestionBtns?.length,
      deepThinkText: deepThinkBtn?.textContent?.trim(),
      deepThinkClasses: deepThinkBtn?.className,
      sendBtnW: sendBtn ? Math.round(sendBtn.getBoundingClientRect().width) : null,
      sendDisabled: sendBtn?.disabled,
      convListGroups: [...(main?.querySelectorAll('aside > div:last-child > div') || [])].slice(0, 6).map(d => d.textContent?.trim()).filter(Boolean),
    }
  })
  console.log('桌面:', JSON.stringify(info, null, 1))
  await page.screenshot({ path: '_chat_desktop.png' })

  // 输入文字测试发送按钮激活
  await textarea?.fill('测试问题')
  await page.waitForTimeout(300)
  const sendState = await page.evaluate(() => {
    const btn = document.querySelector('main .chat-input-card button')
    return { disabled: btn?.disabled, bg: btn ? getComputedStyle(btn).backgroundColor : null }
  })
  console.log('输入后发送按钮:', JSON.stringify(sendState))
  await page.close()
}

// --- Markdown 渲染测试(注入一条假历史消息不可行, 直接单测 renderMarkdown 无法;
//     用空状态建议按钮验证样式即可) ---
// --- 暗色模式截图 ---
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
  await page.addInitScript((auth) => {
    localStorage.setItem('auth', auth)
    localStorage.setItem('sysSetting', JSON.stringify({ sysStyle: { isDark: true } }))
  }, AUTH)
  await page.goto(BASE + '/_sys/rag/conversation', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  const dark = await page.evaluate(() => ({
    htmlDark: document.documentElement.classList.contains('dark'),
    pageBg: getComputedStyle(document.querySelector('main')?.parentElement || document.body).backgroundColor,
  }))
  console.log('暗色:', JSON.stringify(dark))
  await page.screenshot({ path: '_chat_dark.png' })
  await page.close()
}

await browser.close()
console.log('done')
