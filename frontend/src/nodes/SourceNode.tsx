import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo, useState } from 'react';

export interface SourceNodeData extends Record<string, unknown> {
  filename: string;
  filepath: string;
  entity: string;
  confidence: number;
  chunkId: string;
  timestamp: string;
  tags: string[];
  rawContent?: string;
  parseError?: string;
}

const TAG_COLORS: Record<string, string> = {
  health: '#10b981', finance: '#f59e0b', legal: '#ef4444',
  contact: '#06b6d4', risk: '#ef4444', opportunity: '#10b981',
  threat: '#f97316', context: '#8b5cf6', research: '#06b6d4',
  urgent: '#ef4444',
};

const SourceNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as SourceNodeData;
  const [expanded, setExpanded] = useState(false);
  const accent = '#a3e635';

  const confPct = Math.round(nodeData.confidence * 100);
  const confColor = confPct >= 70 ? '#10b981' : confPct >= 40 ? '#f59e0b' : '#ef4444';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        position: 'relative',
        width: expanded ? 300 : 200,
        borderRadius: 14,
        background: 'rgba(10,10,18,0.88)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(163,230,53,0.15)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
        cursor: 'pointer',
        transition: 'all 0.3s',
      }}
    >
      <Handle type="source" position={Position.Right} style={{ background: accent, width: 8, height: 8, right: -5, border: `2px solid ${accent}` }} />
      <Handle type="source" position={Position.Bottom} style={{ background: accent, width: 6, height: 6, bottom: -4 }} />
      <Handle type="target" position={Position.Left} style={{ background: accent, width: 8, height: 8, left: -5 }} />

      <div style={{ height: 3, borderRadius: '14px 14px 0 0', background: `linear-gradient(90deg, ${accent}, ${accent}44, transparent)` }} />

      <div style={{ padding: 12 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontSize: 20 }}>📄</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#a3e635', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Source File
            </div>
            <div style={{
              color: '#fff', fontWeight: 600, fontSize: 12, lineHeight: 1.3,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {nodeData.filename}
            </div>
          </div>
          {nodeData.parseError && (
            <div style={{
              padding: '2px 6px', borderRadius: 8, fontSize: 8, fontWeight: 700,
              background: 'rgba(239,68,68,0.15)', color: '#ef4444',
              border: '1px solid rgba(239,68,68,0.3)',
            }}>
              ERROR
            </div>
          )}
        </div>

        {/* Entity badge */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '2px 10px', borderRadius: 10, marginBottom: 8,
          background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)',
          fontSize: 10, fontWeight: 600, color: '#c084fc',
        }}>
          <span>🎯</span>
          <span>{nodeData.entity}</span>
        </div>

        {/* Confidence meter */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: 'rgba(255,255,255,0.3)', marginBottom: 2 }}>
            <span>Confidence</span>
            <span style={{ color: confColor }}>{confPct}%</span>
          </div>
          <div style={{ height: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 2,
              width: `${confPct}%`,
              background: confColor,
              transition: 'width 0.5s',
            }} />
          </div>
        </div>

        {/* Tags */}
        {nodeData.tags && nodeData.tags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {nodeData.tags.slice(0, 4).map(tag => {
              const tc = TAG_COLORS[tag] || 'rgba(255,255,255,0.4)';
              return (
                <span key={tag} style={{
                  fontSize: 8, fontWeight: 600,
                  padding: '1px 6px', borderRadius: 6,
                  color: tc, background: `${tc}15`,
                  border: `1px solid ${tc}30`,
                }}>
                  #{tag}
                </span>
              );
            })}
            {nodeData.tags.length > 4 && (
              <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)', padding: '1px 4px' }}>
                +{nodeData.tags.length - 4}
              </span>
            )}
          </div>
        )}

        {/* Expanded content */}
        {expanded && nodeData.rawContent && (
          <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
            <div style={{ fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'rgba(255,255,255,0.25)', marginBottom: 6 }}>
              Content Preview
            </div>
            <div style={{
              fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
              color: 'rgba(255,255,255,0.45)', lineHeight: 1.5,
              maxHeight: 160, overflowY: 'auto',
              background: 'rgba(255,255,255,0.02)',
              padding: 8, borderRadius: 8,
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {nodeData.rawContent.slice(0, 800)}
              {nodeData.rawContent.length > 800 && (
                <span style={{ color: 'rgba(255,255,255,0.2)' }}>…truncated ({nodeData.rawContent.length - 800} more chars)</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

SourceNode.displayName = 'SourceNode';
export default SourceNode;
