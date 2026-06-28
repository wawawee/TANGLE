import type { EdgeProps } from '@xyflow/react';
import {
    BaseEdge,
    EdgeLabelRenderer,
    getBezierPath
} from '@xyflow/react';
import { memo } from 'react';
import { useAgentStore } from '../store/agentStore';

export interface TelemetryEdgeData {
  edgeId: string;
  label?: string;
  type?: string;
  color?: string;
}

const TYPE_COLORS: Record<string, string> = {
  delegate:       '#c084fc',
  vector_search:  '#22d3ee',
  api_call:       '#f59e0b',
  memory_read:    '#a3e635',
  memory_write:   '#f43f5e',
  kill_action:    '#ef4444',
  alert:          '#fb923c',
};

const TelemetryEdge = memo(({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data, markerEnd,
}: EdgeProps) => {
  const edgeData = data as TelemetryEdgeData | undefined;
  const activeEdges = useAgentStore(s => s.activeEdges);
  const latestEvent = useAgentStore(s => s.telemetryLog.find(e => e.from && e.to));

  const isActive = activeEdges.has(id);
  const color = edgeData?.color || (isActive ? (TYPE_COLORS[latestEvent?.type || ''] || '#c084fc') : 'rgba(255,255,255,0.08)');

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: isActive ? color : 'rgba(255,255,255,0.06)',
          strokeWidth: isActive ? 2 : 1,
          strokeDasharray: isActive ? '8 4' : 'none',
          filter: isActive ? `drop-shadow(0 0 4px ${color})` : 'none',
          transition: 'all 0.3s ease',
          animation: isActive ? 'dash-flow 1s linear infinite' : 'none',
        }}
      />

      {/* Glowing dot travelling along edge when active */}
      {isActive && (
        <circle r={4} fill={color} style={{ filter: `drop-shadow(0 0 6px ${color})` }}>
          <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}

      {isActive && edgeData?.label && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'none',
              zIndex: 1000,
            }}
          >
            <div
              className="px-2 py-1 rounded-lg text-[8px] font-mono font-bold whitespace-nowrap max-w-[180px] truncate"
              style={{
                background: `rgba(10,10,18,0.95)`,
                border: `1px solid ${color}50`,
                color: color,
                boxShadow: `0 2px 12px rgba(0,0,0,0.5), 0 0 8px ${color}30`,
              }}
            >
              {edgeData.label}
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

TelemetryEdge.displayName = 'TelemetryEdge';
export default TelemetryEdge;
