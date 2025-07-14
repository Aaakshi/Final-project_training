
import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Table, 
  Button, 
  Input, 
  Select, 
  Space, 
  Tag, 
  Modal, 
  Typography, 
  Row, 
  Col,
  message,
  Popconfirm,
  Tooltip,
  Divider
} from 'antd';
import {
  SearchOutlined,
  EyeOutlined,
  CheckOutlined,
  CloseOutlined,
  DownloadOutlined,
  FilterOutlined,
  ReloadOutlined,
} from '@ant-design/icons';

const { Title } = Typography;
const { Option } = Select;

const Documents = () => {
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [filteredDocuments, setFilteredDocuments] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [previewVisible, setPreviewVisible] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    filterDocuments();
  }, [documents, searchTerm, selectedDepartment, selectedStatus]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/documents', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (error) {
      message.error('Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  const filterDocuments = () => {
    let filtered = documents;

    if (searchTerm) {
      filtered = filtered.filter(doc => 
        doc.original_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.department?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (selectedDepartment) {
      filtered = filtered.filter(doc => doc.department === selectedDepartment);
    }

    if (selectedStatus) {
      filtered = filtered.filter(doc => 
        (doc.approval_status || 'pending').toLowerCase() === selectedStatus.toLowerCase()
      );
    }

    setFilteredDocuments(filtered);
  };

  const handleApprove = async (documentId) => {
    try {
      const response = await fetch(`/api/documents/${documentId}/approve`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      
      if (response.ok) {
        message.success('Document approved successfully');
        fetchDocuments();
      } else {
        message.error('Failed to approve document');
      }
    } catch (error) {
      message.error('Failed to approve document');
    }
  };

  const handleReject = async (documentId) => {
    try {
      const response = await fetch(`/api/documents/${documentId}/reject`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      
      if (response.ok) {
        message.success('Document rejected successfully');
        fetchDocuments();
      } else {
        message.error('Failed to reject document');
      }
    } catch (error) {
      message.error('Failed to reject document');
    }
  };

  const handlePreview = (document) => {
    setSelectedDocument(document);
    setPreviewVisible(true);
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'approved': return 'success';
      case 'rejected': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'red';
      case 'medium': return 'orange';
      case 'low': return 'green';
      default: return 'default';
    }
  };

  const departments = [...new Set(documents.map(doc => doc.department).filter(Boolean))];
  const statuses = ['pending', 'approved', 'rejected'];

  const columns = [
    {
      title: 'Document Name',
      dataIndex: 'original_name',
      key: 'name',
      ellipsis: true,
      render: (text, record) => (
        <Button 
          type="link" 
          onClick={() => handlePreview(record)}
          className="p-0 h-auto"
        >
          {text}
        </Button>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => dept ? <Tag color="blue">{dept}</Tag> : '-',
      filters: departments.map(dept => ({ text: dept, value: dept })),
      onFilter: (value, record) => record.department === value,
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority) => (
        <Tag color={getPriorityColor(priority)}>
          {priority || 'Medium'}
        </Tag>
      ),
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
      filters: statuses.map(status => ({ 
        text: status.charAt(0).toUpperCase() + status.slice(1), 
        value: status 
      })),
      onFilter: (value, record) => (record.approval_status || 'pending').toLowerCase() === value,
    },
    {
      title: 'Uploaded By',
      dataIndex: 'uploaded_by',
      key: 'uploaded_by',
      ellipsis: true,
    },
    {
      title: 'Upload Date',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      render: (date) => new Date(date).toLocaleDateString(),
      sorter: (a, b) => new Date(a.uploaded_at) - new Date(b.uploaded_at),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="Preview">
            <Button 
              type="text" 
              icon={<EyeOutlined />} 
              onClick={() => handlePreview(record)}
              size="small"
            />
          </Tooltip>
          
          {(!record.approval_status || record.approval_status === 'pending') && (
            <>
              <Tooltip title="Approve">
                <Popconfirm
                  title="Are you sure you want to approve this document?"
                  onConfirm={() => handleApprove(record.id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Button 
                    type="text" 
                    icon={<CheckOutlined />} 
                    className="text-green-600 hover:text-green-700"
                    size="small"
                  />
                </Popconfirm>
              </Tooltip>
              
              <Tooltip title="Reject">
                <Popconfirm
                  title="Are you sure you want to reject this document?"
                  onConfirm={() => handleReject(record.id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Button 
                    type="text" 
                    icon={<CloseOutlined />} 
                    className="text-red-600 hover:text-red-700"
                    size="small"
                  />
                </Popconfirm>
              </Tooltip>
            </>
          )}
          
          <Tooltip title="Download">
            <Button 
              type="text" 
              icon={<DownloadOutlined />} 
              size="small"
              onClick={() => window.open(`/api/documents/${record.id}/download`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Title level={2}>Documents</Title>
        <p className="text-gray-600">
          Manage and review all uploaded documents.
        </p>
      </div>

      {/* Filters */}
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} md={8}>
            <Input
              placeholder="Search documents..."
              prefix={<SearchOutlined />}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              allowClear
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Select
              placeholder="Select Department"
              value={selectedDepartment}
              onChange={setSelectedDepartment}
              allowClear
              style={{ width: '100%' }}
            >
              {departments.map(dept => (
                <Option key={dept} value={dept}>{dept}</Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Select
              placeholder="Select Status"
              value={selectedStatus}
              onChange={setSelectedStatus}
              allowClear
              style={{ width: '100%' }}
            >
              {statuses.map(status => (
                <Option key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={fetchDocuments}
              loading={loading}
            >
              Refresh
            </Button>
          </Col>
        </Row>
      </Card>

      {/* Documents Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={filteredDocuments}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => 
              `${range[0]}-${range[1]} of ${total} documents`,
          }}
          scroll={{ x: 800 }}
        />
      </Card>

      {/* Document Preview Modal */}
      <Modal
        title="Document Details"
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            Close
          </Button>,
          <Button 
            key="download" 
            type="primary" 
            icon={<DownloadOutlined />}
            onClick={() => window.open(`/api/documents/${selectedDocument?.id}/download`)}
          >
            Download
          </Button>,
        ]}
        width={800}
      >
        {selectedDocument && (
          <div className="space-y-4">
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <strong>Name:</strong> {selectedDocument.original_name}
              </Col>
              <Col span={12}>
                <strong>Department:</strong> {selectedDocument.department || '-'}
              </Col>
              <Col span={12}>
                <strong>Priority:</strong> 
                <Tag color={getPriorityColor(selectedDocument.priority)} className="ml-2">
                  {selectedDocument.priority || 'Medium'}
                </Tag>
              </Col>
              <Col span={12}>
                <strong>Status:</strong> 
                <Tag color={getStatusColor(selectedDocument.approval_status)} className="ml-2">
                  {selectedDocument.approval_status || 'Pending'}
                </Tag>
              </Col>
              <Col span={12}>
                <strong>Uploaded By:</strong> {selectedDocument.uploaded_by}
              </Col>
              <Col span={12}>
                <strong>Upload Date:</strong> {new Date(selectedDocument.uploaded_at).toLocaleString()}
              </Col>
            </Row>
            
            <Divider />
            
            <div>
              <strong>Content Preview:</strong>
              <div className="mt-2 p-3 bg-gray-50 rounded max-h-60 overflow-y-auto">
                {selectedDocument.extracted_text || 'No text content available'}
              </div>
            </div>
            
            {selectedDocument.summary && (
              <div>
                <strong>AI Summary:</strong>
                <div className="mt-2 p-3 bg-blue-50 rounded">
                  {selectedDocument.summary}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Documents;
