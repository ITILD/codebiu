"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, Button } from "antd";
import { 
  HomeOutlined, 
  SettingOutlined, 
  DatabaseOutlined, 
  LayoutOutlined,
  MessageOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined
} from "@ant-design/icons";
import { useServerStore } from './store';

export default function ServerManagement() {
  const { collapsed, setCollapsed, activeMenuKey, setActiveMenuKey } = useServerStore();
  
  const menuItems = [
    {
      key: '/_server',
      icon: <HomeOutlined />,
      label: 'Overview',
      disabled: false,
    },
    {
      key: '/_server/authorization',
      icon: <SettingOutlined />,
      label: 'Authorization',
      disabled: false,
      children: [
        {
          key: '/_server/authorization/user',
          label: 'User',
        }
      ]
    },
    {
      key: '/_server/database',
      icon: <DatabaseOutlined />,
      label: 'DataBase',
      children: [
        {
          key: '/_server/database/overview',
          label: 'Overview',
        }
      ]
    },
    {
      key: '/_server/ai',
      icon: <SettingOutlined />,
      label: 'AI',
      children: [
        {
          key: '/_server/ai/chat',
          label: 'Chat',
        }
      ]
    }
  ];

  const onClick = (e: any) => {
    console.log('click ', e);
    setActiveMenuKey(e.key);
  };

  return (
    <div className="flex w-full">
      {/* 左侧菜单 */}
      <div className={`bg-white h-screen sticky top-0 transition-all duration-300 ${collapsed ? 'w-20' : 'w-60'}`}>
        <Menu
          mode="inline"
          theme="light"
          inlineCollapsed={collapsed}
          selectedKeys={[activeMenuKey]}
          items={menuItems}
          onClick={onClick}
          className="h-full border-r"
        />
      </div>
      
      {/* 右侧内容区域 */}
      <div className="flex-1 min-w-0 p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">服务器管理</h1>
          <Button 
            type="primary" 
            onClick={() => setCollapsed(!collapsed)}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          >
            {!collapsed && '收起菜单'}
          </Button>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">欢迎来到服务器管理页面</h2>
          <p>这是服务器管理的主页面。您可以使用左侧菜单导航到不同的功能模块。</p>
          
          <div className="mt-8">
            <h3 className="text-lg font-medium mb-3">系统状态</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="border rounded-lg p-4">
                <h4 className="font-medium">CPU 使用率</h4>
                <p className="text-2xl font-bold text-blue-600">42%</p>
              </div>
              <div className="border rounded-lg p-4">
                <h4 className="font-medium">内存使用率</h4>
                <p className="text-2xl font-bold text-green-600">68%</p>
              </div>
              <div className="border rounded-lg p-4">
                <h4 className="font-medium">磁盘空间</h4>
                <p className="text-2xl font-bold text-yellow-600">256GB / 1TB</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}