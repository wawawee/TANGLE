import { Loader2, Play, Send, Terminal, Shield, Bot, Zap, Code2, Cpu, Activity } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

interface CliCommand {
  id: string;
  label: string;
  cmd: string;
  group: string;
}

const CLI_COMMANDS: CliCommand[] = [
  { id: 'status', label: 'System Status', cmd: 'tsh status', group: 'system' },
  { id: 'agents', label: 'List Agents', cmd: 'tsh agents list', group: 'system' },
  { id: 'health', label: 'Health Check', cmd: 'curl -s http://localhost:8000/api/health | jq', group: 'system' },
  { id: 'pip-install', label: 'Install Dependencies', cmd: 'pip install -r AGENTS/requirements.txt', group: 'setup' },
  { id: 'npm-install', label: 'Install Frontend', cmd: 'cd frontend && npm install', group: 'setup' },
  { id: 'vectorize', label: 'Vectorize Codebase', cmd: 'python twisted-stacks-agentic-team/vectorize_codebase.py', group: 'setup' },
  { id: 'heartbeat', label: 'Start Heartbeat Monitor', cmd: 'python twisted-stacks-agentic-team/system/heartbeat-monitor.py', group: 'monitor' },
  { id: 'start-backend', label: 'Start Backend', cmd: 'cd backend && uvicorn main:app --reload --port 8000', group: 'dev' },
  { id: 'start-frontend', label: 'Start Frontend', cmd: 'cd frontend && npm run dev', group: 'dev' },
  { id: 'api-hunt', label: 'Run API Hunter', cmd: 'python AGENTS/API-Hunter/api_hunter_agent.py', group: 'tools' },
  { id: 'build', label: 'Build Frontend', cmd: 'cd frontend && npm run build', group: 'dev' },
  { id: 'lint', label: 'Run Linter', cmd: 'cd frontend && npm run lint', group: 'dev' },
  { id: 'git-status', label: 'Git Status', cmd: 'git status', group: 'git' },
  { id: 'git-log', label: 'Git Log', cmd: 'git log --oneline -10', group: 'git' },
  { id: 'docker-ps', label: 'Docker PS', cmd: 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"', group: 'docker' },
  { id: 'docker-logs', label: 'Docker Logs', cmd: 'docker compose logs --tail=50', group: 'docker' },
];

const GROUP_META = {
  system: { label: 'System', icon: Activity, color: '#06b6d4' },
  setup: { label: 'Setup', icon: Zap, color: '#f59e0b' },
  dev: { label: 'Development', icon: Code2, color: '#8b5cf6' },
  monitor: { label: 'Monitor', icon: Cpu, color: '#10b981' },
  tools: { label: 'Tools', icon: Bot, color: '#ec4899' },
  git: { label: 'Git', icon: Terminal, color: '#f97316' },
  docker: { label: 'Docker', icon: Shield, color: '#ef4444' },
} as const;

const MOCK_OUTPUTS: Record<string, string[]> = {
  status: ['SYSTEM STATUS', '─────────────', 'Agents: 15/15 online', 'Heartbeat: OK', 'Vector DB: connected', 'Memory: 84% utilized'],
  agents: ['AGENTS', '───────', '01 Scout         ● online', '02 Blueprint     ● online', '03 Forge         ● online', '04 Hammer        ● online', '05 Aegis         ● online', '06 Pipeline      ● idle', '07 Launcher      ● idle', '08 Canvas        ● online', '09 Scribe        ● online', '10 Tracer        ● online', '11 Turbo         ● idle', '12 Bridge        ● online', '14 Packager      ● idle', '15 Inspector     ● online', '16 Watchdog      ● online'],
  health: ['{', '  "status": "healthy",', '  "agents": 15,', '  "uptime": "12h 34m",', '  "version": "1.0.0"', '}'],
  heartbeat: ['Starting Heartbeat Monitor...', 'Monitoring 15 agents @ 30s interval', 'All agents responding.'],
  'api-hunt': ['Initializing API Hunter...', 'Checking browser-use installation...', 'Available: 7 providers', 'Ready.'],
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
    width: '100%',
    overflow: 'hidden',
    background: '#0a0a0f',
    fontFamily: "'JetBrains Mono', monospace",
  },
  topBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 16px',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    background: 'rgba(10,10,20,0.8)',
    overflowX: 'auto' as const,
    flexShrink: 0,
  },
  groupBtn: (active: boolean, color: string) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    borderRadius: '8px',
    border: `1px solid ${active ? color + '60' : 'rgba(255,255,255,0.08)'}`,
    background: active ? `${color}15` : 'rgba(255,255,255,0.03)',
    color: active ? color : 'rgba(255,255,255,0.35)',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.1em',
    cursor: 'pointer',
    transition: 'all 0.15s',
    whiteSpace: 'nowrap' as const,
    outline: 'none',
  }),
  mainArea: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  sidebar: {
    width: '200px',
    borderRight: '1px solid rgba(255,255,255,0.06)',
    background: 'rgba(10,10,20,0.4)',
    overflowY: 'auto' as const,
    padding: '12px',
    flexShrink: 0,
  },
  sidebarLabel: {
    fontSize: '9px',
    fontFamily: "'JetBrains Mono', monospace",
    color: 'rgba(255,255,255,0.25)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.15em',
    marginBottom: '12px',
    padding: '0 4px',
  },
  cmdBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    width: '100%',
    padding: '8px 12px',
    marginBottom: '6px',
    borderRadius: '8px',
    border: '1px solid rgba(255,255,255,0.06)',
    background: 'rgba(255,255,255,0.02)',
    color: 'rgba(255,255,255,0.4)',
    fontSize: '11px',
    fontFamily: "'JetBrains Mono', monospace",
    textAlign: 'left' as const,
    cursor: 'pointer',
    transition: 'all 0.15s',
    outline: 'none',
  },
  terminalOuter: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    background: 'rgba(0,0,0,0.4)',
  },
  outputArea: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '16px',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '13px',
    lineHeight: '1.7',
  },
  inputBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '12px 16px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    background: 'rgba(10,10,20,0.8)',
    flexShrink: 0,
  },
  prompt: {
    color: 'rgba(255,255,255,0.35)',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '14px',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    fontSize: '14px',
    fontFamily: "'JetBrains Mono', monospace",
    color: 'rgba(255,255,255,0.8)',
    outline: 'none',
  },
  sendBtn: (disabled: boolean) => ({
    padding: '8px',
    borderRadius: '8px',
    border: 'none',
    background: disabled ? 'transparent' : 'rgba(255,255,255,0.05)',
    color: disabled ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.4)',
    cursor: disabled ? 'default' : 'pointer',
    transition: 'all 0.15s',
  }),
  emptyState: {
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column' as const,
    gap: '12px',
    opacity: 0.3,
  },
  spinner: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    color: 'rgba(255,255,255,0.35)',
    marginTop: '8px',
    fontSize: '12px',
  },
};

