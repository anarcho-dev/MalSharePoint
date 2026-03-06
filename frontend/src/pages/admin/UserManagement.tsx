import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Shield,
  ShieldOff,
  Trash2,
  Users,
  UserPlus,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import { adminApi } from '../../api/admin';
import { useAuthStore } from '../../store/authStore';
import type { User } from '../../types';

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-500/10 text-red-400 border-red-500/20',
  user: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  readonly: 'bg-slate-700 text-slate-400 border-slate-600',
};

interface CreateUserFormProps {
  onClose: () => void;
  onSuccess: () => void;
}

function CreateUserForm({ onClose, onSuccess }: CreateUserFormProps) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await adminApi.createUser({ username, email, password, role });
      onSuccess();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ??
        'Failed to create user';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Create New User</h3>
        <button
          onClick={onClose}
          className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Username</label>
          <input
            className="input"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label">Email</label>
          <input
            type="email"
            className="input"
            placeholder="user@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label">Password</label>
          <input
            type="password"
            className="input"
            placeholder="Min. 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label">Role</label>
          <select
            className="input"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
            <option value="readonly">readonly</option>
          </select>
        </div>
        <div className="col-span-2 flex gap-2 justify-end mt-1">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading && <Loader2 size={12} className="animate-spin" />}
            Create User
          </button>
        </div>
      </form>
    </div>
  );
}

export default function UserManagement() {
  const { user: self } = useAuthStore();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page],
    queryFn: () => adminApi.users(page, 20),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Pick<User, 'role' | 'is_active'>> }) =>
      adminApi.updateUser(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const toggleActive = (user: User) => {
    if (user.id === self?.id) return;
    updateMutation.mutate({ id: user.id, data: { is_active: !user.is_active } });
  };

  const cycleRole = (user: User) => {
    if (user.id === self?.id) return;
    const next: Record<string, User['role']> = {
      user: 'admin',
      admin: 'readonly',
      readonly: 'user',
    };
    updateMutation.mutate({ id: user.id, data: { role: next[user.role] } });
  };

  const handleDelete = (user: User) => {
    if (user.id === self?.id) return;
    if (window.confirm(`Delete user "${user.username}"? This cannot be undone.`)) {
      deleteMutation.mutate(user.id);
    }
  };

  const users = data?.data?.users ?? [];
  const total = data?.data?.total ?? 0;
  const totalPages = data?.data?.pages ?? 1;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">User Management</h1>
          <p className="text-sm text-slate-500 mt-1">
            {total.toLocaleString()} registered user{total !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="btn-primary"
        >
          <UserPlus size={14} />
          New User
        </button>
      </div>

      {showCreate && (
        <CreateUserForm
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ['admin-users'] });
            setShowCreate(false);
          }}
        />
      )}

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-slate-600" size={22} />
          </div>
        ) : users.length === 0 ? (
          <div className="py-20 text-center">
            <Users size={32} className="text-slate-800 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No users found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="table-th">User</th>
                    <th className="table-th">Role</th>
                    <th className="table-th">Status</th>
                    <th className="table-th">Registered</th>
                    <th className="table-th">Last Login</th>
                    <th className="table-th text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {users.map((user) => {
                    const isSelf = user.id === self?.id;
                    return (
                      <tr key={user.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="table-td">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0">
                              <span className="text-[10px] font-bold text-slate-400 uppercase">
                                {user.username[0]}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium text-slate-200">
                                {user.username}
                                {isSelf && (
                                  <span className="ml-1.5 text-[10px] text-slate-600">(you)</span>
                                )}
                              </p>
                              <p className="text-xs text-slate-500">{user.email}</p>
                            </div>
                          </div>
                        </td>

                        <td className="table-td">
                          <button
                            onClick={() => cycleRole(user)}
                            className={clsx(
                              'badge border transition-colors',
                              ROLE_COLORS[user.role],
                              !isSelf && 'hover:opacity-80 cursor-pointer',
                              isSelf && 'cursor-default'
                            )}
                            title={isSelf ? 'Cannot change your own role' : 'Click to cycle role'}
                          >
                            {user.role}
                          </button>
                        </td>

                        <td className="table-td">
                          <span
                            className={clsx(
                              'badge border',
                              user.is_active
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : 'bg-slate-800 text-slate-500 border-slate-700'
                            )}
                          >
                            {user.is_active ? 'active' : 'disabled'}
                          </span>
                        </td>

                        <td className="table-td text-slate-500 text-xs whitespace-nowrap">
                          {new Date(user.created_at).toLocaleDateString()}
                        </td>

                        <td className="table-td text-slate-500 text-xs whitespace-nowrap">
                          {user.last_login
                            ? new Date(user.last_login).toLocaleDateString()
                            : '—'}
                        </td>

                        <td className="table-td">
                          <div className="flex items-center gap-1 justify-end">
                            {!isSelf && (
                              <>
                                <button
                                  onClick={() => toggleActive(user)}
                                  className={clsx(
                                    'p-1.5 rounded transition-colors',
                                    user.is_active
                                      ? 'text-slate-500 hover:text-yellow-400 hover:bg-yellow-400/10'
                                      : 'text-slate-500 hover:text-emerald-400 hover:bg-emerald-400/10'
                                  )}
                                  title={user.is_active ? 'Deactivate user' : 'Activate user'}
                                >
                                  {user.is_active ? <ShieldOff size={14} /> : <Shield size={14} />}
                                </button>
                                <button
                                  onClick={() => handleDelete(user)}
                                  className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                                  title="Delete user"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800">
                <span className="text-xs text-slate-500">
                  Page {page} of {totalPages}
                </span>
                <div className="flex gap-1.5">
                  <button
                    className="btn-secondary !px-2 !py-1.5"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    <ChevronLeft size={14} />
                  </button>
                  <button
                    className="btn-secondary !px-2 !py-1.5"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
