import { useQuery } from '@tanstack/react-query';
import { Users, FolderOpen, Download, Globe, Activity, Loader2, TrendingUp } from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../api/files';
import { adminApi } from '../api/admin';
import { useAuthStore } from '../store/authStore';
import { formatBytes, formatDate } from '../utils/format';
import type { AdminStats } from '../types';

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number | string;
  colorClass: string;
}

function StatCard({ icon: Icon, label, value, colorClass }: StatCardProps) {
  return (
    <div className="stat-card group">
      <div
        className={clsx(
          'w-10 h-10 rounded-xl border flex items-center justify-center mb-4 transition-shadow duration-300',
          colorClass
        )}
      >
        <Icon size={18} />
      </div>
      <p className="text-2xl font-black text-slate-100 tabular-nums tracking-tight">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
      <p className="text-xs font-semibold text-slate-500 mt-1.5 uppercase tracking-wider">{label}</p>
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
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Welcome back,{' '}
            <span className="text-slate-300 font-semibold">{user?.username}</span>
          </p>
        </div>
        <HealthBadge />
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

      {/* Recent files */}
      <div className="card">
        <div className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-slate-500" />
            <h2 className="font-bold text-slate-200 text-sm uppercase tracking-wider">Recent Files</h2>
          </div>
          <span className="text-xs font-semibold text-slate-600 tabular-nums">
            {filesData?.data?.total ?? 0} total
          </span>
        </div>

        {filesLoading ? (
          <div className="flex justify-center py-14">
            <Loader2 className="animate-spin text-slate-700" size={22} />
          </div>
        ) : recentFiles.length === 0 ? (
          <div className="py-14 text-center text-slate-600 text-sm">No files uploaded yet.</div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {recentFiles.map((f) => (
              <div key={f.id} className="flex items-center gap-4 px-5 py-3 hover:bg-slate-800/20 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-200 truncate">{f.filename}</p>
                  <p className="text-[11px] text-slate-600 font-mono mt-0.5">
                    {f.sha256.slice(0, 20)}…
                  </p>
                </div>
                <span className="text-xs text-slate-500 tabular-nums font-mono">
                  {formatBytes(f.size)}
                </span>
                <span className="text-xs text-slate-600">{formatDate(f.upload_date)}</span>
                <span
                  className={clsx(
                    'badge text-[10px]',
                    f.is_public
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-slate-800 text-slate-500 border border-slate-700/50'
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
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border',
        healthy
          ? 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400'
          : 'bg-red-500/8 border-red-500/20 text-red-400'
      )}
    >
      <span className={clsx(
        'w-1.5 h-1.5 rounded-full animate-pulse-dot',
        healthy ? 'bg-emerald-400' : 'bg-red-400'
      )} />
      DB {data?.database ?? 'unknown'}
    </div>
  );
}

