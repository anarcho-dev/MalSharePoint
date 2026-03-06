import api from './client';
import type { FileItem, FileListResponse } from '../types';

export const filesApi = {
  list: (page = 1, perPage = 20) =>
    api.get<FileListResponse>('/files', { params: { page, per_page: perPage } }),

  getById: (id: number) => api.get<FileItem>(`/files/${id}`),

  upload: (formData: FormData, onProgress?: (pct: number) => void) =>
    api.post<{ message: string; file: FileItem }>('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) =>
        onProgress && onProgress(Math.round((e.loaded * 100) / (e.total ?? 1))),
    }),

  update: (
    id: number,
    data: Partial<Pick<FileItem, 'description' | 'tags' | 'is_public'>>
  ) => api.put<FileItem>(`/files/${id}`, data),

  delete: (id: number) => api.delete(`/files/${id}`),

  /** Returns the URL to trigger a browser download (includes auth token via interceptor) */
  getDownloadUrl: (id: number) => `/api/files/${id}/download`,
};
