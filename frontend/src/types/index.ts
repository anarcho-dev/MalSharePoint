export interface User {
  id: number;
  username: string;
  email: string;
  role: 'user' | 'admin' | 'readonly';
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login: string | null;
}

export interface FileItem {
  id: number;
  filename: string;
  sha256: string;
  size: number;
  mime_type: string | null;
  description: string | null;
  tags: string[];
  is_public: boolean;
  download_count: number;
  uploaded_by: number;
  upload_date: string;
}

export interface AuditLog {
  id: number;
  user_id: number | null;
  action: string;
  target: string | null;
  details: string | null;
  ip_address: string | null;
  timestamp: string;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  total_files: number;
  public_files: number;
  total_downloads: number;
  audit_log_entries: number;
}

export interface FileListResponse {
  files: FileItem[];
  total: number;
  pages: number;
  current_page: number;
}

export interface UserListResponse {
  users: User[];
  total: number;
  pages: number;
  current_page: number;
}

export interface LogListResponse {
  logs: AuditLog[];
  total: number;
  pages: number;
  current_page: number;
}
