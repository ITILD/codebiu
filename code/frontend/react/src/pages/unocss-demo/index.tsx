"use client";

import { Card, Typography, Row, Col, Badge, Tag } from "antd";
import { 
  ThunderboltOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  StarOutlined
} from "@ant-design/icons";

export default function UnoCssDemoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-r from-blue-500 to-purple-600 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 text-center">
          <Typography.Title level={1} className="text-white mb-4">
            UnoCSS 演示页面
          </Typography.Title>
          <Typography.Paragraph className="text-blue-100 text-lg">
            展示 UnoCSS 原子化 CSS 引擎的强大功能和性能优势
          </Typography.Paragraph>
        </div>
        
        {/* 功能演示 */}
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={12}>
            <Card 
              title={
                <span className="flex items-center">
                  <ThunderboltOutlined className="mr-2" />
                  颜色工具类
                </span>
              }
              className="h-full"
            >
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-red-500 p-3 bg-red-50 rounded text-center">红色文字</div>
                  <div className="text-green-500 p-3 bg-green-50 rounded text-center">绿色文字</div>
                  <div className="text-blue-500 p-3 bg-blue-50 rounded text-center">蓝色文字</div>
                  <div className="text-purple-500 p-3 bg-purple-50 rounded text-center">紫色文字</div>
                </div>
                <div className="flex space-x-2">
                  <Tag color="magenta">magenta</Tag>
                  <Tag color="red">red</Tag>
                  <Tag color="volcano">volcano</Tag>
                  <Tag color="orange">orange</Tag>
                  <Tag color="gold">gold</Tag>
                </div>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <span className="flex items-center">
                  <RocketOutlined className="mr-2" />
                  布局工具类
                </span>
              }
              className="h-full"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between bg-gray-100 p-3 rounded">
                  <div className="bg-red-200 px-3 py-1 rounded text-sm">左对齐</div>
                  <div className="bg-blue-200 px-3 py-1 rounded text-sm">居中对齐</div>
                  <div className="bg-green-200 px-3 py-1 rounded text-sm">右对齐</div>
                </div>
                <div className="flex flex-col space-y-2">
                  <div className="bg-gray-200 p-2 rounded text-sm">垂直排列 1</div>
                  <div className="bg-gray-300 p-3 rounded text-sm">垂直排列 2</div>
                  <div className="bg-gray-400 p-4 rounded text-sm">垂直排列 3</div>
                </div>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <span className="flex items-center">
                  <CheckCircleOutlined className="mr-2" />
                  间距工具类
                </span>
              }
              className="h-full"
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="bg-gray-200 p-2 rounded">小间距 (p-2)</div>
                  <div className="bg-gray-300 p-4 rounded">中间距 (p-4)</div>
                  <div className="bg-gray-400 p-6 rounded">大间距 (p-6)</div>
                </div>
                <div className="flex space-x-4">
                  <div className="bg-blue-200 px-2 py-1 rounded text-xs">外边距</div>
                  <div className="bg-green-200 px-2 py-1 rounded text-xs">外边距</div>
                  <div className="bg-purple-200 px-2 py-1 rounded text-xs">外边距</div>
                </div>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <span className="flex items-center">
                  <StarOutlined className="mr-2" />
                  响应式设计
                </span>
              }
              className="h-full"
            >
              <div className="space-y-4">
                <div className="text-sm md:text-base lg:text-lg xl:text-xl text-blue-600 font-medium">
                  响应式文字大小
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs sm:text-sm">
                  <div className="bg-red-100 p-2 rounded text-center">移动端</div>
                  <div className="bg-blue-100 p-2 rounded text-center">平板端</div>
                  <div className="bg-green-100 p-2 rounded text-center">桌面端</div>
                </div>
                <div className="hidden md:block bg-yellow-100 p-2 rounded text-center">
                  在中等及以上屏幕显示
                </div>
              </div>
            </Card>
          </Col>
        </Row>

        {/* UnoCSS 优势对比 */}
        <Card 
          title="UnoCSS vs Tailwind CSS" 
          className="mt-8"
          extra={<Badge color="green" text="性能对比" />}
        >
          <Row gutter={[24, 24]}>
            <Col xs={24} md={12}>
              <div className="space-y-4">
                <h4 className="text-lg font-semibold text-green-600">🚀 UnoCSS 优势</h4>
                <ul className="space-y-2">
                  <li className="flex items-center">
                    <CheckCircleOutlined className="text-green-500 mr-2" />
                    <span>更快的构建速度</span>
                  </li>
                  <li className="flex items-center">
                    <CheckCircleOutlined className="text-green-500 mr-2" />
                    <span>更小的包体积</span>
                  </li>
                  <li className="flex items-center">
                    <CheckCircleOutlined className="text-green-500 mr-2" />
                    <span>更灵活的自定义规则</span>
                  </li>
                  <li className="flex items-center">
                    <CheckCircleOutlined className="text-green-500 mr-2" />
                    <span>更好的 TypeScript 支持</span>
                  </li>
                  <li className="flex items-center">
                    <CheckCircleOutlined className="text-green-500 mr-2" />
                    <span>即时按需生成 CSS</span>
                  </li>
                </ul>
              </div>
            </Col>
            <Col xs={24} md={12}>
              <div className="space-y-4">
                <h4 className="text-lg font-semibold text-blue-600">⚡ 性能数据</h4>
                <div className="bg-gray-50 p-4 rounded">
                  <div className="mb-3">
                    <div className="flex justify-between text-sm">
                      <span>构建速度</span>
                      <span className="text-green-600 font-bold">+65%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-green-500 h-2 rounded-full" style={{width: '85%'}}></div>
                    </div>
                  </div>
                  <div className="mb-3">
                    <div className="flex justify-between text-sm">
                      <span>包体积减少</span>
                      <span className="text-blue-600 font-bold">-45%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-500 h-2 rounded-full" style={{width: '55%'}}></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm">
                      <span>开发体验</span>
                      <span className="text-purple-600 font-bold">+80%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-purple-500 h-2 rounded-full" style={{width: '90%'}}></div>
                    </div>
                  </div>
                </div>
              </div>
            </Col>
          </Row>
        </Card>

        {/* 使用示例 */}
        <Card title="代码示例" className="mt-8">
          <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm overflow-x-auto">
            <pre>{`// UnoCSS 使用示例
<div className="min-h-screen bg-gradient-to-r from-blue-500 to-purple-600 p-8">
  <div className="max-w-4xl mx-auto">
    <h1 className="text-4xl font-bold text-white mb-8 text-center">
      UnoCSS 功能演示
    </h1>
    
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="bg-white p-6 rounded-lg shadow-lg">
        <h2 className="text-2xl font-semibold mb-4">原子化类名</h2>
        <p className="text-gray-600">简单、高效、响应式</p>
      </div>
    </div>
  </div>
</div>`}</pre>
          </div>
        </Card>
      </div>
    </div>
  );
}