export default function CliHarness() {
  const [logs, setLogs] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeGroup, setActiveGroup] = useState('system');
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const executeCommand = useCallback(async (cmd: string) => {
    if (!cmd.trim() || isProcessing) return;
    setIsProcessing(true);
    setLogs(prev => [...prev, `$ ${cmd}`]);

    try {
      const res = await fetch('http://localhost:8000/api/terminal/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      });
      if (res.ok) {
        const data = await res.json();
        const output = data.output || data.stdout || '';
        if (output) setLogs(prev => [...prev, ...output.split('\n').filter(Boolean).slice(0, 50)]);
        if (data.stderr) setLogs(prev => [...prev, `[STDERR] ${data.stderr.slice(0, 500)}`]);
        setIsProcessing(false);
        return;
      }
    } catch {
      // fall through to mock
    }

    await new Promise(r => setTimeout(r, 400 + Math.random() * 600));
    const cmdKey = Object.keys(MOCK_OUTPUTS).find(k => cmd.includes(k));
    const output = cmdKey
      ? MOCK_OUTPUTS[cmdKey]
      : [`> executed: ${cmd}`, '', '[mock mode] connect backend for real execution'];
    setLogs(prev => [...prev, ...output]);
    setIsProcessing(false);
  }, [isProcessing]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (input) {
      executeCommand(input);
      setInput('');
    }
  }, [input, executeCommand]);

  const groups = Object.entries(GROUP_META);
  const filteredCommands = CLI_COMMANDS.filter(c => c.group === activeGroup);

  return (
    <div style={styles.container}>
      {/* Group toggles */}
      <div style={styles.topBar}>
        {groups.map(([id, meta]) => (
          <button
            key={id}
            onClick={() => setActiveGroup(id)}
            style={styles.groupBtn(activeGroup === id, meta.color)}
            onMouseEnter={e => {
              if (activeGroup !== id) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.color = 'rgba(255,255,255,0.6)';
              }
            }}
            onMouseLeave={e => {
              if (activeGroup !== id) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                e.currentTarget.style.color = 'rgba(255,255,255,0.35)';
              }
            }}
          >
            <meta.icon size={12} />
            {meta.label}
          </button>
        ))}
      </div>

      <div style={styles.mainArea}>
        {/* Command buttons sidebar */}
        <div style={styles.sidebar}>
          <div style={styles.sidebarLabel}>
            {GROUP_META[activeGroup as keyof typeof GROUP_META]?.label} Commands
          </div>
          {filteredCommands.map(cmd => (
            <button
              key={cmd.id}
              onClick={() => executeCommand(cmd.cmd)}
              disabled={isProcessing}
              style={{
                ...styles.cmdBtn,
                opacity: isProcessing ? 0.4 : 1,
                cursor: isProcessing ? 'default' : 'pointer',
              }}
              onMouseEnter={e => {
                if (!isProcessing) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
                  e.currentTarget.style.color = 'rgba(255,255,255,0.7)';
                }
              }}
              onMouseLeave={e => {
                if (!isProcessing) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                  e.currentTarget.style.color = 'rgba(255,255,255,0.4)';
                }
              }}
            >
              <Play size={10} style={{ color: 'rgba(255,255,255,0.25)', flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {cmd.label}
              </span>
            </button>
          ))}
        </div>

        {/* Terminal output */}
        <div style={styles.terminalOuter}>
          <div ref={scrollRef} style={styles.outputArea}>
            {logs.length === 0 && (
              <div style={styles.emptyState}>
                <Terminal size={32} color="rgba(255,255,255,0.3)" />
                <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: '12px' }}>
                  Click a command button or type below
                </p>
              </div>
            )}
            {logs.map((line, i) => (
              <div
                key={i}
                style={{
                  padding: '1px 0',
                  color: line.startsWith('$')
                    ? '#34d399'
                    : line.startsWith('[ERROR]')
                      ? '#ef4444'
                      : line.startsWith('[STDERR]')
                        ? '#f59e0b'
                        : 'rgba(255,255,255,0.5)',
                  fontWeight: line.startsWith('$') ? 700 : 400,
                }}
              >
                {line}
              </div>
            ))}
            {isProcessing && (
              <div style={styles.spinner}>
                <Loader2 size={12} className="spin" />
                executing...
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} style={styles.inputBar}>
            <span style={styles.prompt}>$</span>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={isProcessing}
              placeholder="Type a command..."
              style={{
                ...styles.input,
                opacity: isProcessing ? 0.5 : 1,
              }}
            />
            <button
              type="submit"
              disabled={isProcessing || !input.trim()}
              style={styles.sendBtn(isProcessing || !input.trim())}
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}


