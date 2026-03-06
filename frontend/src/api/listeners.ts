import api from './client';

// ── Listener Types ────────────────────────────────────────────────────────

export interface ListenerProfile {
  id: number;
  name: string;
  description: string;
  server_header: string;
  custom_headers: Record<string, string>;
  default_response_body: string;
  default_content_type: string;
  created_by: number | null;
  created_at: string;
}

export interface ListenerItem {
  id: number;
  name: string;
  listener_type: 'http' | 'https';
  bind_address: string;
  bind_port: number;
  status: 'stopped' | 'starting' | 'running' | 'error';
  tls_cert_path: string | null;
  tls_key_path: string | null;
  profile_id: number | null;
  profile_name: string | null;
  created_by: number;
  pid: number | null;
  last_started_at: string | null;
  last_stopped_at: string | null;
  created_at: string;
  error_message: string | null;
  callback_count: number;
  agent_count: number;
  staged_count: number;
  runtime?: { running: boolean; thread_name?: string };
}

export interface CallbackItem {
  id: number;
  listener_id: number;
  source_ip: string;
  source_port: number | null;
  hostname: string | null;
  user_agent: string;
  request_method: string;
  request_path: string;
  request_headers: Record<string, string>;
  request_body: string | null;
  file_id: number | null;
  timestamp: string;
  metadata: Record<string, unknown> | null;
}

export interface StagedPayloadItem {
  id: number;
  name: string;
  listener_id: number;
  payload_type: string;
  content_hash: string;
  stage_path: string;
  is_active: boolean;
  download_count: number;
  created_by: number;
  created_at: string;
}

export interface AgentItem {
  id: string;
  hostname: string | null;
  username: string | null;
  os_info: string | null;
  internal_ip: string | null;
  external_ip: string | null;
  listener_id: number | null;
  sleep_interval: number;
  jitter: number;
  status: 'active' | 'dormant' | 'dead' | 'disconnected';
  last_seen: string | null;
  first_seen: string | null;
  metadata: Record<string, unknown> | null;
  task_count: number;
}

export interface AgentTaskItem {
  id: string;
  agent_id: string;
  command: string;
  task_type: string;
  status: 'queued' | 'sent' | 'completed' | 'failed';
  created_by: number | null;
  created_at: string;
  sent_at: string | null;
  completed_at: string | null;
  result: string | null;
  success: boolean | null;
}

// ── Listeners CRUD ────────────────────────────────────────────────────────

export const getListeners = () => api.get<ListenerItem[]>('/listeners');

export const createListener = (data: {
  name: string; listener_type?: string; bind_address?: string;
  bind_port: number; profile_id?: number | null;
  tls_cert_path?: string; tls_key_path?: string;
}) => api.post<ListenerItem>('/listeners', data);

export const updateListener = (id: number, data: Partial<ListenerItem>) =>
  api.put<ListenerItem>(`/listeners/${id}`, data);

export const deleteListener = (id: number) =>
  api.delete(`/listeners/${id}`);

// ── Lifecycle ─────────────────────────────────────────────────────────────

export const startListener = (id: number) =>
  api.post(`/listeners/${id}/start`);

export const stopListener = (id: number) =>
  api.post(`/listeners/${id}/stop`);

export const restartListener = (id: number) =>
  api.post(`/listeners/${id}/restart`);

// ── Profiles ──────────────────────────────────────────────────────────────

export const getProfiles = () =>
  api.get<ListenerProfile[]>('/listeners/profiles');

export const createProfile = (data: Partial<ListenerProfile>) =>
  api.post<ListenerProfile>('/listeners/profiles', data);

export const updateProfile = (id: number, data: Partial<ListenerProfile>) =>
  api.put<ListenerProfile>(`/listeners/profiles/${id}`, data);

export const deleteProfile = (id: number) =>
  api.delete(`/listeners/profiles/${id}`);

// ── Callbacks ─────────────────────────────────────────────────────────────

