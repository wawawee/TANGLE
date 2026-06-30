import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react';
import type { Node, Edge, NodeProps, EdgeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { Contradiction, ContradictionResult } from '../../types/contradiction';
import {
  CONTRADICTION_KIND_COLORS,
  CONTRADICTION_KIND_LABELS,
  CONTRADICTION_SEVERITY_COLORS,
} from '../../types/contradiction';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 100;

function SourceNode({ data }: NodeProps) {
  return (
    <div
      className="bg-white dark:bg-[#0a0a0a] border-4 border-[#111] dark:border-[#eee] 
                  shadow-[4px_4px_0px_0px_#111] dark:shadow-[4px_4px_0px_0px_#eee]
                  px-4 py-3 min-w-[180px]"
      style={{ width: NODE_WIDTH }}
    >
      <Handle type="source" position={Position.Right} className="!bg-[#111] dark:!bg-[#eee] !w-3 !h-3 !border-2" />
      <Handle type="target" position={Position.Left} className="!bg-[#111] dark:!bg-[#eee] !w-3 !h-3 !border-2" />
      <div className="text-xs font-black uppercase tracking-wider text-gray-500 mb-1 truncate">
        Source
      </div>
      <div className="text-sm font-bold dark:text-[#eee] leading-tight line-clamp-2">
        {data.label as string}
      </div>
      {data.claimsCount > 0 && (
        <div className="text-xs text-gray-400 mt-1 font-mono">
          {data.claimsCount} claim{data.claimsCount !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

const nodeTypes = { sourceNode: SourceNode };

function ContradictionEdge({
  id,
  source,
  target,
  data,
  selected,
}: EdgeProps) {
  const contradiction = data?.contradiction as Contradiction | undefined;
  if (!contradiction) return null;

  const color = CONTRADICTION_KIND_COLORS[contradiction.kind];
  const width = Math.max(2, Math.round(contradiction.confidence * 6));

  return (
    <>
      <path
        id={id}
        className={`react-flow__edge-path ${selected ? 'selected' : ''}`}
        d={data?.path as string}
        style={{
          stroke: color,
          strokeWidth: width,
          strokeDasharray: contradiction.kind === 'legal' ? '8,4' : 'none',
          opacity: 0.8,
          cursor: 'pointer',
        }}
        markerEnd={
          selected
            ? `url(#arrow-${contradiction.kind})`
            : `url(#arrow-${contradiction.kind}-dim)`
        }
      />
      {selected && contradiction && (
        <foreignObject
          width={240}
          height={180}
          x={-120}
          y={-200}
          className="overflow-visible pointer-events-none"
          requiredExtensions="http://www.w3.org/1999/xhtml"
        >
          <div
            className="bg-white dark:bg-[#0a0a0a] border-4 border-[#111] dark:border-[#eee] 
                        p-3 shadow-[4px_4px_0px_0px_#111] dark:shadow-[4px_4px_0px_0px_#eee]
                        pointer-events-auto"
            style={{ borderLeftColor: color, borderLeftWidth: 6 }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span
                className="text-xs font-black uppercase px-1.5 py-0.5 text-white"
                style={{ backgroundColor: color }}
              >
                {CONTRADICTION_KIND_LABELS[contradiction.kind]}
              </span>
              <span
                className="text-xs font-bold font-mono uppercase"
                style={{ color: CONTRADICTION_SEVERITY_COLORS[contradiction.severity] }}
              >
                {contradiction.severity}
              </span>
              <span className="text-xs font-mono text-gray-500">
                {Math.round(contradiction.confidence * 100)}%
              </span>
            </div>
            <div className="text-xs space-y-1">
              <div>
                <span className="font-bold dark:text-[#eee]">Claim: </span>
                <span className="text-gray-600 dark:text-gray-400 line-clamp-2">
                  "{contradiction.claim_excerpt}"
                </span>
              </div>
              <div>
                <span className="font-bold dark:text-[#eee] v">vs: </span>
                <span className="text-gray-600 dark:text-gray-400 line-clamp-2">
                  "{contradiction.conflicts_with_excerpt}"
                </span>
              </div>
            </div>
          </div>
        </foreignObject>
      )}
    </>
  );
}

const edgeTypes = { contradictionEdge: ContradictionEdge };

function buildGraph(
  contradictions: Contradiction[]
): { nodes: Node[]; edges: Edge[] } {
  if (!contradictions.length) {
    return { nodes: [], edges: [] };
  }

  const sourceSet = new Set<string>();
  contradictions.forEach((c) => {
    sourceSet.add(c.claim_source);
    sourceSet.add(c.conflicts_with_source);
  });

  const sources = Array.from(sourceSet);
  const centerX = 400;
  const centerY = 300;
  const radius = Math.min(
    200,
    (sources.length <= 3 ? 150 : 180)
  );

  const sourceClaimCounts: Record<string, number> = {};
  contradictions.forEach((c) => {
    sourceClaimCounts[c.claim_source] =
      (sourceClaimCounts[c.claim_source] || 0) + 1;
    sourceClaimCounts[c.conflicts_with_source] =
      (sourceClaimCounts[c.conflicts_with_source] || 0) + 1;
  });

  const nodes: Node[] = sources.map((source, i) => {
    const angle = (2 * Math.PI * i) / sources.length - Math.PI / 2;
    return {
      id: `source-${i}`,
      type: 'sourceNode',
      position: {
        x: centerX + radius * Math.cos(angle) - NODE_WIDTH / 2,
        y: centerY + radius * Math.sin(angle) - NODE_HEIGHT / 2,
      },
      data: {
        label: source,
        claimsCount: sourceClaimCounts[source] || 0,
      },
    };
  });

  const edges: Edge[] = contradictions.map((c, i) => {
    const sourceIdx = sources.indexOf(c.claim_source);
    const targetIdx = sources.indexOf(c.conflicts_with_source);
    return {
      id: `contra-${i}`,
      source: `source-${sourceIdx}`,
      target: `source-${targetIdx}`,
      type: 'contradictionEdge',
      animated: true,
      style: {
        stroke: CONTRADICTION_KIND_COLORS[c.kind],
        strokeWidth: Math.max(2, Math.round(c.confidence * 6)),
        opacity: 0.8,
      },
      data: { contradiction: c },
      label: `${CONTRADICTION_KIND_LABELS[c.kind]} · ${c.severity}`,
    };
  });

  return { nodes, edges };
}

interface ContradictionGraphProps {
  result: ContradictionResult | null;
  loading?: boolean;
  error?: string | null;
  onClose?: () => void;
  onAnalyze?: () => void;
}

function ContradictionGraphInner({
  result,
  loading,
  error,
  onClose,
  onAnalyze,
}: ContradictionGraphProps) {
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraph(result?.contradictions || []),
    [result]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = buildGraph(
      result?.contradictions || []
    );
    setNodes(newNodes);
    setEdges(newEdges);
  }, [result, setNodes, setEdges]);

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      setSelectedEdge((prev) => (prev === edge.id ? null : edge.id));
    },
    []
  );

  const onPaneClick = useCallback(() => {
    setSelectedEdge(null);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-800 dark:text-gray-400 p-6 text-center">
        <div className="w-12 h-12 border-4 border-[#111] border-t-transparent rounded-full animate-spin mb-4 dark:border-[#eee] dark:border-t-transparent" />
        <p className="font-mono text-sm uppercase">Analysing contradictions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <p className="font-mono text-sm text-red-500 mb-4">{error}</p>
        {onAnalyze && (
          <button
            onClick={onAnalyze}
            className="px-4 py-2 bg-[#111] text-white font-black text-sm uppercase tracking-wider hover:bg-gray-800 transition-colors dark:bg-[#eee] dark:text-[#111]"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (!result || !result.contradictions.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <div className="text-4xl mb-4 opacity-30">⚖️</div>
        <p className="font-mono text-sm uppercase dark:text-[#eee] mb-2">
          No contradictions found
        </p>
        <p className="text-xs text-gray-500 max-w-xs">
          The evidence appears internally consistent. No conflicting statements detected.
        </p>
        {onAnalyze && (
          <button
            onClick={onAnalyze}
            className="mt-6 px-4 py-2 bg-[#111] text-white font-black text-sm uppercase tracking-wider hover:bg-gray-800 transition-colors dark:bg-[#eee] dark:text-[#111]"
          >
            Run Analysis
          </button>
        )}
      </div>
    );
  }

  const byKind = (kind: string) =>
    result.contradictions.filter((c) => c.kind === kind).length;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b-4 border-[#111] dark:border-[#eee]">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-black uppercase text-sm dark:text-[#eee]">
            Contradictions
          </h4>
          {onClose && (
            <button
              onClick={onClose}
              className="text-xs font-mono text-gray-500 hover:text-[#111] dark:hover:text-[#eee] transition-colors"
            >
              ×
            </button>
          )}
        </div>

        <div className="flex gap-3 text-xs font-mono">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ef4444' }} />
            <span className="dark:text-[#eee]">{byKind('intra_source')} intra</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#eab308' }} />
            <span className="dark:text-[#eee]">{byKind('inter_source')} inter</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3b82f6' }} />
            <span className="dark:text-[#eee]">{byKind('legal')} legal</span>
          </span>
        </div>
      </div>

      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onEdgeClick={onEdgeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          selectNodesOnDrag={false}
        >
          <defs>
            {(['intra_source', 'inter_source', 'legal'] as const).map((kind) => (
              <marker
                key={kind}
                id={`arrow-${kind}`}
                viewBox="0 0 10 10"
                refX="10"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto"
              >
                <path
                  d="M0,0 L10,5 L0,10 Z"
                  fill={CONTRADICTION_KIND_COLORS[kind]}
                />
              </marker>
            ))}
            {(['intra_source', 'inter_source', 'legal'] as const).map((kind) => (
              <marker
                key={`${kind}-dim`}
                id={`arrow-${kind}-dim`}
                viewBox="0 0 10 10"
                refX="10"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto"
              >
                <path
                  d="M0,0 L10,5 L0,10 Z"
                  fill={CONTRADICTION_KIND_COLORS[kind]}
                  opacity={0.4}
                />
              </marker>
            ))}
          </defs>
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#555"
          />
        </ReactFlow>
      </div>

      <div className="px-4 py-2 border-t-4 border-[#111] dark:border-[#eee] text-xs font-mono text-gray-500 flex items-center justify-between">
        <span>
          {result.contradictions.length} contradiction{result.contradictions.length !== 1 ? 's' : ''}
          {' · '}
          {result.evidence_count} evidence source{result.evidence_count !== 1 ? 's' : ''}
        </span>
        {selectedEdge && (
          <span className="dark:text-[#eee] text-[10px]">
            Click edge again to dismiss detail
          </span>
        )}
      </div>
    </div>
  );
}

export default function ContradictionGraph(props: ContradictionGraphProps) {
  return (
    <ReactFlowProvider>
      <ContradictionGraphInner {...props} />
    </ReactFlowProvider>
  );
}
