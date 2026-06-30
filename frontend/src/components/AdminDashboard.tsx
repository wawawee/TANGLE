import React, { useState, useEffect } from 'react';
import { Database, Activity, Brain, Sliders, X, Save, ChevronDown, ChevronRight, Zap, Terminal, MessageCircle, Server, FolderOpen, History, BookOpen } from 'lucide-react';
import { getAdminIndex, getSystemHealth, getEntities, getMissions, getKnowledgeDocs, getRunHistory, getSystemMetrics, getProviderHealth, getUsageStats } from '../services/api';
import { AgentChat } from './admin/AgentChat';

const AGENT_VERBOSE_INFO: Record<string, any> = {
  coordinator: {
    id: 'coordinator',
    name: 'Coordinator Alpha',
    description: 'Orchestrates the entire swarm debate cycle',
    model: 'openrouter/qwen/qwen3-coder:free',
    capabilities: ['Task delegation', 'Consensus detection', 'Debate management', 'Quality gate'],
    useCase: 'First agent invoked — manages the flow between all other agents',
    verbosePrompt: 'You are the CONDUCTOR of a multi-agent swarm debate. Your role is to:\n1. Receive the initial query\n2. Delegate to Context Weaver for entity extraction\n3. Route to Echo Vault for memory/research\n4. Aggregate findings for Outcome Architect\n5. Have Chronicle Scribe draft deliverables\n6. Detect consensus or trigger additional debate rounds'
  },
  context_weaver: {
    id: 'context_weaver',
    name: 'Context Weaver',
    description: 'Extracts entities, relationships, and core problem from evidence',
    model: 'openrouter/openai/gpt-oss-120b:free',
    capabilities: ['Entity extraction', 'Relationship mapping', 'Timeline construction', 'Risk flagging'],
    useCase: 'Analyzes uploaded files, text, images to extract structured data',
    verbosePrompt: 'You are a CONTEXT WEAVER — an elite analyst specializing in extracting structured information from chaos.\n\nYour responsibilities:\n1. Parse all evidence types (text, PDF, images, audio transcripts)\n2. Extract: People, Organizations, Locations, Dates, Evidence items\n3. Map relationships between entities\n4. Identify the core problem statement\n5. Flag risks and contradictions'
  },
  echo_vault: {
    id: 'echo_vault',
    name: 'Echo Vault',
    description: 'Long-term memory and web research agent',
    model: 'openrouter/meta-llama/llama-3.3-70b-instruct:free',
    capabilities: ['Vector search', 'Web search', 'Past case retrieval', 'Knowledge synthesis'],
    useCase: 'Searches vector database and web for relevant information',
    verbosePrompt: 'You are ECHO VAULT — the memory and research specialist.\n\nYour capabilities:\n1. Query vector store for similar past cases\n2. Perform web searches\n3. Synthesize findings into research summary'
  },
  outcome_architect: {
    id: 'outcome_architect',
    name: 'Outcome Architect',
    description: 'Devises strategic recommendations based on evidence and research',
    model: 'openrouter/nousresearch/hermes-3-llama-3.1-405b:free',
    capabilities: ['Strategy formulation', 'Option analysis', 'Risk assessment', 'Action planning'],
    useCase: 'Takes extracted context + research and creates actionable strategy',
    verbosePrompt: 'You are an OUTCOME ARCHITECT — a strategic advisor who transforms evidence into action.\n\nYour methodology:\n1. Review Context Weaver\'s extracted problem\n2. Analyze Echo Vault\'s research findings\n3. Identify 3-5 strategic options\n4. For each option: assess pros/cons, risks, timeline\n5. Recommend best course of action'
  },
  chronicle_scribe: {
    id: 'chronicle_scribe',
    name: 'Chronicle Scribe',
    description: 'Drafts final deliverables — reports, emails, contacts',
    model: 'openrouter/qwen/qwen3-coder:free',
    capabilities: ['Report drafting', 'Email generation', 'Contact extraction', 'Timeline creation'],
    useCase: 'Creates the final output package from strategy',
    verbosePrompt: 'You are a CHRONICLE SCRIBE — the documentation specialist.\n\nYour outputs:\n1. Strategic Report (markdown)\n2. Draft Emails (to, from, subject, body)\n3. Contact List (name, role, org, priority, contact methods)\n4. Timeline/Checklist'
  },
  pulse_monitor: {
    id: 'pulse_monitor',
    name: 'Pulse Monitor',
    description: 'Real-time telemetry and quality assurance',
    model: 'openrouter/meta-llama/llama-3.2-3b-instruct:free',
    capabilities: ['Token counting', 'Latency monitoring', 'Quality scoring', 'Error detection'],
    useCase: 'Tracks swarm health and reports metrics',
    verbosePrompt: 'You are the PULSE MONITOR — system telemetry agent.\n\nTrack and report:\n1. Token usage per agent\n2. API latency\n3. Confidence scores across debate\n4. Quality metrics\n5. Error rates'
  }
};

