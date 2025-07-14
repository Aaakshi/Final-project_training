
import React, { useState, useEffect } from 'react';
import { 
  Table, Card, Input, Select, Button, Tag, Space, 
  Drawer, Descriptions, Typography, message, Modal,
  Row, Col 
} from 'antd';
import {
  SearchOutlined,
  EyeOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { documentService } from '../services/apiService.js';

const { Search } = Input;
const { Option } = Select;
const { Title, Text } = Typography;

function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [filters, setFilters] = useState({
    search: '',
    department: '',
    sort_by: 'uploaded_at_desc'
  });

  useEffect(() => {
    fetchDocuments();
  }, [filters]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await documentService.getAll(filters);
      setDocuments(response.documents || []);
    } catch (error) {
      message.error('Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (documentId) => {
    try {
      const document = await documentService.getById(documentId);
      setSelectedDocument(document);
      setDrawerVisible(true);
    } catch (error) {
      message.error('Failed to load document details');
    }
  };

  const handleDelete = (documentId) => {
    Modal.confirm({
      title: 'Delete Document',
      content: 'Are you sure you want to delete this document?',
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await documentService.delete(documentId);
          message.success('Document deleted successfully');
          fetchDocuments();
        } catch (error) {
          message.error('Failed to delete document');
        }
      },
    });
  };

  const handleReview = async (documentId, reviewData) => {
    try {
      await documentService.review(documentId, reviewData);
      message.success('Document reviewed successfully');
      fetchDocuments();
      setDrawerVisible(false);
    } catch (error) {
      message.error('Failed to review document');
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      processed: 'success',
      pending: 'warning',
      failed: 'error',
      reviewing: 'processing',
    };
    return colors[status?.toLowerCase()] || 'default';
  };

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

  const columns = [
    {
      title: 'Document',
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
      render: (filename, record) => (
        <Space>
          <FileTextOutlined />
          <Text strong>{filename}</Text>
        </Space>
      ),
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
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority) => {
        const color = priority === 'urgent' ? 'red' : priority === 'high' ? 'orange' : 'default';
        return <Tag color={color}>{priority?.toUpperCase() || 'NORMAL'}</Tag>;
      },
    },
    {
      title: 'Uploaded',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      render: (date) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => handleView(record.id)}
          >
            View
          </Button>
          <Button
            type="link"
            icon={<DownloadOutlined />}
            href={`/api/documents/${record.id}/download`}
            target="_blank"
          >
            Download
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2}>Document Management</Title>
        </Col>
        <Col>
          <Button type="primary" href="/upload">
            Upload Documents
          </Button>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={8}>
            <Search
              placeholder="Search documents..."
              allowClear
              onSearch={(value) => setFilters(prev => ({ ...prev, search: value }))}
              style={{ width: '100%' }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Select
              placeholder="Filter by department"
              allowClear
              style={{ width: '100%' }}
              onChange={(value) => setFilters(prev => ({ ...prev, department: value || '' }))}
            >
              <Option value="hr">HR</Option>
              <Option value="finance">Finance</Option>
              <Option value="legal">Legal</Option>
              <Option value="it">IT</Option>
              <Option value="marketing">Marketing</Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Select
              defaultValue="uploaded_at_desc"
              style={{ width: '100%' }}
              onChange={(value) => setFilters(prev => ({ ...prev, sort_by: value }))}
            >
              <Option value="uploaded_at_desc">Newest First</Option>
              <Option value="uploaded_at_asc">Oldest First</Option>
              <Option value="filename_asc">Name A-Z</Option>
              <Option value="filename_desc">Name Z-A</Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Button 
              icon={<SearchOutlined />} 
              onClick={fetchDocuments}
              style={{ width: '100%' }}
            >
              Refresh
            </Button>
          </Col>
        </Row>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          pagination={{
            total: documents.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} documents`,
          }}
        />
      </Card>

      <Drawer
        title="Document Details"
        placement="right"
        size="large"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {selectedDocument && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Descriptions title="Document Information" bordered column={1}>
              <Descriptions.Item label="Filename">
                {selectedDocument.filename}
              </Descriptions.Item>
              <Descriptions.Item label="Type">
                <Tag color={getTypeColor(selectedDocument.document_type)}>
                  {selectedDocument.document_type?.toUpperCase() || 'UNKNOWN'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Department">
                {selectedDocument.assigned_department || 'Unassigned'}
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={getStatusColor(selectedDocument.status)}>
                  {selectedDocument.status?.toUpperCase() || 'PENDING'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Priority">
                {selectedDocument.priority || 'Normal'}
              </Descriptions.Item>
              <Descriptions.Item label="Uploaded">
                {new Date(selectedDocument.uploaded_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="File Size">
                {selectedDocument.file_size ? `${(selectedDocument.file_size / 1024).toFixed(2)} KB` : 'Unknown'}
              </Descriptions.Item>
            </Descriptions>

            {selectedDocument.content && (
              <Card title="Document Content" size="small">
                <div style={{ 
                  maxHeight: 300, 
                  overflow: 'auto', 
                  padding: 16,
                  background: '#f5f5f5',
                  borderRadius: 4,
                  whiteSpace: 'pre-wrap'
                }}>
                  {selectedDocument.content}
                </div>
              </Card>
            )}

            <Space>
              <Button
                type="primary"
                onClick={() => handleReview(selectedDocument.id, { status: 'approved' })}
              >
                Approve
              </Button>
              <Button
                onClick={() => handleReview(selectedDocument.id, { status: 'rejected' })}
              >
                Reject
              </Button>
              <Button
                href={`/api/documents/${selectedDocument.id}/download`}
                target="_blank"
                icon={<DownloadOutlined />}
              >
                Download
              </Button>
            </Space>
          </Space>
        )}
      </Drawer>
    </div>
  );
}

export default Documents;