export const getCallbacks = (params?: {
  page?: number; per_page?: number; listener_id?: number;
  ip?: string; method?: string; search?: string;
}) => api.get<{
  callbacks: CallbackItem[]; total: number; pages: number; current_page: number;
}>('/listeners/callbacks', { params });

export const deleteCallbacks = (params?: {
  older_than_days?: number; listener_id?: number;
}) => api.delete('/listeners/callbacks', { params });

// ── Staged Payloads ───────────────────────────────────────────────────────

export const getStagedPayloads = (listenerId: number) =>
  api.get<StagedPayloadItem[]>(`/listeners/${listenerId}/staged`);

export const createStagedPayload = (listenerId: number, data: {
  name: string; content: string; stage_path: string;
  payload_type?: string; is_active?: boolean;
}) => api.post<StagedPayloadItem>(`/listeners/${listenerId}/staged`, data);

export const updateStagedPayload = (listenerId: number, stagedId: number, data: Partial<StagedPayloadItem & { content: string }>) =>
  api.put<StagedPayloadItem>(`/listeners/${listenerId}/staged/${stagedId}`, data);

export const deleteStagedPayload = (listenerId: number, stagedId: number) =>
  api.delete(`/listeners/${listenerId}/staged/${stagedId}`);

// ── Agents ────────────────────────────────────────────────────────────────

export const getAgents = (params?: {
  page?: number; per_page?: number; status?: string; search?: string;
}) => api.get<{
  agents: AgentItem[]; total: number; pages: number; current_page: number;
}>('/admin/agents', { params });

export const getAgent = (id: string) =>
  api.get<AgentItem & { recent_tasks: AgentTaskItem[] }>(`/admin/agents/${id}`);

export const deleteAgent = (id: string) =>
  api.delete(`/admin/agents/${id}`);

export const createAgentTask = (agentId: string, data: {
  command: string; task_type?: string;
}) => api.post<AgentTaskItem>(`/admin/agents/${agentId}/tasks`, data);

export const getAgentTasks = (agentId: string, params?: {
  page?: number; per_page?: number; status?: string;
}) => api.get<{
  tasks: AgentTaskItem[]; total: number; pages: number; current_page: number;
}>(`/admin/agents/${agentId}/tasks`, { params });

export const setAgentSleep = (agentId: string, data: {
  sleep_interval?: number; jitter?: number;
}) => api.post(`/admin/agents/${agentId}/sleep`, data);

export const killAgent = (agentId: string) =>
  api.post(`/admin/agents/${agentId}/kill`);

export const refreshAgentStatus = () =>
  api.post('/admin/agents/refresh-status');

export const getAgentStats = () =>
  api.get<{
    total_agents: number; active: number; dormant: number; dead: number;
    total_tasks: number; queued_tasks: number; completed_tasks: number;
  }>('/admin/agents/stats');

// ── Payload Templates ─────────────────────────────────────────────────────

export interface PayloadTemplate {
  id: string;
  name: string;
  description: string;
  platform: string;
  payload_type: string;
  default_stage_path: string;
  params: string[];
}

export interface RenderedPayload {
  template_id: string;
  name: string;
  payload_type: string;
  platform: string;
  default_stage_path: string;
  content: string;
  params_used: Record<string, string>;
}

export const getTemplates = () =>
  api.get<PayloadTemplate[]>('/listeners/templates');

export const getTemplateDetail = (id: string) =>
  api.get<PayloadTemplate & { content: string }>(`/listeners/templates/${id}`);

export const renderTemplate = (id: string, params: Record<string, string | number>) =>
  api.post<RenderedPayload>(`/listeners/templates/${id}/render`, params);

export const createStagedFromTemplate = (listenerId: number, data: {
  template_id: string;
  LHOST?: string;
  LPORT?: number;
  SLEEP?: number;
  JITTER?: number;
  STAGE_PATH?: string;
  SCHEME?: string;
  name?: string;
  stage_path?: string;
}) => api.post<StagedPayloadItem>(`/listeners/${listenerId}/staged/from-template`, data);
