"use client";

import { Card, Button, Space, Typography, InputNumber, Row, Col, Divider } from "antd";
import { useCounterStore } from "../../stores/counterStore";

export default function CounterDemoPage() {
  const { 
    count, 
    increment, 
    decrement, 
    reset, 
    incrementBy, 
    decrementBy 
  } = useCounterStore();

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 text-center">
          <Typography.Title level={2} className="mb-2">计数器状态管理演示</Typography.Title>
          <Typography.Paragraph className="text-gray-600">
            演示如何使用 Zustand 进行状态管理，包括基础操作和复杂逻辑
          </Typography.Paragraph>
        </div>

        <Row gutter={[24, 24]}>
          {/* 主要计数器显示 */}
          <Col xs={24} lg={12}>
            <Card title="计数器" className="text-center">
              <div className="py-8">
                <div className="text-6xl font-bold text-blue-600 mb-6">
                  {count}
                </div>
                <Space size="large">
                  <Button 
                    type="primary" 
                    size="large"
                    onClick={increment}
                    className="w-16 h-16 text-xl"
                  >
                    +
                  </Button>
                  <Button 
                    size="large"
                    onClick={decrement}
                    className="w-16 h-16 text-xl"
                  >
                    -
                  </Button>
                </Space>
              </div>
              
              <Divider />
              
              <Space wrap>
                <Button onClick={reset} danger>
                  重置为 0
                </Button>
              </Space>
            </Card>
          </Col>

          {/* 自定义数值操作 */}
          <Col xs={24} lg={12}>
            <Card title="自定义操作" className="h-full">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Typography.Text strong>增加指定数值:</Typography.Text>
                  <div className="mt-2">
                    <InputNumber
                      min={1}
                      max={100}
                      defaultValue={5}
                      onPressEnter={(e: any) => {
                        const value = parseInt(e.target.value);
                        if (!isNaN(value)) {
                          incrementBy(value);
                        }
                      }}
                    />
                    <Button 
                      type="primary" 
                      className="ml-2"
                      onClick={(e: any) => {
                        const input = e.currentTarget.previousElementSibling.querySelector('input');
                        const value = parseInt(input.value);
                        if (!isNaN(value)) {
                          incrementBy(value);
                        }
                      }}
                    >
                      增加
                    </Button>
                  </div>
                </div>

                <div>
                  <Typography.Text strong>减少指定数值:</Typography.Text>
                  <div className="mt-2">
                    <InputNumber
                      min={1}
                      max={100}
                      defaultValue={5}
                      onPressEnter={(e: any) => {
                        const value = parseInt(e.target.value);
                        if (!isNaN(value) && value <= count) {
                          decrementBy(value);
                        }
                      }}
                    />
                    <Button 
                      className="ml-2"
                      onClick={(e: any) => {
                        const input = e.currentTarget.previousElementSibling.querySelector('input');
                        const value = parseInt(input.value);
                        if (!isNaN(value) && value <= count) {
                          decrementBy(value);
                        }
                      }}
                    >
                      减少
                    </Button>
                  </div>
                </div>

                <Divider />

                <div>
                  <Typography.Text strong>快速操作:</Typography.Text>
                  <div className="mt-2 space-x-2 space-y-2">
                    <Button onClick={() => incrementBy(10)}>+10</Button>
                    <Button onClick={() => incrementBy(50)}>+50</Button>
                    <Button onClick={() => incrementBy(100)}>+100</Button>
                  </div>
                  <div className="mt-2 space-x-2 space-y-2">
                    <Button onClick={() => decrementBy(10)} disabled={count < 10}>-10</Button>
                    <Button onClick={() => decrementBy(50)} disabled={count < 50}>-50</Button>
                    <Button onClick={() => decrementBy(100)} disabled={count < 100}>-100</Button>
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
        </Row>

        {/* 状态说明 */}
        <Card title="Zustand 状态管理说明" className="mt-6">
          <Row gutter={[24, 16]}>
            <Col xs={24} md={12}>
              <Typography.Title level={4}>Store 结构</Typography.Title>
              <Typography.Paragraph>
                这个演示展示了如何使用 Zustand 创建和管理应用状态:
              </Typography.Paragraph>
              <ul className="space-y-2">
                <li><Typography.Text code>count</Typography.Text> - 当前计数值</li>
                <li><Typography.Text code>increment()</Typography.Text> - 增加 1</li>
                <li><Typography.Text code>decrement()</Typography.Text> - 减少 1</li>
                <li><Typography.Text code>reset()</Typography.Text> - 重置为 0</li>
                <li><Typography.Text code>incrementBy(amount)</Typography.Text> - 增加指定数值</li>
                <li><Typography.Text code>decrementBy(amount)</Typography.Text> - 减少指定数值</li>
              </ul>
            </Col>
            <Col xs={24} md={12}>
              <Typography.Title level={4}>使用优势</Typography.Title>
              <Typography.Paragraph>
                Zustand 是一个轻量级的状态管理库，相比 Redux 有以下优势:
              </Typography.Paragraph>
              <ul className="space-y-2">
                <li>• 极简的 API，学习成本低</li>
                <li>• 优秀的 TypeScript 支持</li>
                <li>• 灵活的中间件系统</li>
                <li>• 优秀的开发体验</li>
                <li>• 包体积小，性能优秀</li>
                <li>• 支持 React 和原生 JavaScript</li>
              </ul>
            </Col>
          </Row>
        </Card>
      </div>
    </div>
  );
}