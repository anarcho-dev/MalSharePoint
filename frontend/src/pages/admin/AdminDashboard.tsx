import { useQuery } from '@tanstack/react-query';
import {
  Users,
  FolderOpen,
  Download,
  Globe,
  Activity,
  UserCheck,
  Loader2,
} from 'lucide-react';
import clsx from 'clsx';
import { Link } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import type { AdminStats } from '../../types';

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number;
  colorClass: string;
  link?: string;
}

function StatCard({ icon: Icon, label, value, colorClass, link }: StatCardProps) {
  const content = (
    <div className="card p-5 hover:border-slate-700 transition-colors">
      <div
        className={clsx(
          'w-10 h-10 rounded-lg border flex items-center justify-center mb-4',
          colorClass
        )}
      >
        <Icon size={18} />
      </div>
      <p className="text-2xl font-bold text-slate-100 tabular-nums">
        {value.toLocaleString()}
      </p>
      <p className="text-sm text-slate-500 mt-1">{label}</p>
    </div>
  );

  return link ? <Link to={link}>{content}</Link> : content;
}

export default function AdminDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => adminApi.stats(),
    refetchInterval: 30_000,
  });

  const stats: AdminStats | undefined = data?.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Admin Overview</h1>
        <p className="text-sm text-slate-500 mt-1">Server statistics and health</p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="animate-spin text-slate-600" size={22} />
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard
            icon={Users}
            label="Total Users"
            value={stats.total_users}
            colorClass="bg-blue-500/10 border-blue-500/20 text-blue-400"
            link="/admin/users"
          />
          <StatCard
            icon={UserCheck}
            label="Active Users"
            value={stats.active_users}
            colorClass="bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
          />
          <StatCard
            icon={FolderOpen}
            label="Total Files"
            value={stats.total_files}
            colorClass="bg-violet-500/10 border-violet-500/20 text-violet-400"
          />
          <StatCard
            icon={Globe}
            label="Public Files"
            value={stats.public_files}
            colorClass="bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
          />
          <StatCard
            icon={Download}
            label="Total Downloads"
            value={stats.total_downloads}
            colorClass="bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
          />
          <StatCard
            icon={Activity}
            label="Audit Log Entries"
            value={stats.audit_log_entries}
            colorClass="bg-red-500/10 border-red-500/20 text-red-400"
            link="/admin/logs"
          />
        </div>
      ) : null}

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link to="/admin/users" className="card p-5 hover:border-slate-700 transition-colors group">
          <div className="flex items-center gap-3">
            <Users size={20} className="text-slate-500 group-hover:text-slate-300 transition-colors" />
            <div>
              <p className="font-medium text-slate-200 text-sm">User Management</p>
              <p className="text-xs text-slate-500 mt-0.5">
                Manage roles, activate or deactivate accounts
              </p>
            </div>
          </div>
        </Link>
        <Link to="/admin/logs" className="card p-5 hover:border-slate-700 transition-colors group">
          <div className="flex items-center gap-3">
            <Activity size={20} className="text-slate-500 group-hover:text-slate-300 transition-colors" />
            <div>
              <p className="font-medium text-slate-200 text-sm">Audit Logs</p>
              <p className="text-xs text-slate-500 mt-0.5">
                Review all user actions and system events
              </p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
