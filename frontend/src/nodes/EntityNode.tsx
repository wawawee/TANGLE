import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface EntityNodeData extends Record<string, unknown> {
  entity: string;
  status: 'idle' | 'uploading' | 'running' | 'done' | 'error';
  filepath?: string;
  report?: string;
  reportMarkdown?: string;
  verified?: boolean;
  criticScore?: number;
  errorMessage?: string;
}

function guessIcon(entity: string): string {
  const lower = entity.toLowerCase();
  if (lower.includes('cat') || lower.includes('katt') || lower.includes('luna')) return '🐱';
  if (lower.includes('dog') || lower.includes('hund')) return '🐕';
  if (lower.includes('inc') || lower.includes('corp') || lower.includes('ab') || lower.includes('ltd')) return '🏢';
  return '🎯';
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  idle: { label: 'Ready', color: 'rgba(255,255,255,0.2)' },
  uploading: { label: 'Uploading…', color: '#f59e0b' },
  running: { label: 'Running…', color: '#06b6d4' },
  done: { label: 'Complete ✓', color: '#10b981' },
  error: { label: 'Failed ✗', color: '#ef4444' },
};

const EntityNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as EntityNodeData;
  const [expanded, setExpanded] = useState(false);
  const [showFullReport, setShowFullReport] = useState(false);
  const [copyState, setCopyState] = useState<'idle' | 'ok' | 'fail'>('idle');
  const statusCfg = STATUS_LABELS[nodeData.status] || STATUS_LABELS.idle;
  const icon = guessIcon(nodeData.entity);
  const isActive = nodeData.status === 'running' || nodeData.status === 'uploading';

  const handleCopyReport = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const md = nodeData.reportMarkdown || nodeData.report || '';
    try {
      await navigator.clipboard.writeText(md);
      setCopyState('ok');
      setTimeout(() => setCopyState('idle'), 1500);
    } catch {
      setCopyState('fail');
      setTimeout(() => setCopyState('idle'), 1500);
    }
  };

  const handleToggleFull = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowFullReport(s => !s);
  };

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        position: 'relative',
        width: expanded ? 320 : 220,
        borderRadius: 18,
        background: 'radial-gradient(ellipse at center, rgba(139,92,246,0.12) 0%, rgba(10,10,18,0.92) 100%)',
        backdropFilter: 'blur(16px)',
        border: `1px solid ${isActive ? 'rgba(139,92,246,0.5)' : 'rgba(139,92,246,0.2)'}`,
        boxShadow: isActive
          ? '0 0 32px rgba(139,92,246,0.25), 0 4px 24px rgba(0,0,0,0.4)'
          : '0 4px 24px rgba(0,0,0,0.35)',
        cursor: 'pointer',
        transition: 'all 0.4s',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#8b5cf6', width: 10, height: 10, left: -6, border: '2px solid #8b5cf6' }} />
      <Handle type="target" position={Position.Top} style={{ background: '#8b5cf6', width: 8, height: 8, top: -5 }} />
      <Handle type="source" position={Position.Right} style={{ background: '#8b5cf6', width: 10, height: 10, right: -6, border: '2px solid #8b5cf6' }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#8b5cf6', width: 10, height: 10, bottom: -6 }} />

      {/* Top glow */}
      <div style={{
        height: 4, borderRadius: '18px 18px 0 0',
        background: isActive
          ? 'linear-gradient(90deg, transparent, #8b5cf6, #c084fc, transparent)'
          : 'linear-gradient(90deg, transparent, rgba(139,92,246,0.3), transparent)',
        opacity: isActive ? 1 : 0.5,
        transition: 'opacity 0.4s',
      }} />

      <div style={{ padding: 14 }}>
        {/* Entity header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 28 }}>{icon}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'rgba(192,132,252,0.7)' }}>
              Entity
            </div>
            <div style={{
              color: '#fff', fontWeight: 700, fontSize: 16, lineHeight: 1.2,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {nodeData.entity}
            </div>
          </div>
          {/* Status badge */}
          <div style={{
            padding: '3px 10px', borderRadius: 12,
            fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
            background: `${statusCfg.color}18`,
            border: `1px solid ${statusCfg.color}40`,
            color: statusCfg.color,
          }}>
            {statusCfg.label}
          </div>
        </div>

        {/* Progress bar when running */}
        {isActive && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                borderRadius: 2,
                background: 'linear-gradient(90deg, #8b5cf6, #06b6d4)',
                animation: 'pulse-glow 1.5s ease-in-out infinite',
                width: nodeData.status === 'running' ? '100%' : '60%',
                transition: 'width 0.5s',
              }} />
            </div>
          </div>
        )}

        {/* File indicator */}
        {nodeData.filepath && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 8, marginBottom: 8,
            background: 'rgba(163,230,53,0.08)', border: '1px solid rgba(163,230,53,0.12)',
            fontSize: 10, color: 'rgba(255,255,255,0.5)',
          }}>
            <span>📄</span>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9 }}>
              {nodeData.filepath.split('/').pop()}
            </span>
          </div>
        )}

        {/* Critic score (when done) */}
        {nodeData.status === 'done' && nodeData.criticScore !== undefined && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            marginBottom: 8, fontSize: 10,
          }}>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>Critic:</span>
            <span style={{
              fontWeight: 700,
              color: nodeData.verified ? '#10b981' : '#ef4444',
            }}>
              {nodeData.criticScore.toFixed(2)}
            </span>
            {!nodeData.verified && (
              <span style={{
                fontSize: 8, fontWeight: 700,
                padding: '1px 6px', borderRadius: 6,
                background: 'rgba(239,68,68,0.15)', color: '#ef4444',
                border: '1px solid rgba(239,68,68,0.3)',
              }}>
                UNVERIFIED
              </span>
            )}
          </div>
        )}

        {/* Error message */}
        {nodeData.status === 'error' && nodeData.errorMessage && (
          <div style={{
            padding: 8, borderRadius: 8,
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
            fontSize: 10, color: '#ef4444', fontFamily: 'JetBrains Mono, monospace',
            wordBreak: 'break-word',
          }}>
            {nodeData.errorMessage}
          </div>
        )}

        {/* Expanded: report preview with markdown rendering */}
        {expanded && nodeData.status === 'done' && nodeData.reportMarkdown && (
          <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
            <div style={{ fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'rgba(255,255,255,0.25)', marginBottom: 6 }}>
              Report
            </div>
            <div
              className="tangle-markdown-report"
              style={{
                maxHeight: showFullReport ? 600 : 280, overflowY: 'auto',
                background: 'rgba(255,255,255,0.03)',
                padding: '10px 12px', borderRadius: 8,
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {showFullReport ? (nodeData.reportMarkdown || '') : (nodeData.reportMarkdown || '').slice(0, 1200)}
              </ReactMarkdown>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8, alignItems: 'center' }}>
              <button
                onClick={handleCopyReport}
                title="Copy full report to clipboard"
                style={{
                  flex: 1, padding: '5px 0', fontSize: 9, fontWeight: 600,
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                  background: copyState === 'ok' ? 'rgba(16,185,129,0.18)' : 'rgba(139,92,246,0.18)',
                  border: `1px solid ${copyState === 'ok' ? 'rgba(16,185,129,0.4)' : 'rgba(139,92,246,0.35)'}`,
                  borderRadius: 6, color: copyState === 'ok' ? '#10b981' : '#c084fc',
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'background 120ms, color 120ms',
                }}
              >
                {copyState === 'ok' ? '✓ Copied' : copyState === 'fail' ? '✗ Failed' : 'Copy'}
              </button>
              {(nodeData.reportMarkdown || '').length > 1200 && (
                <button
                  onClick={handleToggleFull}
                  style={{
                    flex: 1, padding: '5px 0', fontSize: 9, fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.08em',
                    background: showFullReport ? 'rgba(239,68,68,0.18)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${showFullReport ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.12)'}`,
                    borderRadius: 6, color: showFullReport ? '#fca5a5' : 'rgba(255,255,255,0.5)',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  {showFullReport ? 'Collapse' : `Full (${(nodeData.reportMarkdown || '').length} chars)`}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

EntityNode.displayName = 'EntityNode';
export default EntityNode;
