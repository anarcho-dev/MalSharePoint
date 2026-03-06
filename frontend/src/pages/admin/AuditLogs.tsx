import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Loader2, ScrollText } from 'lucide-react';
import clsx from 'clsx';
import { adminApi } from '../../api/admin';
import type { AuditLog } from '../../types';

const ACTION_COLORS: Record<string, string> = {
  login: 'bg-emerald-500/10 text-emerald-400',
  register: 'bg-blue-500/10 text-blue-400',
  logout: 'bg-slate-700 text-slate-400',
  upload: 'bg-violet-500/10 text-violet-400',
  download: 'bg-cyan-500/10 text-cyan-400',
  delete: 'bg-red-500/10 text-red-400',
  login_failed: 'bg-orange-500/10 text-orange-400',
  change_password: 'bg-yellow-500/10 text-yellow-400',
  payload_checkin: 'bg-rose-500/10 text-rose-400',
  data_exfil: 'bg-pink-500/10 text-pink-400',
};

function actionColor(action: string): string {
  return ACTION_COLORS[action] ?? 'bg-slate-800 text-slate-400';
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function AuditLogs() {
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-logs', page],
    queryFn: () => adminApi.logs(page, 50),
    refetchInterval: 15_000,
  });

  const logs: AuditLog[] = data?.data?.logs ?? [];
  const total = data?.data?.total ?? 0;
  const totalPages = data?.data?.pages ?? 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Audit Logs</h1>
        <p className="text-sm text-slate-500 mt-1">
          {total.toLocaleString()} event{total !== 1 ? 's' : ''} recorded · auto-refreshes every 15 s
        </p>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-slate-600" size={22} />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-20 text-center">
            <ScrollText size={32} className="text-slate-800 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No log entries yet</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="table-th">Timestamp</th>
                    <th className="table-th">Action</th>
                    <th className="table-th">User ID</th>
                    <th className="table-th">Target</th>
                    <th className="table-th">Details</th>
                    <th className="table-th">IP Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {logs.map((log) => (
                    <LogRow key={log.id} log={log} />
                  ))}
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

function LogRow({ log }: { log: AuditLog }) {
  return (
    <tr className="hover:bg-slate-800/30 transition-colors font-mono text-xs">
      <td className="table-td text-slate-500 whitespace-nowrap">
        {formatTimestamp(log.timestamp)}
      </td>
      <td className="table-td">
        <span className={clsx('badge', actionColor(log.action))}>{log.action}</span>
      </td>
      <td className="table-td text-slate-400">
        {log.user_id ?? <span className="text-slate-700">—</span>}
      </td>
      <td className="table-td text-slate-400 max-w-[160px] truncate">
        {log.target ?? <span className="text-slate-700">—</span>}
      </td>
      <td className="table-td text-slate-500 max-w-[200px] truncate">
        {log.details ?? <span className="text-slate-700">—</span>}
      </td>
      <td className="table-td text-slate-500 whitespace-nowrap">
        {log.ip_address ?? <span className="text-slate-700">—</span>}
      </td>
    </tr>
  );
}
