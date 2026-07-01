import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Terminal, Activity, Palette, Save, X, Wifi, WifiOff, Play, Trash2,
  GripVertical, Minimize2, Maximize2,
} from 'lucide-react';
import { executeTerminal } from '../../services/api';

const BUILD_WS_URL = 'ws://localhost:8000/api/ws/build';

interface BuildEvent {
  id: string;
  timestamp: string;
  type: string;
  module: string;
  message: string;
  detail?: string;
  status: 'ok' | 'warn' | 'error';
}

interface ColorScheme {
  name: string;
  hue: number;
  saturation: number;
  lightness: number;
}

const DEFAULT_SCHEMES: ColorScheme[] = [
  { name: 'Neon Cyan', hue: 190, saturation: 100, lightness: 42 },
  { name: 'Matrix Green', hue: 120, saturation: 100, lightness: 40 },
  { name: 'Synthwave', hue: 280, saturation: 80, lightness: 50 },
  { name: 'Sunset', hue: 10, saturation: 90, lightness: 55 },
  { name: 'Ocean', hue: 210, saturation: 70, lightness: 45 },
];

interface BuildModeProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BuildMode: React.FC<BuildModeProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'terminal' | 'telemetry' | 'colors'>('terminal');
  const [buildEvents, setBuildEvents] = useState<BuildEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const [isMinimized, setIsMinimized] = useState(false);

  // Drag state
  const [position, setPosition] = useState({ x: 80, y: 80 });
  const [size, setSize] = useState({ width: 640, height: 520 });
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  // Terminal
  const [terminalInput, setTerminalInput] = useState('');
  const [terminalOutput, setTerminalOutput] = useState<string[]>([
    'TANGLE Build Terminal — /Users/perbrinell/Documents/DROPHELP',
    'Type a command and press Enter.',
    '',
  ]);
  const [terminalBusy, setTerminalBusy] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Telemetry filter
  const [eventFilter, setEventFilter] = useState<string>('all');

  // Color schemes
  const [hue, setHue] = useState(190);
  const [saturation, setSaturation] = useState(100);
  const [lightness, setLightness] = useState(42);
  const [savedSchemes, setSavedSchemes] = useState<ColorScheme[]>(() => {
    try { return JSON.parse(localStorage.getItem('tangle-color-schemes') || '[]'); }
    catch { return []; }
  });

  // Apply color scheme to CSS vars
  useEffect(() => {
    document.documentElement.style.setProperty('--build-hue', hue.toString());
    document.documentElement.style.setProperty('--build-sat', `${saturation}%`);
    document.documentElement.style.setProperty('--build-lit', `${lightness}%`);
  }, [hue, saturation, lightness]);

  // Connect to build WebSocket
  useEffect(() => {
    let ws: WebSocket;
    try {
      ws = new WebSocket(BUILD_WS_URL);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onmessage = (ev) => {
        try {
          const event = JSON.parse(ev.data);
          setBuildEvents(prev => [event, ...prev].slice(0, 200));
        } catch {}
      };
      wsRef.current = ws;
    } catch {}
    return () => { ws?.close(); };
  }, []);

  if (!isOpen) return null;

  const handleMouseDown = (e: React.MouseEvent) => {
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: position.x,
      startPosY: position.y,
    };
    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setPosition({
        x: dragRef.current.startPosX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.startPosY + (ev.clientY - dragRef.current.startY),
      });
    };
    const handleMouseUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleResizeDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startW = size.width;
    const startH = size.height;
    const handleMouseMove = (ev: MouseEvent) => {
      setSize({
        width: Math.max(480, Math.min(900, startW + (ev.clientX - startX))),
        height: Math.max(360, Math.min(900, startH + (ev.clientY - startY))),
      });
    };
    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const runTerminal = useCallback(async () => {
    if (!terminalInput.trim() || terminalBusy) return;
    setTerminalBusy(true);
    const cmd = terminalInput;
    setTerminalOutput(prev => [...prev, `$ ${cmd}`]);
    setTerminalInput('');
    try {
      const res = await executeTerminal(cmd);
      if (res.output) setTerminalOutput(prev => [...prev, res.output.trim()]);
      if (res.stderr) setTerminalOutput(prev => [...prev, `STDERR: ${res.stderr.trim()}`]);
      if (res.exit_code !== 0) setTerminalOutput(prev => [...prev, `Exit code: ${res.exit_code}`]);
    } catch (err: any) {
      setTerminalOutput(prev => [...prev, `Error: ${err.message}`]);
    }
    setTerminalBusy(false);
    setTimeout(() => terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: 'smooth' }), 50);
  }, [terminalInput, terminalBusy]);

  const applyScheme = (scheme: ColorScheme) => {
    setHue(scheme.hue);
    setSaturation(scheme.saturation);
    setLightness(scheme.lightness);
  };

  const saveCurrentScheme = () => {
    const name = prompt('Name this color scheme:');
    if (!name) return;
    const scheme: ColorScheme = { name, hue, saturation, lightness };
    const updated = [...savedSchemes, scheme];
    setSavedSchemes(updated);
    localStorage.setItem('tangle-color-schemes', JSON.stringify(updated));
  };

  const deleteScheme = (index: number) => {
    const updated = savedSchemes.filter((_, i) => i !== index);
    setSavedSchemes(updated);
    localStorage.setItem('tangle-color-schemes', JSON.stringify(updated));
  };

  return (
    <div
      ref={popupRef}
      className="fixed flex flex-col z-[99999]"
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: isMinimized ? 'auto' : size.height,
        border: '3px solid #333',
        backgroundColor: '#0a0a0a',
        boxShadow: '8px 8px 0px 0px rgba(0,0,0,0.4)',
      }}
    >
      {/* Title bar — drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="flex items-center justify-between px-3 py-2 border-b border-[#333] bg-black/80 cursor-move select-none"
      >
        <div className="flex items-center gap-2">
          <GripVertical size={14} className="text-gray-600" />
          <Terminal size={16} className="text-[#00d4ff]" />
          <span className="text-sm font-black uppercase tracking-widest text-[#00d4ff]">Build Mode</span>
          <span className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full ${wsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
            {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
            {wsConnected ? 'Live' : 'Off'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-600 mr-1">{buildEvents.length} events</span>
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 hover:bg-[#333] transition-colors rounded"
          >
            {isMinimized ? <Maximize2 size={12} className="text-gray-500" /> : <Minimize2 size={12} className="text-gray-500" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[#ff003c] hover:text-white transition-colors rounded"
          >
            <X size={14} className="text-gray-500 hover:text-white" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Tab bar */}
          <div className="flex gap-0 px-4 border-b border-[#222] bg-black/50 shrink-0">
            {[
              { id: 'terminal', label: 'Terminal', icon: <Terminal size={12} /> },
              { id: 'telemetry', label: 'Telemetry', icon: <Activity size={12} /> },
              { id: 'colors', label: 'Colors', icon: <Palette size={12} /> },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-bold uppercase tracking-wider transition-colors border-t-2 ${
                  activeTab === tab.id
                    ? 'bg-[#00d4ff]/10 text-[#00d4ff] border-t-[#00d4ff]'
                    : 'text-gray-500 hover:text-gray-300 border-t-transparent'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-hidden">
            {/* ── Terminal Tab ── */}
            {activeTab === 'terminal' && (
              <div className="h-full flex flex-col p-3">
                <div
                  ref={terminalRef}
                  className="flex-1 bg-black border border-[#333] rounded p-2 overflow-y-auto text-[11px] leading-relaxed font-mono"
                >
                  {terminalOutput.map((line, i) => (
                    <div key={i} className={`${
                      line.startsWith('$ ') ? 'text-[#00ff88]' :
                      line.startsWith('STDERR') || line.startsWith('Error') ? 'text-red-400' :
                      line.startsWith('Exit code') && !line.endsWith('0') ? 'text-yellow-500' :
                      'text-gray-400'
                    }`}>
                      {line}
                    </div>
                  ))}
                  {terminalBusy && (
                    <div className="text-yellow-500 animate-pulse mt-1">Running...</div>
                  )}
                </div>
                <div className="flex mt-2 gap-2">
                  <input
                    value={terminalInput}
                    onChange={(e) => setTerminalInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') runTerminal();
                      if (e.key === 'ArrowUp') setTerminalInput(terminalOutput.filter(l => l.startsWith('$ ')).pop()?.slice(2) || '');
                    }}
                    placeholder="$ git status, npm run dev, etc..."
                    disabled={terminalBusy}
                    className="flex-1 bg-black border border-[#333] rounded px-2 py-1.5 text-[11px] font-mono text-[#00ff88] placeholder-gray-700 focus:outline-none focus:border-[#00d4ff]"
                  />
                  <button
                    onClick={runTerminal}
                    disabled={terminalBusy || !terminalInput.trim()}
                    className="px-2 py-1.5 bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30 rounded text-xs font-bold hover:bg-[#00d4ff]/25 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Play size={12} />
                  </button>
                </div>
              </div>
            )}

            {/* ── Telemetry Tab ── */}
            {activeTab === 'telemetry' && (
              <div className="h-full flex flex-col p-3">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-[11px] font-bold uppercase tracking-wider text-gray-400">Live Events</h2>
                  <div className="flex gap-1">
                    {['all', 'api_call', 'terminal', 'db_write', 'vector_op'].map(f => (
                      <button
                        key={f}
                        onClick={() => setEventFilter(f)}
                        className={`text-[9px] px-1.5 py-0.5 uppercase font-bold rounded ${
                          eventFilter === f ? 'bg-[#00d4ff] text-black' : 'bg-[#222] text-gray-500 hover:bg-[#333]'
                        }`}
                      >
                        {f.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex-1 overflow-y-auto bg-black/30 border border-[#222] rounded p-2 space-y-1">
                  {buildEvents.length === 0 && (
                    <div className="flex items-center justify-center h-full text-gray-700 text-[11px]">
                      No events yet — start a mission or run a command
                    </div>
                  )}
                  {buildEvents
                    .filter(e => eventFilter === 'all' || e.type === eventFilter)
                    .map((ev, i) => (
                    <div key={ev.id || i} className="flex items-start gap-2 py-1 border-b border-[#222]/30 text-[11px] hover:bg-[#ffffff05] group">
                      <span className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
                        ev.status === 'ok' ? 'bg-green-500' : ev.status === 'warn' ? 'bg-yellow-500' : 'bg-red-500'
                      }`} />
                      <span className="text-gray-600 shrink-0 w-12 font-mono">{ev.timestamp?.split('T')[1]?.split('.')[0]?.slice(0, 8) || ''}</span>
                      <span className="text-gray-500 shrink-0 font-bold w-14">{ev.module}</span>
                      <span className="text-gray-400 shrink-0 text-[9px] uppercase w-12">{ev.type.replace('_', ' ')}</span>
                      <span className="text-gray-300 flex-1 truncate">{ev.message}</span>
                      {ev.detail && (
                        <span className="text-gray-600 hidden group-hover:block text-[9px] max-w-[200px] truncate">{ev.detail}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Colors Tab ── */}
            {activeTab === 'colors' && (
              <div className="h-full flex flex-col p-3 overflow-y-auto">
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <label className="block text-[10px] uppercase text-gray-500 mb-1">Hue ({hue}°)</label>
                    <input type="range" min="0" max="360" value={hue} onChange={(e) => setHue(Number(e.target.value))}
                      className="w-full accent-[#00d4ff] h-1 bg-[#222] cursor-pointer" />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase text-gray-500 mb-1">Saturation ({saturation}%)</label>
                    <input type="range" min="0" max="100" value={saturation} onChange={(e) => setSaturation(Number(e.target.value))}
                      className="w-full accent-[#00d4ff] h-1 bg-[#222] cursor-pointer" />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase text-gray-500 mb-1">Lightness ({lightness}%)</label>
                    <input type="range" min="1" max="60" value={lightness} onChange={(e) => setLightness(Number(e.target.value))}
                      className="w-full accent-[#00d4ff] h-1 bg-[#222] cursor-pointer" />
                  </div>
                  <div className="flex items-end">
                    <div className="w-full h-8 rounded border border-[#333]"
                      style={{ background: `hsl(${hue}, ${saturation}%, ${lightness}%)` }} />
                  </div>
                </div>

                <div className="flex gap-2 mb-4">
                  {DEFAULT_SCHEMES.map((scheme) => (
                    <button
                      key={scheme.name}
                      onClick={() => applyScheme(scheme)}
                      className="flex-1 p-1.5 text-[9px] font-bold uppercase text-center border border-[#333] rounded hover:border-[#00d4ff] transition-colors"
                      style={{ background: `hsl(${scheme.hue}, ${scheme.saturation}%, ${scheme.lightness})`, color: scheme.lightness > 40 ? '#000' : '#fff' }}
                    >
                      {scheme.name}
                    </button>
                  ))}
                </div>

                <button
                  onClick={saveCurrentScheme}
                  className="mb-3 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30 rounded text-[11px] font-bold hover:bg-[#00d4ff]/25"
                >
                  <Save size={12} /> Save Current as Preset
                </button>

                {savedSchemes.length > 0 && (
                  <div className="flex-1 overflow-y-auto">
                    <h3 className="text-[10px] uppercase text-gray-500 mb-2">Saved Presets ({savedSchemes.length})</h3>
                    <div className="space-y-1">
                      {savedSchemes.map((scheme, i) => (
                        <div key={i} className="flex items-center justify-between bg-black/30 border border-[#222] rounded p-2 group">
                          <div className="flex items-center gap-2">
                            <div className="w-5 h-5 rounded border border-[#333]"
                              style={{ background: `hsl(${scheme.hue}, ${scheme.saturation}%, ${scheme.lightness}%)` }} />
                            <span className="text-[11px]">{scheme.name}</span>
                          </div>
                          <button onClick={() => deleteScheme(i)}
                            className="p-1 text-red-400 opacity-0 group-hover:opacity-100 hover:bg-red-900/30 rounded">
                            <Trash2 size={10} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Resize handle */}
          <div
            onMouseDown={handleResizeDown}
            className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
            style={{ background: 'linear-gradient(135deg, transparent 50%, #444 50%)' }}
          />
        </>
      )}
    </div>
  );
};
