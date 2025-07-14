import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Statistic, 
  Table, 
  Select, 
  DatePicker, 
  Typography,
  Tag,
  Progress,
  Space,
  Alert,
  Spin,
} from 'antd';
import {
  BarChartOutlined,
  PieChartOutlined,
  RiseOutlined,
  TeamOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';

const { Title } = Typography;
const { RangePicker } = DatePicker;
const { Option } = Select;

const Analytics = () => {
  const [loading, setLoading] = useState(true);
  const [analyticsData, setAnalyticsData] = useState({});
  const [selectedPeriod, setSelectedPeriod] = useState('7d');
  const [selectedDepartment, setSelectedDepartment] = useState('all');

  useEffect(() => {
    fetchAnalyticsData();
  }, [selectedPeriod, selectedDepartment]);

  const fetchAnalyticsData = async () => {
    setLoading(true);
    try {
      // Simulated analytics data - replace with actual API call
      const mockData = {
        totalDocuments: 1247,
        approvedDocuments: 987,
        pendingDocuments: 156,
        rejectedDocuments: 104,
        avgProcessingTime: '2.4 hours',
        departmentStats: [
          { department: 'HR', total: 324, approved: 289, pending: 23, rejected: 12, percentage: 89.2 },
          { department: 'Finance', total: 298, approved: 245, pending: 31, rejected: 22, percentage: 82.2 },
          { department: 'Legal', total: 267, approved: 234, pending: 19, rejected: 14, percentage: 87.6 },
          { department: 'IT', total: 198, approved: 156, pending: 28, rejected: 14, percentage: 78.8 },
          { department: 'Marketing', total: 160, approved: 135, pending: 15, rejected: 10, percentage: 84.4 },
        ],
        recentActivity: [
          { time: '10:30 AM', action: 'Document approved', user: 'John Manager', department: 'HR' },
          { time: '10:15 AM', action: 'Bulk upload completed', user: 'Jane Employee', department: 'Finance' },
          { time: '09:45 AM', action: 'Document rejected', user: 'Bob Manager', department: 'Legal' },
          { time: '09:30 AM', action: 'New document uploaded', user: 'Alice Employee', department: 'IT' },
        ],
        processingTimes: [
          { department: 'HR', avgTime: '1.8 hours', efficiency: 92 },
          { department: 'Finance', avgTime: '3.2 hours', efficiency: 78 },
          { department: 'Legal', avgTime: '4.1 hours', efficiency: 65 },
          { department: 'IT', avgTime: '2.1 hours', efficiency: 88 },
          { department: 'Marketing', avgTime: '2.7 hours', efficiency: 82 },
        ],
      };

      setAnalyticsData(mockData);
    } catch (error) {
      console.error('Failed to fetch analytics data:', error);
    } finally {
      setLoading(false);
    }
  };

  const departmentColumns = [
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => <Tag color="blue">{dept}</Tag>,
    },
    {
      title: 'Total Documents',
      dataIndex: 'total',
      key: 'total',
      sorter: (a, b) => a.total - b.total,
    },
    {
      title: 'Approved',
      dataIndex: 'approved',
      key: 'approved',
      render: (value) => <span style={{ color: '#52c41a' }}>{value}</span>,
    },
    {
      title: 'Pending',
      dataIndex: 'pending',
      key: 'pending',
      render: (value) => <span style={{ color: '#faad14' }}>{value}</span>,
    },
    {
      title: 'Rejected',
      dataIndex: 'rejected',
      key: 'rejected',
      render: (value) => <span style={{ color: '#ff4d4f' }}>{value}</span>,
    },
    {
      title: 'Approval Rate',
      dataIndex: 'percentage',
      key: 'percentage',
      render: (value) => (
        <div style={{ width: 100 }}>
          <Progress 
            percent={value} 
            size="small" 
            strokeColor={value >= 85 ? '#52c41a' : value >= 70 ? '#faad14' : '#ff4d4f'}
          />
        </div>
      ),
      sorter: (a, b) => a.percentage - b.percentage,
    },
  ];

  const processingColumns = [
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => <Tag color="blue">{dept}</Tag>,
    },
    {
      title: 'Avg Processing Time',
      dataIndex: 'avgTime',
      key: 'avgTime',
    },
    {
      title: 'Efficiency Score',
      dataIndex: 'efficiency',
      key: 'efficiency',
      render: (value) => (
        <div style={{ width: 100 }}>
          <Progress 
            percent={value} 
            size="small"
            strokeColor={value >= 85 ? '#52c41a' : value >= 70 ? '#faad14' : '#ff4d4f'}
          />
        </div>
      ),
    },
  ];

  const activityColumns = [
    {
      title: 'Time',
      dataIndex: 'time',
      key: 'time',
      width: 100,
    },
    {
      title: 'Action',
      dataIndex: 'action',
      key: 'action',
    },
    {
      title: 'User',
      dataIndex: 'user',
      key: 'user',
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => <Tag color="blue">{dept}</Tag>,
    },
  ];

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <Title level={2}>Analytics & Reports</Title>
          <p className="text-gray-600">
            Track document processing performance and system usage.
          </p>
        </div>

        <Space>
          <Select
            value={selectedDepartment}
            onChange={setSelectedDepartment}
            style={{ width: 150 }}
          >
            <Option value="all">All Departments</Option>
            <Option value="hr">HR</Option>
            <Option value="finance">Finance</Option>
            <Option value="legal">Legal</Option>
            <Option value="it">IT</Option>
            <Option value="marketing">Marketing</Option>
          </Select>

          <Select
            value={selectedPeriod}
            onChange={setSelectedPeriod}
            style={{ width: 120 }}
          >
            <Option value="24h">Last 24h</Option>
            <Option value="7d">Last 7 days</Option>
            <Option value="30d">Last 30 days</Option>
            <Option value="90d">Last 90 days</Option>
          </Select>
        </Space>
      </div>

      {/* Key Metrics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Documents"
              value={analyticsData.totalDocuments}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Approved"
              value={analyticsData.approvedDocuments}
              prefix={<RiseOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Pending Review"
              value={analyticsData.pendingDocuments}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Avg Processing"
              value={analyticsData.avgProcessingTime}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Performance Overview */}
      <Alert
        message="System Performance"
        description={`Overall approval rate: ${((analyticsData.approvedDocuments / analyticsData.totalDocuments) * 100).toFixed(1)}% | Average processing time: ${analyticsData.avgProcessingTime}`}
        type="info"
        showIcon
      />

      {/* Department Statistics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Department Performance" extra={<PieChartOutlined />}>
            <Table
              columns={departmentColumns}
              dataSource={analyticsData.departmentStats}
              rowKey="department"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card title="Processing Efficiency" extra={<TeamOutlined />}>
            <Table
              columns={processingColumns}
              dataSource={analyticsData.processingTimes}
              rowKey="department"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* Recent Activity */}
      <Card title="Recent Activity" extra={<ClockCircleOutlined />}>
        <Table
          columns={activityColumns}
          dataSource={analyticsData.recentActivity}
          rowKey={(record, index) => index}
          pagination={false}
          size="small"
        />
      </Card>

      {/* Additional Insights */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Top Performing Departments">
            <div className="space-y-3">
              {analyticsData.departmentStats
                ?.sort((a, b) => b.percentage - a.percentage)
                ?.slice(0, 3)
                ?.map((dept, index) => (
                  <div key={dept.department} className="flex justify-between items-center">
                    <div className="flex items-center space-x-2">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                        index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : 'bg-orange-500'
                      }`}>
                        {index + 1}
                      </span>
                      <Tag color="blue">{dept.department}</Tag>
                    </div>
                    <span className="font-semibold">{dept.percentage.toFixed(1)}%</span>
                  </div>
                ))
              }
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="System Health">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span>Classification Accuracy</span>
                <Progress percent={94} size="small" strokeColor="#52c41a" />
              </div>
              <div className="flex justify-between items-center">
                <span>Routing Efficiency</span>
                <Progress percent={88} size="small" strokeColor="#1890ff" />
              </div>
              <div className="flex justify-between items-center">
                <span>Content Analysis Quality</span>
                <Progress percent={91} size="small" strokeColor="#722ed1" />
              </div>
              <div className="flex justify-between items-center">
                <span>System Uptime</span>
                <Progress percent={99.8} size="small" strokeColor="#52c41a" />
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Analytics;