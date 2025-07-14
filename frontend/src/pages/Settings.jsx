
import React, { useState } from 'react';
import { Card, Form, Input, Button, Switch, Select, Space, Typography, Divider, message } from 'antd';

const { Title } = Typography;
const { Option } = Select;

function Settings() {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const handleSave = async (values) => {
    setLoading(true);
    try {
      // Save settings logic here
      console.log('Saving settings:', values);
      message.success('Settings saved successfully');
    } catch (error) {
      message.error('Failed to save settings');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        System Settings
      </Title>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          autoClassification: true,
          emailNotifications: true,
          retentionPeriod: '12',
          language: 'en',
        }}
      >
        <Card title="Classification Settings" style={{ marginBottom: 24 }}>
          <Form.Item
            name="autoClassification"
            label="Auto Classification"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="confidenceThreshold"
            label="Classification Confidence Threshold (%)"
          >
            <Input type="number" min={0} max={100} placeholder="85" />
          </Form.Item>

          <Form.Item
            name="defaultDepartment"
            label="Default Department for Unclassified Documents"
          >
            <Select placeholder="Select default department">
              <Option value="general">General</Option>
              <Option value="hr">HR</Option>
              <Option value="finance">Finance</Option>
              <Option value="legal">Legal</Option>
              <Option value="it">IT</Option>
            </Select>
          </Form.Item>
        </Card>

        <Card title="Notification Settings" style={{ marginBottom: 24 }}>
          <Form.Item
            name="emailNotifications"
            label="Email Notifications"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="smtpServer"
            label="SMTP Server"
          >
            <Input placeholder="smtp.company.com" />
          </Form.Item>

          <Form.Item
            name="smtpPort"
            label="SMTP Port"
          >
            <Input type="number" placeholder="587" />
          </Form.Item>

          <Form.Item
            name="emailUsername"
            label="Email Username"
          >
            <Input placeholder="notifications@company.com" />
          </Form.Item>

          <Form.Item
            name="emailPassword"
            label="Email Password"
          >
            <Input.Password placeholder="Enter password" />
          </Form.Item>
        </Card>

        <Card title="Document Management" style={{ marginBottom: 24 }}>
          <Form.Item
            name="maxFileSize"
            label="Maximum File Size (MB)"
          >
            <Input type="number" placeholder="10" />
          </Form.Item>

          <Form.Item
            name="retentionPeriod"
            label="Document Retention Period (months)"
          >
            <Select>
              <Option value="6">6 months</Option>
              <Option value="12">12 months</Option>
              <Option value="24">24 months</Option>
              <Option value="60">5 years</Option>
              <Option value="-1">Indefinite</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="storageLocation"
            label="Storage Location"
          >
            <Input placeholder="/app/uploads" />
          </Form.Item>
        </Card>

        <Card title="System Configuration" style={{ marginBottom: 24 }}>
          <Form.Item
            name="language"
            label="System Language"
          >
            <Select>
              <Option value="en">English</Option>
              <Option value="es">Spanish</Option>
              <Option value="fr">French</Option>
              <Option value="de">German</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="timezone"
            label="Timezone"
          >
            <Select placeholder="Select timezone">
              <Option value="UTC">UTC</Option>
              <Option value="America/New_York">Eastern Time</Option>
              <Option value="America/Chicago">Central Time</Option>
              <Option value="America/Denver">Mountain Time</Option>
              <Option value="America/Los_Angeles">Pacific Time</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="logLevel"
            label="Log Level"
          >
            <Select>
              <Option value="debug">Debug</Option>
              <Option value="info">Info</Option>
              <Option value="warning">Warning</Option>
              <Option value="error">Error</Option>
            </Select>
          </Form.Item>
        </Card>

        <Card title="Security Settings">
          <Form.Item
            name="sessionTimeout"
            label="Session Timeout (minutes)"
          >
            <Input type="number" placeholder="60" />
          </Form.Item>

          <Form.Item
            name="passwordPolicy"
            label="Enforce Strong Passwords"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="twoFactorAuth"
            label="Two-Factor Authentication"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Card>

        <Divider />

        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            Save Settings
          </Button>
          <Button onClick={() => form.resetFields()}>
            Reset to Defaults
          </Button>
        </Space>
      </Form>
    </div>
  );
}

export default Settings;
