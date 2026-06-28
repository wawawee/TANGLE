import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import axios from 'axios';
import React, { memo, useCallback, useEffect, useState } from 'react';
import type { ProcessInfo, SystemMetrics } from '../store/agentStore';
import { useAgentStore } from '../store/agentStore';

const SystemGuardianNode = memo((_: NodeProps) => {
  const { systemMetrics, setSystemMetrics, addTelemetryEvent, agentStatuses } = useAgentStore();
  const [expanded, setExpanded] = useState(false);
  const [killTarget, setKillTarget] = useState<number | null>(null);
  const [killing, setKilling] = useState(false);
  const status = agentStatuses['16'] || 'idle';
  const isActive = status !== 'idle';

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await axios.get<SystemMetrics>('http://localhost:8000/api/system/metrics');
      setSystemMetrics(res.data);
    } catch {
      // Backend offline — use mock data
      setSystemMetrics({
        cpu_percent: Math.random() * 40 + 10,
        total_ram_mb: 16384,
        free_ram_mb: Math.random() * 4000 + 2000,
        used_ram_pct: Math.random() * 50 + 30,
        disk_total_gb: 512,
        disk_free_gb: 234,
        disk_used_pct: 54,
        platform: 'macOS 14.x',
        processes: generateMockProcesses(),
        alerts: [],
        timestamp: new Date().toISOString(),
      } as any);
    }
  }, [setSystemMetrics]);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  const handleKill = async (pid: number, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setKilling(true);
    setKillTarget(pid);
    addTelemetryEvent({
      from: '16', to: '13', type: 'kill_action',
      label: `🔴 KILL REQUEST: PID ${pid} (${name}) — awaiting approval`,
      latency: 0, status: 'warn',
    });
    try {
      await axios.post('http://localhost:8000/api/system/kill', {
        pid, signal_type: 'SIGTERM', reason: 'User initiated via WATCHDOG panel'
      });
      addTelemetryEvent({
        from: '16', to: '16', type: 'kill_action',
        label: `✅ KILLED: PID ${pid} (${name}) — process terminated`,
        latency: 5000, status: 'ok',
      });
      await fetchMetrics();
    } catch (err: any) {
      addTelemetryEvent({
        from: '16', to: '16', type: 'kill_action',
        label: `❌ KILL FAILED: PID ${pid} — ${err?.response?.data?.detail || 'access denied'}`,
        latency: 0, status: 'error',
      });
    } finally {
      setKilling(false);
      setKillTarget(null);
    }
  };

  const m = systemMetrics as any;
  const cpuPct = m?.cpu_percent ?? 0;
  const ramPct = m?.used_ram_pct ?? 0;
  const freeRamGb = m ? (m.free_ram_mb / 1024).toFixed(1) : '?';
  const processes: ProcessInfo[] = m?.processes || [];
  const alerts = m?.alerts || [];

  return (
    <div
      className="relative cursor-pointer transition-all duration-500"
      style={{ width: expanded ? 340 : 220 }}
      onClick={() => setExpanded(!expanded)}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#e879f9', width: 8, height: 8, left: -5 }} />
      <Handle type="source" position={Position.Right} style={{ background: '#e879f9', width: 8, height: 8, right: -5 }} />
      <Handle type="target" position={Position.Top} style={{ background: '#e879f9', width: 6, height: 6, top: -4 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#e879f9', width: 6, height: 6, bottom: -4 }} />

      <div
        className="rounded-2xl border transition-all duration-500"
        style={{
          background: 'rgba(10,10,18,0.9)',
          borderColor: alerts.length > 0 ? 'rgba(239,68,68,0.7)' : isActive ? 'rgba(232,121,249,0.7)' : 'rgba(232,121,249,0.25)',
          boxShadow: alerts.length > 0
            ? '0 0 20px rgba(239,68,68,0.3)'
            : isActive ? '0 0 20px rgba(232,121,249,0.25)' : 'none',
        }}
      >
        <div className="h-1 rounded-t-2xl" style={{ background: 'linear-gradient(90deg, #e879f9, #a855f7, #e879f9)' }} />

        <div className="p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">🖥️</span>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color: '#e879f9' }}>[16] WATCHDOG</div>
                <div className="text-white font-semibold text-sm">System Guardian</div>
              </div>
            </div>
            {alerts.length > 0 && (
              <div className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-red-500/20 text-red-400 border border-red-500/40">
                {alerts.length} ALERT{alerts.length !== 1 ? 'S' : ''}
              </div>
            )}
          </div>

          {/* Mini gauges */}
          <div className="space-y-1.5 mb-2">
            <GaugeBar label="CPU" value={cpuPct} max={100} color={cpuPct > 80 ? '#ef4444' : cpuPct > 60 ? '#f59e0b' : '#e879f9'} />
            <GaugeBar label="RAM" value={ramPct} max={100} color={ramPct > 80 ? '#ef4444' : ramPct > 60 ? '#f59e0b' : '#22d3ee'} unit="%" />
            <div className="flex justify-between text-[9px] text-white/30">
              <span>Free RAM: {freeRamGb} GB</span>
              <span>{m?.platform?.split(' ')?.[0] || 'macOS'}</span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[9px] text-white/30 font-mono">Polling every 5s</span>
          </div>

          {/* Expanded process table */}
          {expanded && (
            <div className="mt-3 border-t border-white/5 pt-3" onClick={e => e.stopPropagation()}>
              {alerts.length > 0 && (
                <div className="mb-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="text-[9px] text-red-400 font-bold uppercase mb-1">⚠️ Active Alerts</div>
                  {alerts.slice(0, 3).map((a: any, i: number) => (
                    <div key={i} className={`text-[9px] ${a.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}`}>
                      PID {a.pid} {a.name}: {a.reason}
                    </div>
                  ))}
                </div>
              )}
              <div className="text-[9px] text-white/30 uppercase tracking-widest mb-1.5">Top Processes</div>
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {processes.slice(0, 12).map((proc: any) => (
                  <div
                    key={proc.pid}
                    className="flex items-center justify-between p-1.5 rounded-lg transition-all duration-200"
                    style={{
                      background: proc.cpu > 80 ? 'rgba(239,68,68,0.1)' : proc.cpu > 40 ? 'rgba(245,158,11,0.08)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${proc.cpu > 80 ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.05)'}`,
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] text-white/70 font-mono truncate max-w-[140px]">{proc.name}</div>
                      <div className="text-[8px] text-white/30">PID {proc.pid}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-right">
                        <div className={`text-[9px] font-bold ${proc.cpu > 80 ? 'text-red-400' : proc.cpu > 40 ? 'text-amber-400' : 'text-white/50'}`}>
                          {proc.cpu.toFixed(1)}%
                        </div>
                        <div className="text-[8px] text-white/30">{proc.memory_mb?.toFixed(0) || '?'}MB</div>
                      </div>
                      <button
                        onClick={(e) => handleKill(proc.pid, proc.name, e)}
                        disabled={killing && killTarget === proc.pid}
                        className="px-1.5 py-0.5 rounded text-[8px] font-bold text-red-400/70 hover:text-red-400 hover:bg-red-500/20 transition-all border border-red-500/10 hover:border-red-500/40"
                      >
                        {killing && killTarget === proc.pid ? '...' : 'KILL'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); fetchMetrics(); }}
                className="mt-2 w-full text-[9px] py-1 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/5 transition-all border border-white/5"
              >
                🔄 Refresh
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

const GaugeBar = ({ label, value, max, color, unit = '%' }: { label: string; value: number; max: number; color: string; unit?: string }) => (
  <div>
    <div className="flex justify-between text-[9px] text-white/40 mb-0.5">
      <span>{label}</span>
      <span style={{ color }}>{value.toFixed(1)}{unit}</span>
    </div>
    <div className="h-1 rounded-full bg-white/5 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min((value / max) * 100, 100)}%`, background: color }}
      />
    </div>
  </div>
);

function generateMockProcesses(): ProcessInfo[] {
  const names = ['node', 'python3', 'Chrome', 'Finder', 'Spotlight', 'Safari', 'Docker', 'code', 'Terminal', 'Slack', 'postgres', 'redis-server', 'uvicorn', 'webpack'];
  return names.map((name, i) => ({
    pid: 1000 + i * 137,
    name,
    cpu: Math.random() * 60,
    memory: Math.random() * 500,
    memory_mb: Math.random() * 500,
    user: 'perbrinell',
    status: 'running',
    rss: Math.random() * 500000000,
    vsz: Math.random() * 1000000000,
    started: '01:00:00',
  }));
}

SystemGuardianNode.displayName = 'SystemGuardianNode';
export default SystemGuardianNode;
