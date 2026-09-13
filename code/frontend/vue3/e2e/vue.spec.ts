import { test, expect } from '@playwright/test';

// 首页冒烟测试: 校验未登录引导区(品牌标题+印章)与应用入口正常渲染
test('首页正常渲染', async ({ page }) => {
  await page.goto('/');
  // Hero 区品牌标题 + 末尾"憩"印章(note-seal)
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('h1 .note-seal')).toHaveText('憩');
  // 主应用入口卡
  await expect(page.getByRole('heading', { name: '应用' })).toBeVisible();
});
