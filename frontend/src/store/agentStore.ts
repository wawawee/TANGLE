import { format } from 'date-fns';
import { create } from 'zustand';

export type AgentStatus = 'idle' | 'thinking' | 'executing' | 'error' | 'done';

export interface TelemetryEvent {
  id: string;
  timestamp: string;
  from: string;
  to: string;
  type: 'delegate' | 'vector_search' | 'api_call' | 'memory_read' | 'memory_write' | 'kill_action' | 'alert';
  label: string;
  latency: number;
  payload?: string;
  status: 'ok' | 'warn' | 'error';
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu: number;
  memory: number;
  user: string;
  status: string;
  rss: number;
  vsz: number;
  started: string;
}

export interface SystemMetrics {
  totalRam: number;
  freeRam: number;
  cpuUsage: number;
  processes: ProcessInfo[];
  alerts: Array<{pid: number; name: string; reason: string; severity: 'warn' | 'critical'}>;
  timestamp: string;
}

export interface QdrantCollection {
  name: string;
  vectorCount: number;
  status: 'green' | 'yellow' | 'red';
  lastIndexed: string;
}

export interface BinItem {
  id: string;
  name: string;
  type: 'file' | 'package';
  deletedAt: string;
  deletedBy: string;
  content?: string;
}

export type ActiveFlow = 'none' | 'research_to_code' | 'security_sweep' | 'devops_deploy' | 'examination_eval' | 'system_guardian';

export interface AgentVerboseLog {
  agentId: string;
  events: Array<{
    type: 'think' | 'tool_call' | 'tool_result' | 'complete' | 'error' | 'delegate' | 'workflow_step';
    message: string;
    ts: number;
  }>;
}

interface AgentStore {
  agentStatuses: Record<string, AgentStatus>;
  activeEdges: Set<string>;
  telemetryLog: TelemetryEvent[];
  activeFlow: ActiveFlow;
  systemMetrics: SystemMetrics | null;
  qdrantCollections: QdrantCollection[];
  binItems: BinItem[];
  selectedNodeId: string | null;
  isPanelOpen: boolean;
  isSystemPanelOpen: boolean;

  visibleNodes: Set<string>;
  visibleEdges: Set<string>;
  is3DMode: boolean;
  intensity: number;

  verboseLogs: Record<string, string[]>;
  gatewayStatus: { openrouter: boolean; gemini: boolean };
  wsConnected: boolean;

  setAgentStatus: (agentId: string, status: AgentStatus) => void;
  setActiveEdge: (edgeId: string, active: boolean) => void;
  addTelemetryEvent: (event: Omit<TelemetryEvent, 'id' | 'timestamp'>) => void;
  clearTelemetry: () => void;
  setActiveFlow: (flow: ActiveFlow) => void;
  setSystemMetrics: (metrics: SystemMetrics) => void;
  setQdrantCollections: (collections: QdrantCollection[]) => void;
  addBinItem: (item: Omit<BinItem, 'id'>) => void;
  restoreFromBin: (id: string) => void;
  setSelectedNode: (id: string | null) => void;
  togglePanel: () => void;
  toggleSystemPanel: () => void;
  set3DMode: (active: boolean) => void;
  setVisibleNode: (id: string) => void;
  setVisibleEdge: (id: string) => void;
  resetVisibility: () => void;
  runFlow: (flow: ActiveFlow) => void;
  addVerboseLog: (agentId: string, message: string) => void;
  connectWs: () => void;
  executeAgent: (agentId: string, task: string) => void;
}

