
import React from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  UploadOutlined,
  BarChartOutlined,
  SettingOutlined,
  BellOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';

const { Sider } = Layout;

const Sidebar = ({ collapsed, user, onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: 'Documents',
    },
    {
      key: '/upload',
      icon: <UploadOutlined />,
      label: 'Upload',
    },
    {
      key: '/analytics',
      icon: <BarChartOutlined />,
      label: 'Analytics',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: 'Settings',
    },
  ];

  const handleMenuClick = ({ key }) => {
    if (key === 'logout') {
      onLogout();
    } else {
      navigate(key);
    }
  };

  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={collapsed}
      theme="dark"
      width={240}
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 1000,
      }}
    >
      <div className="flex items-center justify-center h-16 bg-blue-900">
        <div className="text-white font-bold text-lg">
          {collapsed ? 'IDCR' : 'IDCR System'}
        </div>
      </div>
      
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ borderRight: 0 }}
      />

      <div className="absolute bottom-0 left-0 right-0 p-4">
        <Menu
          theme="dark"
          mode="inline"
          items={[
            {
              key: 'logout',
              icon: <LogoutOutlined />,
              label: collapsed ? null : 'Logout',
            },
          ]}
          onClick={handleMenuClick}
        />
        
        {!collapsed && user && (
          <div className="text-white text-xs mt-2 p-2 bg-gray-800 rounded">
            <div className="font-medium">{user.full_name}</div>
            <div className="text-gray-400">{user.email}</div>
            <div className="text-gray-400 capitalize">{user.role} • {user.department}</div>
          </div>
        )}
      </div>
    </Sider>
  );
};

export default Sidebar;
