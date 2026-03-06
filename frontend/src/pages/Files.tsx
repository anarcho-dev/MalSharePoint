import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Download,
  Trash2,
  Copy,
  Check,
  Globe,
  Lock,
  FileText,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../api/files';
import { useAuthStore } from '../store/authStore';
import type { FileItem } from '../types';

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

export default function Files() {
  const { user, isAdmin } = useAuthStore();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['files', page],
    queryFn: () => filesApi.list(page, 20),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => filesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['files'] }),
  });

  const copyHash = (id: number, hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDelete = (id: number) => {
    if (window.confirm('Permanently delete this file?')) {
      deleteMutation.mutate(id);
    }
  };

  const files = data?.data?.files ?? [];
  const total = data?.data?.total ?? 0;
  const totalPages = data?.data?.pages ?? 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Files</h1>
          <p className="text-sm text-slate-500 mt-1">
            {total.toLocaleString()} file{total !== 1 ? 's' : ''} in the repository
          </p>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center py-20">
            <Loader2 className="animate-spin text-slate-600" size={22} />
          </div>
        ) : files.length === 0 ? (
          <div className="py-20 text-center">
            <FileText size={32} className="text-slate-800 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No files found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="table-th">File</th>
                    <th className="table-th">SHA-256</th>
                    <th className="table-th">Size</th>
                    <th className="table-th">Visibility</th>
                    <th className="table-th">Date</th>
                    <th className="table-th text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {files.map((file) => (
                    <FileRow
                      key={file.id}
                      file={file}
                      currentUserId={user!.id}
                      isAdmin={isAdmin()}
                      copiedId={copiedId}
                      onCopy={copyHash}
                      onDelete={handleDelete}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
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

interface FileRowProps {
  file: FileItem;
  currentUserId: number;
  isAdmin: boolean;
  copiedId: number | null;
  onCopy: (id: number, hash: string) => void;
  onDelete: (id: number) => void;
}

function FileRow({ file, currentUserId, isAdmin, copiedId, onCopy, onDelete }: FileRowProps) {
  const canDelete = isAdmin || file.uploaded_by === currentUserId;
  const token = localStorage.getItem('access_token');
  const downloadUrl = filesApi.getDownloadUrl(file.id);

  const handleDownload = () => {
    const a = document.createElement('a');
    a.href = downloadUrl;
    // Attach token via a temporary anchor — server validates from header
    // For a proper download with header auth, use fetch + blob:
    fetch(downloadUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        a.href = url;
        a.download = file.filename;
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  return (
    <tr className="hover:bg-slate-800/30 transition-colors">
      <td className="table-td">
        <p className="font-medium text-slate-200 max-w-[200px] truncate">{file.filename}</p>
        {file.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {file.tags.map((t) => (
              <span key={t} className="badge bg-slate-800 text-slate-400">
                {t.trim()}
              </span>
            ))}
          </div>
        )}
      </td>

      <td className="table-td">
        <div className="flex items-center gap-1.5">
          <code className="text-[11px] text-slate-400 font-mono">
            {file.sha256.slice(0, 14)}…
          </code>
          <button
            onClick={() => onCopy(file.id, file.sha256)}
            className="text-slate-700 hover:text-slate-400 transition-colors"
            title="Copy full SHA-256"
          >
            {copiedId === file.id ? (
              <Check size={11} className="text-emerald-400" />
            ) : (
              <Copy size={11} />
            )}
          </button>
        </div>
      </td>

      <td className="table-td text-slate-400 text-xs tabular-nums whitespace-nowrap">
        {formatBytes(file.size)}
      </td>

      <td className="table-td">
        {file.is_public ? (
          <span className="badge bg-emerald-500/10 text-emerald-400">
            <Globe size={10} />
            public
          </span>
        ) : (
          <span className="badge bg-slate-800 text-slate-500">
            <Lock size={10} />
            private
          </span>
        )}
      </td>

      <td className="table-td text-slate-500 text-xs whitespace-nowrap">
        {formatDate(file.upload_date)}
      </td>

      <td className="table-td">
        <div
          className={clsx(
            'flex items-center gap-1 justify-end',
            canDelete ? 'justify-end' : 'justify-end'
          )}
        >
          <button
            onClick={handleDownload}
            className="p-1.5 rounded text-slate-500 hover:text-emerald-400 hover:bg-emerald-400/10 transition-colors"
            title="Download"
          >
            <Download size={14} />
          </button>
          {canDelete && (
            <button
              onClick={() => onDelete(file.id)}
              className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
              title="Delete"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
