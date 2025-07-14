
import apiClient from './apiClient.js';

// Auth-related API calls
export const authService = {
  login: (credentials) => apiClient.post('/login', credentials),
  logout: () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    window.location.href = '/';
  },
  getCurrentUser: () => apiClient.get('/me'),
};

// Document-related API calls
export const documentService = {
  getAll: (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    return apiClient.get(`/documents${queryString ? '?' + queryString : ''}`);
  },
  getById: (id) => apiClient.get(`/documents/${id}`),
  approve: (id) => apiClient.post(`/documents/${id}/approve`),
  reject: (id) => apiClient.post(`/documents/${id}/reject`),
  download: (id) => window.open(`/api/documents/${id}/download`),
  bulkUpload: (formData) => apiClient.post('/bulk-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
};

// Stats and analytics
export const statsService = {
  getStats: () => apiClient.get('/stats'),
  getAnalytics: (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    return apiClient.get(`/analytics${queryString ? '?' + queryString : ''}`);
  },
};

// Email notifications
export const notificationService = {
  getAll: () => apiClient.get('/email-notifications'),
  markAsRead: (id) => apiClient.patch(`/email-notifications/${id}/read`),
  getUnreadCount: () => apiClient.get('/email-notifications/unread-count'),
};

// System health and monitoring
export const systemService = {
  getHealth: () => apiClient.get('/health'),
  getSystemStats: () => apiClient.get('/system/stats'),
};
