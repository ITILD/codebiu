"use client";

import { Card, Divider, Input, Modal, notification, Popconfirm, Select, Space, Switch, Tabs, Tag, Tooltip, Typography, Button } from "antd";
import { useState } from "react";

export default function AntDDemoPage() {
  const [inputValue, setInputValue] = useState("");
  const [selectValue, setSelectValue] = useState<string>();
  const [switchChecked, setSwitchChecked] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [api, contextHolder] = notification.useNotification();

  const showNotification = () => {
    api.success({
      message: "操作成功",
      description: "您的操作已成功完成！",
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <Typography.Title level={2} className="mb-2">Ant Design 组件演示</Typography.Title>
          <Typography.Paragraph className="text-gray-600">
            展示 Ant Design 组件库的各种组件使用示例和最佳实践
          </Typography.Paragraph>
        </div>

        {contextHolder}
        
        {/* 基础组件 */}
        <Card title="基础组件" className="mb-6">
          <Typography.Title level={4}>按钮组件</Typography.Title>
          <Space wrap className="mb-6">
            <Button type="primary">主要按钮</Button>
            <Button>默认按钮</Button>
            <Button type="dashed">虚线按钮</Button>
            <Button type="link">链接按钮</Button>
            <Button type="text">文本按钮</Button>
            <Button danger>危险按钮</Button>
          </Space>
          
          <Divider />
          
          <Typography.Title level={4}>标签组件</Typography.Title>
          <Space wrap>
            <Tag color="magenta">magenta</Tag>
            <Tag color="red">red</Tag>
            <Tag color="volcano">volcano</Tag>
            <Tag color="orange">orange</Tag>
            <Tag color="gold">gold</Tag>
            <Tag color="lime">lime</Tag>
            <Tag color="green">green</Tag>
            <Tag color="cyan">cyan</Tag>
            <Tag color="blue">blue</Tag>
            <Tag color="geekblue">geekblue</Tag>
            <Tag color="purple">purple</Tag>
          </Space>
          
          <Divider />
          
          <Typography.Title level={4}>工具提示</Typography.Title>
          <Tooltip title="这是一个提示文字">
            <Button>鼠标移过显示提示</Button>
          </Tooltip>
        </Card>
        
        {/* 输入组件 */}
        <Card title="输入组件" className="mb-6">
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Typography.Text strong>单行输入:</Typography.Text>
              <Input 
                placeholder="请输入内容" 
                value={inputValue} 
                onChange={(e) => setInputValue(e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Typography.Text strong>多行输入:</Typography.Text>
              <Input.TextArea 
                placeholder="多行文本输入" 
                rows={4}
                className="mt-2"
              />
            </div>
            <div>
              <Typography.Text strong>搜索输入:</Typography.Text>
              <Input.Search 
                placeholder="请输入搜索关键词"
                className="mt-2"
                onSearch={(value) => console.log('搜索:', value)}
              />
            </div>
          </Space>
        </Card>
        
        {/* 选择器 */}
        <Card title="选择器" className="mb-6">
          <Space wrap>
            <div>
              <Typography.Text strong>下拉选择:</Typography.Text>
              <Select
                value={selectValue}
                placeholder="请选择"
                style={{ width: 200, marginTop: 8 }}
                onChange={(value) => setSelectValue(value)}
                options={[
                  { value: 'option1', label: '选项1' },
                  { value: 'option2', label: '选项2' },
                  { value: 'option3', label: '选项3' },
                  { value: 'disabled', label: '禁用选项', disabled: true },
                ]}
              />
            </div>
            
            <div>
              <Typography.Text strong>多选:</Typography.Text>
              <Select
                mode="multiple"
                placeholder="请选择多个选项"
                style={{ width: 200, marginTop: 8 }}
                options={[
                  { value: 'option1', label: '选项1' },
                  { value: 'option2', label: '选项2' },
                  { value: 'option3', label: '选项3' },
                ]}
              />
            </div>
          </Space>
        </Card>
        
        {/* 反馈组件 */}
        <Card title="反馈组件" className="mb-6">
          <Space wrap>
            <Switch 
              checked={switchChecked} 
              onChange={(checked) => setSwitchChecked(checked)} 
            />
            <Button onClick={() => setModalVisible(true)}>打开模态框</Button>
            <Button onClick={showNotification} type="primary">显示通知</Button>
            <Popconfirm 
              title="删除确认"
              description="确定要删除这个项目吗？此操作不可撤销。"
              onConfirm={() => console.log("确认删除")}
              onCancel={() => console.log("取消删除")}
              okText="确认"
              cancelText="取消"
            >
              <Button danger>删除确认</Button>
            </Popconfirm>
          </Space>
        </Card>
        
        {/* 导航组件 */}
        <Card title="导航组件" className="mb-6">
          <Tabs
            defaultActiveKey="1"
            items={[
              {
                key: '1',
                label: 'Tab 1',
                children: (
                  <div>
                    <Typography.Title level={4}>第一个标签页</Typography.Title>
                    <Typography.Paragraph>
                      这是第一个标签页的内容。您可以在这里放置任何您想要展示的内容。
                    </Typography.Paragraph>
                  </div>
                ),
              },
              {
                key: '2',
                label: 'Tab 2',
                children: (
                  <div>
                    <Typography.Title level={4}>第二个标签页</Typography.Title>
                    <Typography.Paragraph>
                      这是第二个标签页的内容。您可以在这里放置任何您想要展示的内容。
                    </Typography.Paragraph>
                  </div>
                ),
              },
              {
                key: '3',
                label: 'Tab 3',
                children: (
                  <div>
                    <Typography.Title level={4}>第三个标签页</Typography.Title>
                    <Typography.Paragraph>
                      这是第三个标签页的内容。您可以在这里放置任何您想要展示的内容。
                    </Typography.Paragraph>
                  </div>
                ),
              },
            ]}
          />
        </Card>
        
        {/* 模态框 */}
        <Modal
          title="模态框标题"
          open={modalVisible}
          onOk={() => setModalVisible(false)}
          onCancel={() => setModalVisible(false)}
        >
          <Typography.Paragraph>
            这是模态框的内容。您可以在这里放置任何您想要展示的内容。
          </Typography.Paragraph>
          <Typography.Paragraph>
            模态框可以用于显示重要信息、确认操作或收集用户输入。
          </Typography.Paragraph>
        </Modal>
      </div>
    </div>
  );
}