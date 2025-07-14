
import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { authService } from '../services/apiService.js';

const { Title, Text } = Typography;

function Login({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      let response;
      if (isRegister) {
        response = await authService.register(values);
        message.success('Registration successful! Please login.');
        setIsRegister(false);
      } else {
        response = await authService.login(values);
        message.success('Login successful!');
        onLogin(response.user, response.token);
      }
    } catch (error) {
      const errorMessage = error.response?.data?.message || 
        (isRegister ? 'Registration failed' : 'Login failed');
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px',
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
          borderRadius: 12,
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={2} style={{ marginBottom: 8 }}>
              {isRegister ? 'Create Account' : 'Welcome Back'}
            </Title>
            <Text type="secondary">
              {isRegister 
                ? 'Create your account to get started' 
                : 'Sign in to your account'
              }
            </Text>
          </div>

          <Form
            name={isRegister ? 'register' : 'login'}
            onFinish={handleSubmit}
            layout="vertical"
            requiredMark={false}
          >
            {isRegister && (
              <Form.Item
                name="name"
                label="Full Name"
                rules={[{ required: true, message: 'Please enter your name' }]}
              >
                <Input 
                  prefix={<UserOutlined />} 
                  placeholder="Enter your full name"
                  size="large"
                />
              </Form.Item>
            )}

            <Form.Item
              name="email"
              label="Email"
              rules={[
                { required: true, message: 'Please enter your email' },
                { type: 'email', message: 'Please enter a valid email' }
              ]}
            >
              <Input 
                prefix={<MailOutlined />} 
                placeholder="Enter your email"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="password"
              label="Password"
              rules={[
                { required: true, message: 'Please enter your password' },
                { min: 6, message: 'Password must be at least 6 characters' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Enter your password"
                size="large"
              />
            </Form.Item>

            {isRegister && (
              <Form.Item
                name="department"
                label="Department"
                rules={[{ required: true, message: 'Please enter your department' }]}
              >
                <Input 
                  placeholder="Enter your department"
                  size="large"
                />
              </Form.Item>
            )}

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                style={{ marginTop: 8 }}
              >
                {isRegister ? 'Create Account' : 'Sign In'}
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text>
              {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
              <Button 
                type="link" 
                onClick={() => setIsRegister(!isRegister)}
                style={{ padding: 0 }}
              >
                {isRegister ? 'Sign In' : 'Create Account'}
              </Button>
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  );
}

export default Login;
