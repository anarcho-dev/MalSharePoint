import api from './client';
import type { User } from '../types';

export interface LoginPayload {
  username: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export const authApi = {
  login: (data: LoginPayload) => api.post<LoginResponse>('/auth/login', data),
  register: (data: RegisterPayload) =>
    api.post<{ message: string; role: string }>('/auth/register', data),
  me: () => api.get<User>('/auth/me'),
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
};
