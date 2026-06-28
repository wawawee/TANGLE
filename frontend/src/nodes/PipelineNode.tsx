import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';
import { useAgentStore } from '../store/agentStore';

export interface PipelineNodeData extends Record<string, unknown> {
  agentId: string;
  label: string;
  step: 'planner' | 'scout' | 'librarian' | 'critic' | 'synthesizer';
}

const PIPELINE_META: Record<string, { icon: string; color: string; label: string }> = {
  planner:     { icon: '🧠', color: '#c084fc', label: 'Planner' },
  scout:       { icon: '🔍', color: '#06b6d4', label: 'Scout' },
  librarian:   { icon: '📚', color: '#10b981', label: 'Librarian' },
  critic:      { icon: '⚖️', color: '#f59e0b', label: 'Critic' },
  synthesizer: { icon: '✨', color: '#ec4899', label: 'Synthesizer' },
};

const STATUS_STYLE: Record<string, { bg: string; border: string; dot: string }> = {
  idle:      { bg: 'rgba(10,10,18,0.85)', border: 'rgba(255,255,255,0.08)', dot: 'rgba(255,255,255,0.2)' },
  thinking:  { bg: 'rgba(250,204,21,0.06)', border: 'rgba(250,204,21,0.25)', dot: '#facc15' },
  executing: { bg: 'rgba(6,182,212,0.06)', border: 'rgba(6,182,212,0.25)', dot: '#06b6d4' },
  done:      { bg: 'rgba(16,185,129,0.06)', border: 'rgba(16,185,129,0.25)', dot: '#10b981' },
  error:     { bg: 'rgba(239,68,68,0.06)', border: 'rgba(239,68,68,0.25)', dot: '#ef4444' },
};

const PipelineNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as PipelineNodeData;
  const [expanded, setExpanded] = useState(false);
  const status = useAgentStore(s => s.agentStatuses[nodeData.agentId] || 'idle');
  const logs = useAgentStore(s => s.verboseLogs[nodeData.agentId] || []);
  const style = STATUS_STYLE[status] || STATUS_STYLE.idle;
  const meta = PIPELINE_META[nodeData.step] || { icon: '⚙️', color: '#fff', label: nodeData.step };
  const isActive = status === 'thinking' || status === 'executing';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        position: 'relative',
        width: expanded ? 280 : 150,
        borderRadius: 12,
        background: style.bg,
        backdropFilter: 'blur(12px)',
        border: `1px solid ${style.border}`,
        boxShadow: isActive
          ? `0 0 20px ${meta.color}22, 0 4px 16px rgba(0,0,0,0.35)`
          : '0 2px 12px rgba(0,0,0,0.3)',
        cursor: 'pointer',
        transition: 'all 0.3s',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: meta.color, width: 8, height: 8, left: -5, border: `2px solid ${meta.color}` }} />
      <Handle type="source" position={Position.Right} style={{ background: meta.color, width: 8, height: 8, right: -5, border: `2px solid ${meta.color}` }} />

      {/* Top color bar */}
      <div style={{
        height: 3,
        borderRadius: '12px 12px 0 0',
        background: `linear-gradient(90deg, ${meta.color}, ${meta.color}44, transparent)`,
        opacity: isActive ? 1 : 0.3,
        transition: 'opacity 0.3s',
      }} />

      <div style={{ padding: '10px 12px' }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 20 }}>{meta.icon}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: meta.color,
            }}>
              {meta.label}
            </div>
          </div>
          {/* Status dot */}
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: style.dot,
            boxShadow: isActive ? `0 0 8px ${style.dot}` : 'none',
            transition: 'all 0.3s',
          }} />
        </div>

        {/* Status bar */}
        <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden', marginBottom: 4 }}>
          <div style={{
            height: '100%', borderRadius: 1,
            background: meta.color,
            width: status === 'done' ? '100%' : status === 'executing' ? '100%' : status === 'thinking' ? '50%' : '0%',
            transition: 'width 0.5s',
            animation: isActive ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
          }} />
        </div>

        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono, monospace' }}>
          {status.toUpperCase()}
        </div>

        {/* Expanded output */}
        {expanded && (
          <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
            <div style={{
              fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.15em', color: 'rgba(255,255,255,0.2)',
              marginBottom: 6,
            }}>
              Output
            </div>
            {logs.length === 0 ? (
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', fontStyle: 'italic' }}>
                Waiting for events…
              </div>
            ) : (
              <div style={{
                fontSize: 9, fontFamily: 'JetBrains Mono, monospace',
                color: 'rgba(255,255,255,0.4)', lineHeight: 1.5,
                maxHeight: 160, overflowY: 'auto',
                background: 'rgba(255,255,255,0.02)',
                padding: 8, borderRadius: 8,
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {logs.slice(-8).map((log, i) => (
                  <div key={i} style={{ marginBottom: 2, borderBottom: i < Math.min(logs.length, 8) - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none', paddingBottom: 2 }}>
                    {log}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

PipelineNode.displayName = 'PipelineNode';
export default PipelineNode;
