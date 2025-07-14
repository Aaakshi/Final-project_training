
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Typography, Alert, Spin } from 'antd';
import {
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  UploadOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { authService } from '../services/apiService.js';

const { Title } = Typography;

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({});
  const [recentDocuments, setRecentDocuments] = useState([]);
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      // Fetch user info
      const userData = await authService.getCurrentUser();
      setUser(userData);

      // Fetch stats
      const response = await fetch('/api/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      const statsData = await response.json();
      setStats(statsData);

      // Fetch recent documents
      const docsResponse = await fetch('/api/documents?limit=5', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      const docsData = await docsResponse.json();
      setRecentDocuments(docsData.documents || []);

    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'approved': return 'success';
      case 'rejected': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const documentColumns = [
    {
      title: 'Document Name',
      dataIndex: 'original_name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => <Tag color="blue">{dept}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'approval_status',
      key: 'status',
      render: (status) => (
        <Tag color={getStatusColor(status)}>
          {status || 'Pending'}
        </Tag>
      ),
    },
    {
      title: 'Uploaded',
      dataIndex: 'uploaded_at',
      key: 'uploaded',
      render: (date) => new Date(date).toLocaleDateString(),
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
      {/* Welcome Section */}
      <div>
        <Title level={2}>Welcome back, {user?.full_name}!</Title>
        <p className="text-gray-600">
          Here's what's happening with your documents today.
        </p>
      </div>

      {/* Statistics Cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Documents"
              value={stats.total_documents || 0}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Approved"
              value={stats.approved_documents || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Pending"
              value={stats.pending_documents || 0}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Rejected"
              value={stats.rejected_documents || 0}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Recent Activity */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card 
            title="Recent Documents" 
            extra={<a href="/documents">View All</a>}
          >
            <Table
              dataSource={recentDocuments}
              columns={documentColumns}
              pagination={false}
              rowKey="id"
              size="small"
            />
          </Card>
        </Col>
        
        <Col xs={24} lg={8}>
          <Card title="Quick Actions">
            <Space direction="vertical" size="middle" className="w-full">
              <Card.Grid 
                style={{ width: '100%', textAlign: 'center' }}
                className="cursor-pointer hover:bg-blue-50"
                onClick={() => window.location.href = '/upload'}
              >
                <UploadOutlined style={{ fontSize: '24px', color: '#1890ff' }} />
                <div className="mt-2">Upload Documents</div>
              </Card.Grid>
              
              <Card.Grid 
                style={{ width: '100%', textAlign: 'center' }}
                className="cursor-pointer hover:bg-green-50"
                onClick={() => window.location.href = '/documents'}
              >
                <FileTextOutlined style={{ fontSize: '24px', color: '#52c41a' }} />
                <div className="mt-2">View Documents</div>
              </Card.Grid>
              
              <Card.Grid 
                style={{ width: '100%', textAlign: 'center' }}
                className="cursor-pointer hover:bg-purple-50"
                onClick={() => window.location.href = '/analytics'}
              >
                <TeamOutlined style={{ fontSize: '24px', color: '#722ed1' }} />
                <div className="mt-2">View Analytics</div>
              </Card.Grid>
            </Space>
          </Card>

          {/* System Status */}
          <Card title="System Status" className="mt-4">
            <Space direction="vertical" className="w-full">
              <div className="flex justify-between items-center">
                <span>Classification Service</span>
                <Tag color="success">Online</Tag>
              </div>
              <div className="flex justify-between items-center">
                <span>Routing Engine</span>
                <Tag color="success">Online</Tag>
              </div>
              <div className="flex justify-between items-center">
                <span>Content Analysis</span>
                <Tag color="success">Online</Tag>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Role-specific alerts */}
      {user?.role === 'admin' && (
        <Alert
          message="Admin Notice"
          description="System performance is optimal. All microservices are running smoothly."
          type="info"
          showIcon
          closable
        />
      )}
      
      {user?.role === 'manager' && stats.pending_documents > 0 && (
        <Alert
          message="Pending Approvals"
          description={`You have ${stats.pending_documents} documents waiting for approval.`}
          type="warning"
          showIcon
          action={
            <a href="/documents">Review Now</a>
          }
          closable
        />
      )}
    </div>
  );
};

export default Dashboard;
