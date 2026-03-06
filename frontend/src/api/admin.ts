import api from './client';
import type { User, AdminStats, AuditLog, UserListResponse, LogListResponse } from '../types';

export const adminApi = {
  stats: () => api.get<AdminStats>('/admin/stats'),

  users: (page = 1, perPage = 20) =>
    api.get<UserListResponse>('/admin/users', { params: { page, per_page: perPage } }),

  updateUser: (id: number, data: Partial<Pick<User, 'role' | 'is_active'>>) =>
    api.put<User>(`/admin/users/${id}`, data),

  deleteUser: (id: number) => api.delete(`/admin/users/${id}`),

  createUser: (data: { username: string; email: string; password: string; role: string }) =>
    api.post('/admin/users', data),

  logs: (page = 1, perPage = 50) =>
    api.get<LogListResponse>('/admin/logs', { params: { page, per_page: perPage } }),

  getConfig: () => api.get<Record<string, string>>('/admin/config'),

  updateConfig: (data: Record<string, string>) => api.post('/admin/config', data),
};