const MOCK_QDRANT_COLLECTIONS: QdrantCollection[] = [
  { name: 'research_memories', vectorCount: 1247, status: 'green', lastIndexed: '2026-03-05T01:30:00Z' },
  { name: 'architecture_memories', vectorCount: 892, status: 'green', lastIndexed: '2026-03-05T00:45:00Z' },
  { name: 'code_memories', vectorCount: 3401, status: 'green', lastIndexed: '2026-03-05T01:15:00Z' },
  { name: 'qa_memories', vectorCount: 567, status: 'yellow', lastIndexed: '2026-03-04T22:00:00Z' },
  { name: 'security_memories', vectorCount: 2089, status: 'green', lastIndexed: '2026-03-05T01:50:00Z' },
  { name: 'data_memories', vectorCount: 1104, status: 'green', lastIndexed: '2026-03-05T01:00:00Z' },
  { name: 'devops_memories', vectorCount: 743, status: 'green', lastIndexed: '2026-03-04T23:30:00Z' },
  { name: 'ux_memories', vectorCount: 318, status: 'yellow', lastIndexed: '2026-03-04T20:00:00Z' },
  { name: 'docs_memories', vectorCount: 629, status: 'green', lastIndexed: '2026-03-05T00:00:00Z' },
  { name: 'debug_memories', vectorCount: 1876, status: 'green', lastIndexed: '2026-03-05T01:45:00Z' },
  { name: 'performance_memories', vectorCount: 441, status: 'green', lastIndexed: '2026-03-05T00:30:00Z' },
  { name: 'integration_memories', vectorCount: 958, status: 'green', lastIndexed: '2026-03-05T01:10:00Z' },
  { name: 'orchestrator_memories', vectorCount: 2231, status: 'green', lastIndexed: '2026-03-05T01:55:00Z' },
  { name: 'package_memories', vectorCount: 187, status: 'green', lastIndexed: '2026-03-04T19:00:00Z' },
  { name: 'examination_memories', vectorCount: 94, status: 'green', lastIndexed: '2026-03-05T01:00:00Z' },
  { name: 'system_memories', vectorCount: 512, status: 'green', lastIndexed: '2026-03-05T01:57:00Z' },
];

let eventCounter = 0;
let ws: WebSocket | null = null;