interface AdminDashboardProps {
  onClose: () => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ onClose }) => {
  const [hue, setHue] = useState(0);
  const [saturation, setSaturation] = useState(0);
  const [lightness, setLightness] = useState(7);

  const [adminIndex, setAdminIndex] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [entities, setEntities] = useState<any[]>([]);
  const [missions, setMissions] = useState<any[]>([]);
  const [knowledge, setKnowledge] = useState<any[]>([]);
  const [runHistory, setRunHistory] = useState<any[]>([]);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [providerHealth, setProviderHealth] = useState<any>(null);
  const [usageStats, setUsageStats] = useState<any>(null);

  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showVerbose, setShowVerbose] = useState<Record<string, boolean>>({});
  const [showChat, setShowChat] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'agents' | 'data' | 'system'>('overview');

  useEffect(() => {
    document.documentElement.style.setProperty('--ui-hue', hue.toString());
    document.documentElement.style.setProperty('--ui-sat', `${saturation}%`);
    document.documentElement.style.setProperty('--ui-lit-dark', `${lightness}%`);
    document.documentElement.style.setProperty('--ui-lit-light', `${100 - lightness}%`);
  }, [hue, saturation, lightness]);

  useEffect(() => {
    Promise.all([
      getAdminIndex().then(setAdminIndex).catch(() => {}),
      getSystemHealth().then(setHealth).catch(() => {}),
      getEntities().then(d => setEntities(d.entities || [])).catch(() => {}),
      getMissions().then(d => setMissions(d.missions || [])).catch(() => {}),
      getKnowledgeDocs().then(d => setKnowledge(d.docs || [])).catch(() => {}),
      getRunHistory().then(d => setRunHistory(d.runs || [])).catch(() => {}),
      getSystemMetrics().then(setSystemMetrics).catch(() => {}),
      getProviderHealth().then(setProviderHealth).catch(() => {}),
      getUsageStats().then(setUsageStats).catch(() => {}),
    ]);
  }, []);

  const saveToCSS = () => {
    alert(`UI Colors saved!\nHue: ${hue}°\nSaturation: ${saturation}%\nLightness: ${lightness}%`);
  };

  const verboseInfo = selectedAgent ? AGENT_VERBOSE_INFO[selectedAgent] : null;

  return (
    <div className="absolute inset-0 z-[100] bg-[#111] text-[#eee] overflow-y-auto font-mono p-8">
      <div className="max-w-8xl mx-auto">
        <div className="flex justify-between items-center mb-8 border-b-4 border-[#ff003c] pb-4">
          <h1 className="text-4xl font-black uppercase tracking-widest text-[#ff003c] flex items-center gap-4">
            <Terminal size={40} />
            System Override // Admin
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => setShowChat(true)}
              className="p-2 bg-[#00ff88] text-black hover:bg-white transition-colors"
              title="Chat with The Architect"
            >
              <MessageCircle size={32} />
            </button>
            <button onClick={onClose} className="p-2 bg-[#ff003c] text-black hover:bg-white transition-colors">
              <X size={32} />
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-8 border-b-2 border-[#333] pb-2">
          {(['overview', 'agents', 'data', 'system'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors ${
                activeTab === tab ? 'bg-white text-black' : 'text-gray-500 hover:text-white hover:bg-[#222]'
              }`}
            >
              {tab === 'overview' && <><Zap size={12} className="inline mr-1" />Overview</>}
              {tab === 'agents' && <><Brain size={12} className="inline mr-1" />Agents</>}
              {tab === 'data' && <><Database size={12} className="inline mr-1" />Data</>}
              {tab === 'system' && <><Server size={12} className="inline mr-1" />System</>}
            </button>
          ))}
        </div>

        {/* ── Overview Tab ── */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* Health */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Server size={16} /> System Health
              </h2>
              {health ? (
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Status</span>
                    <span className="text-[#00ff88] font-bold uppercase">{health.status}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Service</span>
                    <span>{health.service}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Version</span>
                    <span>{health.version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Agents</span>
                    <span className="font-bold">{health.agents}</span>
                  </div>
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>

            {/* Provider Health */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Zap size={16} /> Providers
              </h2>
              {providerHealth ? (
                <div className="space-y-2 text-xs">
                  {Object.entries(providerHealth).map(([provider, status]: [string, any]) => (
                    <div key={provider} className="flex justify-between border-b border-[#222] pb-1">
                      <span className="text-gray-500 capitalize">{provider.replace('_', ' ')}</span>
                      <span className={status ? 'text-[#00ff88]' : 'text-red-500'}>
                        {status ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>

            {/* Token Usage */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Activity size={16} /> Token Usage
              </h2>
              {usageStats ? (
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Total Tokens</span>
                    <span className="font-bold">{usageStats.total_tokens?.toLocaleString() || 0}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Total Cost</span>
                    <span className="font-bold">${usageStats.total_cost?.toFixed(4) || '0.00'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Missions</span>
                    <span className="font-bold">{usageStats.mission_count || 0}</span>
                  </div>
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>

            {/* Vector Store */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Database size={16} /> Vector Store
              </h2>
              {adminIndex ? (
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">SQLite</span>
                    <span className={adminIndex.sqlite?.exists ? 'text-[#00ff88]' : 'text-red-500'}>
                      {adminIndex.sqlite?.exists ? `${adminIndex.sqlite.wiki_entries_count || 0} entries` : 'Not found'}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Qdrant</span>
                    <span className={adminIndex.qdrant?.reachable ? 'text-[#00ff88]' : 'text-gray-500'}>
                      {adminIndex.qdrant?.reachable ? `${adminIndex.qdrant.points_count || 0} points` : 'Offline'}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[#222] pb-1">
                    <span className="text-gray-500">Missions</span>
                    <span>{adminIndex.sqlite?.missions_count || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Vault Files</span>
                    <span>{adminIndex.filesystem?.files || 0}</span>
                  </div>
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>

            {/* Entities */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <FolderOpen size={16} /> Entities ({entities.length})
              </h2>
              {entities.length > 0 ? (
                <div className="space-y-1 text-xs max-h-[200px] overflow-y-auto">
                  {entities.map((e: any, i: number) => (
                    <div key={i} className="flex justify-between border-b border-[#222] pb-1">
                      <span>{e.name || e.entity_name || e.id}</span>
                      <span className="text-gray-500">{e.mission_count || 0} missions</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs">No entities yet</div>
              )}
            </div>

            {/* Knowledge Docs */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <BookOpen size={16} /> Knowledge ({knowledge.length})
              </h2>
              {knowledge.length > 0 ? (
                <div className="space-y-1 text-xs max-h-[200px] overflow-y-auto">
                  {knowledge.map((doc: any, i: number) => (
                    <div key={i} className="border-b border-[#222] pb-1">
                      <div className="font-bold">{doc.title}</div>
                      <div className="text-gray-500 truncate">{doc.content?.slice(0, 80)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs">No knowledge docs yet</div>
              )}
            </div>
          </div>
        )}

        {/* ── Agents Tab ── */}
        {activeTab === 'agents' && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* Agent Configuration */}
            <div className="border-2 border-[#333] p-6 bg-black/50 xl:col-span-2">
              <h2 className="text-xl font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Brain size={20} /> Agent Configuration
              </h2>

              <div className="flex flex-wrap gap-2 mb-4">
                {Object.keys(AGENT_VERBOSE_INFO).map(agentId => (
                  <button
                    key={agentId}
                    onClick={() => setSelectedAgent(agentId)}
                    className={`px-3 py-2 text-xs font-bold uppercase border transition-colors ${
                      selectedAgent === agentId
                        ? 'bg-[#00ff88] text-black border-[#00ff88]'
                        : 'bg-black border-[#333] hover:border-[#00ff88]'
                    }`}
                  >
                    {AGENT_VERBOSE_INFO[agentId].name}
                  </button>
                ))}
              </div>

              {selectedAgent && verboseInfo && (
                <div className="space-y-4">
                  <div className="bg-[#0a0a0a] border border-[#333] p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Zap size={16} className="text-[#00ff88]" />
                      <span className="font-bold text-sm uppercase">{verboseInfo.name}</span>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">{verboseInfo.description}</p>

                    <div className="grid grid-cols-2 gap-4 mb-3">
                      <div>
                        <span className="text-xs text-gray-500 uppercase">Model</span>
                        <p className="text-xs">{verboseInfo.model}</p>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500 uppercase">Use Case</span>
                        <p className="text-xs">{verboseInfo.useCase}</p>
                      </div>
                    </div>

                    <div>
                      <span className="text-xs text-gray-500 uppercase">Capabilities</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {verboseInfo.capabilities.map((c: string) => (
                          <span key={c} className="text-[10px] bg-[#222] px-2 py-0.5 border border-[#444]">{c}</span>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={() => setShowVerbose(prev => ({ ...prev, [selectedAgent]: !prev[selectedAgent] }))}
                      className="mt-3 text-xs text-[#00ff88] flex items-center gap-1"
                    >
                      {showVerbose[selectedAgent] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      {showVerbose[selectedAgent] ? 'Hide' : 'Show'} Full Prompt
                    </button>

                    {showVerbose[selectedAgent] && (
                      <pre className="mt-3 p-3 bg-black border border-[#333] text-[10px] overflow-x-auto whitespace-pre-wrap text-gray-300">
                        {verboseInfo.verbosePrompt}
                      </pre>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* UI Colors */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-xl font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Sliders size={20} /> UI Colors
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs uppercase mb-1 flex justify-between">
                    <span>Hue ({hue}°)</span>
                    <span className="text-gray-500">Color shift</span>
                  </label>
                  <input type="range" min="0" max="360" value={hue} onChange={(e) => setHue(Number(e.target.value))} className="w-full accent-[#00ff88] h-2 bg-gray-700 cursor-pointer" />
                </div>
                <div>
                  <label className="block text-xs uppercase mb-1 flex justify-between">
                    <span>Saturation ({saturation}%)</span>
                    <span className="text-gray-500">Vibrancy</span>
                  </label>
                  <input type="range" min="0" max="100" value={saturation} onChange={(e) => setSaturation(Number(e.target.value))} className="w-full accent-[#00ff88] h-2 bg-gray-700 cursor-pointer" />
                </div>
                <div>
                  <label className="block text-xs uppercase mb-1 flex justify-between">
                    <span>Brightness ({lightness}%)</span>
                    <span className="text-gray-500">Dark level</span>
                  </label>
                  <input type="range" min="1" max="30" value={lightness} onChange={(e) => setLightness(Number(e.target.value))} className="w-full accent-[#00ff88] h-2 bg-gray-700 cursor-pointer" />
                </div>
                <button onClick={saveToCSS} className="w-full py-3 bg-[#00ff88] text-black font-bold uppercase hover:bg-white transition-colors flex items-center justify-center gap-2">
                  <Save size={16} /> Save Colors
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Data Tab ── */}
        {activeTab === 'data' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Missions */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Activity size={16} /> Recent Missions ({missions.length})
              </h2>
              {missions.length > 0 ? (
                <div className="space-y-2 text-xs max-h-[400px] overflow-y-auto">
                  {missions.map((m: any, i: number) => (
                    <div key={i} className="border border-[#333] p-3 bg-[#0a0a0a]">
                      <div className="flex justify-between mb-1">
                        <span className="font-bold truncate">{m.objective || m.title || `Mission ${m.id || i}`}</span>
                        <span className={`text-[10px] uppercase ${m.status === 'completed' ? 'text-[#00ff88]' : m.status === 'failed' ? 'text-red-500' : 'text-yellow-500'}`}>
                          {m.status || 'unknown'}
                        </span>
                      </div>
                      <div className="text-gray-500">
                        Entity: {m.entity || 'default'} | {m.timestamp ? new Date(m.timestamp).toLocaleString() : ''}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs">No missions run yet — start from the main flow</div>
              )}
            </div>

            {/* Knowledge */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <BookOpen size={16} /> Knowledge Docs ({knowledge.length})
              </h2>
              {knowledge.length > 0 ? (
                <div className="space-y-2 text-xs max-h-[400px] overflow-y-auto">
                  {knowledge.map((doc: any, i: number) => (
                    <div key={i} className="border border-[#333] p-3 bg-[#0a0a0a]">
                      <div className="font-bold mb-1">{doc.title}</div>
                      <div className="text-gray-400 text-[10px] leading-relaxed">{doc.content?.slice(0, 300)}</div>
                      <div className="text-gray-600 mt-1">Source: {doc.source || 'system'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs">No knowledge docs — add evidence in the main flow</div>
              )}
            </div>

            {/* Run History */}
            <div className="border-2 border-[#333] p-6 bg-black/50 xl:col-span-2">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <History size={16} /> Run History ({runHistory.length})
              </h2>
              {runHistory.length > 0 ? (
                <div className="space-y-1 text-xs max-h-[300px] overflow-y-auto">
                  {runHistory.map((run: any, i: number) => (
                    <div key={i} className="flex justify-between border-b border-[#222] pb-1">
                      <span className="font-mono">{run.run_id || run.id}</span>
                      <span className={`${run.status === 'completed' ? 'text-[#00ff88]' : run.status === 'failed' ? 'text-red-500' : 'text-yellow-500'}`}>
                        {run.status || 'unknown'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs">No run history yet</div>
              )}
            </div>
          </div>
        )}

        {/* ── System Tab ── */}
        {activeTab === 'system' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* System Metrics */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Server size={16} /> System Metrics
              </h2>
              {systemMetrics ? (
                <div className="space-y-2 text-xs">
                  {Object.entries(systemMetrics).slice(0, 15).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex justify-between border-b border-[#222] pb-1">
                      <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}</span>
                      <span>{typeof val === 'number' ? val.toLocaleString() : String(val)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>

            {/* Admin Index */}
            <div className="border-2 border-[#333] p-6 bg-black/50">
              <h2 className="text-lg font-bold uppercase mb-4 flex items-center gap-2 text-[#00ff88]">
                <Database size={16} /> Store Overview
              </h2>
              {adminIndex ? (
                <div className="space-y-3 text-xs">
                  <div className="border border-[#333] p-3 bg-[#0a0a0a]">
                    <div className="font-bold mb-2 uppercase text-gray-400">SQLite</div>
                    <div className="space-y-1">
                      <div className="flex justify-between"><span className="text-gray-500">Exists</span><span>{adminIndex.sqlite?.exists ? '✅' : '❌'}</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Wiki Entries</span><span>{adminIndex.sqlite?.wiki_entries_count || 0}</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Missions</span><span>{adminIndex.sqlite?.missions_count || 0}</span></div>
                    </div>
                  </div>
                  <div className="border border-[#333] p-3 bg-[#0a0a0a]">
                    <div className="font-bold mb-2 uppercase text-gray-400">Qdrant</div>
                    <div className="space-y-1">
                      <div className="flex justify-between"><span className="text-gray-500">Reachable</span><span>{adminIndex.qdrant?.reachable ? '✅' : '❌'}</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Points</span><span>{adminIndex.qdrant?.points_count || 0}</span></div>
                    </div>
                  </div>
                  <div className="border border-[#333] p-3 bg-[#0a0a0a]">
                    <div className="font-bold mb-2 uppercase text-gray-400">Filesystem Vault</div>
                    <div className="space-y-1">
                      <div className="flex justify-between"><span className="text-gray-500">Files</span><span>{adminIndex.filesystem?.files || 0}</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Entities</span><span>{adminIndex.filesystem?.entities || 0}</span></div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-gray-600 text-xs animate-pulse">Connecting...</div>
              )}
            </div>
          </div>
        )}
      </div>

      <AgentChat isOpen={showChat} onClose={() => setShowChat(false)} />
    </div>
  );
};
