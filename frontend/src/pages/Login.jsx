import React, { useState } from 'react';
import { Card, Form, Input, Button, Alert, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { authService } from '../services/apiService.js';

const { Title, Text } = Typography;

const Login = ({ onLogin }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (values) => {
    setLoading(true);
    setError('');

    try {
      const response = await authService.login(values);
      onLogin(response.user, response.access_token);
    } catch (error) {
      setError(error.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Title level={2} className="text-gray-800">
            IDCR System
          </Title>
          <Text className="text-gray-600">
            Intelligent Document Classifier & Router
          </Text>
        </div>

        <Card className="shadow-xl">
          <Title level={3} className="text-center mb-6">
            Sign In
          </Title>

          {error && (
            <Alert
              message={error}
              type="error"
              showIcon
              className="mb-4"
            />
          )}

          <Form
            name="login"
            onFinish={handleSubmit}
            layout="vertical"
            size="large"
          >
            <Form.Item
              label="Email"
              name="username"
              rules={[
                { required: true, message: 'Please input your email!' },
                { type: 'email', message: 'Please enter a valid email!' }
              ]}
            >
              <Input 
                prefix={<UserOutlined />} 
                placeholder="Enter your email" 
              />
            </Form.Item>

            <Form.Item
              label="Password"
              name="password"
              rules={[{ required: true, message: 'Please input your password!' }]}
            >
              <Input.Password 
                prefix={<LockOutlined />} 
                placeholder="Enter your password" 
              />
            </Form.Item>

            <Form.Item>
              <Button 
                type="primary" 
                htmlType="submit" 
                className="w-full h-12 text-base font-medium"
                loading={loading}
              >
                Sign In
              </Button>
            </Form.Item>
          </Form>

          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <Text className="text-sm text-gray-600 block mb-2">Demo Accounts:</Text>
            <div className="space-y-1 text-xs">
              <div><strong>Admin:</strong> admin@company.com / admin123</div>
              <div><strong>Manager:</strong> manager@company.com / manager123</div>
              <div><strong>Employee:</strong> employee@company.com / employee123</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Login;