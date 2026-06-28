import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';
import { useAgentStore } from '../store/agentStore';

const OrchestratorNode = memo((_: NodeProps) => {
  const { agentStatuses, activeFlow, telemetryLog } = useAgentStore();
  const [expanded, setExpanded] = useState(false);
  const activeCount = Object.values(agentStatuses).filter(s => s !== 'idle' && s !== 'done').length;
  const isActive = activeFlow !== 'none';

  const flowLabels: Record<string, string> = {
    research_to_code: '🔬 Research → Code Pipeline',
    security_sweep: '🛡️ Security Sweep',
    devops_deploy: '📦 DevOps Deploy',
    examination_eval: '🔎 Full Examination',
    system_guardian: '🖥️ System Guardian Sweep',
    none: '— STANDBY —',
  };

  return (
    <div
      className="relative cursor-pointer"
      style={{ width: expanded ? 300 : 220 }}
      onClick={() => setExpanded(!expanded)}
    >
      <Handle type="source" position={Position.Right} style={{ background: '#c084fc', width: 10, height: 10, right: -6, border: '2px solid #c084fc' }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#c084fc', width: 10, height: 10, bottom: -6 }} />
      <Handle type="source" position={Position.Left} style={{ background: '#c084fc', width: 10, height: 10, left: -6 }} />
      <Handle type="source" position={Position.Top} style={{ background: '#c084fc', width: 10, height: 10, top: -6 }} />
      <Handle type="target" position={Position.Left} id="target-left" style={{ background: '#c084fc', width: 8, height: 8, left: -5, top: '70%' }} />
      <Handle type="target" position={Position.Bottom} id="target-bottom" style={{ background: '#c084fc', width: 8, height: 8, bottom: -5 }} />

      <div
        className="rounded-3xl border transition-all duration-500"
        style={{
          background: 'radial-gradient(ellipse at center, rgba(192,132,252,0.15) 0%, rgba(10,10,18,0.95) 100%)',
          borderColor: isActive ? 'rgba(192,132,252,0.8)' : 'rgba(192,132,252,0.3)',
          boxShadow: isActive
            ? '0 0 40px rgba(192,132,252,0.4), 0 0 80px rgba(192,132,252,0.1), inset 0 0 40px rgba(192,132,252,0.05)'
            : '0 0 20px rgba(192,132,252,0.15)',
        }}
      >
        {/* Top glow bar */}
        <div className="h-1.5 rounded-t-3xl" style={{
          background: 'linear-gradient(90deg, transparent, #c084fc, #8b5cf6, transparent)',
          opacity: isActive ? 1 : 0.4,
        }} />

        <div className="p-4">
          {/* Identity */}
          <div className="flex items-center gap-3 mb-3">
            <div className="text-3xl">{isActive ? '🧠' : '🎼'}</div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-purple-300/70">AGENT-13 · MAESTRO</div>
              <div className="text-lg font-bold text-white">Orchestrator</div>
            </div>
            {isActive && (
              <div className="ml-auto">
                <div className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
              </div>
            )}
          </div>

          {/* Active flow */}
          <div className="mb-3 p-2 rounded-xl" style={{ background: 'rgba(192,132,252,0.08)', border: '1px solid rgba(192,132,252,0.15)' }}>
            <div className="text-[9px] text-purple-400/60 uppercase tracking-widest mb-0.5">Active Flow</div>
            <div className="text-[11px] font-semibold text-white/80">{flowLabels[activeFlow]}</div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            {[
              { label: 'Active', value: activeCount, color: '#c084fc' },
              { label: 'Events', value: telemetryLog.length, color: '#06b6d4' },
              { label: 'Agents', value: 16, color: '#10b981' },
            ].map(stat => (
              <div key={stat.label} className="text-center p-2 rounded-lg" style={{ background: `${stat.color}10`, border: `1px solid ${stat.color}20` }}>
                <div className="text-base font-bold" style={{ color: stat.color }}>{stat.value}</div>
                <div className="text-[8px] text-white/30 uppercase">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Qdrant collection */}
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-[9px] text-white/30 font-mono">orchestrator_memories</span>
          </div>

          {/* Expanded: last 5 telemetry */}
          {expanded && (
            <div className="mt-3 border-t border-white/5 pt-3">
              <div className="text-[9px] text-purple-300/50 uppercase tracking-widest mb-2">Recent Telemetry</div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {telemetryLog.slice(0, 8).map(evt => (
                  <div key={evt.id} className="text-[9px] font-mono text-white/40 flex gap-2">
                    <span className="text-purple-400/50">{evt.timestamp}</span>
                    <span className={evt.status === 'warn' ? 'text-amber-400' : 'text-white/40'}>{evt.label}</span>
                  </div>
                ))}
                {telemetryLog.length === 0 && <div className="text-[9px] text-white/20">No events yet — run a flow</div>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

OrchestratorNode.displayName = 'OrchestratorNode';
export default OrchestratorNode;
