import {
    BaseEdge,
    EdgeLabelRenderer,
    getBezierPath,
    type EdgeProps,
} from '@xyflow/react';
import { useAgentStore } from '../store/agentStore';

export default function EdgeTelemetry({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetPosition,
    targetX,
    targetY,
  });

  const activeEdges = useAgentStore((s) => s.activeEdges);
  const telemetryLog = useAgentStore((s) => s.telemetryLog);
  const isActive = activeEdges.has(id);

  // Find latest event for this edge
  const latestEvent = telemetryLog.find(e => e.from === data?.sourceId || e.to === data?.targetId);

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: isActive ? 'var(--purple)' : 'var(--border-bright)',
          strokeWidth: isActive ? 2 : 1,
          opacity: isActive ? 1 : 0.2,
          transition: 'all 0.3s ease',
        }}
      />
      {isActive && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 10,
              pointerEvents: 'none',
            }}
            className="glass px-2 py-1 rounded-md text-[9px] font-bold text-purple-600 animate-float-up whitespace-nowrap z-50 shadow-xl border border-purple-200"
          >
            {latestEvent?.label || 'Processing...'}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
