import { useState, useEffect } from 'react';
import { Handle, Position } from '@xyflow/react';

const stateConfig: Record<string, { color: string; label: string }> = {
  idle: { color: '#666', label: 'Idle' },
  thinking: { color: '#f59e0b', label: 'Thinking' },
  querying: { color: '#00d4ff', label: 'Querying' },
  reasoning: { color: '#a855f7', label: 'Reasoning' },
  debating: { color: '#ef4444', label: 'Debating' },
  executing: { color: '#00d4ff', label: 'Executing' },
  done: { color: '#00ff88', label: 'Done' },
  error: { color: '#ff003c', label: 'Error' },
};

function TypewriterThought({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) { setDisplayed(''); setDone(true); return; }
    setDisplayed('');
    setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(interval);
        setDone(true);
      }
    }, 15);
    return () => clearInterval(interval);
  }, [text]);

  if (!text) return null;
  return (
    <div className="mt-2 text-xs font-mono border-t border-[#333] pt-2 text-gray-400 leading-relaxed min-h-[2em]">
      {displayed}
      {!done && <span className="animate-pulse text-[#00d4ff]">▌</span>}
    </div>
  );
}

export function AgentNode({ data }: any) {
  const isActive = data.isActive;
  const cfg = stateConfig[data.state] || stateConfig.idle;

  return (
    <div className={`relative group min-w-[200px] max-w-[260px] transition-all duration-300 ${
      isActive ? 'scale-105' : 'hover:scale-[1.02]'
    }`}>
      {/* Animated border glow when active */}
      {isActive && (
        <div
          className="absolute -inset-[3px] rounded-sm opacity-60 animate-pulse"
          style={{
            background: `linear-gradient(135deg, ${cfg.color}00 0%, ${cfg.color}44 50%, ${cfg.color}00 100%)`,
            filter: 'blur(4px)',
          }}
        />
      )}

      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !border-[#333] !bg-[#0a0a0a]" />

      <div
        className={`relative border-2 p-3 backdrop-blur-sm transition-all ${
          isActive ? 'border-opacity-100' : 'border-opacity-60'
        }`}
        style={{
          borderColor: isActive ? cfg.color : '#333',
          background: isActive ? `${cfg.color}08` : '#0a0a0a',
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">{data.role}</span>
          <div className="flex items-center gap-1 px-1.5 py-0.5 border" style={{ borderColor: cfg.color }}>
            <span
              className={`w-1.5 h-1.5 rounded-full ${data.state !== 'idle' ? 'animate-pulse' : ''}`}
              style={{ backgroundColor: cfg.color }}
            />
            <span className="text-[9px] font-bold uppercase" style={{ color: cfg.color }}>{cfg.label}</span>
          </div>
        </div>

        <h3 className="text-sm font-black uppercase text-gray-200 mb-1">{data.name}</h3>

        {data.confidence > 0 && (
          <div className="w-full h-1.5 bg-[#222] mt-2 overflow-hidden">
            <div
              className="h-full transition-all duration-700 ease-out"
              style={{
                width: `${Math.round(data.confidence * 100)}%`,
                background: `linear-gradient(90deg, ${cfg.color}88, ${cfg.color})`,
              }}
            />
          </div>
        )}

        {data.subtask && (
          <div className="mt-2 text-[10px] text-gray-600 truncate">{data.subtask}</div>
        )}

        <TypewriterThought text={data.lastThought || ''} />

        {data.state === 'executing' && (
          <div className="mt-2 flex gap-1">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="w-2 h-2 rounded-full bg-[#00d4ff] animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !border-[#333] !bg-[#0a0a0a]" />
    </div>
  );
}
