import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_BASE = '';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken && error.config && !error.config._retry) {
        error.config._retry = true;
        try {
          const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
          const { access_token, refresh_token: newRefresh } = res.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', newRefresh);
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return api(error.config);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// Auth
export const authAPI = {
  login: (email: string, password: string) => api.post('/api/auth/login', { email, password }),
  signup: (email: string, password: string, firstName: string, lastName: string) =>
    api.post('/api/auth/signup', { email, password, first_name: firstName, last_name: lastName }),
  refresh: (refreshToken: string) => api.post('/api/auth/refresh', { refresh_token: refreshToken }),
  logout: () => api.post('/api/auth/logout'),
  validate: () => api.get('/api/auth/validate'),
};

// Users
export const usersAPI = {
  getProfile: (userId: string) => api.get(`/api/users/${userId}/profile`),
  createProfile: (userId: string, data: any) => api.post(`/api/users/${userId}/profile`, data),
  updateProfile: (userId: string, data: any) => api.put(`/api/users/${userId}/profile`, data),
  deleteProfile: (userId: string) => api.delete(`/api/users/${userId}/profile`),
  list: (skip = 0, limit = 20) => api.get(`/api/users?skip=${skip}&limit=${limit}`),
  search: (query: string) => api.get(`/api/users/search?q=${query}`),
};

// Roles
export const rolesAPI = {
  list: () => api.get('/api/roles'),
  get: (id: string) => api.get(`/api/roles/${id}`),
  create: (data: any) => api.post('/api/roles', data),
  assign: (userId: string, roleId: string) => api.post('/api/roles/assign', { user_id: userId, role_id: roleId }),
  revoke: (roleId: string, userId: string) => api.delete(`/api/roles/${roleId}/users/${userId}`),
  getUserPermissions: (userId: string) => api.get(`/api/roles/users/${userId}/permissions`),
};

// Audit
export const auditAPI = {
  list: (params?: any) => api.get('/api/audit/logs', { params }),
  get: (id: string) => api.get(`/api/audit/logs/${id}`),
  stats: () => api.get('/api/audit/stats'),
};

// AI
export const aiAPI = {
  query: (question: string, userId?: string) => api.post('/api/ai/query', { question, user_id: userId }),
  evaluate: (question: string) => api.post('/api/ai/evaluate', { question }),
  ingest: (documents: any[]) => api.post('/api/ai/ingest', { documents }),
};