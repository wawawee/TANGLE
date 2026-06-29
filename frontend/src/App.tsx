import {
    Background,
    BackgroundVariant,
    Controls,
    MarkerType,
    MiniMap,
    ReactFlow,
    ReactFlowProvider,
    useEdgesState,
    useNodesState,
    useReactFlow,
    type Edge,
    type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useEffect, useRef, useState } from 'react';

// Width of the right-side panel (INDEX / CLI / LOGS). Kept here so all three
// wrapper <div>s and the toggle width formula stay in sync.
const SIDE_PANEL_WIDTH = 520;
const LS_KEY = 'tangle-canvas-state';
const STATIC_NODE_IDS = new Set(['orchestrator', 'qdrant', 'file-memory', 'agent-16']);

import AgentVerbosePanel from './components/AgentVerbosePanel';
import ChatBox from './components/ChatBox';
import CliHarness from './components/CliHarness';
import EdgeTelemetry from './components/EdgeTelemetry';
import EntitySelector from './components/EntitySelector';
import ErrorBoundary from './components/ErrorBoundary';
import Experience3D from './components/Experience3D';
import IndexPanel from './components/IndexPanel';

import MemoryNode from './nodes/MemoryNode';
import type { PipelineNodeData } from './nodes/PipelineNode';
import OrchestratorNode from './nodes/OrchestratorNode';
import SystemGuardianNode from './nodes/SystemGuardianNode';
import SourceNode from './nodes/SourceNode';
import type { SourceNodeData } from './nodes/SourceNode';
import EntityNode from './nodes/EntityNode';
import type { EntityNodeData } from './nodes/EntityNode';
import PipelineNode from './nodes/PipelineNode';

import { useAgentStore } from './store/agentStore';

// ─── Node Types ───────────────────────────────────────────────
const NODE_TYPES = {
  orchestrator: OrchestratorNode,
  systemGuardian: SystemGuardianNode,
  memory: MemoryNode,
  source: SourceNode,
  entity: EntityNode,
  pipeline: PipelineNode,
};

const EDGE_TYPES = {
  telemetry: EdgeTelemetry,
};

// ─── Canvas Layout ─────────────────────────────────────────────
const makeNodes = (): Node[] => {
  const nodes: Node[] = [];

  nodes.push({
    id: 'orchestrator',
    type: 'orchestrator',
    position: { x: 400, y: 460 },
    data: {},
    draggable: true,
  });

  nodes.push({
    id: 'qdrant',
    type: 'memory',
    position: { x: 80, y: 80 },
    data: { nodeType: 'qdrant', label: 'Qdrant Cloud' },
    draggable: true,
  });

  nodes.push({
    id: 'file-memory',
    type: 'memory',
    position: { x: 80, y: 680 },
    data: { nodeType: 'file', label: 'Markdown Files' },
    draggable: true,
  });

  nodes.push({
    id: 'agent-16',
    type: 'systemGuardian',
    position: { x: 1100, y: 460 },
    data: {},
    draggable: true,
  });

  return nodes;
};

const s = {
  bar: {
    display: 'flex', alignItems: 'center', gap: '16px',
    padding: '12px 24px', flexShrink: 0,
    position: 'relative' as const, zIndex: 60,
    background: 'var(--glass-bg)',
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    borderBottom: '1px solid var(--border)',
  },
  title: {
    fontSize: '18px', fontWeight: 900, letterSpacing: '-0.05em',
    color: 'var(--text)', lineHeight: '1', margin: 0,
  },
  subtitle: {
    fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em',
    textTransform: 'uppercase' as const, color: 'var(--text-muted)', margin: '4px 0 0',
  },
  divider: {
    width: '1px', height: '24px',
    background: 'var(--border-bright)', margin: '0 16px',
  },
  terminalBtn: (active: boolean) => ({
    padding: '8px 16px', borderRadius: '16px', border: '1px solid',
    fontSize: '10px', fontWeight: 900, textTransform: 'uppercase' as const,
    letterSpacing: '0.05em', cursor: 'pointer',
    transition: 'all 0.2s', outline: 'none',
    background: active ? '#10b98120' : 'var(--glass-bg)',
    borderColor: active ? '#10b98160' : 'var(--border)',
    color: active ? '#059669' : 'var(--text-dim)',
  }),
};

