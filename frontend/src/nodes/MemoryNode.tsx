import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { memo } from 'react';
import { useAgentStore } from '../store/agentStore';

export interface MemoryNodeData {
  nodeType: 'qdrant' | 'supabase' | 'file';
  label: string;
  collection?: string;
  vectorCount?: number;
  lastIndexed?: string;
}

const MemoryNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as MemoryNodeData;
  const qdrantCollections = useAgentStore(s => s.qdrantCollections);

  const collection = nodeData.collection
    ? qdrantCollections.find(c => c.name === nodeData.collection)
    : null;

  const typeConfig = {
    qdrant: { color: '#22d3ee', icon: '🧠', label: 'Qdrant Vector Store', bg: 'rgba(34,211,238,0.08)' },
    supabase: { color: '#10b981', icon: '🗄️', label: 'Supabase PostgreSQL', bg: 'rgba(16,185,129,0.08)' },
    file: { color: '#a3e635', icon: '📄', label: 'File Memory', bg: 'rgba(163,230,53,0.08)' },
  }[nodeData.nodeType];

  return (
    <div
      className="rounded-xl border backdrop-blur-xl"
      style={{
        background: typeConfig.bg,
        borderColor: `${typeConfig.color}30`,
        boxShadow: `0 4px 16px rgba(0,0,0,0.3), 0 0 0 1px ${typeConfig.color}15`,
        width: 180,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: typeConfig.color, width: 8, height: 8, left: -5 }} />
      <Handle type="source" position={Position.Right} style={{ background: typeConfig.color, width: 8, height: 8, right: -5 }} />
      <Handle type="target" position={Position.Top} style={{ background: typeConfig.color, width: 6, height: 6, top: -4 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: typeConfig.color, width: 6, height: 6, bottom: -4 }} />

      <div className="h-0.5 rounded-t-xl" style={{ background: `linear-gradient(90deg, transparent, ${typeConfig.color}, transparent)` }} />

      <div className="p-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base">{typeConfig.icon}</span>
          <div>
            <div className="text-[9px] uppercase tracking-widest font-bold" style={{ color: typeConfig.color }}>{typeConfig.label}</div>
            <div className="text-[11px] text-white/80 font-semibold">{nodeData.label}</div>
          </div>
        </div>

        {nodeData.nodeType === 'qdrant' && (
          <div className="space-y-1">
            {nodeData.collection && (
              <>
                <div className="text-[9px] font-mono text-white/30">{nodeData.collection}</div>
                <div className="flex justify-between text-[9px]">
                  <span className="text-white/30">Vectors</span>
                  <span style={{ color: typeConfig.color }}>{collection?.vectorCount?.toLocaleString() ?? '—'}</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${collection?.status === 'green' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                  <span className="text-[9px] text-white/30">{collection?.status === 'green' ? 'Healthy' : 'Degraded'}</span>
                </div>
              </>
            )}
            {!nodeData.collection && (
              <div className="space-y-0.5">
                {qdrantCollections.slice(0, 4).map(c => (
                  <div key={c.name} className="flex justify-between text-[8px]">
                    <span className="text-white/30 truncate max-w-[100px]">{c.name}</span>
                    <span style={{ color: typeConfig.color }}>{c.vectorCount.toLocaleString()}</span>
                  </div>
                ))}
                <div className="text-[8px] text-white/20">+{qdrantCollections.length - 4} more collections</div>
              </div>
            )}
          </div>
        )}

        {nodeData.nodeType === 'supabase' && (
          <div>
            <div className="text-[9px] text-white/30 mb-1">Connected tables</div>
            {['agent_logs', 'telemetry_events', 'task_queue', 'agent_memory'].map(t => (
              <div key={t} className="flex items-center gap-1 text-[8px] text-white/40">
                <div className="w-1 h-1 rounded-full bg-emerald-400" />
                <span className="font-mono">{t}</span>
              </div>
            ))}
          </div>
        )}

        {nodeData.nodeType === 'file' && (
          <div className="space-y-0.5">
            {['IDENTITY.md', 'SOUL.md', 'SKILLS.md', 'MEMORY.md', 'TASKLIST.md'].map(f => (
              <div key={f} className="text-[8px] text-white/30 font-mono flex items-center gap-1">
                <span style={{ color: typeConfig.color }}>›</span> {f}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

MemoryNode.displayName = 'MemoryNode';
export default MemoryNode;
