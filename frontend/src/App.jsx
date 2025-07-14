import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Layout, ConfigProvider } from 'antd';
import { theme } from './themes/theme.js';
import Sidebar from './components/layout/Sidebar.jsx';
import Header from './components/layout/Header.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Documents from './pages/Documents.jsx';
import Upload from './pages/Upload.jsx';
import Analytics from './pages/Analytics.jsx';
import Settings from './pages/Settings.jsx';
import './index.css';

const { Content } = Layout;

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('currentUser');

    if (token && user) {
      setIsAuthenticated(true);
      setCurrentUser(JSON.parse(user));
    }
  }, []);

  const handleLogin = (userData) => {
    setIsAuthenticated(true);
    setCurrentUser(userData);
    localStorage.setItem('token', userData.token || 'demo-token');
    localStorage.setItem('currentUser', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setCurrentUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('currentUser');
  };

  if (!isAuthenticated) {
    return (
      <ConfigProvider theme={theme}>
        <Login onLogin={handleLogin} />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={theme}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sidebar 
          collapsed={sidebarCollapsed}
          currentPath={location.pathname}
        />
        <Layout>
          <Header 
            user={currentUser}
            onLogout={handleLogout}
            onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
            collapsed={sidebarCollapsed}
          />
          <Content style={{ 
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: '#fff',
            borderRadius: 8
          }}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard user={currentUser} />} />
              <Route path="/documents" element={<Documents user={currentUser} />} />
              <Route path="/upload" element={<Upload user={currentUser} />} />
              <Route path="/analytics" element={<Analytics user={currentUser} />} />
              <Route path="/settings" element={<Settings user={currentUser} />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}

export default App;