function TangleCanvas() {
  const [allNodes, setAllNodes] = useState(makeNodes());
  const [allEdges, setAllEdges] = useState<Edge[]>([]);

  const {
    visibleNodes, visibleEdges, is3DMode, intensity, connectWs
  } = useAgentStore();

  const { screenToFlowPosition } = useReactFlow();

  const [nodes, setNodes, _onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [showEntities, setShowEntities] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [showIndex, setShowIndex] = useState(false);

  // Sync dragged positions back to allNodes so localStorage saves them
  const handleNodesChange = (changes: Parameters<typeof _onNodesChange>[0]) => {
    _onNodesChange(changes);
    setAllNodes(prev => {
      let updated = prev;
      for (const ch of changes) {
        if (ch.type === 'position' && 'position' in ch && ch.position) {
          updated = updated.map(n =>
            n.id === ch.id ? { ...n, position: { ...n.position, ...ch.position } } : n
          );
        }
      }
      return updated;
    });
  };

  // ─── Canvas drop & prompt state ────────────────────────────
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [promptValue, setPromptValue] = useState('');
  const [promptEntity, setPromptEntity] = useState('');
  const [activeEntity, setActiveEntity] = useState<string | null>(null);
  const [entityFilepaths, setEntityFilepaths] = useState<Record<string, string>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [isMissionRunning, setIsMissionRunning] = useState(false);
  const [missionEntity, setMissionEntity] = useState<string | null>(null);
  const [currentMissionStep, setCurrentMissionStep] = useState<string>('');

  // ─── localStorage persistence ─────────────────────────────
  const initialLoadDone = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load persisted state on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== 'object') return;

      // Restore dynamic nodes (merge with static nodes from makeNodes)
      if (Array.isArray(saved.nodes)) {
        const staticNodes = makeNodes();
        const restoredNodes: Node[] = saved.nodes
          .filter((n: Node) => !STATIC_NODE_IDS.has(n.id))
          .map((n: Node) => {
            // Reset pipeline nodes stuck in active states
            if (n.type === 'pipeline' && (n.data as PipelineNodeData)?.agentId) {
              const agentId = (n.data as PipelineNodeData).agentId;
              const storeStatus = useAgentStore.getState().agentStatuses[agentId];
              if (storeStatus && storeStatus !== 'idle' && storeStatus !== 'done' && storeStatus !== 'error') {
                useAgentStore.getState().setAgentStatus(agentId, 'idle');
              }
            }
            // Reset entity nodes stuck in 'running'
            if (n.type === 'entity' && (n.data as EntityNodeData)?.status === 'running') {
              return { ...n, data: { ...n.data, status: 'idle' } as EntityNodeData };
            }
            return n;
          });
        setAllNodes([...staticNodes, ...restoredNodes]);
      }

      // Restore edges
      if (Array.isArray(saved.edges)) {
        setAllEdges(saved.edges as Edge[]);
      }

      // Restore entityFilepaths
      if (saved.entityFilepaths && typeof saved.entityFilepaths === 'object') {
        setEntityFilepaths(saved.entityFilepaths as Record<string, string>);
      }
    } catch {
      // Corrupted localStorage — start fresh
      localStorage.removeItem(LS_KEY);
    }
    initialLoadDone.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save to localStorage (debounced) whenever dynamic state changes
  useEffect(() => {
    if (!initialLoadDone.current) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        const dynamicNodes = allNodes.filter(n => !STATIC_NODE_IDS.has(n.id));
        const data = {
          nodes: dynamicNodes,
          edges: allEdges,
          entityFilepaths,
        };
        localStorage.setItem(LS_KEY, JSON.stringify(data));
      } catch {
        // localStorage full or unavailable — silently ignore
      }
    }, 400);

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [allNodes, allEdges, entityFilepaths]);

  useEffect(() => {
    const filteredNodes = allNodes.filter(n =>
      visibleNodes.has(n.id) ||
      n.id === 'orchestrator' ||
      ['source', 'entity', 'pipeline'].includes(n.type!)
    );
    const filteredEdges = allEdges.filter(e => visibleEdges.has(e.id));
    setNodes(filteredNodes);
    setEdges(filteredEdges);
  }, [visibleNodes, visibleEdges, allNodes, allEdges, setNodes, setEdges]);

  // ─── Drag & drop handlers ──────────────────────────────────
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    dragCounterRef.current++;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    const file = files[0];
    const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const entityName = file.name.replace(/\.[^/.]+$/, '');

    // Optimistic SourceNode
    const sourceId = `source-${Date.now()}`;
    const optNode: Node<SourceNodeData> = {
      id: sourceId,
      type: 'source',
      position,
      data: {
        filename: file.name,
        filepath: '',
        entity: entityName,
        confidence: 0,
        chunkId: sourceId,
        timestamp: new Date().toISOString(),
        tags: [],
      },
      draggable: true,
    };
    setAllNodes(prev => [...prev, optNode]);

    // Auto-fill prompt
    setPromptValue(entityName);
    setPromptEntity(entityName);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('entity', entityName);

      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const json = await res.json();

      // Update SourceNode with real data
      setAllNodes(prev => prev.map(n => {
        if (n.id === sourceId) {
          return {
            ...n,
            data: {
              ...n.data,
              filepath: json.filepath || '',
              confidence: json.parsed?.confidence ?? 0.5,
              chunkId: json.parsed?.chunk_id || sourceId,
              timestamp: json.parsed?.timestamp || n.data.timestamp,
              tags: json.parsed?.tags || [],
              rawContent: json.parsed?.raw_content || '',
              parseError: json.parsed?.parse_error || undefined,
            } as SourceNodeData,
          };
        }
        return n;
      }));

      setEntityFilepaths(prev => ({ ...prev, [entityName.toLowerCase()]: json.filepath || '' }));
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setIsUploading(false);
    }

    // If folder: upload all remaining files
    if (files.length > 1) {
      for (let i = 1; i < files.length; i++) {
        const f = files[i];
        const fEntity = f.name.replace(/\.[^/.]+$/, '');
        const fPos = screenToFlowPosition({
          x: e.clientX + i * 40,
          y: e.clientY + i * 30,
        });
        const fId = `source-${Date.now()}-${i}`;
        setAllNodes(prev => [...prev, {
          id: fId,
          type: 'source',
          position: fPos,
          data: {
            filename: f.name,
            filepath: '',
            entity: fEntity,
            confidence: 0,
            chunkId: fId,
            timestamp: new Date().toISOString(),
            tags: [],
          } as SourceNodeData,
          draggable: true,
        }]);

        // Upload in background (don't block main flow)
        const fFormData = new FormData();
        fFormData.append('file', f);
        fFormData.append('entity', fEntity);
        fetch('http://localhost:8000/api/upload', { method: 'POST', body: fFormData })
          .then(r => r.ok ? r.json() : null)
          .then(json => {
            if (!json) return;
            setEntityFilepaths(prev => ({ ...prev, [fEntity.toLowerCase()]: json.filepath || '' }));
            setAllNodes(prev => prev.map(n => {
              if (n.id === fId) {
                return {
                  ...n,
                  data: {
                    ...n.data,
                    filepath: json.filepath || '',
                    confidence: json.parsed?.confidence ?? 0.5,
                    chunkId: json.parsed?.chunk_id || fId,
                    timestamp: json.parsed?.timestamp || (n.data as SourceNodeData).timestamp,
                    tags: json.parsed?.tags || [],
                    rawContent: json.parsed?.raw_content || '',
                    parseError: json.parsed?.parse_error || undefined,
                  } as SourceNodeData,
                };
              }
              return n;
            }));
          })
          .catch(err => console.error(`Upload error for ${f.name}:`, err));
      }
    }
  };

  // ─── Mission start handler ─────────────────────────────────
  const handleStartMission = async (entity: string, existingFilepath?: string) => {
    const finalEntity = entity || promptEntity || 'Unknown Entity';
    const filepath = existingFilepath || entityFilepaths[finalEntity.toLowerCase()] || undefined;

    setIsMissionRunning(true);
    setMissionEntity(finalEntity);
    setPromptEntity('');
    setCurrentMissionStep('Starting mission…');

    // Update step based on pipeline agent statuses via polling (setInterval)
    const stepNames: Record<string, string> = {
      planner:     '🧠 Planning research strategy',
      scout:       '🔍 Searching online sources',
      librarian:   '📚 Querying internal knowledge',
      critic:      '⚖️ Evaluating findings',
      synthesizer: '✨ Synthesizing final report',
    };
    const stepPoll = setInterval(() => { // eslint-disable-line prefer-const
      const statuses = useAgentStore.getState().agentStatuses;
      for (const step of ['synthesizer', 'critic', 'librarian', 'scout', 'planner'] as const) {
        const s = statuses[step];
        if (s === 'thinking' || s === 'executing') {
          setCurrentMissionStep(stepNames[step] || step);
          return;
        }
      }
      // All idle — mission probably done or not started
      setCurrentMissionStep('Waiting for pipeline…');
    }, 500);

    // Hook up WebSocket for live pipeline status
    connectWs();

    // Compute entity node ID early so we can wire edges to it
    const entityId = `entity-${finalEntity.toLowerCase().replace(/\s+/g, '-')}`;

    // Remove old pipeline nodes/edges, create fresh ones
    const pipelineSteps = ['planner', 'scout', 'librarian', 'critic', 'synthesizer'] as const;
    const pipeEdges = [
      { id: 'pipe-ent-p',   source: entityId,  target: 'planner', animated: true },
      { id: 'pipe-p-s',      source: 'planner', target: 'scout', animated: true },
      { id: 'pipe-p-l',      source: 'planner', target: 'librarian', animated: true },
      { id: 'pipe-s-c',      source: 'scout', target: 'critic', animated: true },
      { id: 'pipe-l-c',      source: 'librarian', target: 'critic', animated: true },
      { id: 'pipe-c-syn',    source: 'critic', target: 'synthesizer', animated: true },
      { id: 'pipe-syn-orch', source: 'synthesizer', target: 'orchestrator', animated: true },
    ];

    // Branch layout: Planner → Scout + Librarian (parallel) → Critic → Synthesizer
    const pipePositions: Record<string, { x: number; y: number }> = {
      planner:     { x: 80,  y: 340 },
      scout:       { x: 280, y: 220 },
      librarian:   { x: 280, y: 460 },
      critic:      { x: 500, y: 340 },
      synthesizer: { x: 720, y: 340 },
    };

    setAllNodes(prev => {
      const cleaned = prev.filter(n => !pipelineSteps.includes(n.id as typeof pipelineSteps[number]));
      const newNodes: Node<PipelineNodeData>[] = pipelineSteps.map(step => ({
        id: step,
        type: 'pipeline',
        position: pipePositions[step],
        data: {
          agentId: step,
          step,
          label: step.charAt(0).toUpperCase() + step.slice(1),
        },
        draggable: true,
      }));
      return [...cleaned, ...newNodes];
    });

    setAllEdges(prev => {
      const cleaned = prev.filter(e => !e.id.startsWith('pipe-'));
      const newEdges: Edge[] = pipeEdges.map(pe => ({
        id: pe.id,
        source: pe.source,
        target: pe.target,
        type: 'telemetry',
        animated: true,
        style: { stroke: 'rgba(139,92,246,0.15)', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(139,92,246,0.3)', width: 8, height: 8 },
        data: { edgeId: pe.id, label: '', sourceId: pe.source, targetId: pe.target },
      }));
      return [...cleaned, ...newEdges];
    });

    // Create/update EntityNode
    const existingEntityIdx = allNodes.findIndex(n => n.id === entityId);

    if (existingEntityIdx >= 0) {
      setAllNodes(prev => prev.map(n => {
        if (n.id === entityId) {
          return {
            ...n,
            data: { ...n.data, status: 'running', filepath: filepath || (n.data as unknown as EntityNodeData).filepath } as EntityNodeData,
          };
        }
        return n;
      }));
    } else {
      const entityNode: Node<EntityNodeData> = {
        id: entityId,
        type: 'entity',
        position: { x: 400, y: 180 },
        data: { entity: finalEntity, status: 'running', filepath: filepath || undefined },
        draggable: true,
      };
      setAllNodes(prev => [...prev, entityNode]);
    }

    try {
      const body: Record<string, string> = { entity: finalEntity };
      if (filepath) body.filepath = filepath;

      const res = await fetch('http://localhost:8000/api/mission/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Mission failed: ${res.status}`);
      const json = await res.json();

      setAllNodes(prev => prev.map(n => {
        if (n.id === entityId) {
          return {
            ...n,
            data: {
              ...n.data,
              status: 'done',
              report: json.report,
              reportMarkdown: json.report_markdown || json.report,
              verified: json.verified,
              criticScore: json.critic_score,
            } as EntityNodeData,
          };
        }
        return n;
      }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setAllNodes(prev => prev.map(n => {
        if (n.id === entityId) {
          return {
            ...n,
            data: {
              ...n.data,
              status: 'error',
              errorMessage: msg,
            } as EntityNodeData,
          };
        }
        return n;
      }));
    } finally {
      setIsMissionRunning(false);
      setMissionEntity(null);
      setPromptEntity('');
    }
  };

  const handlePromptSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = promptValue.trim();
    if (!trimmed) return;
    handleStartMission(trimmed);
    setPromptValue('');
  };

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--void)' }}>
      <Experience3D active={is3DMode} intensity={intensity} />
      <ChatBox />

      {/* Top bar */}
      <div style={s.bar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ fontSize: '24px' }}>🦅</div>
          <div>
            <h1 style={s.title}>TANGLE</h1>
            <p style={s.subtitle}>Untangle the world</p>
          </div>
        </div>

        <div style={s.divider} />

        <div style={{ flex: 1 }} />

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => { setShowIndex(!showIndex); if (!showIndex) { setShowTerminal(false); setShowLogs(false); setShowEntities(false); } }}
            style={{
              ...s.terminalBtn(showIndex),
              borderColor: showIndex ? '#a855f760' : 'var(--border)',
              color: showIndex ? '#a855f7' : 'var(--text-dim)',
            }}
            title="Memory index — live snapshot of SQLite, Qdrant, Supabase, filesystem"
          >
            INDEX
          </button>
          <button
            onClick={() => { setShowEntities(!showEntities); if (!showEntities) { setShowTerminal(false); setShowLogs(false); setShowIndex(false); } }}
            style={{
              ...s.terminalBtn(showEntities),
              borderColor: showEntities ? '#c084fc60' : 'var(--border)',
              color: showEntities ? '#c084fc' : 'var(--text-dim)',
            }}
            title="Entity browser — all entities with missions and files"
          >
            ENTITIES
          </button>
          <button
            onClick={() => { setShowTerminal(!showTerminal); if (!showTerminal) { setShowLogs(false); setShowIndex(false); setShowEntities(false); } }}
            style={s.terminalBtn(showTerminal)}
          >
            CLI
          </button>
          <button
            onClick={() => { setShowLogs(!showLogs); if (!showLogs) { setShowTerminal(false); setShowIndex(false); setShowEntities(false); } }}
            style={{
              ...s.terminalBtn(showLogs),
              borderColor: showLogs ? '#06b6d460' : 'var(--border)',
              color: showLogs ? '#06b6d4' : 'var(--text-dim)',
            }}
          >
            LOGS
          </button>
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            colorMode="light"
            fitView
            fitViewOptions={{ padding: 0.5, duration: 800 }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Background variant={BackgroundVariant.Lines} gap={60} size={1} color="rgba(0,0,0,0.02)" />
            <Controls />
            <MiniMap />
          </ReactFlow>

          {/* ─── Drop Zone Overlay ──────────────────────────── */}
          {isDragging && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                zIndex: 100,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(139,92,246,0.08)',
                backdropFilter: 'blur(4px)',
                border: '2px dashed rgba(139,92,246,0.5)',
                borderRadius: 16,
                margin: 8,
                pointerEvents: 'none',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📂</div>
                <div style={{
                  fontSize: 18, fontWeight: 800,
                  color: '#c084fc',
                  letterSpacing: '-0.02em',
                }}>
                  Drop files here
                </div>
                <div style={{
                  fontSize: 11, color: 'rgba(255,255,255,0.4)',
                  marginTop: 6, fontFamily: 'JetBrains Mono, monospace',
                }}>
                  PDF · DOCX · XLSX · TXT · PNG · JPG
                </div>
              </div>
            </div>
          )}

          {/* ─── Floating Prompt ────────────────────────────── */}
          <form
            onSubmit={handlePromptSubmit}
            style={{
              position: 'absolute',
              bottom: 32,
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 80,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(15,15,30,0.85)',
              backdropFilter: 'blur(20px) saturate(180%)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 16,
              padding: '6px 6px 6px 18px',
              boxShadow: '0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(139,92,246,0.1)',
            }}
          >
            {promptEntity && !promptValue && (
              <span style={{
                fontSize: 11, fontWeight: 700,
                color: '#c084fc',
                background: 'rgba(139,92,246,0.12)',
                padding: '3px 10px', borderRadius: 8,
                border: '1px solid rgba(139,92,246,0.25)',
              }}>
                🎯 {promptEntity}
              </span>
            )}
            <input
              type="text"
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder={
                isUploading ? 'Uploading…' :
                isMissionRunning ? currentMissionStep || `Helping ${missionEntity}…` :
                'Help [entity]'
              }
              disabled={isUploading || isMissionRunning}
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                fontFamily: 'JetBrains Mono, monospace',
                width: 220,
              }}
            />
            <button
              type="submit"
              disabled={isUploading || isMissionRunning || !promptValue.trim()}
              style={{
                padding: '8px 18px',
                borderRadius: 12,
                border: 'none',
                background: promptValue.trim()
                  ? 'linear-gradient(135deg, #8b5cf6, #06b6d4)'
                  : 'rgba(255,255,255,0.06)',
                color: promptValue.trim() ? '#fff' : 'rgba(255,255,255,0.3)',
                fontSize: 12,
                fontWeight: 700,
                cursor: promptValue.trim() && !isUploading && !isMissionRunning ? 'pointer' : 'default',
                transition: 'all 0.3s',
                letterSpacing: '0.02em',
              }}
            >
              {isUploading ? '⏳' : isMissionRunning ? '⚡' : '🚀'}
            </button>
          </form>

          {/* Upload status indicator */}
          {isUploading && (
            <div style={{
              position: 'absolute',
              top: 20,
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 80,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(15,15,30,0.85)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(245,158,11,0.3)',
              borderRadius: 10,
              padding: '8px 20px',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#f59e0b',
                animation: 'pulse-glow 1s ease-in-out infinite',
              }} />
              <span style={{
                fontSize: 11, fontWeight: 700,
                color: '#f59e0b',
                fontFamily: 'JetBrains Mono, monospace',
              }}>
                Uploading file…
              </span>
            </div>
          )}
        </div>

        {/* Side panel */}
        <div
          style={{
            borderLeft: '1px solid var(--border)',
            background: 'var(--surface)',
            transition: 'width 0.3s',
            overflow: 'hidden',
            flexShrink: 0,
            width: showTerminal || showLogs || showIndex || showEntities ? SIDE_PANEL_WIDTH : 0,
          }}
        >
          {showIndex && (
            <div style={{ width: SIDE_PANEL_WIDTH, height: '100%', overflow: 'hidden' }}>
              <ErrorBoundary>
                <IndexPanel />
              </ErrorBoundary>
            </div>
          )}
          {showTerminal && (
            <div style={{ width: SIDE_PANEL_WIDTH, height: '100%', overflow: 'hidden' }}>
              <ErrorBoundary>
                <CliHarness />
              </ErrorBoundary>
            </div>
          )}
          {showEntities && (
            <div style={{ width: SIDE_PANEL_WIDTH, height: '100%', overflow: 'hidden' }}>
              <ErrorBoundary>
                <EntitySelector
                  activeEntity={activeEntity}
                  onSelectEntity={(name) => {
                    setActiveEntity(name);
                    setPromptValue(name);
                    setPromptEntity(name);
                    // Ensure entity node exists on canvas
                    const eid = `entity-${name.toLowerCase().replace(/\s+/g, '-')}`;
                    setAllNodes(prev => prev.some(n => n.id === eid) ? prev : [...prev, {
                      id: eid,
                      type: 'entity',
                      position: { x: 300 + Math.random() * 200, y: 100 + Math.random() * 200 },
                      data: { entity: name, status: 'idle' },
                      draggable: true,
                    } as Node<EntityNodeData>]);
                  }}
                  onStartMission={(name) => handleStartMission(name)}
                />
              </ErrorBoundary>
            </div>
          )}
          {showLogs && (
            <div style={{ width: SIDE_PANEL_WIDTH, height: '100%', overflow: 'hidden' }}>
              <ErrorBoundary>
                <AgentVerbosePanel />
              </ErrorBoundary>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <TangleCanvas />
    </ReactFlowProvider>
  );
}
