import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';
import { useAgentStore } from '../store/agentStore';

const OrchestratorNode = memo((_: NodeProps) => {
  const { agentStatuses, activeFlow, telemetryLog } = useAgentStore();
  const [expanded, setExpanded] = useState(false);
  const activeCount = Object.values(agentStatuses).filter(s => s !== 'idle' && s !== 'done').length;
  const isActive = activeFlow !== 'none';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        position: 'relative',
        width: expanded ? 220 : 150,
        borderRadius: 12,
        background: isActive
          ? 'rgba(192,132,252,0.08)'
          : 'rgba(10,10,18,0.85)',
        backdropFilter: 'blur(12px)',
        border: `1px solid ${isActive ? 'rgba(192,132,252,0.4)' : 'rgba(192,132,252,0.15)'}`,
        boxShadow: isActive
          ? '0 0 20px rgba(192,132,252,0.25), 0 4px 16px rgba(0,0,0,0.35)'
          : '0 2px 12px rgba(0,0,0,0.3)',
        cursor: 'pointer',
        transition: 'all 0.3s',
      }}
    >
      {/* Single target handle on the left — only edge that hits this is synthesizer → orchestrator */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#c084fc', width: 8, height: 8, left: -5, border: '2px solid #c084fc' }}
      />

      {/* Top accent bar */}
      <div style={{
        height: 3,
        borderRadius: '12px 12px 0 0',
        background: 'linear-gradient(90deg, #c084fc, #8b5cf6, transparent)',
        opacity: isActive ? 1 : 0.3,
        transition: 'opacity 0.3s',
      }} />

      <div style={{ padding: '10px 12px' }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{isActive ? '🧠' : '🎼'}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: 'rgba(192,132,252,0.7)',
            }}>
              Maestro
            </div>
            <div style={{
              fontSize: 13, fontWeight: 700, color: '#fff', lineHeight: 1.1,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              Orchestrator
            </div>
          </div>
          {/* Status dot */}
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: isActive ? '#c084fc' : 'rgba(255,255,255,0.2)',
            boxShadow: isActive ? '0 0 8px #c084fc' : 'none',
            transition: 'all 0.3s',
            flexShrink: 0,
          }} />
        </div>

        {/* Compact status row */}
        <div style={{
          marginTop: 8,
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 9, color: 'rgba(255,255,255,0.35)',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          <span>{isActive ? 'ACTIVE' : 'STANDBY'}</span>
          <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>
          <span style={{ color: isActive ? '#c084fc' : 'rgba(255,255,255,0.3)' }}>
            {activeCount} / 16
          </span>
        </div>

        {/* Expanded: recent telemetry */}
        {expanded && (
          <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
            <div style={{
              fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.15em', color: 'rgba(192,132,252,0.5)',
              marginBottom: 6,
            }}>
              Telemetry
            </div>
            <div style={{
              fontSize: 9, fontFamily: 'JetBrains Mono, monospace',
              color: 'rgba(255,255,255,0.4)', lineHeight: 1.5,
              maxHeight: 140, overflowY: 'auto',
            }}>
              {telemetryLog.length === 0 ? (
                <div style={{ color: 'rgba(255,255,255,0.2)', fontStyle: 'italic' }}>
                  No events yet
                </div>
              ) : (
                telemetryLog.slice(0, 8).map(evt => (
                  <div key={evt.id} style={{ marginBottom: 2, display: 'flex', gap: 6 }}>
                    <span style={{ color: 'rgba(192,132,252,0.5)' }}>{evt.timestamp}</span>
                    <span className={evt.status === 'warn' ? 'text-amber-400' : ''}>{evt.label}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

OrchestratorNode.displayName = 'OrchestratorNode';
export default OrchestratorNode;