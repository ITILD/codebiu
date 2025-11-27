This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## 项目技术架构

本项目基于 Next.js 构建，集成了多种现代前端技术栈，包括 Ant Design、Ant Design X 和 UnoCSS。

### 技术架构层级

#### 第一层：核心框架层
- **Next.js 16** - React 全栈框架，提供服务端渲染、静态生成和客户端渲染能力
- **React 18** - 用于构建用户界面的 JavaScript 库
- **TypeScript** - JavaScript 的超集，提供静态类型检查
- **App Directory** - Next.js 最新的文件夹结构，更好地组织项目代码

#### 第二层：路由与数据获取层
- **App Router** - Next.js 最新的路由架构，支持服务端渲染和客户端导航
- **Dynamic Routes** - 动态路由，支持参数化页面
- **Loading UI** - 加载状态 UI，提升用户体验
- **Error Handling** - 错误处理机制，增强应用健壮性

#### 第三层：UI 组件层
- **Ant Design 5** - 企业级 UI 设计语言和 React 组件库
- **Ant Design X 1.6** - Ant Design 的下一代扩展组件库
- **UnoCSS** - 原子化 CSS 引擎，提供按需使用的样式解决方案
- **CSS Modules** - 局部作用域 CSS，避免样式冲突

#### 第四层：测试与质量保障层
- **Jest** - JavaScript 测试框架，用于单元测试
- **React Testing Library** - React 组件测试工具，更贴近用户行为的测试方式
- **Cypress** - 端到端测试工具，提供完整的测试生命周期管理
- **ESLint** - 代码质量检查工具，确保代码风格一致性

#### 第五层：监控与运维层
- **Next.js Analytics** - 内置分析工具，跟踪页面访问和性能指标
- **Real-time Monitoring** - 实时监控应用运行状态，及时发现问题
- **Logging Management** - 日志管理系统，记录应用运行过程中的重要信息
- **Nginx Deployment** - 打包后部署到 Nginx 服务器，实现高性能分发

## Getting Started

First, run the development server:

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
