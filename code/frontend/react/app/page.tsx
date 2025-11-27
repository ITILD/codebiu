"use client";

import Link from "next/link";
import { Card, Typography, Button, Space } from "antd";
import { GithubOutlined } from "@ant-design/icons";

const { Title, Paragraph } = Typography;

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="w-full max-w-4xl">
        <div className="text-center mb-12">
          <Title level={1} className="!text-4xl !font-bold !mb-4">
            React 组件库演示平台
          </Title>
          <Paragraph className="text-lg text-gray-600 max-w-2xl mx-auto">
            探索不同的前端技术和组件库实现，包括 Ant Design、Ant Design X 和 UnoCSS
          </Paragraph>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Ant Design 卡片 */}
          <Card 
            hoverable 
            className="shadow-lg rounded-xl overflow-hidden"
            cover={
              <div className="bg-gradient-to-r from-blue-500 to-indigo-600 h-32 flex items-center justify-center">
                <span className="text-white text-2xl font-bold">Ant Design</span>
              </div>
            }
          >
            <Card.Meta
              title="Ant Design 页面"
              description="体验经典的 Ant Design 组件库，包含丰富的 UI 组件和设计规范"
            />
            <Link href="/antd-page" className="block mt-4">
              <Button type="primary" block>访问页面</Button>
            </Link>
          </Card>

          {/* Ant Design X 卡片 */}
          <Card 
            hoverable 
            className="shadow-lg rounded-xl overflow-hidden"
            cover={
              <div className="bg-gradient-to-r from-purple-500 to-pink-600 h-32 flex items-center justify-center">
                <span className="text-white text-2xl font-bold">Ant Design X</span>
              </div>
            }
          >
            <Card.Meta
              title="Ant Design X 页面"
              description="探索下一代 Ant Design X 组件库，提供更多现代化的交互体验"
            />
            <Link href="/antdx-page" className="block mt-4">
              <Button type="primary" block>访问页面</Button>
            </Link>
          </Card>

          {/* UnoCSS 卡片 */}
          <Card 
            hoverable 
            className="shadow-lg rounded-xl overflow-hidden"
            cover={
              <div className="bg-gradient-to-r from-green-500 to-teal-600 h-32 flex items-center justify-center">
                <span className="text-white text-2xl font-bold">UnoCSS</span>
              </div>
            }
          >
            <Card.Meta
              title="UnoCSS 页面"
              description="体验原子化 CSS 框架 UnoCSS，极简的样式解决方案"
            />
            <Link href="/unocss-page" className="block mt-4">
              <Button type="primary" block>访问页面</Button>
            </Link>
          </Card>
        </div>

        <div className="mt-12 text-center">
          <Space size="large">
            <Button 
              icon={<GithubOutlined />} 
              href="https://github.com/codebiu" 
              target="_blank"
            >
              查看 GitHub
            </Button>
          </Space>
        </div>
      </div>
    </div>
  );
}
