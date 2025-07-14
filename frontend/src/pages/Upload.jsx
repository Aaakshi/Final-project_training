
import React, { useState } from 'react';
import { 
  Upload as AntUpload, Card, Button, Typography, Space, 
  Progress, List, Tag, message, Row, Col 
} from 'antd';
import {
  InboxOutlined,
  UploadOutlined,
  FileTextOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { documentService } from '../services/apiService.js';

const { Dragger } = AntUpload;
const { Title, Text } = Typography;

function Upload() {
  const [fileList, setFileList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const uploadProps = {
    name: 'files',
    multiple: true,
    fileList,
    beforeUpload: (file) => {
      const isValidType = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg',
        'image/png'
      ].includes(file.type);

      if (!isValidType) {
        message.error(`${file.name} is not a supported file type`);
        return false;
      }

      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('File must be smaller than 10MB');
        return false;
      }

      return false; // Prevent automatic upload
    },
    onChange: (info) => {
      setFileList(info.fileList);
    },
    onDrop: (e) => {
      console.log('Dropped files', e.dataTransfer.files);
    },
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('Please select files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      fileList.forEach((file) => {
        formData.append('files', file.originFileObj);
      });

      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      const response = await documentService.bulkUpload(formData);
      
      clearInterval(progressInterval);
      setUploadProgress(100);

      message.success(`Successfully uploaded ${response.uploaded_count} files`);
      
      if (response.failed_count > 0) {
        message.warning(`${response.failed_count} files failed to upload`);
      }

      setFileList([]);
      setUploadProgress(0);
    } catch (error) {
      message.error('Upload failed. Please try again.');
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = (file) => {
    const newFileList = fileList.filter(item => item.uid !== file.uid);
    setFileList(newFileList);
  };

  const getFileIcon = (file) => {
    const fileType = file.type || file.originFileObj?.type;
    if (fileType?.includes('pdf')) return '📄';
    if (fileType?.includes('word')) return '📝';
    if (fileType?.includes('image')) return '🖼️';
    return '📄';
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        Upload Documents
      </Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card title="Drag & Drop Files" style={{ marginBottom: 24 }}>
            <Dragger {...uploadProps} style={{ padding: '40px 24px' }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">
                Click or drag files to this area to upload
              </p>
              <p className="ant-upload-hint">
                Support for PDF, Word documents, images, and text files. 
                Maximum file size: 10MB per file.
              </p>
            </Dragger>
          </Card>

          {fileList.length > 0 && (
            <Card title={`Selected Files (${fileList.length})`}>
              <List
                dataSource={fileList}
                renderItem={(file) => (
                  <List.Item
                    actions={[
                      <Button
                        type="link"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleRemoveFile(file)}
                      >
                        Remove
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<span style={{ fontSize: 24 }}>{getFileIcon(file)}</span>}
                      title={file.name}
                      description={
                        <Space>
                          <Text type="secondary">
                            {(file.size / 1024).toFixed(2)} KB
                          </Text>
                          <Tag>{file.type?.split('/')[1] || 'unknown'}</Tag>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />

              {uploading && (
                <div style={{ marginTop: 16 }}>
                  <Text>Uploading files...</Text>
                  <Progress percent={uploadProgress} status="active" />
                </div>
              )}

              <div style={{ marginTop: 16, textAlign: 'center' }}>
                <Space>
                  <Button
                    type="primary"
                    size="large"
                    icon={<UploadOutlined />}
                    loading={uploading}
                    onClick={handleUpload}
                  >
                    Upload {fileList.length} File{fileList.length > 1 ? 's' : ''}
                  </Button>
                  <Button
                    size="large"
                    onClick={() => setFileList([])}
                    disabled={uploading}
                  >
                    Clear All
                  </Button>
                </Space>
              </div>
            </Card>
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Upload Guidelines">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Title level={5}>Supported File Types:</Title>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  <li>PDF Documents (.pdf)</li>
                  <li>Word Documents (.doc, .docx)</li>
                  <li>Text Files (.txt)</li>
                  <li>Images (.jpg, .png)</li>
                </ul>
              </div>

              <div>
                <Title level={5}>File Requirements:</Title>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  <li>Maximum size: 10MB per file</li>
                  <li>Multiple files supported</li>
                  <li>Files will be automatically classified</li>
                  <li>Processing typically takes 1-2 minutes</li>
                </ul>
              </div>

              <div>
                <Title level={5}>What Happens Next:</Title>
                <ol style={{ margin: 0, paddingLeft: 20 }}>
                  <li>Files are uploaded and stored securely</li>
                  <li>Content analysis extracts key information</li>
                  <li>Documents are automatically classified</li>
                  <li>Routing engine assigns to departments</li>
                  <li>Notifications sent to relevant teams</li>
                </ol>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default Upload;
