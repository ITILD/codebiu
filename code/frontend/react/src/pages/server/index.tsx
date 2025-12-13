"use client";

import { useEffect } from "react";
import { Menu, Button, Card, Statistic, Row, Col, Typography, Space } from "antd";
import { 
  HomeOutlined, 
  SettingOutlined, 
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  CloudServerOutlined
} from "@ant-design/icons";
import { useServerStore } from "../../stores/serverStore";

export default function ServerPage() {
  const { 
    collapsed, 
    setCollapsed, 
    activeMenuKey, 
    setActiveMenuKey,
    serverInfo,
    updateServerInfo
  } = useServerStore();

  // 模拟服务器信息更新
  useEffect(() => {
    const interval = setInterval(() => {
      updateServerInfo({
        cpu: Math.floor(Math.random() * 100),
        memory: Math.floor(Math.random() * 100),
        disk: `${Math.floor(Math.random() * 500)}GB / 1TB`,
        uptime: `${Math.floor(Math.random() * 720)}小时`
      });
    }, 5000);

    return () => clearInterval(interval);
  }, [updateServerInfo]);

  const menuItems = [
    {
      key: '/server',
      icon: <HomeOutlined />,
      label: '概览',
      disabled: false,
    },
    {
      key: '/server/database',
      icon: <DatabaseOutlined />,
      label: '数据库',
      children: [
        {
          key: '/server/database/overview',
          label: '概览',
        },
        {
          key: '/server/database/performance',
          label: '性能监控',
        }
      ]
    },
    {
      key: '/server/settings',
      icon: <SettingOutlined />,
      label: '设置',
      children: [
        {
          key: '/server/settings/general',
          label: '常规设置',
        },
        {
          key: '/server/settings/security',
          label: '安全设置',
        }
      ]
    }
  ];

  const onClick = (e: any) => {
    setActiveMenuKey(e.key);
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* 左侧菜单 */}
      <div className={`bg-white shadow-lg transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'}`}>
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            {!collapsed && (
              <div className="flex items-center space-x-2">
                <CloudServerOutlined className="text-2xl text-blue-600" />
                <Typography.Title level={4} className="m-0">服务器管理</Typography.Title>
              </div>
            )}
            <Button 
              type="text"
              onClick={() => setCollapsed(!collapsed)}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            />
          </div>
        </div>
        
        <Menu
          mode="inline"
          theme="light"
          inlineCollapsed={collapsed}
          selectedKeys={[activeMenuKey]}
          items={menuItems}
          onClick={onClick}
          className="border-r-0"
        />
      </div>
      
      {/* 右侧内容区域 */}
      <div className="flex-1 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <Typography.Title level={2} className="mb-2">服务器概览</Typography.Title>
            <Typography.Paragraph className="text-gray-600">
              实时监控系统状态和性能指标
            </Typography.Paragraph>
          </div>
          
          {/* 系统状态卡片 */}
          <Row gutter={[24, 24]} className="mb-8">
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="CPU 使用率"
                  value={serverInfo.cpu}
                  suffix="%"
                  valueStyle={{ color: serverInfo.cpu > 80 ? '#cf1322' : serverInfo.cpu > 60 ? '#faad14' : '#3f8600' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="内存使用率"
                  value={serverInfo.memory}
                  suffix="%"
                  valueStyle={{ color: serverInfo.memory > 80 ? '#cf1322' : serverInfo.memory > 60 ? '#faad14' : '#3f8600' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="磁盘空间"
                  value={serverInfo.disk}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="运行时间"
                  value={serverInfo.uptime}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Card>
            </Col>
          </Row>

          {/* 详细状态信息 */}
          <Row gutter={[24, 24]}>
            <Col xs={24} lg={12}>
              <Card title="系统信息" className="h-full">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div className="flex justify-between">
                    <span>操作系统:</span>
                    <span className="font-mono">Ubuntu 22.04 LTS</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Node.js 版本:</span>
                    <span className="font-mono">v18.17.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span>数据库:</span>
                    <span className="font-mono">PostgreSQL 14.5</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Redis 版本:</span>
                    <span className="font-mono">7.0.8</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Docker 版本:</span>
                    <span className="font-mono">24.0.2</span>
                  </div>
                </Space>
              </Card>
            </Col>
            
            <Col xs={24} lg={12}>
              <Card title="网络状态" className="h-full">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div className="flex justify-between">
                    <span>公网 IP:</span>
                    <span className="font-mono">192.168.1.100</span>
                  </div>
                  <div className="flex justify-between">
                    <span>内网 IP:</span>
                    <span className="font-mono">10.0.0.50</span>
                  </div>
                  <div className="flex justify-between">
                    <span>带宽使用:</span>
                    <span className="font-mono">125 MB/s</span>
                  </div>
                  <div className="flex justify-between">
                    <span>连接数:</span>
                    <span className="font-mono">1,247</span>
                  </div>
                  <div className="flex justify-between">
                    <span>SSL 证书:</span>
                    <span className="text-green-600">有效 (90天)</span>
                  </div>
                </Space>
              </Card>
            </Col>
          </Row>
        </div>
      </div>
    </div>
  );
}