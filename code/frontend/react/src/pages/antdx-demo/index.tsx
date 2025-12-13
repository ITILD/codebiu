"use client";

import { Card, Button, Space, Typography, Row, Col, Badge, Progress } from "antd";
import { 
  BulbOutlined, 
  FireOutlined, 
  StarOutlined,
  ThunderboltOutlined
} from "@ant-design/icons";

export default function AntdxDemoPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <Typography.Title level={2} className="mb-2">Ant Design X 组件演示</Typography.Title>
          <Typography.Paragraph className="text-gray-600">
            展示 Ant Design X 组件库的实验性组件和高级功能
          </Typography.Paragraph>
        </div>
        
        {/* 高级功能展示 */}
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={12}>
            <Card 
              title={
                <Space>
                  <BulbOutlined />
                  <span>智能推荐</span>
                </Space>
              }
              extra={<Badge color="blue" text="Beta" />}
              className="h-full"
            >
              <div className="text-center py-6">
                <BulbOutlined className="text-6xl text-yellow-500 mb-4" />
                <Typography.Title level={3}>智能内容推荐</Typography.Title>
                <Typography.Paragraph>
                  基于 AI 的个性化内容推荐系统，为用户提供最相关的信息。
                </Typography.Paragraph>
                <Button type="primary" size="large">
                  体验推荐
                </Button>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <Space>
                  <FireOutlined />
                  <span>实时数据</span>
                </Space>
              }
              extra={<Badge color="red" text="Live" />}
              className="h-full"
            >
              <div className="py-6">
                <Typography.Title level={4} className="mb-4">实时性能指标</Typography.Title>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span>API 响应时间</span>
                      <span className="text-green-600">125ms</span>
                    </div>
                    <Progress percent={85} status="active" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span>系统负载</span>
                      <span className="text-blue-600">68%</span>
                    </div>
                    <Progress percent={68} strokeColor="#1890ff" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span>错误率</span>
                      <span className="text-red-600">0.1%</span>
                    </div>
                    <Progress percent={10} status="exception" />
                  </div>
                </Space>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <Space>
                  <StarOutlined />
                  <span>高级分析</span>
                </Space>
              }
              className="h-full"
            >
              <div className="py-6">
                <Typography.Title level={4} className="mb-4">用户行为分析</Typography.Title>
                <Row gutter={[16, 16]}>
                  <Col span={12}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-blue-600">1,247</div>
                      <div className="text-gray-600">日活跃用户</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-green-600">89%</div>
                      <div className="text-gray-600">用户满意度</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-purple-600">3.2</div>
                      <div className="text-gray-600">平均会话时长(分钟)</div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-orange-600">12.5%</div>
                      <div className="text-gray-600">转化率</div>
                    </div>
                  </Col>
                </Row>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card 
              title={
                <Space>
                  <ThunderboltOutlined />
                  <span>性能优化</span>
                </Space>
              }
              extra={<Badge color="green" text="优化中" />}
              className="h-full"
            >
              <div className="py-6">
                <Typography.Title level={4} className="mb-4">系统性能优化</Typography.Title>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div className="bg-green-50 p-3 rounded">
                    <Typography.Text strong className="text-green-700">
                      ✅ 代码分割已完成
                    </Typography.Text>
                    <Typography.Paragraph className="text-green-600 mb-0">
                      页面加载时间减少 40%
                    </Typography.Paragraph>
                  </div>
                  <div className="bg-yellow-50 p-3 rounded">
                    <Typography.Text strong className="text-yellow-700">
                      🔄 图像优化进行中
                    </Typography.Text>
                    <Typography.Paragraph className="text-yellow-600 mb-0">
                      预计减少 60% 带宽使用
                    </Typography.Paragraph>
                  </div>
                  <div className="bg-blue-50 p-3 rounded">
                    <Typography.Text strong className="text-blue-700">
                      💡 CDN 缓存策略
                    </Typography.Text>
                    <Typography.Paragraph className="text-blue-600 mb-0">
                      静态资源加载速度提升 80%
                    </Typography.Paragraph>
                  </div>
                </Space>
              </div>
            </Card>
          </Col>
        </Row>

        {/* 实验性功能 */}
        <Card title="实验性功能" className="mt-8">
          <Row gutter={[24, 24]}>
            <Col xs={24} md={8}>
              <Card size="small" className="text-center">
                <div className="text-2xl mb-2">🎨</div>
                <Typography.Text strong>主题定制</Typography.Text>
                <Typography.Paragraph className="text-sm text-gray-600 mt-2">
                  动态主题切换和自定义颜色方案
                </Typography.Paragraph>
                <Button size="small" disabled>即将推出</Button>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card size="small" className="text-center">
                <div className="text-2xl mb-2">🤖</div>
                <Typography.Text strong>AI 助手</Typography.Text>
                <Typography.Paragraph className="text-sm text-gray-600 mt-2">
                  智能对话和自动化任务处理
                </Typography.Paragraph>
                <Button size="small" disabled>即将推出</Button>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card size="small" className="text-center">
                <div className="text-2xl mb-2">📊</div>
                <Typography.Text strong>数据可视化</Typography.Text>
                <Typography.Paragraph className="text-sm text-gray-600 mt-2">
                  交互式图表和实时数据展示
                </Typography.Paragraph>
                <Button size="small" disabled>即将推出</Button>
              </Card>
            </Col>
          </Row>
        </Card>
      </div>
    </div>
  );
}