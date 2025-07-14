
import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Progress, Space, Typography } from 'antd';
import {
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  TrendingUpOutlined,
} from '@ant-design/icons';
import { statsService, documentService } from '../services/apiService.js';

const { Title } = Typography;

function Dashboard() {
  const [stats, setStats] = useState({});
  const [recentDocuments, setRecentDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [statsData, documentsData] = await Promise.all([
        statsService.getDashboardStats(),
        documentService.getAll({ limit: 10, sort_by: 'uploaded_at_desc' })
      ]);
      
      setStats(statsData);
      setRecentDocuments(documentsData.documents || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: 'Document Name',
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
    },
    {
      title: 'Type',
      dataIndex: 'document_type',
      key: 'document_type',
      render: (type) => (
        <Tag color={getTypeColor(type)}>
          {type?.toUpperCase() || 'UNKNOWN'}
        </Tag>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'assigned_department',
      key: 'assigned_department',
      render: (dept) => dept || 'Unassigned',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={getStatusColor(status)}>
          {status?.toUpperCase() || 'PENDING'}
        </Tag>
      ),
    },
  ];

  const getTypeColor = (type) => {
    const colors = {
      legal: 'red',
      hr: 'blue',
      finance: 'green',
      it: 'orange',
      marketing: 'purple',
    };
    return colors[type?.toLowerCase()] || 'default';
  };

  const getStatusColor = (status) => {
    const colors = {
      processed: 'success',
      pending: 'warning',
      failed: 'error',
    };
    return colors[status?.toLowerCase()] || 'default';
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        Dashboard Overview
      </Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
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
              title="Processed"
              value={stats.processed_documents || 0}
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
              title="Processing Rate"
              value={stats.processing_rate || 0}
              suffix="%"
              prefix={<TrendingUpOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card 
            title="Recent Documents" 
            loading={loading}
            extra={<a href="/documents">View All</a>}
          >
            <Table
              columns={columns}
              dataSource={recentDocuments}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Card title="Document Types Distribution">
              {stats.document_types && Object.entries(stats.document_types).map(([type, count]) => (
                <div key={type} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ textTransform: 'capitalize' }}>{type}</span>
                    <span>{count}</span>
                  </div>
                  <Progress 
                    percent={Math.round((count / stats.total_documents) * 100)} 
                    size="small"
                    strokeColor={getTypeColor(type)}
                  />
                </div>
              ))}
            </Card>

            <Card title="Department Workload">
              {stats.departments && Object.entries(stats.departments).map(([dept, count]) => (
                <div key={dept} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span>{dept}</span>
                    <span>{count}</span>
                  </div>
                  <Progress 
                    percent={Math.round((count / stats.total_documents) * 100)} 
                    size="small"
                  />
                </div>
              ))}
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
}

export default Dashboard;