export const useAgentStore = create<AgentStore>((set, get) => ({
  agentStatuses: {},
  activeEdges: new Set(),
  visibleNodes: new Set(['orchestrator']), // Orchestrator is always visible
  visibleEdges: new Set(),
  telemetryLog: [],
  activeFlow: 'none',
  systemMetrics: null,
  qdrantCollections: MOCK_QDRANT_COLLECTIONS,
  binItems: [],
  selectedNodeId: null,
  isPanelOpen: true,
  isSystemPanelOpen: false,
  is3DMode: false,
  intensity: 0,
  verboseLogs: {},
  gatewayStatus: { openrouter: false, gemini: false },
  wsConnected: false,

  setAgentStatus: (agentId, status) =>
    set(s => ({ agentStatuses: { ...s.agentStatuses, [agentId]: status } })),

  setActiveEdge: (edgeId, active) =>
    set(s => {
      const edges = new Set(s.activeEdges);
      if (active) edges.add(edgeId); else edges.delete(edgeId);
      return { activeEdges: edges };
    }),

  addVerboseLog: (agentId, message) =>
    set(s => {
      const logs = { ...s.verboseLogs };
      if (!logs[agentId]) logs[agentId] = [];
      logs[agentId] = [...logs[agentId].slice(-49), message];
      return { verboseLogs: logs };
    }),

  connectWs: () => {
    if (ws?.readyState === WebSocket.OPEN) return;
    try {
      ws = new WebSocket('ws://localhost:8000/api/ws/agents');
      ws.onopen = () => set({ wsConnected: true });
      ws.onclose = () => set({ wsConnected: false });
      ws.onmessage = (ev: MessageEvent) => {
        try {
          const event = JSON.parse(ev.data);
          const store = get();
          const aid = event.agent_id || 'system';
          store.addVerboseLog(aid, event.type + ': ' + JSON.stringify(event).slice(0, 120));
          if (event.type === 'agent_start') {
            store.setAgentStatus(aid, 'thinking');
            store.setVisibleNode(aid === '13' ? 'orchestrator' : `agent-${aid}`);
            store.setVisibleEdge(`e-orch-${aid}`);
          } else if (event.type === 'agent_think') {
            store.setAgentStatus(aid, 'thinking');
          } else if (event.type === 'tool_call') {
            store.setAgentStatus(aid, 'executing');
          } else if (event.type === 'agent_complete') {
            store.setAgentStatus(aid, 'done');
            setTimeout(() => store.setAgentStatus(aid, 'idle'), 3000);
          } else if (event.type === 'agent_error') {
            store.setAgentStatus(aid, 'error');
          } else if (event.type === 'workflow_step') {
            store.setAgentStatus(aid, 'thinking');
          }
        } catch {}
      };
    } catch {}
  },

  executeAgent: (agentId, task) => {
    const store = get();
    store.connectWs();
    store.setAgentStatus(agentId, 'thinking');
    store.addVerboseLog(agentId, `TASK: ${task}`);
    fetch('http://localhost:8000/api/agents/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId, task }),
    }).then(r => r.json()).then(res => {
      if (res.error) {
        store.addVerboseLog(agentId, `ERROR: ${res.error}`);
        store.setAgentStatus(agentId, 'error');
      } else {
        store.addVerboseLog(agentId, `DONE: ${(res.result || '').slice(0, 200)}`);
        store.setAgentStatus(agentId, 'done');
        setTimeout(() => store.setAgentStatus(agentId, 'idle'), 3000);
      }
    }).catch(err => {
      store.addVerboseLog(agentId, `FETCH ERROR: ${err.message}`);
      store.setAgentStatus(agentId, 'error');
    });
  },

  addTelemetryEvent: (event) => {
    const full: TelemetryEvent = {
      ...event,
      id: `evt-${++eventCounter}`,
      timestamp: format(new Date(), 'HH:mm:ss.SSS'),
    };
    set(s => ({ telemetryLog: [full, ...s.telemetryLog].slice(0, 200) }));
  },

  clearTelemetry: () => set({ telemetryLog: [] }),

  setActiveFlow: (flow) => set({ activeFlow: flow }),

  setSystemMetrics: (metrics) => set({ systemMetrics: metrics }),

  setQdrantCollections: (collections) => set({ qdrantCollections: collections }),

  addBinItem: (item) => {
    const full: BinItem = { ...item, id: `bin-${Date.now()}` };
    set(s => ({ binItems: [...s.binItems, full] }));
  },

  restoreFromBin: (id) =>
    set(s => ({ binItems: s.binItems.filter(i => i.id !== id) })),

  setSelectedNode: (id) => set({ selectedNodeId: id }),
  togglePanel: () => set(s => ({ isPanelOpen: !s.isPanelOpen })),
  toggleSystemPanel: () => set(s => ({ isSystemPanelOpen: !s.isSystemPanelOpen })),

  set3DMode: (active) => set({ is3DMode: active }),
  setVisibleNode: (id) => set(s => {
    const next = new Set(s.visibleNodes);
    next.add(id);
    return { visibleNodes: next };
  }),
  setVisibleEdge: (id) => set(s => {
    const next = new Set(s.visibleEdges);
    next.add(id);
    return { visibleEdges: next };
  }),
  resetVisibility: () => set({ visibleNodes: new Set(['orchestrator']), visibleEdges: new Set() }),

  runFlow: async (flow) => {
    const {
        setAgentStatus, setActiveEdge, addTelemetryEvent,
        setActiveFlow, set3DMode, setVisibleNode, setVisibleEdge, resetVisibility
    } = get();

    setActiveFlow(flow);
    resetVisibility();
    set3DMode(false);
    set({ intensity: 0 });

    // Reset all
    const resetAll = () => {
      ['01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16'].forEach(id =>
        setAgentStatus(id, 'idle')
      );
    };
    resetAll();

    const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

    // Helper to map agent internal IDs to canvas node IDs
    const nodeId = (id: string) => {
      if (id === '13') return 'orchestrator';
      if (id === 'qdrant' || id === 'supabase' || id === 'file-memory') return id;
      return `agent-${id}`;
    };

    const emit = async (from: string, to: string, edgeId: string, type: TelemetryEvent['type'], label: string, latency: number, payload?: string) => {
      const fromNodeId = nodeId(from);
      const toNodeId = nodeId(to);

      setVisibleNode(fromNodeId);
      setVisibleNode(toNodeId);
      setVisibleEdge(edgeId);

      setActiveEdge(edgeId, true);
      setAgentStatus(from, 'executing');
      setAgentStatus(to, 'thinking');

      // Wireshark-style preamble
      const hex = Array.from({length: 8}, () => Math.floor(Math.random()*256).toString(16).padStart(2, '0')).join(' ');
      addTelemetryEvent({
        from, to, type: 'api_call',
        label: `[SYN] SEQ=${Math.floor(Math.random()*10000)} LEN=0 WIN=65535`,
        latency: 0, status: 'ok',
        payload: `0x0000:  45 00 00 3c ${hex} 40 06 00 00`
      });
      await delay(100);

      addTelemetryEvent({ from, to, type, label, latency, payload, status: 'ok' });

      if (payload && payload.length > 20) {
          await delay(200);
          addTelemetryEvent({
            from, to, type: 'api_call',
            label: `[ACK] DATA_CHUNK_${Math.floor(Math.random()*100)} TRANSMITTED`,
            latency: 0, status: 'ok',
            payload: `DEBUG: Packet frame ${Math.floor(Math.random()*5000)} | TTL=64 | PROTO=TCP`
          });
      }

      await delay(latency + 100);
      setAgentStatus(from, 'done');
      setActiveEdge(edgeId, false);
    };

    if (flow === 'research_to_code') {
      addTelemetryEvent({ from: '13', to: '13', type: 'api_call', label: 'initializing flow: research_to_code', latency: 0, status: 'ok' });
      await emit('13', '01', 'e-orch-01', 'delegate', 'POST /delegate → SCOUT: Research query', 45, '{"task":"research_react_flow_v12","depth":4,"semantic_search":true}');
      setAgentStatus('01', 'executing');
      await delay(400);
      addTelemetryEvent({ from: '01', to: '01', type: 'api_call', label: 'SCOUT: Analyzing local context tokens...', latency: 150, status: 'ok' });
      await emit('01', 'qdrant', 'e-01-qdrant', 'vector_search', 'Vector Search (similarity=0.87) → research_memories', 234, '{"query":"react flow patterns","k":5,"filters":{"type":"architecture"}}');
      await emit('01', '02', 'e-01-02', 'delegate', 'POST /handoff → BLUEPRINT: Research package [HIGH] 3 findings', 847, '{"confidence":"HIGH","findings":3,"source_ids":["doc_77","kb_12"]}');
      await emit('02', '03', 'e-02-03', 'delegate', 'POST /handoff → FORGE: ADR-007 architecture decision', 234, '{"adr":"ADR-007","approved":true,"impact":"high"}');
      await emit('03', 'qdrant', 'e-03-qdrant', 'memory_write', 'PUT code_memories ← implementation artifact', 189, '{"tokens":2048,"compressed":true,"checksum":"sha256:e3b0c442..."}');
      await emit('03', '04', 'e-03-04', 'delegate', 'POST /handoff → HAMMER: Code artifact for QA', 1102, '{"coverage_target":0.85,"artifact_id":"forge-001","lint_fixed":true}');
      await emit('04', '13', 'e-04-orch', 'api_call', 'POST /report → Orchestrator: QA PASS ✅ (coverage 87%)', 117, '{"status":"PASS","coverage":0.87,"tests_run":42,"failures":0}');
      await emit('13', '15', 'e-orch-15', 'delegate', 'POST /delegate → EXAMINATION: Evaluate research_to_code flow', 55, '{"audit_id":"eval_9982"}');
    }

    if (flow === 'security_sweep') {
      addTelemetryEvent({ from: '13', to: '13', type: 'api_call', label: 'initializing flow: security_sweep', latency: 0, status: 'ok' });
      await emit('13', '05', 'e-orch-05', 'delegate', 'POST /delegate → AEGIS: Full security sweep initiated', 45, '{"scope":"all_deps","recursive":true}');

      // HIGH INTENSITY DETECTED
      set({ intensity: 100 });
      set3DMode(true);
      addTelemetryEvent({ from: '13', to: '13', type: 'alert', label: '⚠️ HIGH INTENSITY PROCESSING: TRANSITIONING TO 3D VULNERABILITY CUBE', latency: 0, status: 'warn' });
      await delay(1200);

      setAgentStatus('05', 'executing');
      await delay(300);
      addTelemetryEvent({ from: '05', to: '05', type: 'api_call', label: 'AEGIS: Loading CVE database signatures...', latency: 400, status: 'ok' });
      await emit('05', 'qdrant', 'e-05-qdrant', 'vector_search', 'Vector Search → security_memories (CVE patterns)', 312, '{"query":"known_vulnerabilities","threshold":0.92,"limit":20}');
      addTelemetryEvent({ from: '05', to: '05', type: 'alert', label: '⚠️ WARN: 2 low-severity patterns matched in node_modules', latency: 0, status: 'warn', payload: 'Matched: prototype-pollution (0.88)' });
      await emit('05', '10', 'e-05-10', 'delegate', 'POST /handoff → Debugger: 3 suspicious patterns flagged', 892, '{"cvss_low":2,"cvss_med":0,"cvss_high":0,"flags":["suspicious_imports"]}');
      await emit('10', 'qdrant', 'e-10-qdrant', 'vector_search', 'Vector Search → debug_memories (pattern correlation)', 445, '{"correlate_with":"aegis_sweep_01"}');
      await emit('10', '15', 'e-10-15', 'delegate', 'POST /report → EXAMINATION: Debug analysis complete', 2100, '{"root_cause":"stale_dep","fix":"npm audit fix","verified":true}');
      await emit('15', '13', 'e-15-orch', 'api_call', 'POST /report → Orchestrator: EXAM COMPLETE — 2 LOW issues', 67, '{"verdict":"HEALTHY_WITH_WARNINGS","security_score":92}');
    }

    if (flow === 'system_guardian') {
      addTelemetryEvent({ from: '13', to: '13', type: 'api_call', label: 'initializing flow: system_guardian', latency: 0, status: 'ok' });
      setAgentStatus('16', 'executing');
      addTelemetryEvent({ from: '16', to: '16', type: 'api_call', label: 'GET /api/system/metrics — polling macOS ps aux', latency: 120, status: 'ok', payload: 'USER PID %CPU %MEM VSZ RSS TT STAT STARTED TIME COMMAND' });
      await delay(500);
      addTelemetryEvent({ from: '16', to: '16', type: 'alert', label: '🔴 CRITICAL: PID 8412 "node" consuming 87% CPU for 45s', latency: 0, status: 'warn', payload: 'THRESHOLD_EXCEEDED: CPU > 85%' });
      await delay(300);
      await emit('16', '13', 'e-16-orch', 'delegate', 'POST /escalate → Orchestrator: Kill approval needed PID 8412', 89, '{"pid":8412,"process":"node","cpu":87,"ram_mb":1240,"load_avg":4.2}');
      await emit('13', '16', 'e-orch-16', 'delegate', 'POST /approve → WATCHDOG: Kill approved — SIGTERM first', 34, '{"approved":true,"signal":"SIGTERM","auth_token":"MASTER_7721"}');
      addTelemetryEvent({ from: '16', to: '16', type: 'kill_action', label: 'kill -SIGTERM 8412 → waiting 5s... → SIGKILL', latency: 5000, status: 'ok', payload: 'SIGNAL Sent: 15 (SIGTERM)' });
      await delay(400);
      addTelemetryEvent({ from: '16', to: '16', type: 'api_call', label: 'kill -SIGKILL 8412 verified', latency: 0, status: 'ok' });
      await delay(400);
      addTelemetryEvent({ from: '16', to: '16', type: 'memory_write', label: 'MEMORY.md ← Kill log entry appended', latency: 12, status: 'ok', payload: '{"log_entry":"PID 8412 terminated. Saved 1.2GB RAM"}' });
      await emit('16', '15', 'e-16-15', 'delegate', 'POST /report → EXAMINATION: Kill action logged', 67, '{"pid_killed":8412,"freed_ram_mb":1240,"exit_code":0}');
    }

    if (flow === 'devops_deploy') {
      addTelemetryEvent({ from: '13', to: '13', type: 'api_call', label: 'initializing flow: devops_deploy', latency: 0, status: 'ok' });
      await emit('13', '14', 'e-orch-14', 'delegate', 'POST /delegate → PackageManager: Audit + update cycle', 45, '{"env":"production"}');
      setAgentStatus('14', 'executing');
      await delay(500);
      addTelemetryEvent({ from: '14', to: '14', type: 'api_call', label: 'npm audit — scanning 847 packages...', latency: 2300, status: 'ok', payload: 'found 0 vulnerabilities' });
      addTelemetryEvent({ from: '14', to: '14', type: 'alert', label: '⚠️ 3 packages outdated → scheduling update', latency: 0, status: 'warn', payload: 'outdated: vite, react, lucide-react' });
      await emit('14', '07', 'e-14-07', 'delegate', 'POST /handoff → DevOps: Dependency manifest updated', 234, '{"updated":3,"deleted":0,"lockfile_version":3}');
      await emit('07', '11', 'e-07-11', 'delegate', 'POST /handoff → PerfTuner: Post-deploy baseline check', 1100, '{"deploy_id":"dep-0042","target_latency":100}');
      await emit('11', 'qdrant', 'e-11-qdrant', 'memory_write', 'PUT performance_memories ← new baseline metrics', 178, '{"p95_latency_ms":87,"throughput_rps":450}');
      await emit('11', '15', 'e-11-15', 'delegate', 'POST /report → EXAMINATION: Deploy complete, perf nominal', 234, '{"p95_latency_ms":87,"status":"OPTIMIZED"}');
    }

    if (flow === 'examination_eval') {
      addTelemetryEvent({ from: '13', to: '13', type: 'api_call', label: 'initializing flow: examination_eval', latency: 0, status: 'ok' });
      setAgentStatus('15', 'executing');
      addTelemetryEvent({ from: '15', to: '15', type: 'memory_read', label: 'Reading TASKLIST.md — 4 completed flows found', latency: 34, status: 'ok', payload: 'Flows detected: research, security, guardian, deploy' });
      await delay(400);
      ['01','02','03','04','05','06','07','08','09','10','11','12','13','14','16'].forEach((id, i) => {
        setTimeout(() => {
          addTelemetryEvent({ from: '15', to: id, type: 'memory_read', label: `GET agent-${id}/MEMORY.md → reading telemetry`, latency: Math.floor(Math.random()*100)+20, status: 'ok', payload: `FRAME_CHUNK_${i} [READ_COMPLETE]` });
          setActiveEdge(`e-15-${id}`, true);
          setTimeout(() => setActiveEdge(`e-15-${id}`, false), 600);
        }, i * 200);
      });
      await delay(3500);
      addTelemetryEvent({ from: '15', to: '15', type: 'memory_write', label: 'TASKLIST.md ← EXAM-003 appended: 15 agents nominal', latency: 23, status: 'ok', payload: '{"status":"HEALTHY","timestamp":1709614210}' });
      await emit('15', '13', 'e-15-orch', 'api_call', 'POST /report → Orchestrator: Full eval HEALTHY 🟢', 78, '{"agents_checked":16,"issues":0,"verdict":"STABLE"}');
    }

    await delay(500);
    resetAll();
    setActiveFlow('none');
  },
}));
