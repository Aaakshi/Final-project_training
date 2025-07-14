
import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  FileTextOutlined,
  UploadOutlined,
  BarChartOutlined,
  SettingOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';

const { Sider } = Layout;

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

function Sidebar({ collapsed }) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  return (
    <Sider 
      trigger={null} 
      collapsible 
      collapsed={collapsed}
      theme="dark"
      width={240}
    >
      <div style={{
        height: 64,
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        padding: collapsed ? 0 : '0 16px',
        background: 'rgba(255, 255, 255, 0.1)',
        margin: '16px 8px',
        borderRadius: 6,
        transition: 'all 0.2s',
      }}>
        <FolderOpenOutlined style={{ 
          color: '#1890ff', 
          fontSize: 24,
          marginRight: collapsed ? 0 : 8 
        }} />
        {!collapsed && (
          <span style={{ 
            color: '#fff', 
            fontSize: 16, 
            fontWeight: 600 
          }}>
            IDCR System
          </span>
        )}
      </div>
      
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ border: 'none' }}
      />
    </Sider>
  );
}

export default Sidebar;
