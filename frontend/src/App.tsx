import { useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  useReactFlow,
  ReactFlowProvider,
  Panel
} from '@xyflow/react';
import type { Connection, Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { WhoNode } from './components/nodes/WhoNode';
import { DropNode } from './components/nodes/DropNode';
import { AgentNode } from './components/agentflow/AgentNode';
import { Settings, Activity, Moon, Sun, Brain, Database, MessageCircle, RotateCcw } from 'lucide-react';
import { getWittyResponse } from './services/gemini';
import { startMission } from './services/api';
import { useCaseState } from './hooks/useCaseState';
import { useWebSocket } from './hooks/useWebSocket';
import { EventLog } from './components/eventlog/EventLog';
import { ReportViewer } from './components/report/ReportViewer';
import { CaseStatus } from './types/case';

import { AdminDashboard } from './components/AdminDashboard';
import { AgentChat } from './components/admin/AgentChat';

const nodeTypes = {
  whoNode: WhoNode,
  dropNode: DropNode,
  agent: AgentNode
};

function FlowApp() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([
    {
      id: 'who-1',
      type: 'whoNode',
      position: { x: window.innerWidth / 2 - 320, y: window.innerHeight / 2 - 200 },
      data: { onSubmit: (id: string, value: string) => handleWhoSubmit(id, value), submitted: false }
    }
  ]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [showSidebar, setShowSidebar] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<'settings'>('settings');
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [isHoveringSettings, setIsHoveringSettings] = useState(false);
  const [deepResearch, setDeepResearch] = useState(false);
  const [tokenUsage, setTokenUsage] = useState<Record<string, any>>({});
  
  const {
    caseState,
    updateProgress,
    addAgentThought,
    addEventLog,
    setDeliverables,
    resetCase
  } = useCaseState();
  
  const { connect, sendMessage, isConnected } = useWebSocket({
    onProgress: updateProgress,
    onAgentThought: addAgentThought,
    onEventLog: addEventLog,
    onTokenUsage: (usage) => {
      setTokenUsage(prev => ({
        ...prev,
        [usage.agentId]: {
          promptTokens: (prev[usage.agentId]?.promptTokens || 0) + usage.promptTokens,
          completionTokens: (prev[usage.agentId]?.completionTokens || 0) + usage.completionTokens,
          totalTokens: (prev[usage.agentId]?.totalTokens || 0) + usage.totalTokens,
        }
      }));
    },
    onComplete: setDeliverables,
    onError: (err) => addEventLog('ERROR', 'System', err.message)
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 't' && isHoveringSettings) {
        setIsAdminMode(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isHoveringSettings]);

  const [pendingAnalysis, setPendingAnalysis] = useState<any>(null);

  useEffect(() => {
    if (isConnected && pendingAnalysis) {
      sendMessage('START_ANALYSIS', pendingAnalysis);
      setPendingAnalysis(null);
    }
  }, [isConnected, pendingAnalysis, sendMessage]);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.type === 'agent') {
          const agentData = caseState.agents.find(a => a.id === node.id);
          if (agentData) {
            return {
              ...node,
              data: {
                ...node.data,
                state: agentData.state,
                confidence: agentData.confidence,
                lastThought: agentData.lastThought,
                isActive: caseState.currentAgent === node.id
              }
            };
          }
        }
        return node;
      })
    );
  }, [caseState.agents, caseState.currentAgent, setNodes]);

  const { fitView } = useReactFlow();

  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('dark');
      document.body.classList.remove('light');
    } else {
      document.body.classList.remove('dark');
      document.body.classList.add('light');
    }
  }, [isDarkMode]);

  const handleWhoSubmit = async (nodeId: string, value: string) => {
    setNodes((nds) => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, submitted: true } } : n));

    const dropNodeId = `drop-${Date.now()}`;
    const sourceNode = nodes.find(n => n.id === nodeId);
    const newY = (sourceNode?.position.y || 0) + 300;
    const newX = (sourceNode?.position.x || 0) + 128;

    const newNode: Node = {
      id: dropNodeId,
      type: 'dropNode',
      position: { x: newX, y: newY },
      data: { 
        wittyText: 'Thinking...',
        onAnalyze: (id: string, evidence: any[]) => handleAnalyze(id, evidence)
      }
    };

    setNodes((nds) => [...nds, newNode]);
    setEdges((eds) => [...eds, {
      id: `e-${nodeId}-${dropNodeId}`,
      source: nodeId,
      target: dropNodeId,
      type: 'step',
      animated: true,
      style: { stroke: isDarkMode ? '#eee' : '#111', strokeWidth: 3 }
    }]);

    setTimeout(() => fitView({ padding: 0.2, duration: 800 }), 100);

    const wittyText = await getWittyResponse(value);
    setNodes((nds) => nds.map(n => n.id === dropNodeId ? { ...n, data: { ...n.data, wittyText } } : n));
  };

  const handleAnalyze = (nodeId: string, evidence: any[]) => {
    setNodes((nds) => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, submitted: true } } : n));

    const sourceNode = nodes.find(n => n.id === nodeId);
    const rightPanelWidth = 514;
    const safeRightEdge = window.innerWidth - rightPanelWidth - 80;

    const evidenceHeight = 200 + (evidence.length * 72);
    const baseX = Math.min(sourceNode?.position.x || 0, safeRightEdge - 500);
    const baseY = (sourceNode?.position.y || 0) + Math.max(400, evidenceHeight + 100);
    const spread = Math.min(360, (safeRightEdge - baseX) / 2 - 40);

    const newNodes: Node[] = [
      { id: 'coordinator', type: 'agent', position: { x: baseX, y: baseY }, data: { name: 'Coordinator Alpha', role: 'orchestrator', state: 'active' } },
      { id: 'context_weaver', type: 'agent', position: { x: baseX - spread, y: baseY + 220 }, data: { name: 'Context Weaver', role: 'analysis', state: 'idle' } },
      { id: 'echo_vault', type: 'agent', position: { x: Math.min(baseX + spread, safeRightEdge - 280), y: baseY + 220 }, data: { name: 'Echo Vault', role: 'memory', state: 'idle' } },
      { id: 'outcome_architect', type: 'agent', position: { x: baseX, y: baseY + 440 }, data: { name: 'Outcome Architect', role: 'strategy', state: 'idle' } },
      { id: 'chronicle_scribe', type: 'agent', position: { x: baseX - spread + 60, y: baseY + 660 }, data: { name: 'Chronicle Scribe', role: 'documentation', state: 'idle' } },
      { id: 'pulse_monitor', type: 'agent', position: { x: Math.min(baseX + spread - 60, safeRightEdge - 280), y: baseY + 660 }, data: { name: 'Pulse Monitor', role: 'telemetry', state: 'idle' } }
    ];

    const strokeColor = isDarkMode ? '#eee' : '#111';
    const newEdges: Edge[] = [
      { id: `e-${nodeId}-coordinator`, source: nodeId, target: 'coordinator', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 3 } },
      { id: 'e-c-cw', source: 'coordinator', target: 'context_weaver', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
      { id: 'e-c-ev', source: 'coordinator', target: 'echo_vault', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
      { id: 'e-cw-oa', source: 'context_weaver', target: 'outcome_architect', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
      { id: 'e-ev-oa', source: 'echo_vault', target: 'outcome_architect', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
      { id: 'e-oa-cs', source: 'outcome_architect', target: 'chronicle_scribe', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
      { id: 'e-oa-pm', source: 'outcome_architect', target: 'pulse_monitor', type: 'step', animated: true, style: { stroke: strokeColor, strokeWidth: 2 } },
    ];

    setNodes(nds => [...nds, ...newNodes]);
    setEdges(eds => [...eds, ...newEdges]);

    setTimeout(() => fitView({ padding: 0.2, duration: 800 }), 100);

    const query = evidence.map(e => e.content || e.preview).join('\n\n');
    setPendingAnalysis({ query, deepResearch });

    const caseId = `case-${Date.now()}`;

    startMission(query, caseId).catch(() => {});

    connect(`ws://localhost:8000/ws/swarm/${caseId}`);
  };

  const handleReset = () => {
    const centerX = window.innerWidth / 2 - 320;
    const centerY = window.innerHeight / 2 - 200;
    setNodes([
      {
        id: `who-${Date.now()}`,
        type: 'whoNode',
        position: { x: centerX, y: centerY },
        data: { onSubmit: (id: string, value: string) => handleWhoSubmit(id, value), submitted: false }
      }
    ]);
    setEdges([]);
    setTokenUsage({});
    setPendingAnalysis(null);
    setShowSidebar(false);
    setShowChat(false);
    setIsAdminMode(false);
    resetCase();
    setTimeout(() => fitView({ padding: 0.2, duration: 600 }), 50);
  };

  const onConnect = useCallback(
    (params: Connection | Edge) => setEdges((eds) => addEdge({ ...params, type: 'step', style: { stroke: isDarkMode ? '#eee' : '#111', strokeWidth: 3 } } as Edge, eds)),
    [setEdges, isDarkMode],
  );

  return (
    <div className="w-screen h-screen overflow-hidden relative transition-colors duration-300">
      {/* Progress bar */}
      {caseState.status !== CaseStatus.IDLE && (
        <div className="absolute bottom-12 left-1/2 -translate-x-1/2 w-[600px] max-w-[90vw] z-50 pointer-events-none">
          <div className="bg-white/60 dark:bg-black/60 backdrop-blur-md border-4 border-[#111] dark:border-[#eee] p-4 shadow-[8px_8px_0px_0px_rgba(17,17,17,0.3)] dark:shadow-[8px_8px_0px_0px_rgba(238,238,238,0.3)] flex flex-col space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-black uppercase tracking-wider text-[#111] dark:text-[#eee] flex items-center space-x-2">
                <Activity size={16} className="animate-pulse" />
                <span>{caseState.stage}</span>
              </span>
              <span className="text-sm font-mono font-bold text-[#111] dark:text-[#eee]">{Math.round(caseState.progress)}%</span>
            </div>
            <div className="w-full h-4 border-2 border-[#111] dark:border-[#eee] bg-white/50 dark:bg-black/50 overflow-hidden">
              <div 
                className="h-full bg-[#111] dark:bg-[#eee] transition-all duration-500 ease-out" 
                style={{ width: `${caseState.progress}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
        maxZoom={2}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2} color={isDarkMode ? "#333" : "#ccc"} />
        
        {/* Left panels: Event Log + Token Usage */}
        {caseState.status !== CaseStatus.IDLE && (
          <Panel position="top-left" className="w-[350px] max-h-[80vh] flex flex-col gap-4 pointer-events-none">
            <div className="flex-1 pointer-events-auto flex flex-col min-h-[300px]">
              <h3 className="font-bold uppercase mb-2 dark:text-[#eee] bg-white/80 dark:bg-black/80 backdrop-blur-sm inline-block px-2">Event Log</h3>
              <div className="flex-1 border-4 border-[#111] bg-white/90 backdrop-blur-md dark:border-[#eee] dark:bg-[#0a0a0a]/90 shadow-[8px_8px_0px_0px_rgba(17,17,17,0.3)] dark:shadow-[8px_8px_0px_0px_rgba(238,238,238,0.3)]">
                <EventLog 
                  entries={caseState.eventLog}
                  status={caseState.status}
                  progress={caseState.progress}
                  stage={caseState.stage}
                />
              </div>
            </div>

            <div className="flex-1 pointer-events-auto flex flex-col min-h-[250px]">
              <h3 className="font-bold uppercase mb-2 dark:text-[#eee] bg-white/80 dark:bg-black/80 backdrop-blur-sm inline-block px-2">Token Usage</h3>
              <div className="flex-1 border-4 border-[#111] bg-white/90 backdrop-blur-md dark:border-[#eee] dark:bg-[#0a0a0a]/90 p-4 overflow-y-auto shadow-[8px_8px_0px_0px_rgba(17,17,17,0.3)] dark:shadow-[8px_8px_0px_0px_rgba(238,238,238,0.3)]">
                {Object.keys(tokenUsage).length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-500 font-mono text-sm uppercase">
                    No usage data yet
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(tokenUsage).map(([agentId, usage]) => (
                      <div key={agentId} className="border-b-2 border-gray-200 dark:border-gray-800 pb-2">
                        <div className="font-bold text-sm uppercase mb-1 dark:text-[#eee]">{agentId}</div>
                        <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                          <div className="flex flex-col">
                            <span className="text-gray-500">Prompt</span>
                            <span className="dark:text-[#eee]">{usage.promptTokens.toLocaleString()}</span>
                          </div>
                          <div className="flex flex-col">
                            <span className="text-gray-500">Completion</span>
                            <span className="dark:text-[#eee]">{usage.completionTokens.toLocaleString()}</span>
                          </div>
                          <div className="flex flex-col">
                            <span className="text-gray-500">Total</span>
                            <span className="font-bold dark:text-[#eee]">{usage.totalTokens.toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                    <div className="pt-2 mt-2 border-t-4 border-[#111] dark:border-[#eee]">
                      <div className="font-black text-sm uppercase mb-1 dark:text-[#eee]">Total Swarm Usage</div>
                      <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                        <div className="flex flex-col">
                          <span className="text-gray-500">Prompt</span>
                          <span className="dark:text-[#eee]">{Object.values(tokenUsage).reduce((acc: number, curr: any) => acc + curr.promptTokens, 0).toLocaleString()}</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-gray-500">Completion</span>
                          <span className="dark:text-[#eee]">{Object.values(tokenUsage).reduce((acc: number, curr: any) => acc + curr.completionTokens, 0).toLocaleString()}</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-gray-500">Total</span>
                          <span className="font-bold dark:text-[#eee]">{Object.values(tokenUsage).reduce((acc: number, curr: any) => acc + curr.totalTokens, 0).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </Panel>
        )}

        {/* Right panel: Strategy/Report */}
        {caseState.status !== CaseStatus.IDLE && (
          <Panel position="top-right" className="w-[450px] max-h-[80vh] pointer-events-none mr-16">
            <div className="pointer-events-auto flex flex-col h-full min-h-[400px]">
              <h3 className="font-bold uppercase mb-2 dark:text-[#eee] bg-white/80 dark:bg-black/80 backdrop-blur-sm inline-block px-2">Strategy</h3>
              <div className="flex-1 border-4 border-[#111] bg-white/90 backdrop-blur-md overflow-hidden dark:border-[#eee] dark:bg-[#0a0a0a]/90 shadow-[8px_8px_0px_0px_rgba(17,17,17,0.3)] dark:shadow-[8px_8px_0px_0px_rgba(238,238,238,0.3)]">
                {caseState.status === CaseStatus.COMPLETE ? (
                  <ReportViewer deliverables={caseState.deliverables} />
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-800 dark:text-gray-400 p-6 text-center">
                    <div className="w-12 h-12 border-4 border-[#111] border-t-transparent rounded-full animate-spin mb-4 dark:border-[#eee] dark:border-t-transparent" />
                    <p className="font-mono text-sm uppercase">Awaiting Swarm Consensus...</p>
                  </div>
                )}
              </div>
            </div>
          </Panel>
        )}
      </ReactFlow>

      {/* Top-right action buttons */}
      <div className="absolute top-6 right-6 flex items-center space-x-4 z-50">
        <button
          onClick={handleReset}
          className="p-3 bg-white border-4 border-[#111] shadow-[4px_4px_0px_0px_#111] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_#111] transition-all dark:bg-[#0a0a0a] dark:border-[#eee] dark:shadow-[4px_4px_0px_0px_#eee] dark:hover:shadow-[2px_2px_0px_0px_#eee] group relative"
          title="New Case"
        >
          <RotateCcw size={22} strokeWidth={2.5} className="dark:text-[#eee]" />
          <span className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs font-bold whitespace-nowrap bg-white border-2 border-[#111] px-2 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity dark:bg-[#0a0a0a] dark:border-[#eee] dark:text-[#eee]">
            NEW CASE
          </span>
        </button>

        <button 
          onClick={() => setShowSidebar(!showSidebar)}
          onMouseEnter={() => setIsHoveringSettings(true)}
          onMouseLeave={() => setIsHoveringSettings(false)}
          className="p-3 bg-white border-4 border-[#111] shadow-[4px_4px_0px_0px_#111] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_#111] transition-all dark:bg-[#0a0a0a] dark:border-[#eee] dark:shadow-[4px_4px_0px_0px_#eee] dark:hover:shadow-[2px_2px_0px_0px_#eee]"
        >
          <Settings size={28} strokeWidth={2.5} className="dark:text-[#eee]" />
        </button>
      </div>

      {/* Settings sidebar */}
      <div 
        className={`absolute top-0 right-0 w-1/3 min-w-[450px] h-full bg-white/90 backdrop-blur-3xl border-l-4 border-[#111] shadow-[-12px_0px_0px_0px_rgba(0,0,0,0.05)] transition-transform duration-500 z-40 dark:bg-[#0a0a0a]/90 dark:border-[#eee] flex flex-col ${showSidebar ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <div className="flex border-b-4 border-[#111] dark:border-[#eee] mt-24">
          <button 
            onClick={() => setSidebarTab('settings')}
            className={`flex-1 py-4 font-black uppercase flex items-center justify-center space-x-2 transition-colors ${sidebarTab === 'settings' ? 'bg-[#111] text-white dark:bg-[#eee] dark:text-[#111]' : 'hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-[#eee]'}`}
          >
            <Settings size={20} />
            <span>Settings</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-8">
          <div className="space-y-8 dark:text-[#eee]">
              <div className="brutalist-card p-6">
                <h3 className="font-black uppercase text-xl mb-4 border-b-2 border-[#111] dark:border-[#eee] pb-2 text-black dark:text-white">User Settings</h3>
                
                <div className="flex items-center justify-between mb-6">
                  <span className="font-mono font-bold text-black dark:text-white">Dark Mode</span>
                  <button 
                    onClick={() => setIsDarkMode(!isDarkMode)}
                    className="w-16 h-8 border-2 border-[#111] dark:border-[#eee] rounded-full relative bg-[#f4f4f0] dark:bg-[#111] transition-colors"
                  >
                    <div className={`absolute top-0.5 w-6 h-6 rounded-full border-2 border-[#111] dark:border-[#eee] flex items-center justify-center transition-transform ${isDarkMode ? 'translate-x-8 bg-[#eee]' : 'translate-x-0.5 bg-[#111]'}`}>
                      {isDarkMode ? <Moon size={12} className="text-[#111]" /> : <Sun size={12} className="text-[#fff]" />}
                    </div>
                  </button>
                </div>

                <div className="flex items-center justify-between mb-6">
                  <div className="flex flex-col pr-4">
                    <span className="font-mono font-bold flex items-center space-x-2 text-black dark:text-white">
                      <Brain size={16} />
                      <span>Deep Research</span>
                    </span>
                    <span className="text-xs text-gray-800 dark:text-gray-400 mt-1">
                      Uses extended analysis with OpenRouter models. Will take significantly longer.
                    </span>
                  </div>
                  <button 
                    onClick={() => setDeepResearch(!deepResearch)}
                    className="w-16 h-8 border-2 border-[#111] dark:border-[#eee] rounded-full relative bg-[#f4f4f0] dark:bg-[#111] transition-colors shrink-0"
                  >
                    <div className={`absolute top-0.5 w-6 h-6 rounded-full border-2 border-[#111] dark:border-[#eee] transition-transform ${deepResearch ? 'translate-x-8 bg-[#00ff88]' : 'translate-x-0.5 bg-gray-400'}`} />
                  </button>
                </div>

                <div className="flex items-center justify-between pt-6 border-t-2 border-[#111] dark:border-[#eee]">
                  <div className="flex flex-col pr-4">
                    <span className="font-mono font-bold flex items-center space-x-2 text-[#ff003c]">
                      <Database size={16} />
                      <span>Admin Mode</span>
                    </span>
                    <span className="text-xs text-gray-800 dark:text-gray-400 mt-1">
                      Unlock advanced configuration, memory management, and model settings.
                    </span>
                  </div>
                  <button 
                    onClick={() => setIsAdminMode(!isAdminMode)}
                    className="w-16 h-8 border-2 border-[#111] dark:border-[#eee] rounded-full relative bg-[#f4f4f0] dark:bg-[#111] transition-colors shrink-0"
                  >
                    <div className={`absolute top-0.5 w-6 h-6 rounded-full border-2 border-[#111] dark:border-[#eee] transition-transform ${isAdminMode ? 'translate-x-8 bg-[#ff003c]' : 'translate-x-0.5 bg-gray-400'}`} />
                  </button>
                </div>
              </div>

              <div className="brutalist-card p-6 border-[#ff003c] dark:border-[#ff003c]">
                <h3 className="font-black uppercase text-xl mb-4 border-b-2 border-[#111] dark:border-[#eee] pb-2 flex items-center space-x-2 text-black dark:text-white">
                  <Database size={20} />
                  <span>Admin Dashboard</span>
                </h3>
                <p className="text-xs font-mono mb-4 text-gray-800 dark:text-gray-400">
                  Access advanced configuration, memory management, token telemetry, and API keys.
                  <br /><br />
                  <span className="text-[#ff003c] font-bold">Shortcut:</span> Hover over the settings icon and press 'T'.
                </p>
                <button 
                  onClick={() => setIsAdminMode(true)}
                  className="w-full py-3 bg-[#ff003c] text-white font-black uppercase tracking-widest hover:bg-black transition-colors"
                >
                  Launch Admin Mode
                </button>
              </div>
            </div>
        </div>
      </div>

      {isAdminMode && (
        <AdminDashboard onClose={() => setIsAdminMode(false)} />
      )}

      {/* Floating Agent Chat Button */}
      <button
        onClick={() => setShowChat(!showChat)}
        className="fixed bottom-6 left-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-[#7B68EE] to-[#00D4FF] text-white shadow-lg hover:shadow-xl hover:scale-110 transition-all flex items-center justify-center"
        style={{ boxShadow: '0 4px 20px rgba(123, 104, 238, 0.4)' }}
        title="Chat with Agents"
      >
        <MessageCircle size={24} />
      </button>

      <AgentChat isOpen={showChat} onClose={() => setShowChat(false)} />
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <FlowApp />
    </ReactFlowProvider>
  );
}
