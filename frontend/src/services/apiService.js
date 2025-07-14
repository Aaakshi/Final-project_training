
import apiClient from './apiClient.js';

// Authentication Service
export const authService = {
  login: (credentials) => apiClient.post('/login', credentials),
  register: (userData) => apiClient.post('/register', userData),
  logout: () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    return Promise.resolve();
  },
  getCurrentUser: () => apiClient.get('/me'),
};

// Document Service
export const documentService = {
  getAll: (params = {}) => {
    const queryString = new URLSearchParams(params).toString();
    return apiClient.get(`/documents${queryString ? `?${queryString}` : ''}`);
  },
  getById: (id) => apiClient.get(`/documents/${id}`),
  bulkUpload: (formData) => apiClient.post('/bulk-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  review: (id, reviewData) => apiClient.post(`/documents/${id}/review`, reviewData),
  delete: (id) => apiClient.delete(`/documents/${id}`),
};

// Statistics Service
export const statsService = {
  getDashboardStats: () => apiClient.get('/stats'),
  getHealth: () => apiClient.get('/health'),
};

// Microservices Health Check
export const microservicesService = {
  checkApiGateway: () => apiClient.get('http://localhost:8001/ping'),
  checkClassification: () => apiClient.get('http://localhost:8002/ping'),
  checkContentAnalysis: () => apiClient.get('http://localhost:8003/ping'),
  checkRoutingEngine: () => apiClient.get('http://localhost:8004/ping'),
  checkWorkflowIntegration: () => apiClient.get('http://localhost:8005/ping'),
};

// Email Notifications Service
export const notificationService = {
  getEmailNotifications: () => apiClient.get('/email-notifications'),
  sendNotification: (data) => apiClient.post('/notifications', data),
};
