import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';
import type { AgentStatus } from '../store/agentStore';
import { useAgentStore } from '../store/agentStore';

const STATUS_CFG: Record<AgentStatus, { color: string; label: string }> = {
  idle:      { color: 'rgba(255,255,255,0.15)', label: 'IDLE' },
  thinking:  { color: '#f59e0b',                 label: 'THINKING' },
  executing: { color: '#06b6d4',                 label: 'EXECUTING' },
  error:     { color: '#ef4444',                 label: 'ERROR' },
  done:      { color: '#10b981',                 label: 'DONE' },
};

const AGENT_COLORS: Record<string, string> = {
  '01': '#06b6d4', '02': '#8b5cf6', '03': '#f59e0b',
  '04': '#10b981', '05': '#ef4444', '06': '#3b82f6',
  '07': '#f97316', '08': '#ec4899', '09': '#a3e635',
  '10': '#f43f5e', '11': '#facc15', '12': '#22d3ee',
  '13': '#c084fc', '14': '#fb923c', '15': '#34d399', '16': '#e879f9',
};

const AGENT_EMOJIS: Record<string, string> = {
  '01': '🔬', '02': '🏗️', '03': '✍️', '04': '🧪',
  '05': '🛡️', '06': '🗄️', '07': '🚀', '08': '🎨',
  '09': '📝', '10': '🔍', '11': '⚡', '12': '🔗',
  '13': '🎼', '14': '📦', '15': '🔎', '16': '🖥️',
};

export interface AgentNodeData {
  agentId: string; name: string; codename: string; role: string; collection: string;
  skills?: string[]; identity?: string; soul?: string; skillsContent?: string;
}

type Tab = 'overview' | 'identity' | 'soul' | 'skills';

const AgentNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as AgentNodeData;
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const status = useAgentStore(s => s.agentStatuses[nodeData.agentId] || 'idle');
  const verboseLogs = useAgentStore(s => s.verboseLogs[nodeData.agentId] || []);
  const { label } = STATUS_CFG[status];
  const accent = AGENT_COLORS[nodeData.agentId] || '#06b6d4';
  const emoji = AGENT_EMOJIS[nodeData.agentId] || '🤖';
  const isActive = status !== 'idle';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        position: 'relative',
        width: expanded ? 288 : 208,
        borderRadius: 16,
        background: 'rgba(10,10,18,0.85)',
        backdropFilter: 'blur(12px)',
        border: `1px solid ${isActive ? `${accent}44` : 'rgba(255,255,255,0.06)'}`,
        boxShadow: isActive ? `0 0 24px ${accent}22, 0 4px 24px rgba(0,0,0,0.4)` : `0 4px 24px rgba(0,0,0,0.4)`,
        cursor: 'pointer',
        transition: 'all 0.3s',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: accent, width: 8, height: 8, border: `2px solid ${accent}`, left: -5 }} />
      <Handle type="source" position={Position.Right} style={{ background: accent, width: 8, height: 8, border: `2px solid ${accent}`, right: -5 }} />
      <Handle type="target" position={Position.Top} style={{ background: accent, width: 6, height: 6, top: -4 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: accent, width: 6, height: 6, bottom: -4 }} />

      <div style={{ height: 4, borderRadius: '16px 16px 0 0', background: `linear-gradient(90deg, ${accent}, ${accent}44)` }} />

      <div style={{ padding: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18 }}>{emoji}</span>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: accent }}>
                [{nodeData.agentId}] {nodeData.codename}
              </div>
              <div style={{ color: '#fff', fontWeight: 600, fontSize: 14, lineHeight: 1.2 }}>{nodeData.name}</div>
            </div>
          </div>
          <div style={{
            padding: '2px 8px',
            borderRadius: 999,
            fontSize: 9,
            fontWeight: 700,
            border: `1px solid ${isActive ? accent : 'rgba(255,255,255,0.13)'}`,
            color: isActive ? accent : 'rgba(255,255,255,0.27)',
            background: `${accent}15`,
          }}>
            {label}
          </div>
        </div>

        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>{nodeData.role}</div>

        <div style={{ height: 2, width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
          <div style={{
            height: '100%',
            borderRadius: 4,
            width: status === 'executing' ? '100%' : status === 'thinking' ? '60%' : status === 'done' ? '100%' : '20%',
            background: `linear-gradient(90deg, ${accent}, ${accent}88)`,
            transition: 'width 0.5s',
          }} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b980' }} />
          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'monospace' }}>{nodeData.collection}</span>
        </div>

        {verboseLogs.length > 0 && !expanded && (
          <div style={{ marginTop: 4, fontSize: 9, color: accent, fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {verboseLogs[verboseLogs.length - 1].slice(0, 60)}
          </div>
        )}

        {expanded && (
          <div style={{ marginTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 12 }}>
            <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
              {(['overview', 'identity', 'soul', 'skills'] as Tab[]).map(tab => (
                <button
                  key={tab}
                  onClick={(e) => { e.stopPropagation(); setActiveTab(tab); }}
                  style={{
                    fontSize: 9,
                    padding: '2px 8px',
                    borderRadius: 8,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    border: 'none',
                    cursor: 'pointer',
                    color: activeTab === tab ? '#fff' : 'rgba(255,255,255,0.3)',
                    background: activeTab === tab ? `${accent}33` : 'transparent',
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, maxHeight: 128, overflowY: 'auto' }}>
              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div><span style={{ color: 'rgba(255,255,255,0.3)' }}>Role:</span> <span style={{ color: 'rgba(255,255,255,0.7)' }}>{nodeData.role}</span></div>
                  <div><span style={{ color: 'rgba(255,255,255,0.3)' }}>Collection:</span> <span style={{ color: accent }}>{nodeData.collection}</span></div>
                  <div><span style={{ color: 'rgba(255,255,255,0.3)' }}>Status:</span> <span style={{ color: accent }}>{label}</span></div>
                </div>
              )}
              {activeTab === 'identity' && <div style={{ whiteSpace: 'pre-wrap' }}>{nodeData.identity || `IDENTITY.md\n\nCodename: ${nodeData.codename}\nVersion: 1.0.0\nRole: ${nodeData.role}\nStatus: ACTIVE`}</div>}
              {activeTab === 'soul' && <div style={{ whiteSpace: 'pre-wrap' }}>{nodeData.soul || `SOUL.md\n\nValues:\n• Excellence in every output\n• Transparency in decisions\n• Human-in-the-loop for critical actions`}</div>}
              {activeTab === 'skills' && <div style={{ whiteSpace: 'pre-wrap' }}>{nodeData.skillsContent || `SKILLS.md\n\nCore capabilities:\n• Qdrant vector search\n• LLM chain-of-thought\n• Structured output formatting\n• Inter-agent handoff protocol`}</div>}
            </div>

            {verboseLogs.length > 0 && (
              <div style={{ marginTop: 8, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 8 }}>
                <div style={{ fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'rgba(255,255,255,0.25)', marginBottom: 4 }}>Activity Log</div>
                {verboseLogs.slice(-6).map((log, i) => (
                  <div key={i} style={{ fontSize: 8, fontFamily: 'monospace', color: 'rgba(255,255,255,0.35)', lineHeight: 1.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
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

AgentNode.displayName = 'AgentNode';
export default AgentNode;
