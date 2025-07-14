
import React from 'react';
import { Layout, Button, Avatar, Dropdown, Space, Badge } from 'antd';
import {
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
} from '@ant-design/icons';

const { Header: AntHeader } = Layout;

const Header = ({ collapsed, onToggle, user, onLogout }) => {
  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: 'Profile',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: 'Settings',
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: onLogout,
    },
  ];

  return (
    <AntHeader
      style={{
        padding: '0 24px',
        background: '#fff',
        borderBottom: '1px solid #f0f0f0',
        position: 'fixed',
        zIndex: 999,
        width: '100%',
        left: collapsed ? 80 : 240,
        transition: 'left 0.2s',
      }}
    >
      <div className="flex items-center justify-between h-full">
        <div className="flex items-center">
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={onToggle}
            style={{
              fontSize: '16px',
              width: 64,
              height: 64,
            }}
          />
          <h1 className="text-xl font-semibold text-gray-800 ml-4">
            Intelligent Document Classifier & Router
          </h1>
        </div>

        <div className="flex items-center space-x-4">
          <Badge count={5} size="small">
            <Button
              type="text"
              icon={<BellOutlined />}
              size="large"
            />
          </Badge>

          <Dropdown
            menu={{ items: userMenuItems }}
            placement="bottomRight"
            trigger={['click']}
          >
            <Space className="cursor-pointer hover:bg-gray-50 px-3 py-2 rounded">
              <Avatar icon={<UserOutlined />} />
              <div className="hidden md:block">
                <div className="text-sm font-medium">{user?.full_name}</div>
                <div className="text-xs text-gray-500 capitalize">
                  {user?.role} • {user?.department}
                </div>
              </div>
            </Space>
          </Dropdown>
        </div>
      </div>
    </AntHeader>
  );
};

export default Header;
