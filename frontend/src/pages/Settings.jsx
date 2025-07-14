
import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Form, 
  Input, 
  Button, 
  Switch, 
  Select, 
  Divider,
  Typography,
  Row,
  Col,
  Avatar,
  Upload,
  message,
  Tabs,
  Alert,
  Space,
} from 'antd';
import {
  UserOutlined,
  SettingOutlined,
  BellOutlined,
  SecurityScanOutlined,
  UploadOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { authService } from '../services/apiService.js';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

const Settings = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [profileForm] = Form.useForm();
  const [notificationForm] = Form.useForm();
  const [securityForm] = Form.useForm();

  useEffect(() => {
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);
      profileForm.setFieldsValue(userData);
      
      // Set default notification preferences
      notificationForm.setFieldsValue({
        emailNotifications: true,
        documentApproval: true,
        newDocuments: true,
        systemAlerts: false,
        weeklyReports: true,
      });
    } catch (error) {
      message.error('Failed to fetch user data');
    }
  };

  const handleProfileUpdate = async (values) => {
    setLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      message.success('Profile updated successfully');
    } catch (error) {
      message.error('Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const handleNotificationUpdate = async (values) => {
    setLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      message.success('Notification preferences updated');
    } catch (error) {
      message.error('Failed to update notifications');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (values) => {
    if (values.newPassword !== values.confirmPassword) {
      message.error('Passwords do not match');
      return;
    }
    
    setLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      message.success('Password changed successfully');
      securityForm.resetFields();
    } catch (error) {
      message.error('Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  const profileTab = (
    <Card>
      <div className="flex items-center space-x-4 mb-6">
        <Avatar size={80} icon={<UserOutlined />} />
        <div>
          <Title level={4} className="mb-1">{user?.full_name}</Title>
          <Text className="text-gray-600">{user?.email}</Text>
          <br />
          <Text className="text-gray-500 capitalize">{user?.role} • {user?.department}</Text>
        </div>
      </div>

      <Form
        form={profileForm}
        layout="vertical"
        onFinish={handleProfileUpdate}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Form.Item
              label="Full Name"
              name="full_name"
              rules={[{ required: true, message: 'Please enter your full name' }]}
            >
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              label="Email"
              name="email"
              rules={[
                { required: true, message: 'Please enter your email' },
                { type: 'email', message: 'Please enter a valid email' }
              ]}
            >
              <Input disabled />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item label="Department" name="department">
              <Select disabled>
                <Option value="hr">HR</Option>
                <Option value="finance">Finance</Option>
                <Option value="legal">Legal</Option>
                <Option value="it">IT</Option>
                <Option value="marketing">Marketing</Option>
              </Select>
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item label="Role" name="role">
              <Select disabled>
                <Option value="admin">Admin</Option>
                <Option value="manager">Manager</Option>
                <Option value="employee">Employee</Option>
              </Select>
            </Form.Item>
          </Col>
          <Col xs={24}>
            <Form.Item label="Bio" name="bio">
              <TextArea rows={3} placeholder="Tell us about yourself..." />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} icon={<SaveOutlined />}>
            Update Profile
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );

  const notificationTab = (
    <Card>
      <Alert
        message="Notification Preferences"
        description="Configure how and when you want to receive notifications about document activities."
        type="info"
        showIcon
        className="mb-6"
      />

      <Form
        form={notificationForm}
        layout="vertical"
        onFinish={handleNotificationUpdate}
      >
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <Text strong>Email Notifications</Text>
              <br />
              <Text className="text-gray-600">Receive notifications via email</Text>
            </div>
            <Form.Item name="emailNotifications" valuePropName="checked" className="mb-0">
              <Switch />
            </Form.Item>
          </div>

          <Divider />

          <div className="flex justify-between items-center">
            <div>
              <Text strong>Document Approvals</Text>
              <br />
              <Text className="text-gray-600">Notify when documents are approved/rejected</Text>
            </div>
            <Form.Item name="documentApproval" valuePropName="checked" className="mb-0">
              <Switch />
            </Form.Item>
          </div>

          <div className="flex justify-between items-center">
            <div>
              <Text strong>New Document Uploads</Text>
              <br />
              <Text className="text-gray-600">Notify when new documents are uploaded</Text>
            </div>
            <Form.Item name="newDocuments" valuePropName="checked" className="mb-0">
              <Switch />
            </Form.Item>
          </div>

          <div className="flex justify-between items-center">
            <div>
              <Text strong>System Alerts</Text>
              <br />
              <Text className="text-gray-600">Notify about system maintenance and updates</Text>
            </div>
            <Form.Item name="systemAlerts" valuePropName="checked" className="mb-0">
              <Switch />
            </Form.Item>
          </div>

          <div className="flex justify-between items-center">
            <div>
              <Text strong>Weekly Reports</Text>
              <br />
              <Text className="text-gray-600">Receive weekly activity summaries</Text>
            </div>
            <Form.Item name="weeklyReports" valuePropName="checked" className="mb-0">
              <Switch />
            </Form.Item>
          </div>
        </div>

        <Divider />

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} icon={<SaveOutlined />}>
            Save Preferences
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );

  const securityTab = (
    <Card>
      <Alert
        message="Security Settings"
        description="Keep your account secure by updating your password regularly."
        type="warning"
        showIcon
        className="mb-6"
      />

      <Form
        form={securityForm}
        layout="vertical"
        onFinish={handlePasswordChange}
      >
        <Form.Item
          label="Current Password"
          name="currentPassword"
          rules={[{ required: true, message: 'Please enter your current password' }]}
        >
          <Input.Password />
        </Form.Item>

        <Form.Item
          label="New Password"
          name="newPassword"
          rules={[
            { required: true, message: 'Please enter a new password' },
            { min: 8, message: 'Password must be at least 8 characters' }
          ]}
        >
          <Input.Password />
        </Form.Item>

        <Form.Item
          label="Confirm New Password"
          name="confirmPassword"
          rules={[{ required: true, message: 'Please confirm your new password' }]}
        >
          <Input.Password />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} icon={<SaveOutlined />}>
            Change Password
          </Button>
        </Form.Item>
      </Form>

      <Divider />

      <div className="space-y-4">
        <Title level={5}>Account Security</Title>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span>Two-Factor Authentication</span>
            <Button size="small">Enable</Button>
          </div>
          <div className="flex justify-between items-center">
            <span>Login Sessions</span>
            <Button size="small">View Active Sessions</Button>
          </div>
          <div className="flex justify-between items-center">
            <span>Account Activity</span>
            <Button size="small">View History</Button>
          </div>
        </div>
      </div>
    </Card>
  );

  const systemTab = (
    <Card>
      <Alert
        message="System Configuration"
        description="Configure system-wide settings and preferences."
        type="info"
        showIcon
        className="mb-6"
      />

      <div className="space-y-6">
        <div>
          <Title level={5}>Interface Settings</Title>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <Text strong>Dark Mode</Text>
                <br />
                <Text className="text-gray-600">Enable dark theme</Text>
              </div>
              <Switch />
            </div>
            <div className="flex justify-between items-center">
              <div>
                <Text strong>Compact Layout</Text>
                <br />
                <Text className="text-gray-600">Use smaller spacing and components</Text>
              </div>
              <Switch />
            </div>
          </div>
        </div>

        <Divider />

        <div>
          <Title level={5}>Default Settings</Title>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Text strong>Default Upload Priority</Text>
              <Select defaultValue="medium" style={{ width: '100%', marginTop: 8 }}>
                <Option value="low">Low</Option>
                <Option value="medium">Medium</Option>
                <Option value="high">High</Option>
              </Select>
            </Col>
            <Col xs={24} md={12}>
              <Text strong>Documents Per Page</Text>
              <Select defaultValue="10" style={{ width: '100%', marginTop: 8 }}>
                <Option value="5">5</Option>
                <Option value="10">10</Option>
                <Option value="25">25</Option>
                <Option value="50">50</Option>
              </Select>
            </Col>
          </Row>
        </div>

        <Divider />

        <Button type="primary" icon={<SaveOutlined />}>
          Save System Settings
        </Button>
      </div>
    </Card>
  );

  const tabItems = [
    {
      key: 'profile',
      label: (
        <span>
          <UserOutlined />
          Profile
        </span>
      ),
      children: profileTab,
    },
    {
      key: 'notifications',
      label: (
        <span>
          <BellOutlined />
          Notifications
        </span>
      ),
      children: notificationTab,
    },
    {
      key: 'security',
      label: (
        <span>
          <SecurityScanOutlined />
          Security
        </span>
      ),
      children: securityTab,
    },
    {
      key: 'system',
      label: (
        <span>
          <SettingOutlined />
          System
        </span>
      ),
      children: systemTab,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Title level={2}>Settings</Title>
        <Text className="text-gray-600">
          Manage your account settings and preferences.
        </Text>
      </div>

      <Tabs items={tabItems} defaultActiveKey="profile" />
    </div>
  );
};

export default Settings;
