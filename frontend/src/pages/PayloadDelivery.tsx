import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';
import {
  Terminal,
  Copy,
  Check,
  Globe,
  Lock,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Zap,
} from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../api/files';
import apiAxios from '../api/client';
import type { FileItem } from '../types';

interface DeliveryCommand {
  technique: string;
  description: string;
  platform: string;
  cmd: string;
}

interface DeliveryData {
  file_id: number;
  filename: string;
  sha256: string;
  raw_url: string;
  is_public: boolean;
  warning: string | null;
  commands: DeliveryCommand[];
}

async function fetchDelivery(fileId: number): Promise<DeliveryData> {
  const res = await apiAxios.get(`/files/${fileId}/delivery`, {
    headers: { 'X-Base-URL': window.location.origin },
  });
  return res.data;
}

function CommandCard({ cmd }: { cmd: DeliveryCommand }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(cmd.cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isWindows = cmd.platform === 'Windows';
  const isLinux = cmd.platform.startsWith('Linux');

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-800 transition-colors"
        onClick={() => setExpanded((p) => !p)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <Terminal size={14} className="text-red-400 flex-shrink-0" />
          <span className="text-sm font-medium text-slate-200 truncate">{cmd.technique}</span>
          <span
            className={clsx(
              'text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider flex-shrink-0',
              isWindows
                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                : 'bg-green-500/15 text-green-400 border border-green-500/30'
            )}
          >
            {isWindows ? 'Win' : 'Linux'}
          </span>
        </div>
        <div className="flex items-center gap-2 ml-3">
          <button
            onClick={(e) => {
              e.stopPropagation();
              copy();
            }}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
          >
            {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          {expanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-slate-700 px-4 py-3 space-y-3">
          <p className="text-xs text-slate-400">{cmd.description}</p>
          <pre className="text-xs bg-slate-900 rounded-md p-3 overflow-x-auto text-green-300 font-mono leading-relaxed whitespace-pre-wrap break-all">
            {cmd.cmd}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function PayloadDelivery() {
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [loadDelivery, setLoadDelivery] = useState(false);

  const { data: filesResponse, isLoading: filesLoading } = useQuery({
    queryKey: ['files', 1],
    queryFn: () => filesApi.list(1, 100),
  });

  const { data: delivery, isLoading: deliveryLoading, error: deliveryError } = useQuery({
    queryKey: ['delivery', selectedFileId],
    queryFn: () => fetchDelivery(selectedFileId!),
    enabled: !!selectedFileId && loadDelivery,
  });

  const filesData = (filesResponse as AxiosResponse | undefined)?.data;
  const files: FileItem[] = filesData?.files ?? [];

  const handleGenerate = () => {
    if (selectedFileId) setLoadDelivery(true);
  };

  const selectedFile = files.find((f) => f.id === selectedFileId);

  return (
    <div className="min-h-full p-6 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Zap size={18} className="text-red-400" />
          <h1 className="text-xl font-semibold text-slate-100">Payload Delivery</h1>
        </div>
        <p className="text-sm text-slate-400">
          Generate HTTP-based payload delivery one-liners for Windows and Linux targets.
          Covers PowerShell WebClient, IEX, certutil, bitsadmin, mshta, and more.
        </p>
      </div>

      {/* Info banner */}
      <div className="rounded-lg border border-amber-600/30 bg-amber-600/10 px-4 py-3 flex gap-3">
        <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-amber-300">
          Raw delivery endpoints are <span className="font-semibold">only available for public files</span>.
          Mark a file as public before sharing its raw URL. Unauthenticated fetches are logged in the audit trail.
        </p>
      </div>

      {/* File selector */}
      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-200">Select File</h2>

        {filesLoading ? (
          <p className="text-sm text-slate-500">Loading files…</p>
        ) : files.length === 0 ? (
          <p className="text-sm text-slate-500">No files uploaded yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 max-h-64 overflow-y-auto pr-1">
            {files.map((f) => (
              <label
                key={f.id}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-all',
                  selectedFileId === f.id
                    ? 'border-red-600/50 bg-red-600/10'
                    : 'border-slate-700 bg-slate-800/40 hover:border-slate-600'
                )}
              >
                <input
                  type="radio"
                  name="file"
                  value={f.id}
                  checked={selectedFileId === f.id}
                  onChange={() => {
                    setSelectedFileId(f.id);
                    setLoadDelivery(false);
                  }}
                  className="accent-red-500"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 truncate font-mono">{f.filename}</p>
                  <p className="text-[10px] text-slate-500 font-mono truncate">{f.sha256?.slice(0, 16)}…</p>
                </div>
                {f.is_public ? (
                  <Globe size={13} className="text-green-400 flex-shrink-0" />
                ) : (
                  <Lock size={13} className="text-slate-500 flex-shrink-0" />
                )}
              </label>
            ))}
          </div>
        )}

        <button
          disabled={!selectedFileId}
          onClick={handleGenerate}
          className="mt-1 flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Terminal size={14} />
          Generate Delivery Commands
        </button>
      </div>

      {/* Results */}
      {loadDelivery && selectedFileId && (
        <div className="space-y-4">
          {deliveryLoading && (
            <p className="text-sm text-slate-400">Generating commands…</p>
          )}

          {deliveryError && (
            <div className="rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-3 text-sm text-red-400">
              Failed to generate commands.
            </div>
          )}

          {delivery && (
            <>
              {/* Meta */}
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-200">{delivery.filename}</h2>
                  {delivery.is_public ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 border border-green-500/30 text-green-400 font-semibold uppercase">Public</span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-600/40 border border-slate-600 text-slate-400 font-semibold uppercase">Private</span>
                  )}
                </div>
                <p className="text-xs text-slate-500 font-mono break-all">SHA256: {delivery.sha256}</p>
                <div className="flex items-center gap-2">
                  <p className="text-xs text-slate-500 font-mono break-all flex-1">Raw URL: {delivery.raw_url}</p>
                  <button
                    onClick={() => navigator.clipboard.writeText(delivery.raw_url)}
                    className="flex-shrink-0 p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    <Copy size={12} />
                  </button>
                </div>
                {delivery.warning && (
                  <div className="flex gap-2 items-start rounded-md border border-amber-600/30 bg-amber-600/10 px-3 py-2">
                    <AlertTriangle size={13} className="text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-300">{delivery.warning}</p>
                  </div>
                )}
              </div>

              {/* Commands */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
                  {delivery.commands.length} Delivery Techniques
                </h3>
                {delivery.commands.map((cmd, i) => (
                  <CommandCard key={i} cmd={cmd} />
                ))}
              </div>

              {/* Quick reference table */}
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 space-y-3">
                <h3 className="text-sm font-semibold text-slate-200">Quick Reference – Technique Overview</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-2 pr-4 text-slate-400 font-semibold">Technique</th>
                        <th className="text-left py-2 pr-4 text-slate-400 font-semibold">Platform</th>
                        <th className="text-left py-2 text-slate-400 font-semibold">Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {delivery.commands.map((cmd, i) => (
                        <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-2 pr-4 text-slate-300 font-medium">{cmd.technique.split('–')[0].trim()}</td>
                          <td className="py-2 pr-4">
                            <span className={clsx(
                              'text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider',
                              cmd.platform === 'Windows'
                                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                                : 'bg-green-500/15 text-green-400 border border-green-500/30'
                            )}>
                              {cmd.platform}
                            </span>
                          </td>
                          <td className="py-2 text-slate-500">{cmd.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
