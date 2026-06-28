import { useCallback, useRef, useEffect, useState } from 'react';
import { useAgentStore } from '../store/agentStore';

const AGENT_COLORS: Record<string, string> = {
  '01': '#06b6d4', '02': '#8b5cf6', '03': '#f59e0b',
  '04': '#10b981', '05': '#ef4444', '06': '#3b82f6',
  '07': '#f97316', '08': '#ec4899', '09': '#a3e635',
  '10': '#f43f5e', '11': '#facc15', '12': '#22d3ee',
  '13': '#c084fc', '14': '#fb923c', '15': '#34d399', '16': '#e879f9',
};

const EVENT_ICONS: Record<string, string> = {
  agent_start: '▶️', agent_think: '💭', agent_complete: '✅', agent_error: '❌',
  tool_call: '🔧', tool_result: '📦', delegate: '🔀', workflow_step: '📋',
};

export default function AgentVerbosePanel() {
  const { verboseLogs, gatewayStatus, wsConnected, executeAgent } = useAgentStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [taskInput, setTaskInput] = useState('');
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const logEntries = Object.entries(verboseLogs);
  const totalEvents = logEntries.reduce((a, [, v]) => a + v.length, 0);

  useEffect(() => {
    if (autoScroll && scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [totalEvents, autoScroll]);

  const toggleAgent = useCallback((aid: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev);
      if (next.has(aid)) next.delete(aid); else next.add(aid);
      return next;
    });
  }, []);

  const handleExecute = useCallback(() => {
    if (!taskInput.trim() || !selectedAgent) return;
    executeAgent(`agent-${selectedAgent}`, taskInput);
    setTaskInput('');
  }, [taskInput, selectedAgent, executeAgent]);

  const currentLogs = selectedAgent
    ? verboseLogs[`agent-${selectedAgent}`] || []
    : null;

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: 8 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, padding: '4px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12 }}>📊</span>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text)' }}>
            Agent Telemetry
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>
            {totalEvents} events
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%',
            background: wsConnected ? '#10b981' : '#ef4444',
            boxShadow: wsConnected ? '0 0 6px #10b98188' : 'none',
          }} />
          <span style={{ fontSize: 8, color: wsConnected ? '#10b981' : '#ef4444', fontWeight: 700 }}>
            {wsConnected ? 'WS' : 'OFF'}
          </span>
          <div style={{ width: 6, height: 6, borderRadius: '50%',
            background: gatewayStatus.openrouter ? '#10b981' : 'rgba(255,255,255,0.2)',
          }} />
          <span style={{ fontSize: 8, color: gatewayStatus.openrouter ? '#10b981' : 'var(--text-muted)', fontWeight: 700 }}>OR</span>
          <div style={{ width: 6, height: 6, borderRadius: '50%',
            background: gatewayStatus.gemini ? '#10b981' : 'rgba(255,255,255,0.2)',
          }} />
          <span style={{ fontSize: 8, color: gatewayStatus.gemini ? '#10b981' : 'var(--text-muted)', fontWeight: 700 }}>GM</span>
          <label style={{ fontSize: 8, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} style={{ accentColor: '#06b6d4' }} />
            auto
          </label>
        </div>
      </div>

      {/* Agent selector bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        <button
          onClick={() => setSelectedAgent(null)}
          style={{
            fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 8,
            border: selectedAgent === null ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent',
            background: selectedAgent === null ? 'rgba(255,255,255,0.08)' : 'transparent',
            color: selectedAgent === null ? '#fff' : 'var(--text-muted)', cursor: 'pointer',
          }}
        >ALL</button>
        {logEntries.map(([aid]) => {
          const shortId = aid.replace('agent-', '');
          const color = AGENT_COLORS[shortId] || '#06b6d4';
          return (
            <button
              key={aid}
              onClick={() => setSelectedAgent(shortId)}
              style={{
                fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 8,
                border: selectedAgent === shortId ? `1px solid ${color}44` : '1px solid transparent',
                background: selectedAgent === shortId ? `${color}15` : 'transparent',
                color: selectedAgent === shortId ? color : 'var(--text-muted)', cursor: 'pointer',
              }}
            >{aid.replace('agent-', '')}</button>
          );
        })}
      </div>

      {/* Log list or agent detail */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', marginBottom: 8 }}>
        {selectedAgent ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {(currentLogs || []).length === 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: 16, textAlign: 'center' }}>
                No events yet for agent {selectedAgent}
              </div>
            )}
            {(currentLogs || []).slice(-100).map((line, i) => (
              <div key={i} style={{ fontSize: 9, fontFamily: 'monospace', color: 'var(--text-dim)', lineHeight: 1.6, padding: '1px 8px',
                background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
              }}>
                {line}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {logEntries.length === 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: 16, textAlign: 'center' }}>
                No agent activity yet. Run a flow or click execute below.
              </div>
            )}
            {logEntries.map(([aid, logs]) => {
              const shortId = aid.replace('agent-', '');
              const color = AGENT_COLORS[shortId] || '#06b6d4';
              const expanded = expandedAgents.has(aid);
              const latest = logs[logs.length - 1] || '';
              return (
                <div key={aid} style={{ border: '1px solid rgba(255,255,255,0.04)', borderRadius: 8, overflow: 'hidden' }}>
                  <div
                    onClick={() => toggleAgent(aid)}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', cursor: 'pointer',
                      background: 'rgba(255,255,255,0.02)', userSelect: 'none',
                    }}
                  >
                    <span style={{ fontSize: 11, fontWeight: 700, color }}>{shortId}</span>
                    <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>{logs.length} events</span>
                    <span style={{ fontSize: 8, color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {latest.slice(0, 60)}
                    </span>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)', transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}>▶</span>
                  </div>
                  {expanded && (
                    <div style={{ maxHeight: 200, overflowY: 'auto', padding: '4px 8px 8px' }}>
                      {logs.slice(-50).map((line, i) => (
                        <div key={i} style={{ fontSize: 9, fontFamily: 'monospace', color: 'var(--text-dim)', lineHeight: 1.5, padding: '1px 4px',
                          background: i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent',
                        }}>
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Execute control */}
      <div style={{ display: 'flex', gap: 6 }}>
        <select
          value={selectedAgent || ''}
          onChange={e => setSelectedAgent(e.target.value || null)}
          style={{
            fontSize: 9, padding: '6px 8px', borderRadius: 8,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            color: 'var(--text)', outline: 'none',
          }}
        >
          <option value="">Select agent...</option>
          {['01','02','03','04','05','06','07','08','09','10','11','12','14','15','16'].map(id => (
            <option key={id} value={id}>Agent {id}</option>
          ))}
        </select>
        <input
          value={taskInput}
          onChange={e => setTaskInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleExecute()}
          placeholder="Task description..."
          style={{
            flex: 1, fontSize: 10, padding: '6px 8px', borderRadius: 8,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            color: 'var(--text)', outline: 'none',
          }}
        />
        <button
          onClick={handleExecute}
          disabled={!selectedAgent || !taskInput.trim()}
          style={{
            fontSize: 9, fontWeight: 700, padding: '6px 12px', borderRadius: 8, border: 'none',
            background: selectedAgent && taskInput.trim() ? '#06b6d4' : 'var(--text-muted)',
            color: selectedAgent && taskInput.trim() ? '#000' : 'var(--text-dim)',
            cursor: selectedAgent && taskInput.trim() ? 'pointer' : 'not-allowed',
          }}
        >EXEC</button>
      </div>
    </div>
  );
}
