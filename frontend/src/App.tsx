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
    type Edge,
    type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useEffect, useState } from 'react';

import AgentVerbosePanel from './components/AgentVerbosePanel';
import ChatBox from './components/ChatBox';
import CliHarness from './components/CliHarness';
import EdgeTelemetry from './components/EdgeTelemetry';
import Experience3D from './components/Experience3D';
import AgentNode from './nodes/AgentNode';
import MemoryNode from './nodes/MemoryNode';
import OrchestratorNode from './nodes/OrchestratorNode';
import SystemGuardianNode from './nodes/SystemGuardianNode';
import type { ActiveFlow } from './store/agentStore';
import { useAgentStore } from './store/agentStore';

// ─── Node Types ───────────────────────────────────────────────
const NODE_TYPES = {
  agent: AgentNode,
  orchestrator: OrchestratorNode,
  systemGuardian: SystemGuardianNode,
  memory: MemoryNode,
};

const EDGE_TYPES = {
  telemetry: EdgeTelemetry,
};

// ─── Agent Definitions ────────────────────────────────────────
const AGENTS = [
  { id: '01', name: 'Scout',     codename: 'SCOUT',    role: 'Researcher',           collection: 'research_memories' },
  { id: '02', name: 'Blueprint', codename: 'BLUEPRINT', role: 'Architect',            collection: 'architecture_memories' },
  { id: '03', name: 'Forge',     codename: 'FORGE',    role: 'Code Writer',          collection: 'code_memories' },
  { id: '04', name: 'Hammer',    codename: 'HAMMER',   role: 'QA Engineer',          collection: 'qa_memories' },
  { id: '05', name: 'Aegis',     codename: 'AEGIS',    role: 'Security Sentinel',    collection: 'security_memories' },
  { id: '06', name: 'Pipeline',  codename: 'PIPELINE', role: 'Data Engineer',        collection: 'data_memories' },
  { id: '07', name: 'Launcher',  codename: 'LAUNCHER', role: 'DevOps Runner',        collection: 'devops_memories' },
  { id: '08', name: 'Canvas',    codename: 'CANVAS',   role: 'UX Designer',          collection: 'ux_memories' },
  { id: '09', name: 'Scribe',    codename: 'SCRIBE',   role: 'Technical Writer',     collection: 'docs_memories' },
  { id: '10', name: 'Tracer',    codename: 'TRACER',   role: 'Debugger',             collection: 'debug_memories' },
  { id: '11', name: 'Turbo',     codename: 'TURBO',    role: 'Performance Tuner',    collection: 'performance_memories' },
  { id: '12', name: 'Bridge',    codename: 'BRIDGE',   role: 'Integration Specialist', collection: 'integration_memories' },
  { id: '14', name: 'Packager',  codename: 'PACKAGER', role: 'Package Manager',      collection: 'package_memories' },
  { id: '15', name: 'Inspector', codename: 'INSPECTOR', role: 'Examination Agent',   collection: 'examination_memories' },
];

// ─── Canvas Layout ─────────────────────────────────────────────
const makeNodes = (): Node[] => {
  const nodes: Node[] = [];

  nodes.push({
    id: 'orchestrator',
    type: 'orchestrator',
    position: { x: 700, y: 460 },
    data: {},
    draggable: true,
  });

  nodes.push({
    id: 'qdrant',
    type: 'memory',
    position: { x: 700, y: 80 },
    data: { nodeType: 'qdrant', label: 'Qdrant Cloud' },
    draggable: true,
  });

  nodes.push({
    id: 'supabase',
    type: 'memory',
    position: { x: 1320, y: 560 },
    data: { nodeType: 'supabase', label: 'Supabase DB' },
    draggable: true,
  });

  nodes.push({
    id: 'file-memory',
    type: 'memory',
    position: { x: 60, y: 80 },
    data: { nodeType: 'file', label: 'Markdown Files' },
    draggable: true,
  });

  nodes.push({
    id: 'agent-16',
    type: 'systemGuardian',
    position: { x: 1320, y: 300 },
    data: {},
    draggable: true,
  });

  const ring1 = ['01', '02', '03', '04', '05', '06', '07'];
  ring1.forEach((id, i) => {
    const agent = AGENTS.find(a => a.id === id)!;
    nodes.push({
      id: `agent-${id}`,
      type: 'agent',
      position: { x: 60 + i * 230, y: 280 },
      data: { agentId: id, ...agent },
      draggable: true,
    });
  });

  const ring2 = ['08', '09', '10', '11', '12', '14', '15'];
  ring2.forEach((id, i) => {
    const agent = AGENTS.find(a => a.id === id)!;
    nodes.push({
      id: `agent-${id}`,
      type: 'agent',
      position: { x: 60 + i * 230, y: 680 },
      data: { agentId: id, ...agent },
      draggable: true,
    });
  });

  return nodes;
};

