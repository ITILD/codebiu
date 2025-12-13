"use client";

import Link from "next/link";
import { Button, Card, Space, Typography, Row, Col } from "antd";
import { 
  HomeOutlined, 
  SettingOutlined, 
  DatabaseOutlined,
  UserOutlined,
  PlusOutlined
} from "@ant-design/icons";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* 头部欢迎区域 */}
        <div className="text-center mb-12">
          <Typography.Title level={1} className="text-blue-600 mb-4">
            欢迎来到 React 项目
          </Typography.Title>
          <Typography.Paragraph className="text-lg text-gray-600 mb-8">
            基于 src/pages 架构的现代化 React 应用演示，包含状态管理示例
          </Typography.Paragraph>
          <Space size="large">
            <Link href="/server">
              <Button type="primary" size="large" icon={<DatabaseOutlined />}>
                服务器管理
              </Button>
            </Link>
            <Link href="/antd-demo">
              <Button size="large" icon={<SettingOutlined />}>
                组件演示
              </Button>
            </Link>
          </Space>
        </div>

        {/* 功能卡片区域 */}
        <Row gutter={[24, 24]} className="mb-12">
          <Col xs={24} sm={12} lg={8}>
            <Card 
              hoverable 
              className="h-full text-center"
              cover={<div className="text-4xl p-4 text-blue-500"><DatabaseOutlined /></div>}
            >
              <Card.Meta 
                title="服务器管理" 
                description="查看和管理服务器状态，使用 Zustand 进行状态管理"
              />
              <div className="mt-4">
                <Link href="/server">
                  <Button type="link">进入管理</Button>
                </Link>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={8}>
            <Card 
              hoverable 
              className="h-full text-center"
              cover={<div className="text-4xl p-4 text-green-500"><SettingOutlined /></div>}
            >
              <Card.Meta 
                title="AntD 组件" 
                description="展示 Ant Design 组件库的各种组件使用示例"
              />
              <div className="mt-4">
                <Link href="/antd-demo">
                  <Button type="link">查看组件</Button>
                </Link>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={8}>
            <Card 
              hoverable 
              className="h-full text-center"
              cover={<div className="text-4xl p-4 text-orange-500"><PlusOutlined /></div>}
            >
              <Card.Meta 
                title="状态管理" 
                description="演示计数器状态管理，包括基础操作和复杂逻辑"
              />
              <div className="mt-4">
                <Link href="/counter-demo">
                  <Button type="link">体验计数</Button>
                </Link>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={8}>
            <Card 
              hoverable 
              className="h-full text-center"
              cover={<div className="text-4xl p-4 text-purple-500"><UserOutlined /></div>}
            >
              <Card.Meta 
                title="用户资料" 
                description="用户登录状态管理和个人资料展示"
              />
              <div className="mt-4">
                <Link href="/profile">
                  <Button type="link">用户中心</Button>
                </Link>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={8}>
            <Card 
              hoverable 
              className="h-full text-center"
              cover={<div className="text-4xl p-4 text-cyan-500"><HomeOutlined /></div>}
            >
              <Card.Meta 
                title="项目架构" 
                description="基于 src/pages 的清晰目录结构，易于维护"
              />
              <div className="mt-4">
                <Button type="link" disabled>即将推出</Button>
              </div>
            </Card>
          </Col>
        </Row>

        {/* 技术栈介绍 */}
        <Card title="技术栈" className="text-center">
          <Row justify="center" gutter={[32, 16]}>
            <Col>
              <Space direction="vertical" size="small">
                <div className="text-2xl">⚛️</div>
                <Typography.Text strong>React 19</Typography.Text>
              </Space>
            </Col>
            <Col>
              <Space direction="vertical" size="small">
                <div className="text-2xl">📦</div>
                <Typography.Text strong>Next.js 16</Typography.Text>
              </Space>
            </Col>
            <Col>
              <Space direction="vertical" size="small">
                <div className="text-2xl">🎨</div>
                <Typography.Text strong>Ant Design</Typography.Text>
              </Space>
            </Col>
            <Col>
              <Space direction="vertical" size="small">
                <div className="text-2xl">🔄</div>
                <Typography.Text strong>Zustand</Typography.Text>
              </Space>
            </Col>
            <Col>
              <Space direction="vertical" size="small">
                <div className="text-2xl">💨</div>
                <Typography.Text strong>TailwindCSS</Typography.Text>
              </Space>
            </Col>
          </Row>
        </Card>
      </div>
    </div>
  );
}