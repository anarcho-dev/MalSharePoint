import { useQuery } from '@tanstack/react-query';
import { Users, FolderOpen, Download, Globe, Activity, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../api/files';
import { adminApi } from '../api/admin';
import { useAuthStore } from '../store/authStore';
import type { AdminStats } from '../types';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number | string;
  colorClass: string;
}

function StatCard({ icon: Icon, label, value, colorClass }: StatCardProps) {
  return (
    <div className="card p-5">
      <div
        className={clsx(
          'w-10 h-10 rounded-lg border flex items-center justify-center mb-4',
          colorClass
        )}
      >
        <Icon size={18} />
      </div>
      <p className="text-2xl font-bold text-slate-100 tabular-nums">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
      <p className="text-sm text-slate-500 mt-1">{label}</p>
    </div>
  );
}

export default function Dashboard() {
  const { user, isAdmin } = useAuthStore();

  const { data: filesData, isLoading: filesLoading } = useQuery({
    queryKey: ['files', 1, 5],
    queryFn: () => filesApi.list(1, 5),
  });

  const { data: statsData } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => adminApi.stats(),
    enabled: isAdmin(),
  });

  const stats: AdminStats | undefined = statsData?.data;
  const recentFiles = filesData?.data?.files ?? [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">
          Welcome back,{' '}
          <span className="text-slate-300 font-medium">{user?.username}</span>
        </p>
      </div>

      {/* Admin stats grid */}
      {isAdmin() && stats && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard
            icon={Users}
            label="Total Users"
            value={stats.total_users}
            colorClass="bg-blue-500/10 border-blue-500/20 text-blue-400"
          />
          <StatCard
            icon={FolderOpen}
            label="Total Files"
            value={stats.total_files}
            colorClass="bg-violet-500/10 border-violet-500/20 text-violet-400"
          />
          <StatCard
            icon={Download}
            label="Total Downloads"
            value={stats.total_downloads}
            colorClass="bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
          />
          <StatCard
            icon={Globe}
            label="Public Files"
            value={stats.public_files}
            colorClass="bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
          />
          <StatCard
            icon={Users}
            label="Active Users"
            value={stats.active_users}
            colorClass="bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
          />
          <StatCard
            icon={Activity}
            label="Audit Entries"
            value={stats.audit_log_entries}
            colorClass="bg-red-500/10 border-red-500/20 text-red-400"
          />
        </div>
      )}

      {/* Health indicator */}
      <HealthBadge />

      {/* Recent files */}
      <div className="card">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold text-slate-100 text-sm">Recent Files</h2>
          <span className="text-xs text-slate-500">{filesData?.data?.total ?? 0} total</span>
        </div>

        {filesLoading ? (
          <div className="flex justify-center py-14">
            <Loader2 className="animate-spin text-slate-600" size={22} />
          </div>
        ) : recentFiles.length === 0 ? (
          <div className="py-14 text-center text-slate-600 text-sm">No files uploaded yet.</div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {recentFiles.map((f) => (
              <div key={f.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{f.filename}</p>
                  <p className="text-[11px] text-slate-600 font-mono mt-0.5">
                    {f.sha256.slice(0, 20)}…
                  </p>
                </div>
                <span className="text-xs text-slate-500 tabular-nums">
                  {formatBytes(f.size)}
                </span>
                <span className="text-xs text-slate-600">{formatDate(f.upload_date)}</span>
                <span
                  className={clsx(
                    'badge',
                    f.is_public
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-slate-800 text-slate-500'
                  )}
                >
                  {f.is_public ? 'public' : 'private'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HealthBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await fetch('/api/health');
      return res.json() as Promise<{ status: string; database: string }>;
    },
    refetchInterval: 60_000,
  });

  if (isLoading) return null;

  const healthy = data?.database === 'healthy';
  return (
    <div
      className={clsx(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border',
        healthy
          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
          : 'bg-red-500/10 border-red-500/20 text-red-400'
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full', healthy ? 'bg-emerald-400' : 'bg-red-400')} />
      Database: {data?.database ?? 'unknown'}
    </div>
  );
}
