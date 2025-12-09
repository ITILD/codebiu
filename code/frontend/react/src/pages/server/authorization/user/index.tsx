"use client";

import { Card, Table, Button, Space, Tag } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";

/**
 * 用户管理页面组件
 * 提供用户账号的增删改查功能
 */
export default function UserManagement() {
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'admin' ? 'red' : 'blue'}>{role.toUpperCase()}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'volcano'}>{status === 'active' ? '活跃' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="middle">
          <Button icon={<EditOutlined />}>编辑</Button>
          <Button icon={<DeleteOutlined />} danger>删除</Button>
        </Space>
      ),
    },
  ];

  const data = [
    {
      key: '1',
      id: 1,
      username: 'admin',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
    },
    {
      key: '2',
      id: 2,
      username: 'user1',
      email: 'user1@example.com',
      role: 'user',
      status: 'active',
    },
    {
      key: '3',
      id: 3,
      username: 'user2',
      email: 'user2@example.com',
      role: 'user',
      status: 'inactive',
    },
  ];

  return (
    <div>
      <Card 
        title="用户管理" 
        extra={
          <Button type="primary" icon={<PlusOutlined />}>
            添加用户
          </Button>
        }
      >
        <Table columns={columns} dataSource={data} pagination={{ pageSize: 5 }} />
      </Card>
    </div>
  );
}