const BASE_MARKER = {
  type: MarkerType.ArrowClosed,
  color: 'var(--border-bright)',
  width: 10,
  height: 10,
};

const makeEdges = (): Edge[] => {
  const e: Edge[] = [];

  const connect = (source: string, target: string, id: string, label = '', color?: string) =>
    e.push({
      id, source, target,
      type: 'telemetry',
      data: { edgeId: id, label, color, sourceId: source, targetId: target },
      markerEnd: { ...BASE_MARKER, color: color || 'var(--border-bright)' },
      animated: false,
    });

  AGENTS.forEach(a => {
    connect('orchestrator', `agent-${a.id}`, `e-orch-${a.id}`, `Delegate → ${a.codename}`);
    connect(`agent-${a.id}`, 'orchestrator', `e-${a.id}-orch`, `Report → Maestro`);
  });

  connect('orchestrator', 'agent-16', 'e-orch-16', 'Approve → WATCHDOG');
  connect('agent-16', 'orchestrator', 'e-16-orch', 'Escalate → Maestro');

  AGENTS.forEach(a => connect(`agent-${a.id}`, 'qdrant', `e-${a.id}-qdrant`, 'Vector Search'));
  connect('agent-16', 'qdrant', 'e-16-qdrant', 'Memory Write');

  ['07', '12', '06', '14'].forEach(id => connect(`agent-${id}`, 'supabase', `e-${id}-sb`, 'SQL Query'));

  ['09', '01', '02', '15'].forEach(id => connect(`agent-${id}`, 'file-memory', `e-${id}-fm`, 'Read Markdown'));
  connect('agent-15', 'file-memory', 'e-15-fm', 'Write TASKLIST');

  connect('agent-01', 'agent-02', 'e-01-02', 'POST /handoff → Research package');
  connect('agent-02', 'agent-03', 'e-02-03', 'POST /handoff → ADR decision');
  connect('agent-03', 'agent-04', 'e-03-04', 'POST /handoff → Code artifact');
  connect('agent-05', 'agent-10', 'e-05-10', 'POST /handoff → CVE patterns');
  connect('agent-10', 'agent-15', 'e-10-15', 'POST /report → Debug analysis');
  connect('agent-14', 'agent-07', 'e-14-07', 'POST /handoff → Updated manifest');
  connect('agent-07', 'agent-11', 'e-07-11', 'POST /handoff → Deploy complete');
  connect('agent-11', 'agent-15', 'e-11-15', 'POST /report → Perf baseline');
  connect('agent-15', 'orchestrator', 'e-15-orch', 'POST /report → Exam complete');
  connect('agent-16', 'agent-15', 'e-16-15', 'POST /report → Kill logged');

  return e;
};

