
import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Table, Progress, Select, DatePicker, Space, Typography } from 'antd';
import { statsService } from '../services/apiService.js';

const { RangePicker } = DatePicker;
const { Title } = Typography;
const { Option } = Select;

function Analytics() {
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState(null);
  const [department, setDepartment] = useState('all');

  useEffect(() => {
    fetchAnalytics();
  }, [dateRange, department]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const data = await statsService.getDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const processData = () => {
    if (!stats.upload_trends) return [];
    
    return stats.upload_trends.map((item, index) => ({
      key: index,
      date: item.date,
      count: item.count,
      department: item.department || 'All',
    }));
  };

  const columns = [
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
    },
    {
      title: 'Documents',
      dataIndex: 'count',
      key: 'count',
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        Analytics & Reports
      </Title>

      <Card style={{ marginBottom: 24 }}>
        <Space size="large">
          <div>
            <label style={{ display: 'block', marginBottom: 4 }}>Date Range:</label>
            <RangePicker onChange={setDateRange} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4 }}>Department:</label>
            <Select
              value={department}
              onChange={setDepartment}
              style={{ width: 150 }}
            >
              <Option value="all">All Departments</Option>
              <Option value="hr">HR</Option>
              <Option value="finance">Finance</Option>
              <Option value="legal">Legal</Option>
              <Option value="it">IT</Option>
              <Option value="marketing">Marketing</Option>
            </Select>
          </div>
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Documents"
              value={stats.total_documents || 0}
              precision={0}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Processing Rate"
              value={stats.processing_rate || 0}
              precision={1}
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Avg. Processing Time"
              value={2.4}
              precision={1}
              suffix="min"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Success Rate"
              value={96.8}
              precision={1}
              suffix="%"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Document Types Distribution" loading={loading}>
            {stats.document_types && Object.entries(stats.document_types).map(([type, count]) => (
              <div key={type} style={{ marginBottom: 16 }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  marginBottom: 4 
                }}>
                  <span style={{ textTransform: 'capitalize' }}>{type}</span>
                  <span>{count} ({Math.round((count / stats.total_documents) * 100)}%)</span>
                </div>
                <Progress 
                  percent={Math.round((count / stats.total_documents) * 100)}
                  size="small"
                />
              </div>
            ))}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Department Workload" loading={loading}>
            {stats.departments && Object.entries(stats.departments).map(([dept, count]) => (
              <div key={dept} style={{ marginBottom: 16 }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  marginBottom: 4 
                }}>
                  <span>{dept}</span>
                  <span>{count} ({Math.round((count / stats.total_documents) * 100)}%)</span>
                </div>
                <Progress 
                  percent={Math.round((count / stats.total_documents) * 100)}
                  size="small"
                  strokeColor="#52c41a"
                />
              </div>
            ))}
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="Upload Trends" loading={loading}>
            <Table
              columns={columns}
              dataSource={processData()}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default Analytics;
