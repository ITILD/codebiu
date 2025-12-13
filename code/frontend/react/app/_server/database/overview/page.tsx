"use client";

import { Card, Statistic, Row, Col, Table, Progress } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

export default function DatabaseOverview() {
  const dataSource = [
    {
      key: '1',
      name: '用户表',
      rows: '12,458',
      size: '245 MB',
      growth: '+2.3%',
    },
    {
      key: '2',
      name: '订单表',
      rows: '45,782',
      size: '1.2 GB',
      growth: '+5.7%',
    },
    {
      key: '3',
      name: '产品表',
      rows: '3,245',
      size: '89 MB',
      growth: '+1.2%',
    },
  ];

  const columns = [
    {
      title: '表名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '行数',
      dataIndex: 'rows',
      key: 'rows',
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
    },
    {
      title: '增长',
      dataIndex: 'growth',
      key: 'growth',
      render: (growth: string) => (
        <span style={{ color: growth.startsWith('+') ? '#3f8600' : '#cf1322' }}>
          {growth} {growth.startsWith('+') ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        </span>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} className="mb-6">
        <Col span={8}>
          <Card>
            <Statistic
              title="总连接数"
              value={1128}
              precision={0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<ArrowUpOutlined />}
              suffix=""
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="QPS"
              value={324}
              precision={0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<ArrowDownOutlined />}
              suffix=""
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="缓存命中率"
              value={98.2}
              precision={1}
              valueStyle={{ color: '#3f8600' }}
              prefix=""
              suffix="%"
            />
          </Card>
        </Col>
      </Row>

      <Card title="数据库状态">
        <div className="mb-6">
          <div className="flex justify-between mb-2">
            <span>CPU 使用率</span>
            <span>65%</span>
          </div>
          <Progress percent={65} status="active" strokeColor="#4A90E2" />
        </div>
        
        <div className="mb-6">
          <div className="flex justify-between mb-2">
            <span>内存使用率</span>
            <span>72%</span>
          </div>
          <Progress percent={72} status="active" strokeColor="#7ED321" />
        </div>
        
        <div className="mb-6">
          <div className="flex justify-between mb-2">
            <span>磁盘使用率</span>
            <span>45%</span>
          </div>
          <Progress percent={45} status="active" strokeColor="#F5A623" />
        </div>
      </Card>

      <Card title="数据表信息" className="mt-6">
        <Table dataSource={dataSource} columns={columns} pagination={false} />
      </Card>
    </div>
  );
}