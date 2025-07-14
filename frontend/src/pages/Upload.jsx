
import React, { useState } from 'react';
import { 
  Card, 
  Upload, 
  Button, 
  Typography, 
  Row, 
  Col, 
  Alert, 
  Progress,
  List,
  Tag,
  Space,
  message,
  Modal,
  Select,
} from 'antd';
import {
  UploadOutlined,
  InboxOutlined,
  FileTextOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Dragger } = Upload;
const { Option } = Select;

const UploadPage = () => {
  const [fileList, setFileList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedPriority, setSelectedPriority] = useState('medium');
  const [uploadResults, setUploadResults] = useState([]);
  const [showResults, setShowResults] = useState(false);

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('Please select files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    fileList.forEach((file) => {
      formData.append('files', file.originFileObj);
    });
    formData.append('priority', selectedPriority);

    try {
      const response = await fetch('/api/bulk-upload', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: formData,
      });

      const data = await response.json();
      
      if (response.ok) {
        setUploadResults(data.results || []);
        setShowResults(true);
        setFileList([]);
        message.success(`Successfully uploaded ${data.results?.length || 0} files`);
      } else {
        message.error(data.detail || 'Upload failed');
      }
    } catch (error) {
      message.error('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const uploadProps = {
    name: 'files',
    multiple: true,
    fileList,
    beforeUpload: (file) => {
      // Check file type
      const allowedTypes = [
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg',
        'image/png',
      ];
      
      if (!allowedTypes.includes(file.type)) {
        message.error(`${file.name} is not a supported file type`);
        return false;
      }

      // Check file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        message.error(`${file.name} is too large. Maximum size is 10MB`);
        return false;
      }

      setFileList(prev => [...prev, {
        uid: file.uid,
        name: file.name,
        status: 'done',
        originFileObj: file,
      }]);
      
      return false; // Prevent automatic upload
    },
    onRemove: (file) => {
      setFileList(prev => prev.filter(item => item.uid !== file.uid));
    },
  };

  const getResultIcon = (status) => {
    switch (status) {
      case 'success': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error': return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default: return <FileTextOutlined />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <Title level={2}>Upload Documents</Title>
        <Text className="text-gray-600">
          Upload multiple documents for automatic classification and routing.
        </Text>
      </div>

      {/* Upload Configuration */}
      <Card title="Upload Settings">
        <Row gutter={[16, 16]} align="middle">
          <Col span={8}>
            <Text strong>Priority Level:</Text>
          </Col>
          <Col span={16}>
            <Select
              value={selectedPriority}
              onChange={setSelectedPriority}
              style={{ width: 200 }}
            >
              <Option value="low">
                <Tag color="green">Low Priority</Tag>
              </Option>
              <Option value="medium">
                <Tag color="orange">Medium Priority</Tag>
              </Option>
              <Option value="high">
                <Tag color="red">High Priority</Tag>
              </Option>
            </Select>
          </Col>
        </Row>
      </Card>

      {/* File Upload Area */}
      <Card title="Select Files">
        <Dragger {...uploadProps} style={{ padding: '20px' }}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
          </p>
          <p className="ant-upload-text text-lg">
            Click or drag files to this area to upload
          </p>
          <p className="ant-upload-hint">
            Support for multiple files. Accepted formats: PDF, DOC, DOCX, TXT, JPG, PNG
            <br />
            Maximum file size: 10MB per file
          </p>
        </Dragger>

        {fileList.length > 0 && (
          <div className="mt-4">
            <Alert
              message={`${fileList.length} file(s) selected`}
              type="info"
              showIcon
              className="mb-4"
            />
            
            <List
              size="small"
              dataSource={fileList}
              renderItem={(file) => (
                <List.Item
                  actions={[
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => uploadProps.onRemove(file)}
                    />
                  ]}
                >
                  <List.Item.Meta
                    avatar={<FileTextOutlined />}
                    title={file.name}
                    description={`${(file.originFileObj.size / 1024).toFixed(1)} KB`}
                  />
                </List.Item>
              )}
            />
          </div>
        )}
      </Card>

      {/* Upload Actions */}
      <Card>
        <Space>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={handleUpload}
            loading={uploading}
            disabled={fileList.length === 0}
            size="large"
          >
            {uploading ? 'Uploading...' : `Upload ${fileList.length} Files`}
          </Button>
          
          <Button
            onClick={() => setFileList([])}
            disabled={fileList.length === 0 || uploading}
          >
            Clear All
          </Button>
        </Space>

        {uploading && (
          <div className="mt-4">
            <Progress 
              percent={uploadProgress} 
              status="active"
              strokeColor="#1890ff"
            />
          </div>
        )}
      </Card>

      {/* Upload Instructions */}
      <Card title="Instructions">
        <div className="space-y-3">
          <div>
            <Text strong>📁 Supported File Types:</Text>
            <div className="ml-4 mt-1">
              <Tag>PDF</Tag>
              <Tag>DOC/DOCX</Tag>
              <Tag>TXT</Tag>
              <Tag>JPG/PNG</Tag>
            </div>
          </div>
          
          <div>
            <Text strong>⚡ Automatic Processing:</Text>
            <ul className="ml-4 mt-1 space-y-1">
              <li>• Documents are automatically classified by department</li>
              <li>• Content is extracted and analyzed</li>
              <li>• Files are routed to appropriate managers for approval</li>
              <li>• Email notifications are sent to relevant stakeholders</li>
            </ul>
          </div>
          
          <div>
            <Text strong>🏷️ Priority Levels:</Text>
            <ul className="ml-4 mt-1 space-y-1">
              <li>• <Tag color="red">High</Tag> - Urgent documents requiring immediate attention</li>
              <li>• <Tag color="orange">Medium</Tag> - Standard processing time</li>
              <li>• <Tag color="green">Low</Tag> - Non-urgent, can be processed later</li>
            </ul>
          </div>
        </div>
      </Card>

      {/* Results Modal */}
      <Modal
        title="Upload Results"
        open={showResults}
        onCancel={() => setShowResults(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setShowResults(false)}>
            Close
          </Button>
        ]}
        width={700}
      >
        <List
          dataSource={uploadResults}
          renderItem={(result) => (
            <List.Item>
              <List.Item.Meta
                avatar={getResultIcon(result.status)}
                title={result.filename}
                description={
                  <div>
                    <div>Status: {result.status}</div>
                    {result.department && <div>Department: <Tag color="blue">{result.department}</Tag></div>}
                    {result.message && <div className="text-gray-600">{result.message}</div>}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
};

export default UploadPage;
