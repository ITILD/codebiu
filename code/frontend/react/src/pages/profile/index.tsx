"use client";

import { Card, Button, Space, Typography, Avatar, Row, Col, Tag, Input, Modal, Form, notification } from "antd";
import { 
  UserOutlined, 
  EditOutlined, 
  LogoutOutlined, 
  LoginOutlined,
  MailOutlined,
  PhoneOutlined,
  CalendarOutlined
} from "@ant-design/icons";
import { useState, useEffect } from "react";
import { useUserStore } from "../../stores/userStore";

export default function ProfilePage() {
  const { user, isAuthenticated, login, logout, updateProfile } = useUserStore();
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [loginModalVisible, setLoginModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [loginForm] = Form.useForm();
  const [api, contextHolder] = notification.useNotification();

  // 模拟自动登录演示
  useEffect(() => {
    if (!isAuthenticated) {
      // 延迟显示登录模态框
      const timer = setTimeout(() => {
        setLoginModalVisible(true);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated]);

  const handleLogin = (values: any) => {
    login({
      id: '1',
      name: values.name,
      email: values.email,
      avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${values.name}`,
      role: values.role || 'user'
    });
    setLoginModalVisible(false);
    api.success({
      message: "登录成功",
      description: `欢迎回来，${values.name}!`,
    });
  };

  const handleUpdateProfile = (values: any) => {
    updateProfile(values);
    setEditModalVisible(false);
    api.success({
      message: "更新成功",
      description: "您的个人资料已成功更新！",
    });
  };

  const handleLogout = () => {
    logout();
    api.info({
      message: "已退出登录",
      description: "您已成功退出登录，期待您的下次访问！",
    });
  };

  // 模拟用户数据
  const mockUser = {
    id: '1',
    name: '演示用户',
    email: 'demo@example.com',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=demo',
    role: 'admin' as const
  };

  const currentUser = user || (isAuthenticated ? mockUser : null);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        {contextHolder}
        
        <div className="mb-8">
          <Typography.Title level={2} className="mb-2">个人资料</Typography.Title>
          <Typography.Paragraph className="text-gray-600">
            管理您的个人信息和账户设置
          </Typography.Paragraph>
        </div>

        {currentUser ? (
          <Row gutter={[24, 24]}>
            {/* 用户信息卡片 */}
            <Col xs={24} lg={8}>
              <Card className="text-center h-full">
                <div className="mb-6">
                  <Avatar 
                    size={120} 
                    src={currentUser.avatar} 
                    icon={<UserOutlined />}
                    className="mb-4"
                  />
                  <Typography.Title level={3} className="mb-2">
                    {currentUser.name}
                  </Typography.Title>
                  <Tag 
                    color={currentUser.role === 'admin' ? 'red' : currentUser.role === 'user' ? 'blue' : 'default'}
                    className="mb-4"
                  >
                    {currentUser.role === 'admin' ? '管理员' : currentUser.role === 'user' ? '普通用户' : '访客'}
                  </Tag>
                </div>
                
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Button 
                    type="primary" 
                    icon={<EditOutlined />}
                    onClick={() => setEditModalVisible(true)}
                    block
                  >
                    编辑资料
                  </Button>
                  <Button 
                    danger 
                    icon={<LogoutOutlined />}
                    onClick={handleLogout}
                    block
                  >
                    退出登录
                  </Button>
                </Space>
              </Card>
            </Col>

            {/* 详细信息 */}
            <Col xs={24} lg={16}>
              <Card title="基本信息" className="h-full">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div className="flex items-center space-x-3">
                    <MailOutlined className="text-gray-500" />
                    <div>
                      <Typography.Text strong>邮箱:</Typography.Text>
                      <Typography.Paragraph className="mb-0 ml-2">
                        {currentUser.email}
                      </Typography.Paragraph>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <UserOutlined className="text-gray-500" />
                    <div>
                      <Typography.Text strong>用户 ID:</Typography.Text>
                      <Typography.Paragraph className="mb-0 ml-2">
                        {currentUser.id}
                      </Typography.Paragraph>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <CalendarOutlined className="text-gray-500" />
                    <div>
                      <Typography.Text strong>注册时间:</Typography.Text>
                      <Typography.Paragraph className="mb-0 ml-2">
                        2024-01-15
                      </Typography.Paragraph>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <PhoneOutlined className="text-gray-500" />
                    <div>
                      <Typography.Text strong>电话:</Typography.Text>
                      <Typography.Paragraph className="mb-0 ml-2">
                        138****8888
                      </Typography.Paragraph>
                    </div>
                  </div>
                </Space>
              </Card>
            </Col>

            {/* 账户统计 */}
            <Col xs={24}>
              <Card title="账户统计">
                <Row gutter={[24, 24]}>
                  <Col xs={24} sm={8}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-blue-600">156</div>
                      <div className="text-gray-600">登录次数</div>
                    </div>
                  </Col>
                  <Col xs={24} sm={8}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-green-600">23</div>
                      <div className="text-gray-600">项目数量</div>
                    </div>
                  </Col>
                  <Col xs={24} sm={8}>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-purple-600">2.5h</div>
                      <div className="text-gray-600">平均在线时长</div>
                    </div>
                  </Col>
                </Row>
              </Card>
            </Col>
          </Row>
        ) : (
          <Card className="text-center">
            <div className="py-12">
              <UserOutlined className="text-6xl text-gray-400 mb-4" />
              <Typography.Title level={3} className="text-gray-500 mb-4">
                请先登录
              </Typography.Title>
              <Typography.Paragraph className="text-gray-500 mb-6">
                您需要登录后才能查看个人资料
              </Typography.Paragraph>
              <Button 
                type="primary" 
                size="large"
                icon={<LoginOutlined />}
                onClick={() => setLoginModalVisible(true)}
              >
                立即登录
              </Button>
            </div>
          </Card>
        )}

        {/* 编辑资料模态框 */}
        <Modal
          title="编辑个人资料"
          open={editModalVisible}
          onOk={() => form.submit()}
          onCancel={() => setEditModalVisible(false)}
          okText="保存"
          cancelText="取消"
        >
          <Form
            form={form}
            layout="vertical"
            onFinish={handleUpdateProfile}
            initialValues={currentUser ? {
              name: currentUser.name,
              email: currentUser.email,
              role: currentUser.role
            } : {}}
          >
            <Form.Item
              label="姓名"
              name="name"
              rules={[{ required: true, message: '请输入姓名' }]}
            >
              <Input placeholder="请输入姓名" />
            </Form.Item>
            <Form.Item
              label="邮箱"
              name="email"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入正确的邮箱格式' }
              ]}
            >
              <Input placeholder="请输入邮箱" />
            </Form.Item>
            <Form.Item
              label="角色"
              name="role"
            >
              <Input placeholder="请输入角色" />
            </Form.Item>
          </Form>
        </Modal>

        {/* 登录模态框 */}
        <Modal
          title="用户登录"
          open={loginModalVisible}
          onOk={() => loginForm.submit()}
          onCancel={() => setLoginModalVisible(false)}
          okText="登录"
          cancelText="取消"
          footer={null}
        >
          <Form
            form={loginForm}
            layout="vertical"
            onFinish={handleLogin}
            initialValues={{
              name: '演示用户',
              email: 'demo@example.com',
              role: 'admin'
            }}
          >
            <Form.Item
              label="姓名"
              name="name"
              rules={[{ required: true, message: '请输入姓名' }]}
            >
              <Input placeholder="请输入姓名" />
            </Form.Item>
            <Form.Item
              label="邮箱"
              name="email"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入正确的邮箱格式' }
              ]}
            >
              <Input placeholder="请输入邮箱" />
            </Form.Item>
            <Form.Item
              label="角色"
              name="role"
            >
              <Input placeholder="请输入角色 (admin/user/guest)" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block>
                登录
              </Button>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </div>
  );
}