const FLOW_OPTIONS: { id: ActiveFlow; label: string; desc: string; color: string }[] = [
  { id: 'research_to_code', label: '🔬 Research → Code', desc: 'Full feature build pipeline', color: '#06b6d4' },
  { id: 'security_sweep',   label: '🛡️ Security Sweep',  desc: 'CVE scan + debug analysis', color: '#ef4444' },
  { id: 'devops_deploy',    label: '📦 DevOps Deploy',   desc: 'Deps + deploy + perf check', color: '#f97316' },
  { id: 'examination_eval', label: '🔎 Full Examination', desc: 'Evaluation of all agents',  color: '#34d399' },
  { id: 'system_guardian',  label: '🖥️ System Guardian',  desc: 'macOS process monitor + kill', color: '#e879f9' },
];

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
  flowBtn: (active: boolean, color: string) => ({
    padding: '8px 16px', borderRadius: '16px', border: '1px solid',
    fontSize: '10px', fontWeight: 900, textTransform: 'uppercase' as const,
    letterSpacing: '0.05em', cursor: 'pointer',
    transition: 'all 0.3s',
    background: active ? '#fff' : 'var(--glass-bg)',
    borderColor: active ? `${color}40` : 'var(--border)',
    color: active ? '#7c3aed' : 'var(--text-dim)',
    boxShadow: active ? `0 0 0 4px ${color}15` : 'none',
    outline: 'none',
  }),
  resetBtn: {
    padding: '8px 12px', borderRadius: '16px', border: 'none',
    fontSize: '10px', fontWeight: 700, cursor: 'pointer',
    background: 'transparent', color: 'var(--text-muted)',
    outline: 'none',
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

function AnlagstavlanCanvas() {
  const [allNodes] = useState(makeNodes());
  const [allEdges] = useState(makeEdges());

  const {
    runFlow, activeFlow, visibleNodes, visibleEdges, is3DMode, intensity, resetVisibility
  } = useAgentStore();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [showTerminal, setShowTerminal] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    const filteredNodes = allNodes.filter(n => visibleNodes.has(n.id) || n.id === 'orchestrator');
    const filteredEdges = allEdges.filter(e => visibleEdges.has(e.id));
    setNodes(filteredNodes);
    setEdges(filteredEdges);
  }, [visibleNodes, visibleEdges, allNodes, allEdges, setNodes, setEdges]);

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--void)' }}>
      <Experience3D active={is3DMode} intensity={intensity} />
      <ChatBox />

      {/* Top bar */}
      <div style={s.bar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ fontSize: '24px' }}>🦅</div>
          <div>
            <h1 style={s.title}>ANLAGSTAVLAN</h1>
            <p style={s.subtitle}>Tactical Strategy Engine</p>
          </div>
        </div>

        <div style={s.divider} />

        <div style={{ display: 'flex', gap: '8px', flex: 1 }}>
          {FLOW_OPTIONS.map(flow => (
            <button
              key={flow.id}
              onClick={() => runFlow(flow.id)}
              style={s.flowBtn(activeFlow === flow.id, flow.color)}
            >
              {flow.label}
            </button>
          ))}
          <button onClick={resetVisibility} style={s.resetBtn}>RESET</button>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => { setShowTerminal(!showTerminal); if (!showTerminal) setShowLogs(false); }}
            style={s.terminalBtn(showTerminal)}
          >
            CLI
          </button>
          <button
            onClick={() => { setShowLogs(!showLogs); if (!showLogs) setShowTerminal(false); }}
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
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            colorMode="light"
            fitView
            fitViewOptions={{ padding: 0.5, duration: 800 }}
          >
            <Background variant={BackgroundVariant.Lines} gap={60} size={1} color="rgba(0,0,0,0.02)" />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>

        {/* Side panel */}
        <div
          style={{
            borderLeft: '1px solid var(--border)',
            background: 'var(--surface)',
            transition: 'width 0.3s',
            overflow: 'hidden',
            flexShrink: 0,
            width: showTerminal || showLogs ? 520 : 0,
          }}
        >
          {showTerminal && (
            <div style={{ width: 520, height: '100%', overflow: 'hidden' }}>
              <CliHarness />
            </div>
          )}
          {showLogs && (
            <div style={{ width: 520, height: '100%', overflow: 'hidden' }}>
              <AgentVerbosePanel />
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
      <AnlagstavlanCanvas />
    </ReactFlowProvider>
  );
}
