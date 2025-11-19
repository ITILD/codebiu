"use client";

import { Button, Card, Divider, Input, Modal, notification, Popconfirm, Select, Space, Switch, Tabs, Tag, Tooltip, Typography } from "antd";
import { useState } from "react";

const AntDPage = () => {
  const [inputValue, setInputValue] = useState("");
  const [selectValue, setSelectValue] = useState();
  const [switchChecked, setSwitchChecked] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [api, contextHolder] = notification.useNotification();

  const showNotification = () => {
    api.info({
      message: "通知标题",
      title: "这是一条通知信息",
    });
  };

  return (
    <div className="p-6">
      {contextHolder}
      <Typography.Title level={2}>Ant Design 组件展示</Typography.Title>
      
      {/* 基础组件 */}
      <Card title="基础组件" className="mb-6">
        <Space wrap>
          <Button type="primary">主要按钮</Button>
          <Button>默认按钮</Button>
          <Button type="dashed">虚线按钮</Button>
          <Button type="link">链接按钮</Button>
          <Button type="text">文本按钮</Button>
        </Space>
        
        <Divider />
        
        <Space wrap>
          <Tag color="magenta">magenta</Tag>
          <Tag color="red">red</Tag>
          <Tag color="volcano">volcano</Tag>
          <Tag color="orange">orange</Tag>
          <Tag color="gold">gold</Tag>
          <Tag color="lime">lime</Tag>
        </Space>
        
        <Divider />
        
        <Tooltip title="提示文字">
          <span>鼠标移过显示提示文字</span>
        </Tooltip>
      </Card>
      
      {/* 输入组件 */}
      <Card title="输入组件" className="mb-6">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input 
            placeholder="请输入内容" 
            value={inputValue} 
            onChange={(e) => setInputValue(e.target.value)} 
          />
          <Input.TextArea placeholder="多行文本输入" rows={4} />
        </Space>
      </Card>
      
      {/* 选择器 */}
      <Card title="选择器" className="mb-6">
        <Space wrap>
          <Select
            value={selectValue}
            placeholder="请选择"
            style={{ width: 120 }}
            onChange={(value) => setSelectValue(value)}
            options={[
              { value: 'option1', label: '选项1' },
              { value: 'option2', label: '选项2' },
              { value: 'option3', label: '选项3' },
            ]}
          />
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
          <Button onClick={showNotification}>打开通知</Button>
          <Popconfirm 
            title="删除确认"
            description="确定要删除这个项目吗？"
            onConfirm={() => console.log("确认删除")}
            onCancel={() => console.log("取消删除")}
            okText="确认"
            cancelText="取消"
          >
            <Button danger>删除</Button>
          </Popconfirm>
        </Space>
      </Card>
      
      {/* 导航组件 */}
      <Card title="导航组件">
        <Tabs
          defaultActiveKey="1"
          items={[
            {
              key: '1',
              label: 'Tab 1',
              children: 'Tab 1 内容',
            },
            {
              key: '2',
              label: 'Tab 2',
              children: 'Tab 2 内容',
            },
            {
              key: '3',
              label: 'Tab 3',
              children: 'Tab 3 内容',
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
        <p>这是一些模态框内容</p>
      </Modal>
    </div>
  );
};

export default AntDPage;