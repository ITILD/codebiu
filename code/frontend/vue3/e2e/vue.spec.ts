import { test, expect } from '@playwright/test';

// 首页冒烟测试: 校验首页标题与功能模块入口正常渲染
test('首页正常渲染', async ({ page }) => {
  await page.goto('/');
  // Hero 区主标题(取自 VITE_GLOB_APP_TITLE)
  await expect(page.locator('h1')).toHaveText('MiniUI');
  // 功能模块入口卡片
  await expect(page.getByRole('heading', { name: '功能模块' })).toBeVisible();
});
