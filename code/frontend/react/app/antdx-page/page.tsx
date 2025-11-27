"use client";

import { Bubble, Conversations } from "@ant-design/x";
import { useState } from "react";
import { Button, Card, notification, Segmented, Space } from "antd";

export default function AntDXPage() {
  const [bubbleOpen, setBubbleOpen] = useState(false);
  const [segmentedValue, setSegmentedValue] = useState("item1");

  // 使用 antd 的 notification 组件替代 Ant Design X 的 Notification
  const [notificationApi, contextHolder] = notification.useNotification();
  
  const showNotification = () => {
    notificationApi.success({
      title: "通知标题",
      description: "这是一条成功的通知消息",
    });
  };

  // 示例对话数据
  const conversationData = [
    {
      id: '1',
      content: '你好，我是 Ant Design X 的 Conversations 组件',
      role: 'assistant',
      createAt: Date.now() - 1000 * 60 * 2,
    },
    {
      id: '2',
      content: '我可以展示对话历史记录',
      role: 'user',
      createAt: Date.now() - 1000 * 60,
    },
    {
      id: '3',
      content: '支持多种消息类型和交互方式',
      role: 'assistant',
      createAt: Date.now(),
    },
  ];

  return (
    <div style={{ padding: "24px", backgroundColor: "#f0f2f5", minHeight: "100vh" }}>
      {contextHolder}
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <h1 style={{ textAlign: "center", marginBottom: "24px", fontSize: "2rem", fontWeight: "bold" }}>
          Ant Design X 展示页面
        </h1>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px" }}>
          <Card title="气泡组件 (Bubble)" bordered={false}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <p>Bubble 是一个轻量级的浮动容器组件，常用于对话框或提示信息。</p>
              
              <div style={{ position: "relative", height: "200px", border: "1px solid #ddd", borderRadius: "8px" }}>
                <Button 
                  type="primary" 
                  onClick={() => setBubbleOpen(!bubbleOpen)}
                  style={{ position: "absolute", top: "20px", left: "20px" }}
                >
                  {bubbleOpen ? "关闭气泡" : "打开气泡"}
                </Button>
                
                <Bubble 
                  open={bubbleOpen}
                  content="这是一个 Ant Design X 的气泡组件！它可以根据内容自动调整大小和位置。"
                  style={{ position: "absolute", top: "80px", left: "20px" }}
                />
              </div>
            </Space>
          </Card>
          
          <Card title="对话组件 (Conversations)" bordered={false}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <p>Conversations 是 Ant Design X 提供的对话组件，用于展示对话历史。</p>
              
              <div style={{ height: "200px" }}>
                <Conversations items={conversationData.map(item => ({ ...item, key: item.id }))} />
              </div>
              
              <div style={{ marginTop: "16px" }}>
                <p>Conversations 特性：</p>
                <ul>
                  <li>展示对话历史记录</li>
                  <li>支持多种消息类型</li>
                  <li>自动滚动到底部</li>
                  <li>可自定义消息渲染</li>
                </ul>
              </div>
            </Space>
          </Card>
          
          <Card title="分段控制器 (Segmented)" bordered={false}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <p>Segmented 是一种分段控制器，用户可以通过点击选项来切换内容。</p>
              
              <Segmented
                options={[
                  { label: "选项1", value: "item1" },
                  { label: "选项2", value: "item2" },
                  { label: "选项3", value: "item3" },
                ]}
                value={segmentedValue}
                onChange={(value) => setSegmentedValue(value as string)}
              />
              
              <div style={{ marginTop: "16px", padding: "16px", backgroundColor: "#f5f5f5", borderRadius: "8px" }}>
                {segmentedValue === "item1" && <p>这是选项1的内容。你可以在这里放置任何你想展示的内容。</p>}
                {segmentedValue === "item2" && <p>这是选项2的内容。每个选项可以有不同的内容和行为。</p>}
                {segmentedValue === "item3" && <p>这是选项3的内容。分段控制器非常适合用来组织相关内容。</p>}
              </div>
            </Space>
          </Card>
          
          <Card title="Ant Design X 特性" bordered={false}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <h3>Ant Design X 简介</h3>
              <p>Ant Design X 是 Ant Design 团队推出的下一代设计系统，专注于提供更加现代化和创新的组件。</p>
              
              <h3>核心优势</h3>
              <ul>
                <li>更现代的设计语言</li>
                <li>更强的交互体验</li>
                <li>更丰富的动画效果</li>
                <li>更好的响应式支持</li>
                <li>与 Ant Design 生态无缝集成</li>
              </ul>
            </Space>
          </Card>
        </div>
      </div>
    </div>
  );
}